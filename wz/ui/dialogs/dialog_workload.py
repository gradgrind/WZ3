"""
ui/dialogs/dialog_workload.py

Last updated:  2023-03-27

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
    get_payment_weights,
    Workload,
)
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    ### QtGui:
    ### QtCore:
    ### other
    uic,
    Slot,
)

### -----

class WorkloadDialog(QDialog):
    @classmethod
    def popup(cls, start_value:dict, parent=None):
        d = cls(parent)
        return d.activate(start_value)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.val0 = None
        self.suppress_callbacks = True
        uic.loadUi(APPDATAPATH("ui/dialog_workload.ui"), self)
        self.pb_reset = self.buttonBox.button(QDialogButtonBox.StandardButton.Reset)
        self.pb_reset.clicked.connect(self.reset)
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )
        self.factor_list = []
        for k, v in get_payment_weights():
            self.factor_list.append(k)
            self.pay_factor.addItem(f"{k} ({v})")

    def activate(self, start_value:str) -> Optional[str]:
        """Open the dialog. The initial values are taken from <start_value>.
        The value is checked before showing the dialog.
        Return a workload-tag  if the data is changed.
        """
        self.result = None
        self.suppress_events = True
        self.val0 = start_value
        self.IN.setText(start_value)
        self.pb_reset.setVisible(bool(self.val0))
        # Check and decode initial value
        w0 = Workload.build(start_value)
        self.suppress_callbacks = True
        if w0.PAY_FACTOR_TAG:
            self.pay_factor.setCurrentIndex(
                get_payment_weights().index(w0.PAY_FACTOR_TAG)
            )
        else:
            self.pay_factor.setCurrentIndex(0)
        if w0.NLESSONS > 0:
            self.nlessons.setValue(w0.NLESSONS)
        else:
            self.nlessons.setValue(1)
        if w0.PAYMENT > 0.0:
            self.payment.setValue(w0.PAYMENT)
        else:
            self.payment.setValue(1.0)
        if w0.NLESSONS <= 0:
            self.rb_implicit.setChecked(True)
            self.on_rb_explicit_toggled(False)
        else:
            self.rb_explicit.setChecked(True)
            self.on_rb_explicit_toggled(True)
        if w0.NLESSONS == 0 and w0.PAYMENT > 0.0:
            # Plain number
            self.toolBox.setCurrentIndex(1)
        else:
            # Also if no start value, begin with factor option
            self.toolBox.setCurrentIndex(0)
        self.suppress_callbacks = False
        self.update_val()
        self.exec()
        return self.result

    @Slot(bool)
    def on_rb_explicit_toggled(self, on):
        self.stackedWidget.setCurrentIndex(0 if on else 1)
        self.update_val()

    @Slot(int)
    def on_toolBox_currentChanged(self, i):
        self.update_val()

    @Slot(int)
    def on_nlessons_valueChanged(self, i):
        self.update_val()

    @Slot(float)
    def on_payment_valueChanged(self, f):
        self.update_val()

    @Slot(int)
    def on_pay_factor_currentIndexChanged(self, i):
        self.update_val()

    def update_val(self):
        if self.suppress_callbacks:
            return
        i = self.toolBox.currentIndex()
        assert(i >= 0)
        if i == 0:
            # with factor
            pfi = self.pay_factor.currentIndex()
            assert(pfi >= 0)
            pf = self.factor_list[pfi]
            if self.rb_implicit.isChecked():
                self.val = f".*{pf}"
            else:
                self.val = f"{self.nlessons.cleanText()}*{pf}"
        elif i == 1:
            # simple number
            self.val = self.payment.cleanText()
        self.OUT.setText(self.val)
        self.pb_accept.setEnabled(self.val != self.val0)

    def reset(self):
        """Return an "empty" value."""
        self.result = ""
        super().accept()

    def accept(self):
        self.result = self.val
        super().accept()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print("----->", WorkloadDialog.popup(""))
    print("----->", WorkloadDialog.popup(".*HuKl"))
    print("----->", WorkloadDialog.popup("1,2"))
    print("----->", WorkloadDialog.popup("1.23456"))
    print("----->", WorkloadDialog.popup("1*HuEp"))
    print("----->", WorkloadDialog.popup("Fred"))
