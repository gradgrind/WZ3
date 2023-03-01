"""
ui/dialogs/dialog_room_choice.py

Last updated:  2023-03-01

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

T = TRANSLATIONS("ui.dialogs.dialog_workload")

### +++++

from core.basic_data import (
    PAYMENT_FORMAT,
    PAYMENT_TAG_FORMAT,
    get_payment_weights,
    read_payment,
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
    def popup(cls, start_value=""):
        d = cls()
        return d.activate(start_value)

    def __init__(self):
        super().__init__()
        uic.loadUi(APPDATAPATH("ui/dialog_workload.ui"), self)
        pb = self.buttonBox.button(QDialogButtonBox.StandardButton.Reset)
        pb.clicked.connect(self.reset)
        v = QRegularExpressionValidator(PAYMENT_FORMAT)
        self.workload.setValidator(v)
        self.factor_list = (
            [("--", "0")]
            + [(k, f"{k} ({v})") for k, v in get_payment_weights()]
        )
        self.pay_factor.addItems(f[0] for f in self.factor_list)
        v = QRegularExpressionValidator(PAYMENT_TAG_FORMAT)
        self.partner.setValidator(v)

        return

#        form = QFormLayout(self)
        self.number = QLineEdit()
        form.addRow(T["NUMBER"], self.number)
        v = QRegularExpressionValidator(PAYMENT_FORMAT)
        self.number.setValidator(v)
        self.factor = KeySelector()
        form.addRow(T["FACTOR"], self.factor)
        self.factor.set_items(
            [("--", "0")]
            + [(k, f"{k} ({v})") for k, v in get_payment_weights()]
        )
        self.ptag = QLineEdit()
        form.addRow(T["PARALLEL_TAG"], self.ptag)
        v = QRegularExpressionValidator(PAYMENT_TAG_FORMAT)
        self.ptag.setValidator(v)
        form.addRow(HLine())
        buttonBox = QDialogButtonBox()
        form.addRow(buttonBox)
        bt_save = buttonBox.addButton(QDialogButtonBox.StandardButton.Save)
        bt_cancel = buttonBox.addButton(QDialogButtonBox.StandardButton.Cancel)
        bt_clear = buttonBox.addButton(QDialogButtonBox.StandardButton.Discard)
        bt_clear.setText(T["Clear"])
        bt_save.clicked.connect(self.do_accept)
        bt_cancel.clicked.connect(self.reject)
        bt_clear.clicked.connect(self.do_clear)

    def reset(self):
        print("§RESET")

    def do_accept(self):
        n = self.number.text()
        f = self.factor.selected()
        t = self.ptag.text()
        if f == "--":
            if n or t:
                SHOW_ERROR(T["NULL_FACTOR_NOT_CLEAN"])
                return
            text = ""
        else:
            if t:
                if not n:
                    SHOW_ERROR(T["PAYTAG_WITH_NO_NUMBER"])
                    return
                t = "/" + t
            text = n + "*" + f + t
            try:
                # Check final value
                read_payment(text)
            except ValueError as e:
                SHOW_ERROR(str(e))
                return
        if text != self.text0:
            self.result = text
        self.accept()

    def do_clear(self):
        if self.text0:
            self.result = ""
        self.accept()

    def activate(self, start_value=""):
        self.result = None
        self.text0 = start_value
        try:
#TODO:
            pdata = read_payment(start_value)
            if pdata.isNone():
                self.workload.setText("")
                self.pay_factor.setCurrentIndex(0)
                self.partner.setText("")
            else:
                if pdata.tag and not pdata.number:
#?
                    SHOW_ERROR(T["PAYTAG_WITH_NO_NUMBER"])
                    self.partner.setText("")
                else:
                    self.partner.setText(pdata.tag)
                self.workload.setText(pdata.number)
                for i, kv in enumerate(self.factor_list):
                    if kv[0] == pdata.factor:
                        self.pay_factor.setCurrentIndex(i)
                        break
                else:
#TODO: T ...
                    raise ValueError(f"UNKNOWN_PAY_FACTOR: {pdata.factor}")
        except ValueError as e:
            REPORT("ERROR", str(e))
            self.workload.setText("1")
            self.pay_factor.setCurrentIndex(1)
            self.partner.setText("")
        self.exec()
        return self.result


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    widget = WorkloadDialog()
    print("----->", widget.activate(start_value="2*HuEp"))
    print("----->", widget.activate(start_value=""))
    print("----->", PaymentDialog.popup(start_value="0,5*HuEp/tag1"))
    print("----->", widget.activate(start_value="Fred*HuEp"))
