"""
ui/dialogs/dialog_class_groups.py

Last updated:  2023-05-01

Supporting "dialog" for the class-data editor – specify the ways a class
can be divided into groups.


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

T = TRANSLATIONS("ui.dialogs.dialog_class_groups")

### +++++

from typing import Optional
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    QTableWidgetItem,
    QListWidgetItem,
    ### QtGui:
    ### QtCore:
    Qt,
    Slot,
    ### other
    uic,
)
from core.classes import ClassGroups
from core.db_access import db_read_unique_field

### -----

class PupilGroupsDialog(QDialog):
    @classmethod
    def popup(cls, klass, start_value, parent=None):
        d = cls(klass, parent)
        return d.activate(start_value)

    def __init__(self, klass, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_pupil_groups.ui"), self)
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )
        divisions = db_read_unique_field("CLASSES", "DIVISIONS", CLASS=klass)
        self.class_groups = ClassGroups(divisions)
        elist = self.class_groups.filter_atomic_groups()
        if elist:
            REPORT(
                "WARNING",
#TODO: T ...
                T["EMPTY_GROUPS_ERROR"].format(e="\n - ".join(elist))
            )

    def activate(self, start_value:str) -> Optional[str]:
        """Open the dialog.
        """
        self.result = None
        self.value0 = start_value
        self.pgroups = set(start_value.split())
        self.set_groups()
        self.exec()
        return self.result

#TODO
    def set_groups(self):
        self.grouplist.clear()

        divchoice = [""] * len(self.class_groups.divisions)
        first = True
        for div in self.class_groups.divisions:
            if first:
                first = False
            else:
                self.grouplist.addItem(QListWidgetItem())
            for i, g in enumerate(sorted(div)):
                item = QListWidgetItem(g)
                if (active := g in self.pgroups):
                    if divchoice[i]:
#TODO: T ...
                        REPORT("ERROR", T["MULTIPLE_GROUPS_IN_DIV"])
                    else:
#TODO: check combination
                        divchoice[i] = g
                item.setCheckState(
                    Qt.CheckState.Checked if active
                    else Qt.CheckState.Unchecked
                )
                self.grouplist.addItem(item)
        self.value = " ".join(g for g in divchoice if g)
        print("§§§", self.value, self.value != self.value0)


    def accept(self):
        self.result = self.value
        super().accept()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print(
        "----->",
        PupilGroupsDialog.popup("11G", "R A")
    )
#    print("----->", ClassGroupsDialog.popup("A+B;G+R;B+A"))
#    print("----->", ClassGroupsDialog.popup("A+B;G+r:I+II+III"))
#    print("----->", ClassGroupsDialog.popup(""))
