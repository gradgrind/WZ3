"""
ui/dialogs/dialog_class_groups.py

Last updated:  2023-03-21

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
    ### QtGui:
    QRegularExpressionValidator,
    ### QtCore:
    Qt,
    QRegularExpression,
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

NO_ITEM = "–––"

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
        # Add a validator for the line entry
        w = "[A-Za-z0-9]+"
        g = f"{w}(?:[.]{w})*"
        self.regex = QRegularExpression(f"^{g}(?:[+]{g})+$")
#        validator = QRegularExpressionValidator(self.regex, self)
#        self.edit_division.setValidator(validator)

# I should be able to assume that (apart from the dummy "new" entry) all
# lines in the list are somehow "valid". That doesn't mean that the
# collection is valid as a whole (according to the <analyse> function).
# A function <check_division> should check form and meaning – the
# present version is rather inadequate as it accepts, for instance
# "A+A+A". 



    @Slot(str)
    def on_edit_division_textChanged(self, text):
        print("§LINE:", text)
        current_line = self.divisions.currentItem().text()
        if self.regex.match(text).hasMatch():
            glist = text.split('+')
            norm = '+'.join(sorted(glist))
            if norm == current_line:
                self.set_line_error(False)
                if not self.AWAITING_ITEM:
                    self.analyse()
                return
            
            if self.divisions.findItems(
                norm, Qt.MatchFlag.MatchExactly
            ):
#?
                self.analysis.setText("REPEATED_DIVISION")
                self.set_line_error(True)
                return
            if current_line == NO_ITEM:
                self.divisions.setEnabled(True)
                self.AWAITING_ITEM = False
                self.new_division.setEnabled(True)

            dset, e = test_division(glist)
            if e:
                self.analysis.setText(e)
                self.set_line_error(True)
                return
#???

#TODO: This shouldn't be necessary, if setting the current item caused
# a callback to this slot ...
# ... of course it won't, because this a a text-changed handler!
            self.set_line_error(False)
            self.divisions.currentItem().setText(norm)
            self.analyse()
            return
        else:
            self.set_line_error(True)
            self.pb_accept.setEnabled(False)
            self.clear_results()
#?
            self.analysis.setText("INVALID_DIVISION")
            return

    def set_line_error(self, e:bool):
        if self.line_error:
            if not e:
                self.edit_division.setStyleSheet("")
        elif e:
            self.edit_division.setStyleSheet("color: rgb(255, 0, 0);")
        self.line_error = e

#    @Slot(str)
#    def on_divisions_currentTextChanged(self, text):
#        if self.disable_triggers:
#            return
#        print("CURRENT:", text)

    @Slot()
    def on_new_division_clicked(self):
        print("NEW")
        self.AWAITING_ITEM = True
        self.divisions.setEnabled(False)
        self.divisions.addItem(NO_ITEM)
        self.new_division.setEnabled(False)
        self.divisions.setCurrentRow(self.divisions.count() - 1)
#        newline = self.edit_division.text()
#        if newline:
#            d = self.division_lines + [newline]
#            if self.analyse(d):
#                self.division_lines = d
#                self.edit_division.clear()
#                self.divisions.addItem(newline)

    @Slot()
    def on_remove_division_clicked(self):
        print("REMOVE")

    def activate(self, start_value:str) -> Optional[str]:
        """Open the dialog.
        """
        self.result = None
        self.value0 = start_value
        self.pb_reset.setVisible(bool(start_value))
        self.edit_division.setStyleSheet("")
        self.line_error = False
        self.AWAITING_ITEM = False
#?
        self.disable_triggers = True

        self.divisions.clear()
        text = start_value.replace(' ', '')
        if text:
            line_list = text.split(';')
            for l in line_list:
                div, e = self.check_division(l)
                if e:
                    REPORT("ERROR", e.format(div=div, groups=text))
                else:
                    self.divisions.addItem(div)
        else:
            self.AWAITING_ITEM = True
            self.divisions.setEnabled(False)
            self.divisions.addItem(NO_ITEM)
            self.new_division.setEnabled(False)
        self.divisions.setCurrentRow(0)

#?
        self.pb_accept.setEnabled(False)


#?
        self.disable_triggers = False

#TODO--
        self.analyse()

        self.exec()
        return self.result



    def check_division(self, div):
        if self.regex.match(div).hasMatch():
            norm = '+'.join(sorted(div.split('+')))
            if self.divisions.findItems(
                norm, Qt.MatchFlag.MatchExactly
            ):
                return (norm, T["REPEATED_DIVISION"])
            return (norm, None)
        return (div, T["INVALID_DIVISION"])

    def reset(self):
        self.result = ""
        super().accept()

    def accept(self):
        self.result = self.value
        super().accept()

    def clear_results(self):
        self.independent_divisions.clear()
        self.atomic_groups.clear()
        self.group_table.clearContents()

    def analyse(self):
        self.clear_results()
        divs = []
        lines = []
        for i in range(self.divisions.count()):
            line = self.divisions.item(i).text()
            divs.append(line.split('+'))
            lines.append(line)
        try:
            group_data = build_group_data(divs)
        except ValueError as e:
            self.analysis.setText(str(e))
            self.pb_accept.setEnabled(False)
            return
        self.analysis.setText("–––")
        self.value = ';'.join(lines)
        print(f"§VALUE: {self.value} [{self.value0}]")
        self.pb_accept.setEnabled(self.value != self.value0)

        divisions = group_data["INDEPENDENT_DIVISIONS"]
        for d in divisions:
            self.independent_divisions.addItem('+'.join(d))
        group_map = group_data["GROUP_MAP"]
        atoms = group_data["MINIMAL_SUBGROUPS"]
        self.atomic_groups.addItems(atoms)
        self.group_table.setRowCount(len(group_map))
        i = 0
        for g, l in group_map.items():
            item = self.group_table.item(i, 0)
            if not item:
                item = QTableWidgetItem()
                self.group_table.setItem(i, 0, item)
            item.setText(g)
            item = self.group_table.item(i, 1)
            if not item:
                item = QTableWidgetItem()
                self.group_table.setItem(i, 1, item)
            item.setText("; ".join(l))
            i += 1

def test_division(glist:list[str]):
    print("§Test division:", glist)
    gsets = set()
# There shouldn't be a superset of any member here
# It might also be possible to check for incomplete divisions, e.g.
# "A.G+B.R". Can I assume that single elements are mutually exclusive?
# If so I might expect "A.G+X" or "A.G+B.R+X". Whether these are really
# valid can only be determined in combination with the other divisions.
# I could ban more than one dot (for being too complicated!).

    g0map = {}
    doubles = []
    for g in glist:
        gn = g.split(".")
        gnf = frozenset(gn)
        gsets.add(gnf)
        if len(gnf) != len(gn):
            return (None, T["INVALID_GROUP"].format(g=g))
        if len(gn) == 1:
            if g in g0map:
                return (None, T["REPEATED_GROUP"].format(g=g))
            g0map[g] = []                

        elif len(gn) == 2:
            if gnf in doubles:
                return (None, T["REPEATED_GROUP"].format(g=g))
            doubles.append(gnf)

        else:
            return (None, T["TOO_MANY_DOTS"].format(g=g))

    subs = {}
    for g2f in doubles:
        for g in g2f:
            if g in g0map:
                return (
                    None,
                    T["SUBSET"].format(g=g, sub='.'.join(sorted(g2f)))
                )
            try:
                subs[g].append(g2f)
            except KeyError:
                subs[g] = [g2f]
    if not g0map:
        for g, gfl in subs.items():
            if len(gfl) < 2:
                return (
                    None,
                    T["SINGLE_SUBGROUP"].format(
                        g=g,
                        sub='.'.join(sorted(gfl[0]))
                    )
                )
    return (gsets, None)

    groups = set()
    impossible_partners = {}  # {group -> {incompatible groups}}
    # Collect groups and build map (<impossible_partners>) giving all
    # other groups which are incompatible with each group in a "dot-join"
    # (an intersection).

    # Build "frozensets" of the member groups, splitting dotted items.
    divsets = []
    for div in divisions:
        gsets = set()
        for g in div:
            gset = frozenset(g.split("."))
            gsets.add(gset)
            # Add to list of "acceptable" groups
            groups.add(gset)
        divsets.append(gsets)
        # Extend the sets of mutually incompatible groups
        for gset in gsets:
            snew = gsets.copy()
            snew.remove(gset)
            try:
                impossible_partners[gset] |= snew
            except KeyError:
                impossible_partners[gset] = snew

# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
#    from core.db_access import open_database
#    open_database()
    print("----->", ClassGroupsDialog.popup("A+B;G+R;B+A"))
    print("----->", ClassGroupsDialog.popup("A+B;G+r:A+B.G+R;I+II+III"))
    print("----->", ClassGroupsDialog.popup("A+B;G+R;A+B.G+R;I+II+III"))
    print("----->", ClassGroupsDialog.popup(""))


    _divs = [("G", "R"), ("A", "B.G", "B.R"), ("A", "B"), ("I", "II", "III")]

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
