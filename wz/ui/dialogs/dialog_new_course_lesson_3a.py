"""
ui/dialogs/dialog_new_course_lesson.py

Last updated:  2023-07-07

Supporting "dialog" for the course editor – handle course elements.
That is, add new elements or inspect existing ones.
The basic types are simple lesson item, block lesson item and
no-lesson item (payment-only).
A new element can be completely new, that is a new lesson-group, or
attach to an existing lesson-group, i.e. share the lesson times. If in
addition to sharing a lesson-group the new item has the "unit" box
ticked, it will also share the room and pay-data. This latter case is
intended for team-teaching and/or lessons where more than one pupil-group
is present.
If a new lsson-group is added, there will also be a new entry in LESSONS.


=+LICENCE=============================
Copyright 2023 Michael Towers

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

=-LICENCE========================================
"""

BSID_HIGHLIGHT_COLOUR = "#FFb0ff80"

########################################################

if __name__ == "__main__":
    import sys, os

    this = sys.path[0]
    appdir = os.path.dirname(os.path.dirname(this))
    sys.path[0] = appdir
    basedir = os.path.dirname(appdir)
    from core.base import start
    start.setup(os.path.join(basedir, 'TESTDATA'))

#T = TRANSLATIONS("ui.dialogs.dialog_new_course_lesson")

### +++++

from typing import Optional
from core.basic_data import (
    BLOCK_TAG_FORMAT,
    get_subjects,
    get_teachers,
    BlockTag,
)
from core.db_access import (
    db_read_fields,
    db_values,
    db_read_unique_field,
    db_read_unique,
    db_query,
    db_select,
)
from core.course_data_3a import (
    courses_in_block,
    simple_with_subject,
    payonly_with_subject,
    read_block_sid_tags,
)
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QTableWidgetItem,
    QAbstractItemView,
    ### QtGui:
    QColor,
    QBrush,
    ### QtCore:
    Qt,
    QRegularExpressionValidator,
    Slot,
    ### other
    uic,
)

INVALID_RESULT = {"type": "INVALID"}    # invalid result

### -----

#TODO
class NewCourseLessonDialog(QDialog):
    """This dialog is evoked from the course editor.
    There are the following possibilities:

    1) A new course/lesson_group connection is to be made.
       There is the choice between a simple lesson, a block lesson
       and a payment-only item.
       The new item consists of a new COURSE_LESSONS entry. Unless the
       new item is no-lesson (payment-only), this will have a new
       lesson-group and a single new entry in LESSONS for this
       lesson-group.
       Note that further lessons may be added to existing
       lesson_groups in the course editor, using the "+" button.
       A payment-only item doesn't have a lesson-group (it is 0).

    2) A course may "join" an existing lesson-group (block). This
       means, essentially, that the lesson times (and lengths) are
       shared. In this way blocks of courses, etc., can be provided
       for – for blocks there is the possibility of setting a special
       "subject" name and tag as identification.
       This "joining" is also a fairly simple way to ensure that
       distinct lessons take place in parallel.
       In addition, the payment-data and room (lesson-data) can be
       shared, thus covering team-teaching and lessons with multiple
       pupil groups.

    This dialog itself causes no database changes, that must be done by
    the calling code on the basis of the returned value.
    If the dialog is cancelled, <None> is returned and there should be
    no changes to the database.
    Otherwise a mapping is returned: {"type": type of element, ...}
    Further entries depend on the type.
    1) A completely new entry:
        {   "type": "NEW",
            "BLOCK_SID": ("" or block-subject-id),
            "BLOCK_TAG": ("", "$" or block-tag)
        }
        If BLOCK_SID is empty, BLOCK_TAG must be "" (new simple lesson)
        or "$" (new no-lesson item).
    2) Add to existing lesson-group:
        {   "type": "PARALLEL",
            "lesson_group": (lesson_group of existing item),
            "unit": (True or False)
        }
    """
    @classmethod
    def popup(
        cls,
        course_data:dict,
        course_lessons:list[dict],
        lesson_row:int=-1,
        parent=None):
        d = cls(parent)
        return d.activate(course_data, course_lessons)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_new_course_lesson.ui"), self)
        self.table_courses.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )
        validator = QRegularExpressionValidator(BLOCK_TAG_FORMAT)
        self.BLOCK_TAG.setValidator(validator)

    @Slot(bool)
    def on_cb_block_toggled(self, on):
        self.blockstack.setCurrentIndex(1 if on else 0)

    def set_block_subject_list(self):
        """Populate the block-subject chooser.
        This is called (only) at the beginning of <activate>.
        Any block-subjects already in use by the class will appear
        highlighted at the top of the subject list.
        """
        subjects = get_subjects()
        # Get block subjects already used in the current class
        c = self.this_course["CLASS"]
        q = f"""select distinct
            BLOCK_SID
            from COURSE_LESSONS
            inner join COURSES using(Course)
            where BLOCK_SID != '' and CLASS = '{c}'
        """
        bsids = []
        bsindex = {}
        for r in db_query(q):
            sid = r[0]
            bsindex[sid] = len(bsids)
            bsids.append([sid, "???"])
        n = len(bsids)
        qc = QBrush(QColor(BSID_HIGHLIGHT_COLOUR))
        self.block_subject.clear()
        self.sid_list = []
        self.sid_index = {}
        for sid, name in get_subjects():
            if sid[0] == "-":
                continue
            try:
                i = bsindex[sid]
                bsids[i][1] = name
            except KeyError:
                bsids.append((sid, name))
        i = 0
        for sid, name in bsids:
            self.sid_index[sid] = len(self.sid_list)
            self.sid_list.append(sid)
            self.block_subject.addItem(name)
            if i < n:
                self.block_subject.setItemData(
                    i, qc, Qt.ItemDataRole.BackgroundRole
                )
            i += 1
        self.block_subject.setCurrentIndex(-1)

    def get_block_sid_tags(self):
        """Get BLOCK_SID / BLOCK_TAG / lesson_group info:
        Return: {BLOCK_SID: (BLOCK_TAG, lesson_group), ... }
        This is used by <set_sid>, so it can be called multiple times.
        The result is cached to avoid unnecessary reloading.
        """
        if self.__block_sid_tags is None:
            self.__block_sid_tags = read_block_sid_tags()
        return self.__block_sid_tags

    def activate(
        self,
        this_course: dict,
        lesson_list: list[dict],
    ) -> Optional[dict]:
        """Open the dialog.
        If lesson_row < 0, a new element is to be created.
        Otherwise, open in "inspection" mode. The details of the
        current element will be displayed. The only change possible
        is to assign a new name to a block.
        """
