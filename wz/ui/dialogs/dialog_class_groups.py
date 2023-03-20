"""
ui/dialogs/dialog_class_groups.py

Last updated:  2023-03-20

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

#T = TRANSLATIONS("ui.dialogs.dialog_number_constraint")

### +++++

from typing import Optional
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    ### QtGui:
    ### QtCore:
    Slot,
    ### other
    uic,
)
from core.classes import (
    build_group_data,
    atomic_maps,
    atoms2groups,
    class_divisions,
)

### -----

# The data is stored in fields with permitted values n%w, where
#   n is an integer from 0 to 9 (?) and
#   w is the weight: -, 1, 2, 3, ... 9, +
# Such a field may also be empty, indicating no constraint (if the
# weight is '-', that also corresponds to "no constraint").

class ClassGroupsDialog(QDialog):
    @classmethod
    def popup(cls, start_value, parent=None):
        d = cls(parent)
        return d.activate(start_value)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_class_groups.ui"), self)
        self.pb_reset = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Reset
        )
        self.pb_reset.clicked.connect(self.reset)
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )

    @Slot(str)
    def on_divisions_currentTextChanged(self, text):
        if self.disable_triggers:
            return
        print("CURRENT:", text)

    @Slot()
    def on_new_division_clicked(self):
        print("NEW")

    @Slot()
    def on_remove_division_clicked(self):
        print("REMOVE")

    def activate(self, start_value:str) -> Optional[str]:
        """Open the dialog.
        """
        self.result = None
        self.disable_triggers = True
        self.value0 = start_value
        self.pb_accept.setEnabled(False)
        self.disable_triggers = False

#TODO--
        self.analyse()

        self.exec()
        return self.result

    def reset(self):
        self.result = ""
        super().accept()

    def accept(self):
        self.result = self.value
        super().accept()

    def analyse(self):
        divs = []
        for i in range(self.divisions.count()):
            line = self.divisions.item(i).text()
            print("$$$", line)
            divs.append(line.split('+'))
        print(divs)
        group_data = build_group_data(divs)
        divisions = group_data["INDEPENDENT_DIVISIONS"]
        for d in divisions:
            print("  ", d)
        group_map = group_data["GROUP_MAP"]
        atoms = group_data["MINIMAL_SUBGROUPS"]
        self.atomic_groups.clear()
        self.atomic_groups.addItems(atoms)
#        print("\n ... Atoms:", atoms)

# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
#    from core.db_access import open_database
#    open_database()
    print("----->", ClassGroupsDialog.popup(""))


    _divs = [("G", "R"), ("A", "B.G", "R"), ("A", "B"), ("I", "II", "III")]

    print("\nGROUP DIVISIONS:", _divs, "->")
    res = build_group_data(_divs)
    print("\n ... Independent divisions:")
    divisions = res["INDEPENDENT_DIVISIONS"]
    for d in divisions:
        print("  ", d)
    print("\n ... Group-map:")
    group_map = res["GROUP_MAP"]
    for g, l in group_map.items():
        print(f"  {str(g):20}: {l}")
#    print("\n ... Groups:", res["GROUPS"])
    print("\n ... Basic:", res["BASIC"])
    atoms = res["MINIMAL_SUBGROUPS"]
    print("\n ... Atoms:", atoms)

    group2atoms = atomic_maps(atoms, list(group_map))
    print("\n ... group -> atoms:")
    for g, a in group2atoms.items():
        print("       ::", g, "->", a)
    a2glist = atoms2groups(divisions, group2atoms)
    print("\n ... atoms -> groups:")
    for a, g in a2glist.items():
        print("       ::", a, "->", g)

    print("\n ... basics -> groups:")
    a2g = atoms2groups(divisions, group_map, with_divisions=True)
    for a, g in a2g.items():
        print("       ::", a, "->", g)


    all_groups = list(group_map)
    import random
    ng = random.randint(1, len(all_groups))
    groups = random.sample(all_groups, ng)
    print("\n$$$ IN:", groups)

    chipdata = class_divisions(
        groups,
        group_map,
        divisions
    )
    print("    GROUPS:", chipdata.groups)
    print("    SET:", chipdata.basic_groups)
    print(f"    {chipdata.num}/{chipdata.den} @ {chipdata.offset}")
    print("    REST:", chipdata.rest_groups)
