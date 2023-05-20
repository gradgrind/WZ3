"""
ui/dialogs/dialog_pupil_groups.py

Last updated:  2023-05-18

Supporting "dialog" for the class-data editor – specify the groups of
which a pupil is a member.


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

T = TRANSLATIONS("ui.dialogs.dialog_pupil_groups")

### +++++

from typing import Optional

from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
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
    def popup(cls, klass, start_value, parent=None, pos=None):
        d = cls(parent)
        d.init(klass)
        if pos:
            d.move(pos)
        return d.activate(start_value)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_pupil_groups.ui"), self)
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )

    def init(self, klass):
        divisions = db_read_unique_field("CLASSES", "DIVISIONS", CLASS=klass)
        self.class_groups = ClassGroups(divisions)

    def activate(self, start_value:str) -> Optional[str]:
        """Open the dialog.
        """
        self.result = None
        self.value0 = start_value
        self.set_groups(start_value)
        self.exec()
        return self.result

    def print_groups(self):
        return " ".join(g for g in self.divchoice if g)

    def set_groups(self, istring):
        pgroups = set(istring.split())
        self.disable_triggers = True
        self.grouplist.clear()
        self.divmap = {}    # group -> division index
        self.groupmap = {}  # group -> list item
        self.divchoice = [""] * len(self.class_groups.divisions)
        for d, div in enumerate(self.class_groups.divisions):
            if d != 0:
                # Add division spacer
                self.grouplist.addItem(QListWidgetItem())
            for g, v in div:
                if v is not None:
                    continue    # Only include primitive groups
                self.divmap[g] = d
                item = QListWidgetItem(g)
                self.groupmap[g] = item
                checkstate = Qt.CheckState.Unchecked
                try:
                    pgroups.remove(g)
                except KeyError:
                    pass
                else:
                    if self.divchoice[d]:
                        REPORT(
                            "ERROR",
                            T["MULTIPLE_GROUPS_IN_DIV"].format(
                                g1=self.divchoice[d], g2=g
                            )
                        )
                    else:
                        # Check combination
                        self.divchoice[d] = g
                        checkstate = Qt.CheckState.Checked
                item.setCheckState(checkstate)
                self.grouplist.addItem(item)
        self.set_accept_enable()
        self.disable_triggers = False
        if pgroups:
            REPORT(
                "ERROR",
                T["INVALID_GROUPS"].format(g=", ".join(sorted(pgroups)))
            )

    @Slot(QListWidgetItem)
    def on_grouplist_itemChanged(self, lwi):
        if self.disable_triggers:
            return
        g = lwi.text()
        d = self.divmap[g]
        if lwi.checkState() == Qt.CheckState.Checked:
            self.disable_triggers = True
            g0 = self.divchoice[d]
            self.divchoice[d] = g
            if g0:
                # Group in division already set, deselect it
                self.groupmap[g0].setCheckState(Qt.CheckState.Unchecked)
            self.disable_triggers = False
        else:
            self.divchoice[d] = ""
        self.set_accept_enable()

    def set_accept_enable(self):
        self.value = self.print_groups()
        self.pb_accept.setEnabled(self.value != self.value0)

    def accept(self):
        self.result = self.value
        super().accept()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print(
        "----->",
        PupilGroupsDialog.popup("03K", "X")
    )
    print(
        "----->",
        PupilGroupsDialog.popup("13", "m")
    )
    print(
        "----->",
        PupilGroupsDialog.popup("11G", "R A")
    )