#TODO--
        print("\n???", this_course)
        for l in lesson_list:
            print("  --", l[0], l[1])
# <this_course> is needed (contrast dialog_block_name_3a) because the
# lesson list can be empty. If it is, Lesson_group (and Cl_id) will be -1.
# Is <lesson_list> really needed?
# The record passed as <this_course> is not necessarily for the selected
# lesson!

        self.result = None
        self.__block_sid_tags = None    # cache for block-names
        self.__lesson_group = 0         # last lesson-group
        self.this_course = this_course
        self.lesson_list = lesson_list
        self.disable_triggers = True
        self.lesson_group = -1
        self.set_table_use_selection(False)
        self.set_block_subject_list()
        self.pb_accept.setEnabled(False)
        self.rb_new.setChecked(True)
        self.rb_simple.setChecked(True) # default choice
        self.set_sid("")
        for l in lesson_list:
            if l[0] == 0:
                # If there is already a simple lesson, default to block
                self.cb_block.setChecked(True)
                break
        else:
            self.cb_block.setChecked(False)
        self.set_courses()
        self.disable_triggers = False
        self.exec()
        return self.result

    def set_table_use_selection(self, on:bool):
        self.disable_table_row_select = not on
        if on:
            self.table_courses.setSelectionMode(
                QAbstractItemView.SelectionMode.SingleSelection
            )
        else:
            self.table_courses.clearSelection()
            self.table_courses.setSelectionMode(
                QAbstractItemView.SelectionMode.NoSelection
            )

    def set_courses(self):
        """Set up the dialog according to the various parameters.
        This is called whenever a parameter is changed (except line
        change in the course table).
        """
        self.course_table_activate_line(-1)
        self.pb_accept.setEnabled(False)

        self.set_table_use_selection(
            self.cb_unit.isChecked() and self.rb_add2block.isChecked()
        )

        if self.cb_block.isChecked():
            ## Dealing with block lesson element
            i = self.block_subject.currentIndex()
            if i < 0:
                bsid = ""
                btag = ""
                self.course_table_lines = []
            else:
                bsid = self.sid_list[i]
                btag = self.BLOCK_TAG.currentText()
                self.course_table_lines = courses_in_block(bsid, btag)

            self.show_courses()
            if self.course_table_lines:
                self.course_table_activate_line(0)
                if not self.disable_table_row_select:
                    self.table_courses.setCurrentCell(0, 0)


        self.acceptable()
        return



        self.lesson_list


        # At least for a completely new entry, the courses should be
        # shown which "match" the current one and have entries of the
        # same type.
        lg = self.this_course["Lesson_group"]
        pay = self.this_course["Lesson_data"]
        if lg > 0:
            ## Get all COURSE entries for this lesson_group
            q = f"""select
                    CLASS,
                    GRP,
                    SUBJECT,
                    TEACHER,
                    Lesson_data,
                    coalesce(ROOM, '') ROOM,
                    Course,
                    coalesce(Lesson_group, 0) Lesson_group,
                    coalesce(BLOCK_TAG, '') BLOCK_TAG,
                    coalesce(BLOCK_SID, '') BLOCK_SID
                from COURSE_LESSONS
                inner join COURSES using(Course)
                inner join LESSON_DATA using(Lesson_data)
                where Lesson_group = {lg}
            """
            for r in db_select(q):
                print("  ++", r)
        elif lg == 0:
            ## Get all COURSE entries for this pay-tag
            q = f"""select
                    CLASS,
                    GRP,
                    SUBJECT,
                    TEACHER,
                    Lesson_data,
                    Course
                from COURSE_LESSONS
                inner join COURSES using(Course)
                where Lesson_data = {pay}
            """
            for r in db_select(q):
                print("  ++!", r)
        else:
            ## No courses
            pass



