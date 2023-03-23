"""
ui/dialogs/dialog_class_groups.py

Last updated:  2023-03-23

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
    QRegularExpressionValidator,
    ### QtCore:
    Qt,
    QRegularExpression,
    Slot,
    ### other
    uic,
)
from core.classes import ClassGroups

NO_ITEM = "–––"

### -----












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

#TODO ...?
# I should be able to assume that (apart from the dummy "new" entry) all
# lines in the list are somehow "valid". That doesn't mean that the
# collection is valid as a whole (according to the <analyse> function).
# A function <check_division> should check form and meaning – the
# present version is rather inadequate as it accepts, for instance
# "A+A+A". 

    @Slot(str)
    def on_edit_division_textEdited(self, text):
        cg = self.class_groups
        ## Check just structure of division text
        div, e = cg.check_division(text, set())
        if e:
            self.set_line_error(True)
            self.clear_results()
            self.set_analysis_report(e)
            return
        self.set_line_error(False)
        ## Update division list
        row = self.divisions.currentRow()
        divlist = [
            self.divisions.item(r).text()
            for r in range(self.divisions.count())
        ]
        divlist[row] = text
        e = cg.init_divisions(divlist, report_errors=False)
        if e:
            self.clear_results()
            self.set_analysis_report(e)
            return
        self.init_division_list(row)
        
    def set_line_error(self, e:bool):
        if self.line_error:
            if not e:
                self.edit_division.setStyleSheet("")
        elif e:
            self.edit_division.setStyleSheet("color: rgb(255, 0, 0);")
        self.line_error = e

    def set_analysis_report(self, text):
        if text:
            self.analysis.setText(text)
            self.analysis.setStyleSheet("color: rgb(255, 0, 0);")
        else:
            self.analysis.setText(NO_ITEM)
            self.analysis.setStyleSheet("")

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
#?
        self.AWAITING_ITEM = False
        self.class_groups = ClassGroups(start_value)
        self.init_division_list(0)
        self.exec()
        return self.result

    def init_division_list(self, row):
        """Fill the divisions list widget.
        Subsequently the other display widgets are set up.
        """
        self.divisions.clear()
        divlist = self.class_groups.division_lines()
        if divlist:
            self.divisions.addItems(divlist)
            self.divisions.setEnabled(True)
            self.new_division.setEnabled(True)
        else:
#?
            self.AWAITING_ITEM = True
            self.divisions.setEnabled(False)
            self.divisions.addItem(NO_ITEM)
            self.new_division.setEnabled(False)
# disable results?

        self.divisions.setCurrentRow(row)
        ## Set up the atomic groups display and the general groups display
        self.set_atomic_groups()
        self.fill_group_table()

    def set_atomic_groups(self):
        self.atomic_groups.clear()
        elist = self.class_groups.filter_atomic_groups()
        if elist:
            REPORT(
                "WARNING",
                T["EMPTY_GROUPS_ERROR"].format(e="\n - ".join(elist))
            )
        self.atomic_groups_list = [
            (self.class_groups.set2group(ag), ag)
            for ag in self.class_groups.atomic_groups
        ]
        self.atomic_groups_list.sort()
        for agstr, ag in self.atomic_groups_list:
            item = QListWidgetItem(agstr)
            active = ag in self.class_groups.filtered_atomic_groups
            item.setCheckState(
                Qt.CheckState.Checked if active
                else Qt.CheckState.Unchecked
            )
            self.atomic_groups.addItem(item)

    def reset(self):
        self.result = ""
        super().accept()

    def accept(self):
        self.result = self.value
        super().accept()

    def clear_results(self):
        """Clear result tables and disable "accept" button.
        """
        self.atomic_groups.clear()
        self.group_table.clearContents()
        self.pb_accept.setEnabled(False)

    def fill_group_table(self):
        cg = self.class_groups
        aglist = [
            (
                len(g),
                cg.set2group(g), 
                "; ".join(cg.set2group(a) for a in alist)
            )
            for g, alist in cg.group2atoms.items()
        ]
        aglist.sort()
        self.group_table.setRowCount(len(aglist))
        i = 0
        for l, g, agl in aglist:
            item = self.group_table.item(i, 0)
            if not item:
                item = QTableWidgetItem()
                self.group_table.setItem(i, 0, item)
            item.setText(g)
            item = self.group_table.item(i, 1)
            if not item:
                item = QTableWidgetItem()
                self.group_table.setItem(i, 1, item)
            item.setText(agl)
            i += 1
        self.set_analysis_report("")
        ## Regenerate the current text value
        self.value = cg.text_value()
        if self.value != self.value0:
            self.pb_accept.setEnabled(True)

    def on_atomic_groups_itemChanged(self, item):
        # print("§§§§0:", self.class_groups.subgroup_empties.values())
        row = self.atomic_groups.row(item)
        agstr, ag = self.atomic_groups_list[row]
        if item.checkState() == Qt.CheckState.Unchecked:
            self.class_groups.subgroup_empties[ag] = agstr
        else:
            del(self.class_groups.subgroup_empties[ag])
        ## Update group table
        # print("§§§§1:", self.class_groups.subgroup_empties.values())
        elist = self.class_groups.filter_atomic_groups()
        if elist:
            REPORT("WARNING", "\n".join(elist))
        self.fill_group_table()


##################################################################

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
            self.set_analysis_report(str(e))
            self.pb_accept.setEnabled(False)
            return
        self.set_analysis_report("–––")
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

def test_division(self, groups:str):
    print("§Test division:", groups)
    if self.regex.match(groups).hasMatch():
        glist = groups.split('+')

    else:
        # bad pattern
        return (None, )

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
    print(
        "----->",
        ClassGroupsDialog.popup("G+R;A+B;I+II+III-A.R.I-A.R.II-A.R.III")
    )
    print("----->", ClassGroupsDialog.popup("A+B;G+R;B+A"))
    print("----->", ClassGroupsDialog.popup("A+B;G+r:I+II+III"))
    print("----->", ClassGroupsDialog.popup(""))
