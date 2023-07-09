"""
ui/dialogs/dialog_new_course_lesson.py

Last updated:  2023-07-09

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
)
from core.db_access import db_read_fields
from core.course_data_3a import (
    courses_in_block,
    block_sids_in_class,
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

### -----

# block (needs BLOCK_SID != "" to be valid/acceptable):
#       Show courses according to selected BLOCK_SID+BLOCK_TAG.
#       Show lessons according to selected BLOCK_SID+BLOCK_TAG.
#   new:
#       No course selection.
#       May not match any existing BLOCK_SID+BLOCK_TAG pair, tag editable.
#       -> lesson_group = -1, BLOCK_SID, BLOCK_TAG
#   parallel, not unit:
#       Course selection enabled?
#       Must match existing BLOCK_SID+BLOCK_TAG pair, tag not editable.
#       -> lesson_group > 0, BLOCK_SID, BLOCK_TAG, lesson_data = -1
#               + LESSON_DATA pay values to copy?
#   parallel, unit:
#       Course selection enabled.
#       Must match existing BLOCK_SID+BLOCK_TAG pair, tag not editable.
#       Show only courses which match subject of current course.
#       -> lesson_group > 0, BLOCK_SID, BLOCK_TAG, lesson_data > 0

# not block, no-lesson/pay-only:
#       Show no lessons (by definition!).
#   new:
#       Show no courses.
#       (Course selection thus irrelevant).
#       -> lesson_group = -1, BLOCK_SID = "", BLOCK_TAG = "$"
#   parallel, not unit:
#       Probably not very useful ...
#       Show no-lesson items with same subject as current course.
#       Allow course selection.
#       -> lesson_group = 0, lesson_data = -1
#               + LESSON_DATA pay values to copy?
#   parallel, unit:
#       Show no-lesson items with same subject as current course.
#       Allow course selection.
#       -> lesson_group = 0, lesson_data > 0

# not block, "simple" lesson:
#   new:
#       Show no courses.
#       Show no lessons.
#       (Course selection thus irrelevant).
#       -> lesson_group = -1, BLOCK_SID = "", BLOCK_TAG = ""
#   parallel, not unit:
#       Show simple-lesson items (lesson_group > 0, BLOCK_SID == "").
#       Allow course selection.
#       -> lesson_group > 0, BLOCK_SID = "", BLOCK_TAG = "", lesson_data = -1
#               + LESSON_DATA pay values to copy?
#   parallel, unit:
#       Show simple-lesson items with same subject as current course.
#       Allow course selection.
#       -> lesson_group > 0, BLOCK_SID = "", BLOCK_TAG = "", lesson_data > 0


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
        {   "lesson_group": -1,
            "BLOCK_SID": ("" or block-subject-id),
            "BLOCK_TAG": ("", "$" or block-tag)
        }
        If BLOCK_SID is empty, BLOCK_TAG must be "" (new simple lesson)
        or "$" (new no-lesson item).
    2) Add to existing lesson-group:
        {   "lesson_group": > 0 (lesson_group of existing item),
            "BLOCK_SID": ("" or block-subject-id),
            "BLOCK_TAG": ("" or block-tag),
            "lesson_data": -1 (if not "unit") or > 0 (lesson_data of
                existing item),
            "Pay_factor_id": (from existing item),
            "PAY_NLESSONS": (from existing item)
        }
    """
    @classmethod
    def popup(
        cls,
        course_data:dict,
        parent=None):
        d = cls(parent)
        return d.activate(course_data)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_new_course_lesson.ui"), self)
        self.table_courses.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )
        # Validator for block tags – applied in <set_courses>
        self.btvalidator = QRegularExpressionValidator(BLOCK_TAG_FORMAT)

    @Slot(bool)
    def on_cb_block_toggled(self, on):
        self.blockstack.setCurrentIndex(1 if on else 0)
        if self.disable_triggers:
            return
        self.set_courses()

    def set_block_subject_list(self):
        """Populate the block-subject chooser.
        This is called (only) at the beginning of <activate>.
        Any block-subjects already in use by the class will appear
        highlighted at the top of the subject list.
        """
        # Get block subjects already used in the current class
        bsids = []
        bsindex = {}
        for sid in block_sids_in_class(self.this_course["CLASS"]):
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
        This is used by <set_blocksid>, so it can be called multiple times.
        The result is cached to avoid unnecessary reloading.
        """
        if self.__block_sid_tags is None:
            self.__block_sid_tags = read_block_sid_tags()
        return self.__block_sid_tags

    def activate(
        self,
        this_course: dict,
    ) -> Optional[dict]:
        """Open the dialog."""
        #print("\n???", this_course)
        self.this_course = this_course
        self.result = None
        self.__block_sid_tags = None    # cache for block-names
        self.disable_triggers = True
        self.lesson_group = -1
        self.set_table_use_selection(False)
        self.set_block_subject_list()
        self.pb_accept.setEnabled(False)
        self.rb_new.setChecked(True)    # default choice
        self.rb_simple.setChecked(True) # default choice
        self.set_blocksid("")           # clear block data
        self.cb_block.setChecked(False) # default choice
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
        self.btag = ""
        if self.cb_block.isChecked():
            ## Dealing with block lesson element
            if self.rb_add2block.isChecked():
                # "parallel"
                self.set_table_use_selection(True)
                self.BLOCK_TAG.setEditable(False)
            else:
                # "new"
                self.set_table_use_selection(False)
                self.BLOCK_TAG.setEditable(True)
                self.BLOCK_TAG.setValidator(self.btvalidator)
            i = self.block_subject.currentIndex()
            if i < 0:
                self.course_table_lines = []
            else:
                self.btag = self.BLOCK_TAG.currentText()
                self.block = (self.sid_list[i], self.BLOCK_TAG.currentText())
                self.course_table_lines = courses_in_block(
                    bsid=self.blocksid,
                    btag=self.btag
                )
                if self.rb_new.isChecked():
                    if not self.course_table_lines:
                        self.pb_accept.setEnabled(True)
                else:
                    if self.cb_unit.isChecked():
                        # Keep only the lines with the same course subject
                        this_sid = self.this_course["SUBJECT"]
                        self.course_table_lines = [
                            row for row in self.course_table_lines
                            if row["SUBJECT"] == this_sid
                        ]
                    if self.course_table_lines:
                        self.pb_accept.setEnabled(True)
        else:
            self.set_table_use_selection(True)
            if self.rb_add2block.isChecked():
                # "parallel": list only courses with same sid. This is
                # rather like a tagged block with the tag replaced by
                # the shared subject.
                # The "unit" flag is just be an extra-tight binding (one
                # teaching unit).
                if self.rb_simple.isChecked():
                    # Seek only simple lesson items
                    self.course_table_lines = simple_with_subject(
                        self.this_course["SUBJECT"]
                    )
                else:
                    # Seek only no-lesson items
                    self.course_table_lines = payonly_with_subject(
                        self.this_course["SUBJECT"]
                    )
                if self.course_table_lines:
                    self.pb_accept.setEnabled(True)
            else:
                # "new": whether the course table rows are selectable
                # is not relevant as there aren't any rows.
                self.course_table_lines = []
                self.pb_accept.setEnabled(True)
        self.show_courses()
        if self.course_table_lines:
            # If the "calling" course is in the list, disable "accept".
            cid = self.this_course["Course"]
            for cdata in self.course_table_lines:
                if cdata["Course"] == cid:
                    self.pb_accept.setEnabled(False)
                    break
            if not self.disable_table_row_select:
                self.disable_table_row_select = True
                self.table_courses.setCurrentCell(0, 0)
                self.disable_table_row_select = False
            self.course_table_activate_line(0)

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

    @Slot(int)
    def on_block_subject_currentIndexChanged(self, i):
        if self.disable_triggers:
            return
        self.disable_triggers = True
        self.set_blocksid(self.sid_list[i])
        if self.BLOCK_TAG.count():
            self.BLOCK_TAG.setCurrentIndex(0)
        self.disable_triggers = False
        self.on_BLOCK_TAG_currentTextChanged(self.BLOCK_TAG.currentText())

    def set_blocksid(self, sid):
        """Set up the block-tag widget according to the given subject.
        If <sid> is null the block-tag widget will be disabled.
        Otherwise the drop-down list will be filled with existing
        BLOCK_TAG values for BLOCK_SID=sid.
        """
        self.blocksid = sid
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
        self.course_table_activate_line(row)

    def course_table_activate_line(self, row):
        if row < 0:
            self.course_data = None
            lesson_group = 0
        else:
            self.course_data = self.course_table_lines[row]
            lesson_group = self.course_data["Lesson_group"]
        # Display the individual lessons for the given <lesson_group> value.
        if self.lesson_group == lesson_group:
            return
        self.lesson_group = lesson_group
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
    def on_choose_group_idClicked(self, i:int):
        if self.disable_triggers:
            return
        self.set_courses()

    @Slot(bool)
    def on_rb_payonly_toggled(self, on:bool):
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

    def accept(self):
        if self.rb_new.isChecked():
            if self.cb_block.isChecked():
                # There must be a block-sid, and block-sid + block-tag
                # must be new.
                self.result = {
                    "lesson_group": -1,
                    "BLOCK_SID": self.blocksid,
                    "BLOCK_TAG": self.BLOCK_TAG.currentText(),
                }
            else:
                self.result = {
                    "lesson_group": -1,
                    "BLOCK_SID": "",
                    "BLOCK_TAG": "" if self.rb_simple.isChecked() else "$",
                }
        else:
            lesson_data = (
                self.course_data["Lesson_data"]
                if self.cb_unit.isChecked()
                else -1
            )
            self.result = {
                "lesson_group": self.lesson_group,
                "BLOCK_SID": self.blocksid,
                "BLOCK_TAG": self.btag,
                "Lesson_data": lesson_data,
                "PAY_NLESSONS": self.course_data["PAY_NLESSONS"],
                "Pay_factor_id": self.course_data["Pay_factor_id"]
            }
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
    print("----->", NewCourseLessonDialog.popup(course_data))
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
    print("----->", NewCourseLessonDialog.popup(course_data))
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
    print("----->", NewCourseLessonDialog.popup(course_data))
    course_data = {
        "Course": 595,
        "CLASS": "01G",
        "GRP": "*",
        "SUBJECT": "Ma",
        "TEACHER": "--",
        "BLOCK_SID": '',
        "BLOCK_TAG": '',
        "Lesson_data": 0,
        "Lesson_group": -1,
        "LENGTH": 0,
        "TIME": '',
        "ROOM": '',
    }
    print("----->", NewCourseLessonDialog.popup(course_data))
