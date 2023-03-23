"""
ui/dialogs/dialog_choose_one_room.py

Last updated:  2023-03-23

Supporting "dialog" for the class-data editor – select a room as the
classroom of the current class.


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

#T = TRANSLATIONS("ui.dialogs.dialog_choose_one_room")

### +++++

from typing import Optional
from core.basic_data import get_rooms
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    QTableWidgetItem,
    ### QtGui:
    ### QtCore:
    Slot,
    ### other
    uic,
)

### -----

class ChooseOneRoomDialog(QDialog):
    @classmethod
    def popup(cls, start_value, parent=None):
        d = cls(parent)
        d.init()
        return d.activate(start_value)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_choose_one_room.ui"), self)
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )
        self.pb_reset = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Reset
        )
        self.pb_reset.clicked.connect(self.reset)

    def init(self):
        self.rooms = get_rooms()
        n = len(self.rooms)
        self.room_table.setRowCount(n)
        for i in range(n):
            rid, rname = self.rooms[i]
            item = self.room_table.item(i, 0)
            if not item:
                item = QTableWidgetItem()
                self.room_table.setItem(i, 0, item)
            item.setText(rid)
            item = self.room_table.item(i, 1)
            if not item:
                item = QTableWidgetItem()
                self.room_table.setItem(i, 1, item)
            item.setText(rname)

    @Slot(int,int,int,int)
    def on_room_table_currentCellChanged(
        self,
        currentRow,
        currentColumn,
        previousRow,
        previousColumn
    ):
        print("SELECT:", currentRow)
        self.room = self.rooms[currentRow][0]
        self.pb_accept.setEnabled(self.room != self.room0)

    def activate(self, start_value:str) -> Optional[str]:
        """Open the dialog.
        """
        self.result = None
        self.room0 = start_value
        self.pb_reset.setVisible(bool(start_value))
        try:
            row = self.rooms.index(start_value)
        except KeyError:
#TODO
            REPORT("ERROR", "Invalid room: '{room}'".format(room=start_value))
            row = -1
            self.room = ""
#TODO row-changed signal not occurring!
        self.room_table.setCurrentCell(row, 0)

        self.exec()
        return self.result

    def accept(self):
        self.result = self.room
        super().accept()

    def reset(self):
        self.result = ""
        super().accept()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print("----->", ChooseOneRoomDialog.popup(""))
    print("----->", ChooseOneRoomDialog.popup("Ph"))
    print("----->", ChooseOneRoomDialog.popup("??"))
