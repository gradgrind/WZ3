"""
ui/dialogs/dialog_number_constraint.py

Last updated:  2023-03-20

Supporting "dialog" for the course editor – handle constraints where
a number of lesson periods is to be specified.


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

#T = TRANSLATIONS("ui.dialogs.dialog_number_constraint")

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

### -----

# The data is stored in fields with permitted values n%w, where
#   n is an integer from 0 to 9 (?) and
#   w is the weight: -, 1, 2, 3, ... 9, +
# Such a field may also be empty, indicating no constraint (if the
# weight is '-', that also corresponds to "no constraint").

class NumberConstraintDialog(QDialog):
    @classmethod
    def popup(cls, start_value, parent=None):
        d = cls(parent)
        return d.activate(start_value)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_number_constraint.ui"), self)
        self.pb_reset = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Reset
        )
        self.pb_reset.clicked.connect(self.reset)
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )

    @Slot(str)
    def on_number_currentTextChanged(self, text):
        if self.disable_triggers:
            return
        if self.value:
            self.value_changed()
        else:
            self.weight.setCurrentText('+')

    @Slot(str)
    def on_weight_currentTextChanged(self, i):
        if self.disable_triggers:
            return
        self.value_changed()

    def value_changed(self):
        t = self.number.currentText()
        w = self.weight.currentText()
        if t and w:
            self.value = f"{t}%{w}"
            self.pb_accept.setEnabled(self.value != self.value0)
        else:
            self.pb_accept.setEnabled(False) 

    def activate(self, start_value:str) -> Optional[str]:
        """Open the dialog.
        """
        self.result = None
        self.disable_triggers = True
        self.value0 = start_value
        if start_value:
            try:
                n, w = start_value.split('%', 1)
                ni = self.number.findText(n)
                wi = self.weight.findText(w)
                if ni < 0 or wi < 0:
                    raise ValueError
                self.value = start_value
            except ValueError:
                REPORT("ERROR", f"Bug: number constraint = „{start_value}“")
                ni = -1
                wi = -1
                self.value = ""
        else:
            self.pb_reset.hide()
            ni = -1
            wi = -1
            self.value = ""
        self.weight.setCurrentIndex(wi)
        self.number.setCurrentIndex(ni)
        self.pb_accept.setEnabled(False)
        self.disable_triggers = False
        self.exec()
        return self.result

    def reset(self):
        self.result = ""
        super().accept()

    def accept(self):
        self.result = self.value
        super().accept()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print("----->", NumberConstraintDialog.popup(""))
    print("----->", NumberConstraintDialog.popup(("3%5")))
    print("----->", NumberConstraintDialog.popup(("3")))