#        if self.rb_add2block.isChecked():
            ## Add an element to an existing lesson group.
#?
            #self.cb_block.setEnabled(False)
#            self.cb_block.setChecked(True)
        if self.cb_block.isChecked():
            ## Dealing with block lesson element
            self.BLOCK_TAG.setEditable(self.rb_new.isChecked())
            btag = self.BLOCK_TAG.currentText()
#?
            print("??? block:", self.sid, btag)
            self.course_table_lines = courses_in_block(self.sid, btag)
            self.this_sid = self.this_course["SUBJECT"]
            if self.cb_unit.isChecked():
                # Show just the courses with the given subject
                sid = self.this_course["SUBJECT"]
                self.course_table_lines = [
                    cdata for cdata in self.course_table_lines
                    if cdata[2] == sid
                ]
                self.set_table_use_selection(True)
            else:
                self.set_table_use_selection(False)
        elif self.rb_simple.isChecked():
            ## Dealing with simple lesson element
            if self.rb_new.isChecked():
#?
                self.course_table_lines = []
#                self.course_table_data = []
#                c = self.this_course["course"]
#                cdata = (
#                    self.this_course["CLASS"],
#                    self.this_course["GRP"],
#                    self.this_course["SUBJECT"],
#                    self.this_course["TEACHER"],
#                )
                for l in self.lesson_list:
                    if l[0] == 0:
                        # simple lesson
