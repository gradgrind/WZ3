"""
ui/dialogs/dialog_choose_one_item_pair.py

Last updated:  2023-05-10

Supporting "dialog" – select an item from a list of tag-description pairs.


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

T = TRANSLATIONS("ui.dialogs.dialog_choose_one_item_pair")

### +++++

from typing import Optional
from core.basic_data import get_rooms
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    QTableWidgetItem,
    QHeaderView,
    ### QtGui:
    ### QtCore:
    Slot,
    ### other
    uic,
)

### -----

class ChooseOneItemDialog(QDialog):
    @classmethod
    def popup(
        cls,
        items,
        start_value,
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
        uic.loadUi(APPDATAPATH("ui/dialog_choose_one_item_pair.ui"), self)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )
        self.pb_reset = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Reset
        )
        self.pb_reset.clicked.connect(self.reset)

    def init(self, label, items, empty_ok):
        if label:
            if label[-1] == "!":
                label = f'<p style="color:#d50000;">{label}</p>'
            self.label.setText(label)
            self.label.show()
        else:
            self.label.hide()
        self.empty_ok = empty_ok
        self.item_list = items
        self.table.setRowCount(len(items))
        for i, kv in enumerate(items):
            k, v = kv
            twitem = self.table.item(i, 0)
            if not twitem:
                twitem = QTableWidgetItem()
                self.table.setItem(i, 0, twitem)
            twitem.setText(k)
            twitem = self.table.item(i, 1)
            if not twitem:
                twitem = QTableWidgetItem()
                self.table.setItem(i, 1, twitem)
            twitem.setText(v)

    @Slot(int,int,int,int)
    def on_table_currentCellChanged(
        self,
        currentRow,
        currentColumn,
        previousRow,
        previousColumn
    ):
        # print("SELECT:", currentRow)
        self.value = self.item_list[currentRow][0]
        self.pb_accept.setEnabled(self.value != self.value0)

    def activate(self, start_value:str) -> Optional[str]:
        """Open the dialog.
        """
        self.result = None
        self.value0 = start_value
        self.value = start_value
        self.pb_reset.setVisible(self.empty_ok and bool(start_value))
        self.table.setCurrentCell(-1, 0)
        if start_value:
            for row, kv in enumerate(self.item_list):
                if kv[0] == start_value:
                    self.table.setCurrentCell(row, 0)
                    break
            else:
                REPORT("ERROR", T["UNKNOWN_KEY"].format(id=start_value))
                self.value = "!!!"
                self.pb_accept.setEnabled(False)
        else:
            self.pb_accept.setEnabled(False)
        self.exec()
        return self.result

    def accept(self):
        self.result = self.value
        super().accept()

    def reset(self):
        self.result = ""
        super().accept()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print("----->", ChooseOneItemDialog.popup(
        [("1", "one"), ("2", "two"), ("3", "three")],
        "",
        label="Choose just one!",
        empty_ok=True,
    ))
    print("----->", ChooseOneItemDialog.popup(
        [("1", "one"), ("2", "two"), ("3", "three")],
        "5",
        label="Choose one",
        empty_ok=True,
    ))
    print("----->", ChooseOneItemDialog.popup(
        get_rooms(),
        "13",
        empty_ok=False,
    ))
