"""
ui/dialogs/dialog_room_choice.py

Last updated:  2023-03-23

Supporting "dialog" for the course editor – select room(s).


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

T = TRANSLATIONS("ui.dialogs.dialog_room_choice")

### +++++

from core.basic_data import (
    get_rooms,
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

class RoomDialog(QDialog):
    @classmethod
    def popup(cls, start_value="", classroom=None, parent=None, pos=None):
        d = cls(parent)
        d.init()
        if pos:
            d.move(pos)
        return d.activate(start_value, classroom)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_room_choice.ui"), self)
        self.pb_reset = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Reset
        )
        self.pb_reset.clicked.connect(self.reset)
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )
# This would be an alternative to the built-in table search.
#        self.roomlist.installEventFilter(self)

    def on_roomlist_currentItemChanged(self, item):
        """If an item in the room list is selected on the second column,
        reselect it on the first column.
        This causes the built-in search feature to work as intended –
        i.e. on the first letter of the first column.
        """
        if item.column() > 0:
            self.roomlist.setCurrentCell(item.row(), 0)

    def accept(self):
        self.result = self.roomtext.text()
        super().accept()

    def reset(self):
        if self.value0:
            self.result = ""
        super().accept()

    def init(self):
        self.room2line = {}
        rooms = get_rooms()
        n = len(rooms)
        self.roomlist.setRowCount(n)
        for i in range(n):
            rid = rooms[i][0]
            self.room2line[rid] = i
            item = QTableWidgetItem(rid)
            self.roomlist.setItem(i, 0, item)
            item = QTableWidgetItem(rooms[i][1])
            self.roomlist.setItem(i, 1, item)

    def activate(self, start_value="", classroom=None):
        self.value0 = start_value
        self.result = None
        self.classroom = classroom
        if classroom:
            self.home.show()
        else:
            self.home.hide()
        self.set_choices(start_value)
        self.roomlist.selectRow(0)
        self.roomlist.setFocus()
        self.exec()
        return self.result

    def set_choices(self, text):
        if text.endswith("+"):
            extra = True
            text = text[:-1]
        else:
            extra = False
        rids = text.split("/")
        errors = []
        _choices = []
        for rid in rids:
            if not rid:
                continue
            e = self.checkroom(rid, _choices)
            if e:
                if len(errors) > 3:
                    errors.append("  ...")
                    break
                errors.append(e)
            else:
                _choices.append(rid)
        else:
            # Perform changes only if not too many errors
            self.choices = []
            self.roomchoice.setRowCount(0)
            if _choices:
                for rid in _choices:
                    self.add_valid_room_choice(rid)
                self.roomchoice.selectRow(0)
            self.extra.setCheckState(
                Qt.CheckState.Checked if extra else Qt.CheckState.Unchecked
            )
        if errors:
            elist = "\n".join(errors)
            REPORT("ERROR", f'{T["INVALID_ROOM_IDS"]}:\n{elist}')
        self.write_choices()

    def add_valid_room_choice(self, rid):
        """Append the room with given id to the choices table.
        This assumes that the validity of <rid> has already been checked!
        """
        self.choices.append(rid)
        if rid == "$":
            rid = self.classroom
        row = self.room2line[rid]
        at_row = self.roomchoice.rowCount()
        self.roomchoice.insertRow(at_row)
        self.roomchoice.setItem(at_row, 0, self.roomlist.item(row, 0).clone())
        self.roomchoice.setItem(at_row, 1, self.roomlist.item(row, 1).clone())

    def write_choices(self):
        """Write the rooms in <self.choices> to the text field.
        """
        text = "/".join(self.choices)
        if self.extra.isChecked():
            text += "+"
        self.roomtext.setText(text)
        self.pb_accept.setEnabled(text != self.value0)

    def checkroom(self, roomid, choice_list):
        """Check that the given room-id is valid.
        If there is a "classroom", "$" may be used as a short-form.
        A valid room-id is added to the list <self.choices>, <None> is returned.
        Otherwise an error message is returned (a string).
        """
        is_classroom = False
        if roomid == "$":
            if self.classroom:
                rid = self.classroom
                is_classroom = True
            else:
                return T["NO_CLASSROOM_DEFINED"]
        else:
            rid = roomid
            if rid == self.classroom:
                is_classroom = True
        if rid in choice_list or (is_classroom and "$" in choice_list):
            if is_classroom:
                return T["CLASSROOM_ALREADY_CHOSEN"]
            else:
                return f'{T["ROOM_ALREADY_CHOSEN"]}: "{rid}"'
        if rid in self.room2line:
            return None
        return f'{T["UNKNOWN_ROOM_ID"]}: "{rid}"'

    @Slot()
    def on_tb_add_clicked(self):
        row = self.roomlist.currentRow()
        riditem = self.roomlist.item(row, 0)
        self.add2choices(riditem.text())

    @Slot()
    def on_home_clicked(self):
        self.add2choices("$")

    def add2choices(self, roomid):
        e = self.checkroom(roomid, self.choices)
        if e:
            REPORT("ERROR", e)
            return
        self.add_valid_room_choice(roomid)
        self.write_choices()

    @Slot()
    def on_tb_bin_clicked(self):
        row = self.roomchoice.currentRow()
        if row >= 0:
            self.choices.pop(row)
            self.roomchoice.removeRow(row)
            self.write_choices()

    @Slot(int)
    def on_extra_stateChanged(self, state):
        self.write_choices()

    @Slot()
    def on_tb_up_clicked(self):
        row = self.roomchoice.currentRow()
        if row <= 0:
            return
        row1 = row - 1
        item = self.roomchoice.takeItem(row, 0)
        self.roomchoice.setItem(row, 0, self.roomchoice.takeItem(row1, 0))
        self.roomchoice.setItem(row1, 0, item)
        item = self.roomchoice.takeItem(row, 1)
        self.roomchoice.setItem(row, 1, self.roomchoice.takeItem(row1, 1))
        self.roomchoice.setItem(row1, 1, item)
        t = self.choices[row]
        self.choices[row] = self.choices[row1]
        self.choices[row1] = t
        self.write_choices()
        self.roomchoice.selectRow(row1)

    @Slot()
    def on_tb_down_clicked(self):
        row = self.roomchoice.currentRow()
        row1 = row + 1
        if row1 == len(self.choices):
            return
        item = self.roomchoice.takeItem(row, 0)
        self.roomchoice.setItem(row, 0, self.roomchoice.takeItem(row1, 0))
        self.roomchoice.setItem(row1, 0, item)
        item = self.roomchoice.takeItem(row, 1)
        self.roomchoice.setItem(row, 1, self.roomchoice.takeItem(row1, 1))
        self.roomchoice.setItem(row1, 1, item)
        t = self.choices[row]
        self.choices[row] = self.choices[row1]
        self.choices[row1] = t
        self.write_choices()
        self.roomchoice.selectRow(row1)

    '''#In view of the built-in search feature, this seems unnecessary.
    def eventFilter(self, obj: QTableWidget, event: QEvent) -> bool:
        """Implement a key search for the room list:
        Pressing an alphanumeric key will move the selection to the first
        matching room id. Only the starting character of the room id is
        considered.
        """
        if event.type() == QEvent.KeyPress:
            key = event.text()
            if key.isalnum():
                ilist = self.roomlist.findItems(
                    key,
                    Qt.MatchFlag.MatchStartsWith
                )
                if ilist:
                    self.roomlist.setCurrentItem(ilist[0])
                    self.roomlist.scrollToItem(
                        ilist[0],
                        QAbstractItemView.ScrollHint.PositionAtTop
                    )
                return True
        return False
    '''


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    widget = RoomDialog()
    widget.init()
    print("----->", widget.activate(start_value="$/Ph+", classroom="10G"))
    print("----->", widget.activate(start_value=""))
