"""
ui/dialogs/dialog_block_data.py

Last updated:  2023-06-11

Supporting "dialog" for the course editor – handle course elements.
That is, add new elements or inspect existing ones.
The basic types are simple lesson item, block lesson item and
no-lesson item (payment-only).
A new element can be completely new, that is a new entry in
COURSE_WORKLOAD and in WORKLOAD. Unless it is payment-only there
will also be a new entry in LESSON_GROUPS and a single entry in
LESSONS.
A new element can be a membership in an existing block. The
existing LESSON_GROUPS entry for that block will be shared,
there will be a new entry in COURSE_WORKLOAD and in WORKLOAD.
Finally, a new element can share an existing WORKLOAD element
(and thus room and payment details). Here there will only be
a new entry in COURSE_WORKLOAD.
In "inspection mode", no changes can be made, except that a
block may have its name changed.


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

if __name__ == "__main__":
    import sys, os

    this = sys.path[0]
    appdir = os.path.dirname(os.path.dirname(this))
    sys.path[0] = appdir
    basedir = os.path.dirname(appdir)
    from core.base import start
    start.setup(os.path.join(basedir, 'TESTDATA'))

T = TRANSLATIONS("ui.dialogs.dialog_block_name")

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
)
from core.course_data import (
    courses_in_block,
    simple_with_subject,
    payonly_with_subject,
)
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QTableWidgetItem,
    QAbstractItemView,
    ### QtGui:
    ### QtCore:
    Qt,
    QRegularExpressionValidator,
    Slot,
    ### other
    uic,
)

INVALID_RESULT = {"type": "INVALID"}    # invalid result

### -----

class BlockNameDialog(QDialog):
    """This dialog is evoked from the course editor.
    There are the following scenarios:

    1) A new course/lesson_group connection is to be made.
       There is the choice between a simple lesson, a block lesson
       and a payment-only item.
       The new item consists of a new WORKLOAD entry and an entry in
       COURSE_WORKLOAD linking the course to the workload. Unless the
       new item is payment-only, there will also be a new LESSON_GROUPS
       entry (linked from the WORKLOAD entry), and a single entry in
       LESSONS for the lesson_group.
       Note that further lessons may be added to existing
       lesson_groups in the course editor, using the "+" button.
       A payment-only item doesn't have a lesson group.

    2) A course may "join" an existing block (named lesson_group).

    3) A course may "join" an existing workload. All members must have
       the same subject. This covers simple cases of team-teaching and
       mixed pupil groups where only one room (at most) is specified
       and the payment details for all the teachers are the same.
       
    4) The "linkages" of the current course/workload/lesson group can
       be shown.
       In this case the table row (lesson_row) of the current element
       is passed as argument (otherwise).
       In the case of a block member, the name of the block may be
       changed (to a completely new one), otherwise no changes are possible.

    This dialog itself causes no database changes, that must be done by
    the calling code on the basis of the returned value.
    If the dialog is cancelled, <None> is returned and there should be
    no changes to the database.
    Otherwise a mapping is returned: {"type": type of element, ...}
    Further entries depend on the type.
    In "inspection" mode, only one return type is possible:
        {   "type": "CHANGE_BLOCK",
            "BLOCK_SID": new block-subject-id,
            "BLOCK_TAG": new block-tag
        }
    In "new element" mode, the following return values are possible:
    1) A completely new entry:
        {   "type": "NEW",
            "BLOCK_SID": ("" or block-subject-id),
            "BLOCK_TAG": ("", "$" or block-tag)
        }
        If BLOCK_SID is empty, BLOCK_TAG must be "" (new simple lesson)
        or "$" (new payment-only item).
    2) Add to existing block:
        {   "type": "ADD2BLOCK",
            "lesson_group": lesson_group of existing block
        }
    3) Add to existing WORKLOAD entry:
        {   "type": "ADD2TEAM",
            "workload": self.workload,
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
        return d.activate(course_data, course_lessons, lesson_row)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_block_name.ui"), self)
        self.table_courses.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )
        validator = QRegularExpressionValidator(BLOCK_TAG_FORMAT)
        self.BLOCK_TAG.setValidator(validator)

    def activate(
        self,
        this_course: dict,
        lesson_list: list[dict],
        lesson_row: int
    ) -> Optional[dict]:
        """Open the dialog.
        If lesson_row < 0, a new element is to be created.
        Otherwise, open in "inspection" mode. The details of the
        current element will be displayed. The only change possible
        is to assign a new name to a block.
        """
        self.result = None
        self.__block_sid_tags = None    # cache for block-names
        self.this_course = this_course
        self.lesson_list = lesson_list
        self.lesson_row = lesson_row
        self.disable_triggers = True
        self.lesson_group = -1
        self.set_table_use_selection(False)
        self.set_block_subject_list()
        self.pb_accept.setEnabled(False)
        if lesson_row >= 0:
            ## "Inspection" mode, no changes possible except block-name
            self.rb_inspect.setChecked(True)
            # Determine item type
            this_lesson = lesson_list[lesson_row]
            ltype = this_lesson[0]
            if ltype > 0:
                # block
                self.cb_block.setChecked(True)
                self.BLOCK_TAG.setEditable(True)
                data = this_lesson[1]
                bsid = data["BLOCK_SID"]
                self.block_subject.setCurrentIndex(self.sid_index[bsid])
                self.set_sid(bsid)
                self.BLOCK_TAG.setCurrentText(data["BLOCK_TAG"])
            else:
                self.cb_block.setChecked(False)
                if ltype == 0:
                    # simple lessons
                    self.rb_simple.setChecked(True)
                else:
                    # no lessons (pay-only)
                    self.rb_payonly.setChecked(True)
            self.inspect_courses(this_lesson)

        else:
            ## "New element" mode
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
            
    def set_block_subject_list(self):
        """Populate the subject chooser."""
        self.block_subject.clear()
        self.sid_list = []
        self.sid_index = {}
        for sid, name in get_subjects():
            if sid[0] == "-":
                continue
            self.sid_index[sid] = len(self.sid_list)
            self.sid_list.append(sid)
            self.block_subject.addItem(name)
        self.block_subject.setCurrentIndex(-1)

    def set_table_use_selection(self, on:bool):
        self.disable_table_row_select = not on

    def inspect_courses(self, this_data):
        """Set up the courses for the "inspect" mode.
        This is called only once, when initializing this mode, the
        display doesn't change subsequently.
        """
        self.list_lessons.clear()
        ltype, data = this_data
        this_w = data["Workload"]
        lg = data["Lesson_group"]
        if lg:
            ## Show lessons
            for _, d in self.lesson_list:
                if d["Lesson_group"] == lg:
                    n = d["LENGTH"]
                    t = d["TIME"]
                    if t:
                        self.list_lessons.addItem(f"{str(n)}  @ {t}")
                    else:
                        self.list_lessons.addItem(str(n))

