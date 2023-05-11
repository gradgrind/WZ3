"""
ui/dialogs/dialog_constraint_check_list.py

Last updated:  2023-05-11

Supporting "dialog" – select constraint items from a
list (hidden-key / value).


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

#T = TRANSLATIONS("ui.dialogs.dialog_check_list")

### +++++

from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    QListWidgetItem,
    ### QtGui:
    ### QtCore:
    Qt,
    ### other
    uic,
    Slot,
)

### -----


class CheckListDialog(QDialog):
    @classmethod
    def popup(cls,
        start_value,
        items,
        label=None,
        empty_ok=True,
        parent=None,
        pos=None
    ):
        d = cls(parent)
        d.init(label, items, empty_ok)
        if pos:
            d.move(pos)
        return d.activate(start_value)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_constraint_check_list.ui"), self)
        self.pb_reset = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Reset
        )
        self.pb_reset.clicked.connect(self.reset)
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )
        self.item_list.setSpacing(5)

    def accept(self):
        self.result = self.value
        super().accept()

    def reset(self):
        self.result = ""
        super().accept()

    def init(self, label, items, empty_ok):
        if label:
            if label[-1] == "!":
                label = f'<p style="color:#d50000;">{label}</p>'
            self.label.setText(label)
            self.label.show()
        else:
            self.label.hide()
        self.empty_ok = empty_ok
        self.item_pairs = items
        self.item_list.clear()
        for k, v in items:
            self.item_list.addItem(v)

    def activate(self, start_value):
        self.result = None
        self.disable_triggers = True
        self.pb_reset.setVisible(self.empty_ok and bool(start_value))
        self.value0 = start_value
        self.value = start_value
        try:
            v, w = start_value.split('%', 1)
            self.weight.setCurrentText(w)
            iset = set(v.split(','))
        except ValueError:
            if start_value:
                REPORT(
                    "ERROR",
                    f"Bug: check-list constraint = \"{start_value}\""
                )
            self.value = ""
            self.weight.setCurrentIndex(-1)
            iset = set()
        for i, kv in enumerate(self.item_pairs):
            lwitem = self.item_list.item(i)
            try:
                iset.remove(kv[0])
            except KeyError:
                lwitem.setCheckState(Qt.CheckState.Unchecked)
                continue
            lwitem.setCheckState(Qt.CheckState.Checked)
        self.acceptable()
        self.disable_triggers = False
        self.exec()
        return self.result

    @Slot(QListWidgetItem)
    def on_item_list_itemChanged(self, i):
        if self.disable_triggers:
            return
        # print("§CHANGED")
        self.acceptable()

    @Slot(str)
    def on_weight_currentTextChanged(self, text):
        if self.disable_triggers:
            return
        # print("§WEIGHT")
        self.acceptable()

    def acceptable(self):
        w = self.weight.currentText()
        if not w:
            self.pb_accept.setEnabled(False)
            return
        v = []
        for i, kv in enumerate(self.item_pairs):
            lwitem = self.item_list.item(i)
            if lwitem.checkState() == Qt.CheckState.Checked:
                v.append(kv[0])
        if not v:
            self.pb_accept.setEnabled(False)
            return
        self.value = f"{','.join(v)}%{w}"
        self.pb_accept.setEnabled(self.value != self.value0)


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()

    print("----->", CheckListDialog.popup(
        "",
        [("1", "one"), ("2", "two"), ("3", "three")],
    ))
    print("----->", CheckListDialog.popup(
        "1,2%6",
        [("1", "one"), ("2", "two"), ("3", "three")],
    ))
    print("----->", CheckListDialog.popup(
        "1,3",
        [("1", "one"), ("2", "two"), ("3", "three")],
        label="Choose some!",
        empty_ok=True,
    ))