#?
                        self.course_table_lines.append(l[1])
            else:
                sid = self.this_course["SUBJECT"]
                self.course_table_data = simple_with_subject(sid)
            self.set_table_use_selection(True)
        else:
            ## Dealing with pay-only element
            assert(self.rb_payonly.isChecked())
            if self.rb_new.isChecked():
                self.course_table_data = []
                c = self.this_course["course"]
                cdata = (
                    self.this_course["CLASS"],
                    self.this_course["GRP"],
                    self.this_course["SUBJECT"],
                    self.this_course["TEACHER"],
                )
                for l in self.lesson_list:
                    if l[0] < 0:
                        # payment-only item
                        self.course_table_data.append((
                            cdata,
                            l[1]["workload"],
                            0,
                            c
                        ))
                self.set_table_use_selection(False)
            else:
                sid = self.this_course["SUBJECT"]
                self.course_table_data = payonly_with_subject(sid)
                self.set_table_use_selection(True)
            self.set_table_use_selection(self.rb_add2team.isChecked())
        self.show_courses()
        if self.course_table_lines:
            self.course_table_activate_line(0)
            if not self.disable_table_row_select:
                self.table_courses.setCurrentCell(0, 0)
        self.acceptable()

    def show_courses(self):
        """Display the courses corresponding to the "filter" values.
        Their data is stored as a list in <self.course_table_lines>.
        """
        self.table_courses.setRowCount(len(self.course_table_lines))
        for r, cdata in enumerate(self.course_table_lines):
            # class field
            if not (tw := self.table_courses.item(r, 0)):
                tw = QTableWidgetItem()
                tw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_courses.setItem(r, 0, tw)
            tw.setText(cdata["CLASS"])
            # group field
            if not (tw := self.table_courses.item(r, 1)):
                tw = QTableWidgetItem()
                tw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_courses.setItem(r, 1, tw)
            tw.setText(cdata["GRP"])
            # subject field
            if not (tw := self.table_courses.item(r, 2)):
                tw = QTableWidgetItem()
                self.table_courses.setItem(r, 2, tw)
            tw.setText(get_subjects().map(cdata["SUBJECT"]))
            # teacher field
            if not (tw := self.table_courses.item(r, 3)):
                tw = QTableWidgetItem()
                self.table_courses.setItem(r, 3, tw)
            tw.setText(get_teachers().name(cdata["TEACHER"]))
            # pay-tag/lesson-data
            if not (tw := self.table_courses.item(r, 4)):
                tw = QTableWidgetItem()
                tw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_courses.setItem(r, 4, tw)
            tw.setText(str(cdata["Lesson_data"]))
            # room-choice field
            if not (tw := self.table_courses.item(r, 5)):
                tw = QTableWidgetItem()
                self.table_courses.setItem(r, 5, tw)
            tw.setText(cdata.get("ROOM", ""))

    def show_lessons(self, lesson_group:int):
        """Display the individual lessons for the given <lesson_group> value.
        """
        self.list_lessons.clear()
        if self.__lesson_group == lesson_group:
            return
        self.__lesson_group = lesson_group
        if lesson_group:
            for l, t in db_read_fields(
                "LESSONS",
                ["LENGTH", "TIME"],
                lesson_group=lesson_group
            ):
                if t:
                    self.list_lessons.addItem(f"{str(l)}  @ {t}")
                else:
                    self.list_lessons.addItem(str(l))

    @Slot(int)
    def on_block_subject_currentIndexChanged(self, i):
        if self.disable_triggers:
            return
        self.disable_triggers = True
        self.set_sid(self.sid_list[i])
        if self.BLOCK_TAG.count():
            self.BLOCK_TAG.setCurrentIndex(0)
        self.disable_triggers = False
        self.on_BLOCK_TAG_currentTextChanged(self.BLOCK_TAG.currentText())

    def set_sid(self, sid):
        """Set up the block-tag widget according to the given subject.
        If <sid> is null the block-tag widget will be disabled.
        Otherwise the drop-down list will be filled with existing
        BLOCK_TAG values for BLOCK_SID=sid.
        """
        self.sid = sid
        self.BLOCK_TAG.clear()
        self.BLOCK_TAG.clearEditText()
        self.sid_block_map = {}
        if sid:
            self.BLOCK_TAG.setEnabled(True)
            tags = self.get_block_sid_tags().get(sid)
            if tags:
                for t, lg in tags:
                    self.sid_block_map[t] = lg
                    self.BLOCK_TAG.addItem(t)
        else:
            self.BLOCK_TAG.setEnabled(False)

