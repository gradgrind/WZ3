"""
ui/dialogs/dialog_block_name.py

Last updated:  2023-07-07

Supporting "dialog" for the course editor – inspect the lesson group
fields (including block tags and pay-id), allow changing of existing
block tags.


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

#T = TRANSLATIONS("ui.dialogs.dialog_block_name")

### +++++

from typing import Optional
from core.basic_data import (
    BLOCK_TAG_FORMAT,
    get_subjects,
    get_teachers,
)
from core.db_access import (
    db_read_fields,
    db_select,
    Record,
)
from core.course_data_3 import (
    read_block_sid_tags,
)
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QTableWidgetItem,
#    QAbstractItemView,
    ### QtGui:
    ### QtCore:
    Qt,
    QRegularExpressionValidator,
    Slot,
    ### other
    uic,
)

INVALID_RESULT = ("?", "")    # invalid result

### -----

class BlockNameDialog(QDialog):
    """This dialog is evoked from the course editor.
    The "linkages" of the current course/lesson-group are shown.
    The table row (lesson_row) of the current element is passed as argument.
    In the case of a block member, the name of the block may be
    changed (to a completely new one), otherwise no changes are possible.

    This dialog itself causes no database changes, that must be done by
    the calling code on the basis of the returned value.
    If the dialog is cancelled, <None> is returned and there should be
    no changes to the database.
    Otherwise a pair is returned: (
        "BLOCK_SID": new block-subject-id,
        "BLOCK_TAG": new block-tag
    )
    """
    @classmethod
    def popup(
        cls,
        course_lessons:list[tuple[int, Record]],
        lesson_row:int=-1,
        parent=None
    ) -> Optional[tuple[str, str]]:
        d = cls(parent)
        return d.activate(course_lessons, lesson_row)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_block_name_3.ui"), self)
        self.table_courses.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )
        validator = QRegularExpressionValidator(BLOCK_TAG_FORMAT)
        self.BLOCK_TAG.setValidator(validator)

    def set_block_subject_list(self):
        """Populate the subject chooser.
        This is called (only) at the beginning of <activate>.
        """
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
        lesson_list: list[tuple[int, Record]],
        lesson_row: int
    ) -> Optional[tuple[str, str]]:
        """Open the dialog.
        <lesson_row> indicates the selected record < 0, a new element is to be created.
        Otherwise, open in "inspection" mode. The details of the
        current element will be displayed. The only change possible
        is to assign a new name to a block.
        """
        #print("\n§§§", lesson_row)
        #for l in lesson_list:
        #    print("  --", l[0], l[1])
        self.result = None
        self.__block_sid_tags = None    # cache for block-names
        self.lesson_list = lesson_list
        self.lesson_row = lesson_row
        self.disable_triggers = True
        self.lesson_group = -1
        self.pb_accept.setEnabled(False)
        # Determine item type
        this_lesson = lesson_list[lesson_row]
        ltype = this_lesson[0]
        if ltype > 0:
            # block
            self.set_block_subject_list()
            self.block.setEnabled(True)
            self.BLOCK_TAG.setEditable(True)
            data = this_lesson[1]
            bsid = data["BLOCK_SID"]
            self.block_subject.setCurrentIndex(self.sid_index[bsid])
            self.set_sid(bsid)
            self.BLOCK_TAG.setCurrentText(data["BLOCK_TAG"])
        else:
            self.block.setEnabled(False)
        self.inspect_courses(this_lesson)
        self.disable_triggers = False
        self.exec()
        return self.result

    def inspect_courses(self, this_data):
        """Set up the courses. This is called only once, when
        initializing the display, which doesn't change subsequently.
        """
        self.list_lessons.clear()
        ltype, data = this_data
        this_c = data["Course"]
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
            ## Get all COURSE entries for this lesson_group
            q = f"""select
                    CLASS,
                    GRP,
                    SUBJECT,
                    TEACHER,
                    Lesson_data,
                    coalesce(ROOM, '') ROOM,
                    Course
                    --coalesce(Lesson_group, 0) Lesson_group,
                    --coalesce(BLOCK_TAG, '') BLOCK_TAG,
                    --coalesce(BLOCK_SID, '') BLOCK_SID
                from COURSE_LESSONS
                inner join COURSES using(Course)
                inner join LESSON_DATA using(Lesson_data)
                where Lesson_group = {lg}
            """
        else:
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
                where Lesson_data = {data["Lesson_data"]}
            """
        rlist = [None]
        for r in sorted(
            db_select(q),
            key=lambda x: (x["CLASS"], x["SUBJECT"], x["GRP"], x["TEACHER"])
        ):
            if r["Course"] == this_c:
                assert rlist[0] is None
                rlist[0] = r
            else:
                rlist.append(r)
        self.course_table_lines = rlist
        #print("\ninspect_courses:")
        #for r in self.course_table_lines:
        #    print(r)
        self.show_courses()

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

    @Slot(str)
    def on_BLOCK_TAG_currentTextChanged(self, text):
        if self.disable_triggers:
            return
        # Only set enabled state of accept button.
        if self.BLOCK_TAG.findText(text) < 0:
            # new tag
            self.value = (self.sid, text)
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
    print("----->", BlockNameDialog.popup([(-1, course_data)], 0))
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
    print("----->", BlockNameDialog.popup([(0, course_data)]*3, 1))
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
    print("----->", BlockNameDialog.popup([(1, course_data)], 0))
