"""
ui/dialogs/dialog_day_period.py

Last updated:  2023-03-12

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

T = TRANSLATIONS("ui.dialogs.dialog_day_period")

### +++++

from core.db_access import (
    db_values, db_update_field
)
from core.basic_data import (
    get_days,
    get_periods,
    timeslot2index,
    index2timeslot,
    get_simultaneous_weighting,
)
from ui.ui_base import (
    ### QtWidgets:
    APP,
    QDialog,
    QDialogButtonBox,
    ### QtGui:
    ### QtCore:
    Qt,
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
        pb = self.buttonBox.button(QDialogButtonBox.StandardButton.Reset)
        pb.clicked.connect(self.reset)

    def accept(self):
        if self.fixed_time.isChecked():
            self.result = index2timeslot(
                (self.daylist.currentRow(), self.periodlist.currentRow())
            )
        else:
            self.result = self.simultaneous_tag.currentText()
            if self.result:
                if '.' in self.result or '@' in self.result:
                    REPORT("WARNING", T["TAG_WITH_DOT_OR_AT"])
                    return
                self.result += f"@{self.weighting.value()}"
        super().accept()

    def reset(self):
        self.result = ""
        super().accept()

    def on_fixed_time_stateChanged(self, state):
        print("§FIXED TIME:", state)
        if state == Qt.CheckState.Unchecked:
            self.daylist.setEnabled(False)
            self.periodlist.setEnabled(False)
            self.simultaneous_tag.setEnabled(True)
            self.weighting.setEnabled(True)
        else:
            self.daylist.setEnabled(True)
            self.periodlist.setEnabled(True)
            self.simultaneous_tag.setEnabled(False)
            self.simultaneous_tag.setCurrentIndex(-1)
            self.weighting.setEnabled(False)
            if self.daylist.currentRow() < 0:
                self.daylist.setCurrentRow(0)
                self.periodlist.setCurrentRow(0)

    def init(self):
        self.daylist.clear()
        self.daylist.addItems([d[1] for d in get_days()])
        self.periodlist.clear()
        self.periodlist.addItems([p[1] for p in get_periods()])

    def activate(self, start_value=None):
        self.result = None
        try:
            d, p = timeslot2index(start_value)
            fixed = True
            if d < 0:
                d, p = 0, 0
        except ValueError as e:
            if '.' in start_value:
                REPORT("ERROR", str(e))
                d, p, fixed = 0, 0, True
            else:
                # <start_value> is a "simultaneous" tag
                d, p, fixed = -1, -1, False
        self.daylist.setCurrentRow(d)
        self.periodlist.setCurrentRow(p)
        # Enter "simultaneous" tags into combobox
        self.simultaneous_tag.clear()
        self.simultaneous_tag.addItems(
            db_values("PARALLEL_LESSONS", "TAG", sort_field="TAG")
        )
        # Toggle "fixed" flag to ensure callback activated
        self.fixed_time.setChecked(not fixed)
        self.fixed_time.setChecked(fixed)
        if (not fixed) and start_value:
            # If the tag has a weighting, strip this off (the weighting
            # field will be fetched by callback <select_simultaneous_tag>)
            self.simultaneous_tag.setCurrentText(
                start_value.split('@', 1)[0]
            )
        self.exec()
        return self.result

    def on_simultaneous_tag_currentTextChanged(self, tag):
        self.weighting.setValue(get_simultaneous_weighting(tag))


# Used by course/lesson editor
def edit_time(lesson):
    """Pop up a lesson-time choice dialog for the current lesson.
    If the time is changed, update the database entry and return the
    new value.
    Otherwise return <None>.
    The parameter is the <dict> containing the fields of the LESSON record.
    """
    result = DayPeriodDialog.popup(
        start_value=lesson["TIME"],
        parent=APP.activeWindow()
    )
    if result is not None:
        db_update_field(
            "LESSONS",
            "TIME",
            result,
            id=lesson["id"]
        )
        lesson["TIME"] = result
    return result


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    widget = DayPeriodDialog()
    widget.init()
    print("----->", widget.activate(""))
    print("----->", widget.activate("Di.4"))
    print("----->", widget.activate("Di.9"))
