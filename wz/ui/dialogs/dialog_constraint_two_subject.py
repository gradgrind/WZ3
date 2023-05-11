"""
ui/dialogs/dialog_constraint_two_subject.py

Last updated:  2023-05-11

Supporting "dialog" – handle constraints between two subjects.


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

#T = TRANSLATIONS("ui.dialogs.dialog_constraint_two_subject")

### +++++

from typing import Optional
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    ### QtGui:
    ### QtCore:
    Slot,
    ### other
    uic,
)
from core.basic_data import get_subjects

### -----

# The data is stored in fields with permitted values sid1-sid2%w, where
# sid1 and sid2 are the subject ids and w is the weight:
#    -, 1, 2, 3, ... 9, +
# The intended meaning is that if w = '-' there is no constraint, while
# w = '+' implies compulsory constraint. The numbers would be intermediate
# weights, but may not be supported in some systems.
# Although weight '-' doesn't do anything, it is permitted so that a
# constraint can be (temporarily) disabled.

class TwoSubjectConstraintDialog(QDialog):
    @classmethod
    def popup(
        cls,
        start_value,
        label=None,
        parent=None,
        pos=None
    ):
        d = cls(parent)
        d.init(label)
        return d.activate(start_value)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_constraint_two_subject.ui"), self)
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )

    def init(self, label):
        if label:
            if label[-1] == "!":
                label = f'<p style="color:#d50000;">{label}</p>'
            self.label.setText(label)
            self.label.show()
        else:
            self.label.hide()
        self.disable_triggers = True
        self.subjects = get_subjects()
        for k, v in self.subjects:
            self.subject_1.addItem(v)
            self.subject_2.addItem(v)
        self.disable_triggers = False

    @Slot(int)
    def on_subject_1_currentIndexChanged(self, i):
        if self.disable_triggers:
            return
        self.value_changed()
        
    @Slot(int)
    def on_subject_2_currentIndexChanged(self, i):
        if self.disable_triggers:
            return
        self.value_changed()
        
    @Slot(str)
    def on_weight_currentTextChanged(self, i):
        if self.disable_triggers:
            return
        self.value_changed()

    def value_changed(self):
        i1 = self.subject_1.currentIndex()
        i2 = self.subject_2.currentIndex()
        w = self.weight.currentText()
        if i1 and i2 and i1 != i2:
            self.value = f"{self.subjects[i1][0]}-{self.subjects[i2][0]}%{w}"
            self.pb_accept.setEnabled(self.value != self.value0)
        else:
            self.pb_accept.setEnabled(False) 

    def activate(self, start_value:str) -> Optional[str]:
        """Open the dialog.
        """
        self.result = None
        self.disable_triggers = True
        self.value0 = start_value
        try:
            ss, w = start_value.split('%', 1)
            s1, s2 = ss.split("-", 1)
            i1 = self.subjects.index(s1)
            i2 = self.subjects.index(s2)
            if ( iw := self.weight.findText(w)) < 0:
                raise ValueError
            self.value = start_value
        except ValueError:
            if start_value:
                REPORT(
                    "ERROR",
                    f"Bug: two-subject constraint = \"{start_value}\""
                )
            # No initial value
            self.value = ""
            i1, i2 = 0, 0
            iw = self.weight.count() - 1
        self.weight.setCurrentIndex(iw)
        self.subject_1.setCurrentIndex(i1)
        self.subject_2.setCurrentIndex(i2)
        self.pb_accept.setEnabled(False)
        self.disable_triggers = False
        self.exec()
        return self.result

    def accept(self):
        self.result = self.value
        super().accept()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print("----->", TwoSubjectConstraintDialog.popup(
        "",
        "Relationship between two subjects!"
    ))
    print("----->", TwoSubjectConstraintDialog.popup(("Sp-Eu%5")))
    print("----->", TwoSubjectConstraintDialog.popup(("En-Fr")))
