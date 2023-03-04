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

from typing import Optional
from core.basic_data import (
    TAG_FORMAT,
)
from core.db_access import (
    db_read_table, 
    db_read_unique,
    db_read_unique_entry,
)
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
        
    @Slot(str)
    def on_tag_currentTextChanged(self, text): # show courses
#        if self.disable_triggers:
#            return
        try:
            ref_list = self.tag_map[text]
        except KeyError:
            # no references
            return
        self.lesson_list.clear()
        for r in ref_list:
            lid = r[1]
            rlist = db_read_unique(
                "LESSONS", 
                ["lesson_group", "LENGTH", "TIME"], #? 
                id=lid,
            )
            lg_id, ll, lt = rlist
            rlist = db_read_unique(
                "LESSON_GROUP", 
                ["BLOCK_NAME"], #? 
                lesson_group=lg_id,
            )
            bname = rlist[0]
            if not bname:
                rlist = db_read_unique(
                    "COURSE_LESSONS", 
                    ["course"], #? 
                    lesson_group=lg_id,
                )
                course = rlist[0]
                cdata = db_read_unique(
                    "COURSE", 
                    ["CLASS", "GRP", "SUBJECT", "TEACHER"], #? 
                    course=course,
                )
                bname = f"{cdata[0]}.{cdata[1]}: {cdata[2]} / {cdata[3]}"
            self.lesson_list.addItem(bname)
                  
    def activate(self, start_value:str) -> str:
        """Open the dialog.
        """
        self.result = None
#        self.disable_triggers = True
        self.value0 = start_value
        ## Populate the tag chooser
        self.tag_map = {}
        f, records = db_read_table(
            "PARALLEL_LESSONS", 
            ["TAG", "id", "lesson_id", "WEIGHTING"]
        )
#TODO--  just for testing!
#        records = [
#            ("TAG2", 2, 1, 8),
#            ("TAG1", 3, 3, 5),
#            ("TAG1", 4, 8, 5),
#            ("TAG3", 5, 4, 6),
#        ]
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
