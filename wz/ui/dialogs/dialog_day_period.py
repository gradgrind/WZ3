"""
ui/dialogs/dialog_day_period.py

Last updated:  2023-03-23

Supporting "dialog" for the course editor – select day & period.


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

#T = TRANSLATIONS("ui.dialogs.dialog_day_period")

### +++++

from core.basic_data import (
    get_days,
    get_periods,
    timeslot2index,
    index2timeslot,
)
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    ### QtGui:
    ### QtCore:
    ### other
    uic,
)

### -----

class DayPeriodDialog(QDialog):
    @classmethod
    def popup(cls, start_value="", parent=None, pos=None):
        d = cls(parent)
        d.init()
        if pos:
            d.move(pos)
        return d.activate(start_value)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_day_period.ui"), self)
        self.pb_reset = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Reset
        )
        self.pb_reset.clicked.connect(self.reset)
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )

    def accept(self):
        self.result = index2timeslot(
            (self.daylist.currentRow(), self.periodlist.currentRow())
        )
        super().accept()

    def reset(self):
        self.result = ""
        super().accept()

    def init(self):
        self.daylist.clear()
        self.daylist.addItems([d[1] for d in get_days()])
        self.periodlist.clear()
        self.periodlist.addItems([p[1] for p in get_periods()])

    def activate(self, start_value):
        self.result = None
        self.suppress_events = True
        self.pb_reset.setVisible(bool(start_value))
        try:
            d, p = timeslot2index(start_value)
            self.dp0 = (d, p)
            if d < 0:
                d, p = 0, 0
        except ValueError as e:
            REPORT("ERROR", str(e))
            self.dp0 = (-1, -1)
            d, p = 0, 0
        self.daylist.setCurrentRow(d)
        self.periodlist.setCurrentRow(p)
        self.acceptable()
        self.suppress_events = False
        self.exec()
        return self.result

    def on_daylist_currentRowChanged(self, i):
        self.acceptable()

    def on_periodlist_currentRowChanged(self, i):
        self.acceptable()

    def acceptable(self):
        dp = (self.daylist.currentRow(), self.periodlist.currentRow())
        self.pb_accept.setEnabled(dp != self.dp0)


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print("----->", DayPeriodDialog.popup())
    print("----->", DayPeriodDialog.popup("Di.4"))
    print("----->", DayPeriodDialog.popup("Di.9"))