#            lessons = data["lessons"]
#            assert(lessons)
#            ## Show lessons
#            for l in lessons:
#                n = l["LENGTH"]
#                t = l["TIME"]
#                if t:
#                    self.list_lessons.addItem(f"{str(n)}  @ {t}")
#                else:
#                    self.list_lessons.addItem(str(n))



            ## Get all WORKLOAD entries for this lesson_group
            wlist = [this_w]
            for w in db_values(
                "WORKLOAD",
                "workload",
                lesson_group=lg
            ):
                if w != this_w:
                    wlist.append(w)
            if not data["BLOCK_SID"]:
                # simple lessons
                assert(len(wlist) == 1)
        else:
            ## no lessons (pay-only)
            wlist = [data["Workload"]]
        ## Show courses, the current one first
        this_course = data["Course"]
        courses = [(this_course, this_w)]
        for w in wlist:
            for course in db_values("COURSE_WORKLOAD", "course", workload=w):
                if course != this_course:
                    courses.append((course, w))
        self.course_table_data = []
        for course, w in courses:
            cdata = db_read_unique(
                "COURSES",
                ("CLASS", "GRP", "SUBJECT", "TEACHER"),
                course=course
            )
            self.course_table_data.append((cdata, w, lg, course))
        self.show_courses()
        #self.set_table_use_selection(False) # the default?

    def set_courses(self):
        """Set up the dialog according to the various parameters.
        This is only used in "new element" mode and is called
        whenever a parameter is changed (except line change in
        the course table).
        """
        self.course_table_activate_line(-1)
        self.pb_accept.setEnabled(False)
        if self.rb_add2block.isChecked():
            ## Add an element to an existing block.
            self.cb_block.setEnabled(False)
            self.cb_block.setChecked(True)
        else:
            self.cb_block.setEnabled(True)
        if self.cb_block.isChecked():
            ## Dealing with block lesson element
            self.BLOCK_TAG.setEditable(self.rb_new.isChecked())
            btag = self.BLOCK_TAG.currentText()
            self.course_table_data = courses_in_block(self.sid, btag)
            if self.rb_add2team.isChecked():
                # Show just the courses with the given subject
                sid = self.this_course["SUBJECT"]
                self.course_table_data = [
                    ctd for ctd in self.course_table_data
                    if ctd[0][2] == sid
                ]
                self.set_table_use_selection(True)
            else:
                self.set_table_use_selection(False)
        elif self.rb_simple.isChecked():
            ## Dealing with simple lesson element
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
                    if l[0] == 0:
                        # simple lesson
                        self.course_table_data.append((
                            cdata,
                            l[1]["workload"],
                            l[1]["lesson_group"],
                            c
                        ))
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
        if self.course_table_data:
            self.course_table_activate_line(0)
            if not self.disable_table_row_select:
                self.table_courses.setCurrentCell(0, 0)
        self.acceptable()

    def show_courses(self):
        """Display the courses corresponding to the "filter" values.
        Their data is stored as a list in <self.course_table_data>.
        """
        self.table_courses.setRowCount(len(self.course_table_data))
        for r, cw in enumerate(self.course_table_data):
            cdata, workload = cw[:2]    # cdata: (CLASS, GRP, sid, tid)
            # class field
            if not (tw := self.table_courses.item(r, 0)):
                tw = QTableWidgetItem()
                tw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_courses.setItem(r, 0, tw)
            tw.setText(cdata[0])
            # group field
            if not (tw := self.table_courses.item(r, 1)):
                tw = QTableWidgetItem()
                tw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_courses.setItem(r, 1, tw)
            tw.setText(cdata[1])
            # subject field
            if not (tw := self.table_courses.item(r, 2)):
                tw = QTableWidgetItem()
                self.table_courses.setItem(r, 2, tw)
            tw.setText(get_subjects().map(cdata[2]))
            # teacher field
            if not (tw := self.table_courses.item(r, 3)):
                tw = QTableWidgetItem()
                self.table_courses.setItem(r, 3, tw)
            tw.setText(get_teachers().name(cdata[3]))
            # workload (key)
            if not (tw := self.table_courses.item(r, 4)):
                tw = QTableWidgetItem()
                tw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_courses.setItem(r, 4, tw)
            tw.setText(str(workload))
            # room-choice field
            if not (tw := self.table_courses.item(r, 5)):
                tw = QTableWidgetItem()
                self.table_courses.setItem(r, 5, tw)
            room = db_read_unique_field("WORKLOAD", "ROOM", workload=workload)
            tw.setText(room)

    def show_lessons(self, lesson_group:int):
        """Display the individual lessons for the given <lesson_group> value.
        """
        self.list_lessons.clear()
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
        
    def get_block_sid_tags(self):
        """Get mapping from BLOCK_SID to the list of defined BLOCK_TAGs
        for that subject. Also the lesson_group is included:
            {BLOCK_SID: (BLOCK_TAG, lesson_group), ... }
        The result is cached to avoid unnecessary action
        """
        if self.__block_sid_tags is not None:
            return self.__block_sid_tags
        bst = {}
        for lg, BLOCK_SID, BLOCK_TAG in db_read_fields(
            "LESSON_GROUPS", ("lesson_group", "BLOCK_SID", "BLOCK_TAG")
        ):
            if BLOCK_SID:
                tag_lg = (BLOCK_TAG, lg)
                try:
                    bst[BLOCK_SID].append(tag_lg)
                except KeyError:
                    bst[BLOCK_SID] = [tag_lg]
        self.__block_sid_tags = bst
        return bst

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
            self.workload = 0
            self.selected_course = 0
        else:
            ctd = self.course_table_data[row]
            lg = ctd[2]
            self.workload = ctd[1]
            self.selected_course = ctd[3]
        if lg != self.lesson_group:
            self.show_lessons(lg)
            self.lesson_group = lg

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
    def on_rb_payonly_toggled(self, payonly:bool):
        if self.disable_triggers:
            return
        self.set_courses()

    @Slot(str)
    def on_BLOCK_TAG_currentTextChanged(self, text):
        if self.disable_triggers:
            return
        if self.lesson_row >= 0:
            # "inspect" mode, only set enabled state of accept button.
            if self.BLOCK_TAG.findText(text) < 0:
                # new tag
                self.value = {
                    "type": "CHANGE_BLOCK",
                    "BLOCK_SID": self.sid,
                    "BLOCK_TAG": text
                }
                self.pb_accept.setEnabled(True)
            else:
                self.value = INVALID_RESULT
                self.pb_accept.setEnabled(False)
            return
        # "new element" mode
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
            assert(self.cb_block.isChecked())
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
            assert(self.rb_add2team.isChecked())
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
    open_database()
    # Stand-alone testing is difficult because data from the course
    # editor is required. It should rather be tested from there.
    course_data = {
        "course": 2,
        "CLASS": "--",
        "GRP": "",
        "SUBJECT": "KoRa",
        "TEACHER": "ML",
    }
    print("----->", BlockNameDialog.popup(course_data, [], -1))
    course_data = {
        "course": 350,
        "CLASS": "11G",
        "GRP": "R",
        "SUBJECT": "Ma",
        "TEACHER": "MT",
    }
    print("----->", BlockNameDialog.popup(course_data, [], -1))
