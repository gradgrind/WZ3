"""
ui/dialogs/dialog_room_choice.py

Last updated:  2023-03-05

Supporting "dialog" for the course editor – set workload/pay.


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

#TODO: help for handling work-groups?

if __name__ == "__main__":
    import sys, os

    this = sys.path[0]
    appdir = os.path.dirname(os.path.dirname(this))
    sys.path[0] = appdir
    basedir = os.path.dirname(appdir)
    from core.base import start
    start.setup(os.path.join(basedir, 'TESTDATA'))

#T = TRANSLATIONS("ui.dialogs.dialog_workload")

### +++++

from typing import Optional
from core.basic_data import (
    PAYMENT_FORMAT,
    PAYMENT_TAG_FORMAT,
    get_payment_weights,
    Workload,
)
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    ### QtGui:
    ### QtCore:
    QRegularExpressionValidator,
    ### other
    uic,
)

### -----

class WorkloadDialog(QDialog):
    @classmethod
    def popup(cls, start_value:dict, parent=None):
        d = cls(parent)
        return d.activate(start_value)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_workload.ui"), self)
        pb = self.buttonBox.button(QDialogButtonBox.StandardButton.Reset)
        pb.clicked.connect(self.reset)
        v = QRegularExpressionValidator(PAYMENT_FORMAT)
        self.workload.setValidator(v)
        self.factor_list = []
        for k, v in get_payment_weights():
            self.factor_list.append(k)
            self.pay_factor.addItem(f"{k} ({v})")
        v = QRegularExpressionValidator(PAYMENT_TAG_FORMAT)
        self.work_group.setValidator(v)

    def activate(self, start_value:dict) -> Optional[Workload]:
        """Open the dialog. The initial values are taken from <start_value>,
        which must contain the keys WORKLOAD, PAY_FACTOR, WORK_GROUP.
        The values are checked before showing the dialog.
        Return a <Workload> instance if the data is changed.
        """
        self.result = None
        self.val0 = Workload(**start_value)
        w = self.val0.WORKLOAD
        self.workload.setText(w)
        self.nlessons.setChecked(bool(w))
        if self.val0.isValid():
            try:
                i = self.factor_list.index(self.val0.PAY_FACTOR)
            except ValueError:
                raise Bug(f"Unknown PAY_FACTOR: {self.val0.PAY_FACTOR}")
        else:
            i = 0
        self.pay_factor.setCurrentIndex(i)
        self.work_group.setText(self.val0.WORK_GROUP)
        self.exec()
        return self.result

    def on_nlessons_toggled(self, state):
        if state:
            self.workload.setText("1")
        else:
            self.workload.setText("")
            self.work_group.setText("")

    def reset(self):
        """Return an "empty" value."""
        self.result = Workload("", "", "")
        super().accept()

    def accept(self):
        w = self.workload.text()
        wg = self.work_group.text()
        pf = self.factor_list[self.pay_factor.currentIndex()]
        r = Workload(w, pf, wg)
        if r.PAY_FACTOR == '!':
            return  # invalid data
        if r != self.val0:
            self.result = r
        super().accept()
        

# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print("----->", WorkloadDialog.popup(
        {"WORKLOAD": "", "PAY_FACTOR": "HuKl", "WORK_GROUP": ""}
    ))
    print("----->", WorkloadDialog.popup(
        {"WORKLOAD": "2", "PAY_FACTOR": "DpSt", "WORK_GROUP": ""}
    ))
    print("----->", WorkloadDialog.popup(
        {"WORKLOAD": "0,5", "PAY_FACTOR": "HuEp", "WORK_GROUP": "tag1"}
    ))
    print("----->", WorkloadDialog.popup(
        {"WORKLOAD": "Fred", "PAY_FACTOR": "HuEp", "WORK_GROUP": ""}
    ))
