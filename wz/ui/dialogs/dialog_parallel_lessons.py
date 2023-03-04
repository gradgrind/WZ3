"""
ui/dialogs/dialog_parallel_lessons.py

Last updated:  2023-03-04

Supporting "dialog" for the course editor – handle wishes for lessons
starting at the same time.


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

#T = TRANSLATIONS("ui.dialogs.dialog_parallel_lessons")

### +++++

#TODO ...

from typing import Optional
from core.basic_data import (
    TAG_FORMAT,
)
from core.db_access import db_read_table, db_read_unique_entry
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    ### QtGui:
    ### QtCore:
    Qt,
    QRegularExpressionValidator,
    Slot,
    ### other
    uic,
)

### -----

# The data is stored in the db table PARALLEL_LESSONS, with fields
#   (id: primary key)
#   lesson_id: foreign key -> LESSONS.id (unique, non-null)
#   TAG: The tag used to join a group of lessons
#   WEIGHTING: 0 – 10 (empty is like 0?)

#TODO ...
class ParallelsDialog(QDialog):
    @classmethod
    def popup(cls, start_value):
        d = cls()
        return d.activate(start_value)

    def __init__(self):
        super().__init__()
        uic.loadUi(APPDATAPATH("ui/dialog_parallel_lessons.ui"), self)
        pb = self.buttonBox.button(QDialogButtonBox.StandardButton.Reset)
        pb.clicked.connect(self.reset)
        
        
#        self.pb_accept = self.buttonBox.button(
#            QDialogButtonBox.StandardButton.Ok
#        )
        validator = QRegularExpressionValidator(TAG_FORMAT)
        self.tag.setValidator(validator)

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
    def on_tag_currentTextChanged(self, text): # show courses
#        if self.disable_triggers:
#            return
        print("§TAG changed:", text)
#TODO

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
                  
    def activate(self, start_value:str) -> str:
        """Open the dialog.
        """
        self.result = None
        self.disable_triggers = True
        self.value0 = start_value
        ## Populate the tag chooser
        self.tag_map = {}
        f, records = db_read_table(
            "PARALLEL_LESSONS", 
            ["TAG", "id", "lesson_id", "WEIGHTING"]
        )
#TODO--  just for testing!
        records = [
            ("TAG2", 2, 1, 8),
            ("TAG1", 3, 3, 5),
            ("TAG1", 4, 8, 5),
            ("TAG3", 5, 4, 6),
        ]
        for r in records:
            tag = r[0]
            data = r[1:]
            try:
                self.tag_map[tag].append(data)
            except KeyError:
                self.tag_map[tag] = [data]
        self.tag.clear()
        self.tag.addItems(sorted(self.tag_map))
        self.tag.setCurrentText(start_value)
        
        self.exec()
        return self.result

#???
        self.tag.clear()
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
        self.result = ""
        super().accept()

    def accept(self):
        t = self.tag.currentText()
        if t and t != self.value0:
            self.result = t
        super().accept()
        

# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print("----->", ParallelsDialog.popup(""))
    print("----->", ParallelsDialog.popup("TAG1"))
