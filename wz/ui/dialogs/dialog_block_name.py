"""
ui/dialogs/dialog_room_choice.py

Last updated:  2023-03-03

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

#TODO ...

from typing import Optional
from core.basic_data import (
    BLOCK_TAG_FORMAT,
    get_subjects,
    BlockTag,
)
from core.db_access import db_read_table, db_read_unique_entry
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    ### QtGui:
    ### QtCore:
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
        pb = self.buttonBox.button(QDialogButtonBox.StandardButton.Reset)
        pb.clicked.connect(self.reset)
        validator = QRegularExpressionValidator(BLOCK_TAG_FORMAT)
        self.block_tag.setValidator(validator)

    @Slot(int)
    def on_block_subject_currentIndexChanged(self, i):
        if self.disable_triggers:
            return
        print("§SUBJECT:", i)
        sid = self.sid_list[i]
        self.init_tags(sid)

    @Slot(str)
    def on_block_tag_currentTextChanged(self, text): # show courses
        if self.disable_triggers:
            return
        print("§TAG:", text)
        self.init_courses(text)

    def init_tags(self, sid):
        self.sid = sid
        self.block_tag.clear()
        f, self.tags = db_read_table(
            "LESSON_GROUP", 
            ["lesson_group", "BLOCK_NAME"],
            f"BLOCK_NAME LIKE '{sid}#%'",
            sort_field="BLOCK_NAME",
        )
        self.sid_block_map = {}
        l = len(sid)
        for i, t in self.tags:
            btag = t[l:]
            self.sid_block_map[btag] = i
            self.block_tag.addItem(btag)
        
    def init_courses(self, btag):
        self.list_courses.clear()
        print("§COURSES:", btag)
        try:
            lesson_group=self.sid_block_map[btag]
        except KeyError:
            return
        f, self.course_refs = db_read_table(
            "COURSE_LESSONS", 
            ["id", "course"],
            lesson_group=lesson_group
        )
        self.course_map = {}
        for c in self.course_refs:
            cid = c[1]
            cdata = dict(zip(*db_read_unique_entry("COURSES", course=cid)))
            cstr = (
                f'{cdata["CLASS"]}.{cdata["GRP"]}:'
                f'{cdata["SUBJECT"]}/{cdata["TEACHER"]}'
            )
            print("§COURSEDATA:", cstr)
            self.list_courses.addItem(cstr)
        
    def activate(self, start_value:str):
        """Open the dialog.
        """
        self.result = None
        self.disable_triggers = True
        try:
            btag = BlockTag.read(start_value)
            self.value0 = btag
        except ValueError as e:
            REPORT("ERROR", str(e))
            btag = BlockTag.read("")
            self.value0 = "!"   # invalid
        bsid = btag.sid
        print("?", bsid)
        self.sid_list = []
        start_index = -1
        self.block_subject.clear()
        i = 0
        for sid, name in get_subjects():
            if sid[0] == "-":
                continue
            self.sid_list.append(sid)
            self.block_subject.addItem(name)
            if sid == bsid:
                start_index = i
                self.init_tags(sid)
            i += 1
        self.block_subject.setCurrentIndex(start_index)
        self.block_tag.setCurrentText(btag.tag)
        self.disable_triggers = False
        self.exec()
        return self.result

    def reset(self):
        """Return an "empty" value."""
        self.result = BlockTag.read("")
        super().accept()

    def accept(self):
        i = self.block_subject.currentIndex()
        t = self.block_tag.currentText()
        try:
            btag = BlockTag.build(self.sid_list[i] if i >= 0 else "", t)
        except ValueError as e:
            REPORT("ERROR", str(e))
            return
        if btag != self.value0:
            self.result = btag
        super().accept()
        

# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print("----->", BlockNameDialog.popup("XXX#"))
    print("----->", BlockNameDialog.popup("ZwE#09G10G"))
    print("----->", BlockNameDialog.popup("Hu#"))
    print("----->", BlockNameDialog.popup("NoSubject"))
