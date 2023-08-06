"""
ui/dialogs/dialog_workload.py

Last updated:  2023-07-10

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
from core.basic_data_3 import get_payment_weights
from core.db_access import Record, db_read_unique_field
from core.course_data_3a import lesson_pay_display
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
    def popup(cls, start_value:Record, parent=None):
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
            if k:
                self.factor_list.append(k)
                self.pay_factor.addItem(f"{k} ({v})")

    def activate(self, start_value:Record) -> Optional[str]:
        """Open the dialog. The initial values are taken from <start_value>.
        The value is checked before showing the dialog.
        Return a workload-tag  if the data is changed.
        """
        self.result = None
        n = start_value["PAY_NLESSONS"]
        t = start_value["PAY_TAG"]
        self.val0 = (n, t)
        text = lesson_pay_display(start_value)
        #print("???", repr(text), start_value)
        self.IN.setText(text)
        # Check initial value
        self.suppress_callbacks = True
        self.pb_reset.setVisible(bool(t))
        f = 1.0
        index = 0
        mode = 0
        if t:
            try:
                index = self.factor_list.index(t)
            except ValueError:
                pass
        elif text:
            f = float(text.replace(',', '.'))
            mode = 1
        self.toolBox.setCurrentIndex(mode)
        self.pay_factor.setCurrentIndex(index)
        self.payment.setValue(f)
        n0 = 1
        imp = False
        try:
            ni = int(n)
            if ni > 0:
                n0 = ni
            else:
                imp = True
        except ValueError:
            pass
        self.nlessons.setValue(n0)
        if imp:
            self.rb_implicit.setChecked(True)
            self.on_rb_explicit_toggled(False)
        else:
            self.rb_explicit.setChecked(True)
            self.on_rb_explicit_toggled(True)
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
                self.val = ("-1", pf)
            else:
                self.val = (self.nlessons.cleanText(), pf)
        elif i == 1:
            # simple number
            self.val = (self.payment.cleanText(), "")
        self.OUT.setText(lesson_pay_display(
            {"PAY_NLESSONS": self.val[0], "PAY_TAG": self.val[1]}
        ))
        #print("---", self.val)
        self.pb_accept.setEnabled(self.val != self.val0)

    def reset(self):
        """Return an "empty" value."""
        self.result = ("0", 0)
        super().accept()

    def accept(self):
        if self.val:
            pf = self.val[1]
            if pf:
                pfi = db_read_unique_field(
                    "PAY_FACTORS",
                    "Pay_factor_id",
                    PAY_TAG=pf
                )
            else:
                pfi = 0
            self.result = (self.val[0], pfi)
        super().accept()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database("wz_db.sqlite")
    print("----->", WorkloadDialog.popup({"PAY_NLESSONS": "0", "PAY_TAG": ""}))
    print("----->", WorkloadDialog.popup({"PAY_NLESSONS": "-1", "PAY_TAG": "HuKl"}))
    print("----->", WorkloadDialog.popup({"PAY_NLESSONS": "1,2", "PAY_TAG": ""}))
    print("----->", WorkloadDialog.popup({"PAY_NLESSONS": "1.23456", "PAY_TAG": ""}))
    print("----->", WorkloadDialog.popup({"PAY_NLESSONS": "2", "PAY_TAG": "HuEp"}))
    print("----->", WorkloadDialog.popup({"PAY_NLESSONS": "Fred", "PAY_TAG": "Jim"}))
