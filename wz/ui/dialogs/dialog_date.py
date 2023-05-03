"""
ui/dialogs/dialog_date.py

Last updated:  2023-05-03

Supporting "dialog" for editing dates.


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

#T = TRANSLATIONS("ui.dialogs.dialog_date")

### +++++

from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    ### QtGui:
    ### QtCore:
    QDate,
    Qt,
    ### other
    uic,
    Slot,
)

### -----

#TODO: Add range checks?

class DateDialog(QDialog):
    @classmethod
    def popup(cls, start_value="", parent=None, pos=None, null_ok=False):
        d = cls(parent)
        if pos:
            d.move(pos)
        return d.activate(start_value, null_ok)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_date.ui"), self)
        self.pb_reset = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Reset
        )
        self.pb_reset.clicked.connect(self.reset)
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )

    @Slot()
    def on_calendar_selectionChanged(self):
        if self.suppress_events:
            return
        self.new_date()

    def accept(self):
        self.result = self.value
        super().accept()

    def reset(self):
        self.result = ""
        super().accept()

    def activate(self, start_value, null_ok):
        self.value0 = start_value
        self.result = None
        self.suppress_events = True
        self.pb_reset.setVisible(bool(null_ok and start_value))
        self.calendar.setSelectedDate(
            QDate.fromString(start_value, Qt.DateFormat.ISODate)
            if start_value
            else QDate.currentDate()
        )
        self.new_date()
        self.suppress_events = False
        self.exec()
        return self.result

    def new_date(self):
        self.value = self.calendar.selectedDate().toString(
            Qt.DateFormat.ISODate
        )
        self.current_date.setText(self.value)
        self.pb_accept.setEnabled(self.value != self.value0)


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
#    from core.db_access import open_database
#    open_database()
    print("----->", DateDialog.popup())
    print("----->", DateDialog.popup("2023-05-12", null_ok=True))
