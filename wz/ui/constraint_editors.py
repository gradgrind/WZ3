"""
ui/constraint_editors.py

Last updated:  2023-08-07

Editor dialogs for timetable constraints.


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

#T = TRANSLATIONS("ui.constraint_editors")

### +++++

from core.db_access import (
    db_key_value_list,
)
from core.basic_data import get_periods
from ui.ui_base import (
    ### QtWidgets:
    QHeaderView,
)

from ui.dialogs.dialog_constraint_number import NumberConstraintDialog
from ui.dialogs.dialog_constraint_two_subject import TwoSubjectConstraintDialog
from ui.dialogs.dialog_constraint_check_list import CheckListDialog

### -----


def LUNCHBREAK(val, label, empty_ok):
    return CheckListDialog.popup(
        val,
        items=get_periods(),
        label=label,
        empty_ok=empty_ok,
    )


def MINDAILY(val, label, empty_ok):
    return NumberConstraintDialog.popup(
        val,
        items=[str(n) for n in range(len(get_periods()) + 1)],
        label=label,
        empty_ok=empty_ok,
    )


def MAXGAPSWEEKLY(val, label, empty_ok):
    return NumberConstraintDialog.popup(
        val,
        # items=None,
        label=label,
        empty_ok=empty_ok,
    )


def NOTAFTER(val, label, empty_ok):
    return TwoSubjectConstraintDialog.popup(
        val,
        label=label,
    )


def PAIRGAP(val, label, empty_ok):
    return TwoSubjectConstraintDialog.popup(
        val,
        label=label,
    )


def MAXBLOCK(val, label, empty_ok):
    return NumberConstraintDialog.popup(
        val,
        # items=None,
        label=label,
        empty_ok=empty_ok,
    )


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def N_PERIODS():
    pass

def SELECT_PERIODS():
    pass

def TWO_SUBJECTS():
    pass

