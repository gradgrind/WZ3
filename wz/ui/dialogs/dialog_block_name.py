"""
ui/dialogs/dialog_room_choice.py

Last updated:  2023-03-04

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

#T = TRANSLATIONS("ui.dialogs.dialog_block_name")

### +++++

from typing import Optional
from core.basic_data import (
    BLOCK_TAG_FORMAT,
    get_subjects,
    get_teachers,
    BlockTag,
)
from core.db_access import db_read_table, db_read_unique_entry
from ui.ui_base import (
    ### QtWidgets:
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
    def popup(cls, start_value):
        d = cls()
        return d.activate(start_value)

    def __init__(self):
        super().__init__()
        uic.loadUi(APPDATAPATH("ui/dialog_block_name.ui"), self)
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

    def set_sid(self, sid):
        self.sid = sid
        self.block_tag.clear()
        self.block_tag.clearEditText()
        self.sid_block_map = {}
        if sid:
            self.pb_accept.setEnabled(True)
            self.block_tag.setEnabled(True)
            f, self.tags = db_read_table(
                "LESSON_GROUP", 
                ["lesson_group", "BLOCK_NAME"],
                f"BLOCK_NAME LIKE '{sid}#%'",
                sort_field="BLOCK_NAME",
            )
            l = len(sid) + 1
            for i, t in self.tags:
                btag = t[l:]
                self.sid_block_map[btag] = i
                self.block_tag.addItem(btag)
        else:
            self.pb_accept.setEnabled(False)
            self.block_tag.setEnabled(False)
        self.init_courses("")
        
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
            return
        f, self.course_refs = db_read_table(
            "COURSE_LESSONS", 
            ["id", "course", "ROOM"],
            lesson_group=lesson_group
        )
        self.table_courses.setRowCount(len(self.course_refs))
        self.course_map = {}
        for r, c in enumerate(self.course_refs):
            cid = c[1]
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
                  
    def activate(self, start_value:str) -> Optional[BlockTag]:
        """Open the dialog.
        """
        self.result = None
        self.disable_triggers = True
        self.sid0, self.tag0 = "", ""
        if start_value:
            try:
                btag = BlockTag.read(start_value)
                self.sid0, self.tag0 = btag.sid, btag.tag
            except ValueError as e:
                REPORT("ERROR", str(e))
        ## Populate the subject chooser
        self.sid_list = []
#        start_index = -1
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
            self.result = btag
        super().accept()
        

# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print("----->", BlockNameDialog.popup(""))
    print("----->", BlockNameDialog.popup("KoRa#"))
    print("----->", BlockNameDialog.popup("XXX#"))
    print("----->", BlockNameDialog.popup("ZwE#09G10G"))
    print("----->", BlockNameDialog.popup("Hu#"))
    print("----->", BlockNameDialog.popup("NoSubject"))
