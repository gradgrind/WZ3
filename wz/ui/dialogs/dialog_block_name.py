"""
ui/dialogs/dialog_block_name.py

Last updated:  2023-03-07

Supporting "dialog" for the course editor – handle blocks.


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
    db_read_unique_entry,
    db_update_field,
    db_values,
    db_read_unique_field,
)
from ui.ui_base import (
    ### QtWidgets:
    APP,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QTableWidgetItem,
    ### QtGui:
    ### QtCore:
    Qt,
    QRegularExpressionValidator,
    Slot,
    ### other
    uic,
)

### -----

class BlockNameDialog(QDialog):
    @classmethod
    def popup(cls, parent=None, **kargs):
        d = cls(parent)
        return d.activate(**kargs)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_block_name.ui"), self)
        self.pb_reset = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Reset
        )
        self.pb_reset.clicked.connect(self.reset)
        self.table_courses.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )
        validator = QRegularExpressionValidator(BLOCK_TAG_FORMAT)
        self.block_tag.setValidator(validator)

    @Slot(int)
    def on_block_subject_currentIndexChanged(self, i):
        if self.disable_triggers:
            return
        print("§SUBJECT:", i)
        sid = self.sid_list[i]
        self.set_sid(sid)
        if self.block_tag.count():
            self.disable_triggers = True
            self.block_tag.setCurrentIndex(0)
            self.disable_triggers = False
            self.init_courses(self.block_tag.currentText())

    def set_sid(self, sid):
        self.sid = sid
        self.block_tag.clear()
        self.block_tag.clearEditText()
        self.sid_block_map = {}
        if sid:
            self.pb_accept.setEnabled(True)
            self.block_tag.setEnabled(True)
            tags = db_read_fields(
                "LESSON_GROUP", 
                ["lesson_group", "BLOCK_TAG"],
                sort_field="BLOCK_TAG",
                BLOCK_SID=sid,
            )
            for i, t in tags:
                self.sid_block_map[t] = i
                self.block_tag.addItem(t)
        else:
            self.pb_accept.setEnabled(False)
            self.block_tag.setEnabled(False)
        
    @Slot(str)
    def on_block_tag_currentTextChanged(self, text): # show courses
        if self.disable_triggers:
            return
        self.init_courses(text)

    def init_courses(self, btag):
        try:
            lesson_group=self.sid_block_map[btag]
        except KeyError:
            self.table_courses.setRowCount(0)
            self.list_lessons.clear()
            self.pb_reset.setEnabled(False)
            return
        course_refs = db_read_fields(
            "COURSE_LESSONS", 
            ["id", "course", "ROOM"],
            lesson_group=lesson_group
        )
        # Enable the reset button if there is exactly one course:
        self.pb_reset.setEnabled(len(course_refs) == 1)
#TODO: Enable the ok button if there is no LESSON_GROUP entry?
# Surely not correct ... consider how this pop-up is used.
# 1) initializing the block of a new lesson
#      (with pre-choice add-to-existing-block or new-block)
# 2) changing the block of a lesson-group – here it must not exist already
# The difference is the existence of a LESSON_GROUP entry, which is not
# clear if the start value is empty.
        self.pb_accept.setEnabled(not self.lesson_group)
            

        self.table_courses.setRowCount(len(course_refs))
        self.course_map = {}
        self.course_ids = []
        for r, c in enumerate(course_refs):
            cid = c[1]
            self.course_ids.append(cid)
            cdata = dict(zip(*db_read_unique_entry("COURSES", course=cid)))
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
            # room-choice field
            if not (tw := self.table_courses.item(r, 4)):
                tw = QTableWidgetItem()
                self.table_courses.setItem(r, 4, tw)
            tw.setText(c[2])
        ## Show lessons
        self.list_lessons.clear()
        for l, t in db_read_fields(
            "LESSONS",
            ["LENGTH", "TIME"],
            lesson_group=lesson_group
        ):
            text = str(l)
            if t:
                text += f"  @ {t}"
            self.list_lessons.addItem(text)

    def activate(
        self, 
        BLOCK_SID="", 
        BLOCK_TAG="",
        lesson_group=None,
        **xargs
    ) -> Optional[BlockTag]:
        """Open the dialog.
        """
        self.result = None
        self.disable_triggers = True
        self.sid0, self.tag0 = "", ""
        self.lesson_group = lesson_group
        if BLOCK_SID or BLOCK_TAG:
            try:
                btag = BlockTag.build(BLOCK_SID, BLOCK_TAG)
                self.sid0, self.tag0 = btag.sid, btag.tag
            except ValueError as e:
                REPORT("ERROR", str(e))
        ## Populate the subject chooser
        self.sid_list = []
        self.block_subject.clear()
        for sid, name in get_subjects():
            if sid[0] == "-":
                continue
            self.sid_list.append(sid)
            self.block_subject.addItem(name)
        if self.sid0:
            i = self.sid_list.index(self.sid0)
            self.block_subject.setCurrentIndex(i)
        else:
            self.block_subject.setCurrentIndex(-1)
        self.set_sid(self.sid0)
        self.block_tag.setCurrentText(self.tag0)
        self.disable_triggers = False
        self.init_courses(self.tag0)
        self.exec()
        return self.result

    def reset(self):
        """If there is only one course, and this does not already have
        simple lessons, offer to convert the group to a simple group.
        If the conditions are not fulfilled, report this as an error
        and return to the dialog.
        """
        if len(self.course_ids) != 1:
            raise Bug("reset: expected exactly one course!")
        # Check for simple lesson-group
        lesson_refs = db_values(
            "COURSE_LESSONS", 
            "lesson_group",
            course=self.course_ids[0]
        )
        for l in lesson_refs:
            bsid = db_read_unique_field(
                "LESSON_GROUP", 
                "BLOCK_SID",
                lesson_group=l
            )
            if not bsid:
                REPORT("ERROR", T["SIMPLE_LESSONS_EXIST"])
                return
#TODO: Ask whether to do it ...
        self.result = BlockTag("", "", "")   # "illegal" value
        super().accept()

    def accept(self):
        i = self.block_subject.currentIndex()
        s = self.sid_list[i] if i >= 0 else ""
        t = self.block_tag.currentText()
        try:
            btag = BlockTag.build(s, t)
        except ValueError as e:
            REPORT("ERROR", str(e))
            return
        if s != self.sid0 or t != self.tag0:
            # Value has been modified and is valid
#TODO: Actually, I can SEE that the group exists ... it should be
# possible to disable the ok button! But the check is still a good idea,
# it should, however, then raise a Bug exceotion.
#?            # Check that the new value doesn't exist already in LESSON_GROUP
#            if db_check_unique_entry(
#                "LESSON_GROUP", 
#                BLOCK_SID=s,
#                BLOCK_TAG=t,
#            ):
#                REPORT("ERROR", T["BLOCK_EXISTS"])
#                return
            self.result = btag
        super().accept()
        

#TODO ...
# I am now supporting the conversion of a block into a normal lesson.
# This is done via the reset-button. Check that the course editor
# handles this correctly.
# Also the reverse conversion should be possible, perhaps even easier?
# In both cases there should probably be a dialog requesting confirmation.
# For block -> simple, the confirmation dialog could be in the <reset>
# function. For simple -> block, it may be better to have it in the
# trigger code in the course editor.
# In the course editor I would have to enable the block field on the
# simple lessons. Any changes to the block require a course redisplay
# to update the lessons table. 

# Used by course/lesson editor
def edit_block(lesson_group):
    """Pop up a block-tag dialog for the current lesson-group.
    If the info is changed, update the database entry and return the
    string representation of the new value.
    Otherwise return <None>.
    The parameter is the <dict> containing the fields of the
    LESSON_GROUP record.
    """
    btresult = BlockNameDialog.popup(
        start_value=lesson_group["BLOCK_NAME"],
        parent=APP.activeWindow()
    )
    if btresult is None:
        return None
    result = str(btresult)
    db_update_field(
        "LESSON_GROUP",
        "BLOCK_NAME",
        result,
        lesson_group=lesson_group["lesson_group"]
    )
    lesson_group["BLOCK_MAP"] = result
    return result


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print("----->", BlockNameDialog.popup())
    print("----->", BlockNameDialog.popup(BLOCK_SID="KoRa"))
    print("----->", BlockNameDialog.popup(BLOCK_SID="ZwE", BLOCK_TAG="09G10G"))
    print("----->", BlockNameDialog.popup(BLOCK_SID="XXX"))
    print("----->", BlockNameDialog.popup(BLOCK_SID="Hu"))
    print("----->", BlockNameDialog.popup(BLOCK_TAG="NoSubject"))