#?
    def on_table_courses_currentCellChanged(
        self, row, col, oldrow, oldcol
    ):
        if self.disable_table_row_select:
            return
        if row == self.last_table_row:
            return
        assert(row >= 0)
        self.course_table_activate_line(row)
        self.acceptable()

    def course_table_activate_line(self, row):
        self.last_table_row = row
        if row < 0:
            lg = 0
            self.selected_course = 0
        else:
            cdata = self.course_table_lines[row]
            lg = cdata["Lesson_group"]
            self.selected_course = cdata["Course"]
        self.lesson_group = lg
        self.show_lessons(lg)

    @Slot(int)
    def on_choose_group_idClicked(self, i:int):
        if self.disable_triggers:
            return
        self.set_courses()

    @Slot(bool)
    def on_cb_block_toggled(self, block:bool):
        self.blockstack.setCurrentWidget(
            self.page_block if block else self.page_noblock
        )
        if self.disable_triggers:
            return
        self.set_courses()

    @Slot(bool)
    def on_rb_payonly_toggled(self, on:bool):
        if self.disable_triggers:
            return
        self.set_courses()

    @Slot(bool)
    def on_rb_add2block_toggled(self, on:bool):
        if self.disable_triggers:
            return
        self.set_courses()

    @Slot(bool)
    def on_cb_unit_toggled(self, on:bool):
        if self.disable_triggers:
            return
        self.set_courses()

    @Slot(str)
    def on_BLOCK_TAG_currentTextChanged(self, text):
        if self.disable_triggers:
            return
        self.set_courses()

    def acceptable(self):
        """Determine whether a state is valid as a result.
        Set <self.value> and enable the "accept" button as appropriate.
        """
        if self.rb_new.isChecked():
            if self.cb_block.isChecked():
                if self.lesson_group or not self.sid:
                    self.value = INVALID_RESULT
                    self.pb_accept.setEnabled(False)
                else:
                    self.value = {
                        "type": "NEW",
                        "BLOCK_SID": self.sid,
                        "BLOCK_TAG": self.BLOCK_TAG.currentText(),
                    }
                    self.pb_accept.setEnabled(True)
            else:
                self.value = {
                    "type": "NEW",
                    "BLOCK_SID": "",
                    "BLOCK_TAG": "" if self.rb_simple.isChecked() else "$",
                }
                self.pb_accept.setEnabled(True)
        elif self.rb_add2block.isChecked():
#            assert(self.cb_block.isChecked())
#TODO: I think I am allowing non-blocks here ...

            if self.lesson_group:
                self.value = {
                    "type": "ADD2BLOCK",
                    "lesson_group": self.lesson_group,
                }
                self.pb_accept.setEnabled(True)
            else:
                self.value = INVALID_RESULT
                self.pb_accept.setEnabled(False)
        else:
            # share WORKLOAD entry
#            assert(self.rb_add2team.isChecked())
            # Don't allow adding a course to a "workload", if there
            # is already a link.
            if self.workload:
                id_l = db_values(
                    "COURSE_WORKLOAD",
                    "id",
                    course=self.this_course["course"],
                    workload=self.workload,
                )
                if len(id_l) > 0:
                    self.value = INVALID_RESULT
                    self.pb_accept.setEnabled(False)
                else:
                    self.value = {
                        "type": "ADD2TEAM",
                        "workload": self.workload,
                    }
                    self.pb_accept.setEnabled(True)
            else:
                self.value = INVALID_RESULT
                self.pb_accept.setEnabled(False)

    def accept(self):
        assert(self.value != INVALID_RESULT)
        self.result = self.value
        super().accept()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database("wz_db.sqlite")
    # Stand-alone testing is difficult because data from the course
    # editor is required. It should rather be tested from there.
    course_data = {
        "Course": 12,
        "CLASS": "01G",
        "GRP": "*",
        "SUBJECT": "En",
        "TEACHER": "EL",
        "BLOCK_SID": '',
        "BLOCK_TAG": '',
        "Lesson_data": 16,
        "Lesson_group": 17,
        "LENGTH": 1,
        "TIME": '',
    }
    print("----->", NewCourseLessonDialog.popup(course_data, [(0, course_data)]*3))
    course_data = {
        "Course": 690,
        "CLASS": "--",
        "GRP": "",
        "SUBJECT": "Kk",
        "TEACHER": "CG",
        "BLOCK_SID": '',
        "BLOCK_TAG": '',
        "Lesson_data": 429,
        "Lesson_group": 0,
    }
    print("----->", NewCourseLessonDialog.popup(course_data, [(-1, course_data)]))
    course_data = {
        "Course": 17,
        "CLASS": "01G",
        "GRP": "*",
        "SUBJECT": "Rel",
        "TEACHER": "AH",
        "BLOCK_SID": 'Rel',
        "BLOCK_TAG": '01',
        "Lesson_data": 25,
        "Lesson_group": 14,
        "LENGTH": 1,
        "TIME": '',
        "ROOM": '01G',
    }
    print("----->", NewCourseLessonDialog.popup(course_data, [(1, course_data)]))
    course_data = {
        "Course": 595,
        "CLASS": "01G",
        "GRP": "*",
        "SUBJECT": "Cot",
        "TEACHER": "--",
        "BLOCK_SID": '',
        "BLOCK_TAG": '',
        "Lesson_data": 0,
        "Lesson_group": -1,
        "LENGTH": 0,
        "TIME": '',
        "ROOM": '',
    }
    print("----->", NewCourseLessonDialog.popup(course_data, []))
