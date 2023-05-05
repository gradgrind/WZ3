"""
ui/dialogs/dialog_choose_class.py

Last updated:  2023-05-05

"Dialog" for the choosing a class, especially for a pupil.


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

#T = TRANSLATIONS("ui.dialogs.dialog_choose_class")

### +++++

from core.basic_data import (
    get_classes,
)
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    QTableWidgetItem,
    ### QtGui:
    ### QtCore:
    Qt,
    Slot,
    ### other
    uic,
)

### -----

class ClassSelectDialog(QDialog):
    @classmethod
    def popup(cls, start_value="", pos=None, parent=None):
        d = cls(parent)
        d.init()
        if pos:
            d.move(pos)
        return d.activate(start_value)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_choose_class.ui"), self)
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )

    def on_class_table_currentItemChanged(self, item):
        """If an item in the class list is selected on the second column,
        reselect it on the first column.
        This causes the built-in search feature to work as intended –
        i.e. on the first letter of the first column.
        """
        if item.column() > 0:
            self.class_table.setCurrentCell(item.row(), 0)
        if (r := item.row()) != self.current_row:
            self.current_row = r
            self.value = item.text()
            self.pb_accept.setEnabled(self.value != self.value0)

    def accept(self):
        self.result = self.value
        super().accept()

    def init(self):
        self.class2line = {}
        classes = get_classes().get_class_list()
        n = len(classes)
        self.class_table.setRowCount(n)
        for i, c_n in enumerate(classes):
            cid, name = c_n
            self.class2line[cid] = i
            item = QTableWidgetItem(cid)
            self.class_table.setItem(i, 0, item)
            item = QTableWidgetItem(name)
            self.class_table.setItem(i, 1, item)

    def activate(self, start_value=""):
        self.value0 = start_value
        try:
            self.current_row = self.class2line[start_value]
        except KeyError:
            self.current_row = 0
        self.result = None
        self.class_table.setCurrentCell(self.current_row, 0)
        self.class_table.setFocus()
        self.exec()
        return self.result


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print("----->", ClassSelectDialog.popup("10G"))
