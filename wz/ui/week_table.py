"""
ui/week_table.py

Last updated:  2023-03-19

A manager for the weekly availability tables.


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

T = TRANSLATIONS("ui.modules.teacher_editor")

### +++++

from core.db_access import (
    db_key_value_list,
)
from ui.ui_base import (
    ### QtWidgets:
    QHeaderView,
)

### -----

class WeekTable:
    """Manager for the week-table, an EdiTableWidget.
    """
    def __init__(self, table, field, modified):
        self.__table = table
        self.__table.set_align_centre()
        self.__table.setStyleSheet(
            """QTableView {
               selection-background-color: #e0e0ff;
               selection-color: black;
            }
            QTableView::item:focus {
                selection-background-color: #d0ffff;
            }
            """
        )
        self.__modified = modified
        self.__field = field

    def setup(self):
        tt_days = db_key_value_list("TT_DAYS", "N", "NAME", "N")
        tt_periods = db_key_value_list("TT_PERIODS", "N", "TAG", "N")
        self.__table.setup(
            colheaders=[p[1] for p in tt_periods],
            rowheaders=[d[1] for d in tt_days],
            undo_redo=False,
            cut=False,
            paste=True,
            row_add_del=False,
            column_add_del=False,
            on_changed=self.table_changed,
        )
        Hhd = self.__table.horizontalHeader()
        Hhd.setMinimumSectionSize(20)
        self.__table.resizeColumnsToContents()
        # A rather messy attempt to find an appropriate size for the table
        Vhd = self.__table.verticalHeader()
        Hw = Hhd.length()
        Hh = Hhd.sizeHint().height()
        Vw = Vhd.sizeHint().width()
        Vh = Vhd.length()
        self.__table.setMinimumWidth(Hw + Vw + 10)
        self.__table.setFixedHeight(Vh + Hh + 10)
        # self.__table.setMaximumHeight(Vh + Hh + 10)
        Hhd.setSectionResizeMode(QHeaderView.Stretch)
        Vhd.setSectionResizeMode(QHeaderView.Stretch)

    def text(self):
        table = self.__table.read_all()
        return "_".join(["".join(row) for row in table])

    def setText(self, text):
        # Set up table
        table = self.__table
        tdata = []
        daysdata = text.split("_")
        nrows = table.row_count()
        ncols = table.col_count()
        if len(daysdata) > nrows:
            errors = len(daysdata) - nrows
        else:
            errors = 0
        for d in range(nrows):
            ddata = []
            tdata.append(ddata)
            try:
                daydata = daysdata[d]
                if len(daydata) > ncols:
                    errors += 1
            except IndexError:
                daydata = ""
            for p in range(ncols):
                try:
                    v = daydata[p]
                except IndexError:
                    errors += 1
                    v = "+"
                else:
                    # Check validity
                    if period_validator(v):
                        errors += 1
                        v = "+"
                ddata.append(v)
        print("???tdata", tdata)
        table.init_data(tdata)
        self.block_unchanged = bool(errors)
        if errors:
            REPORT(
                "WARNING",
                T["INVALID_PERIOD_VALUES"].format(n=errors, val=text)
            )
            self.__modified(self.__field, True)
        # Add cell validators
        for r in range(nrows):
            for c in range(ncols):
                table.set_validator(r, c, period_validator)

    def table_changed(self, mod):
        print("???", mod, self.__table.table_changes)
        self.__table.reset_modified()
        if not self.block_unchanged:
            self.__modified(self.__field, mod)


def period_validator(value):
    """Validator for teacher period availabilöity table.
    """
    if value in ("+", "-", "*"):
        return None
    return T["INVALID_AVAILABILITY"].format(val=value)
