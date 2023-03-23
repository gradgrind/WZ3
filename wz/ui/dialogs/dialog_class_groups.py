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
    ### QtCore:
    Qt,
    Slot,
    ### other
    uic,
)
from core.classes import ClassGroups

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

    @Slot(str)
    def on_divisions_currentTextChanged(self, text):
        if self.line_error:
            self.set_line_error(False)
            # Handle jumping away from a bad edit
            self.init_division_list(self.divisions.currentRow())
        else:
            self.edit_division.setText(text)

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
        self.analysis.setText(text)

    @Slot()
    def on_new_division_clicked(self):
        self.divisions.setEnabled(False)
        self.divisions.addItem("")
        self.new_division.setEnabled(False)
        self.divisions.setCurrentRow(self.divisions.count() - 1)

    @Slot()
    def on_remove_division_clicked(self):
        row = self.divisions.currentRow()
        divlist = [
            self.divisions.item(r).text()
            for r in range(self.divisions.count())
        ]
        assert(len(divlist) > 1)
        del(divlist[row])
        self.class_groups.init_divisions(divlist, report_errors=True)
        n = len(self.class_groups.divisions)
        self.init_division_list(row if row < n else n-1)

    def activate(self, start_value:str) -> Optional[str]:
        """Open the dialog.
        """
        self.result = None
        self.value0 = start_value
        self.pb_reset.setVisible(bool(start_value))
        self.edit_division.setStyleSheet("")
        self.line_error = False
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
            self.divisions.setEnabled(False)
            self.divisions.addItem("")
            self.new_division.setEnabled(False)
        self.divisions.setCurrentRow(row)
        self.remove_division.setEnabled(len(divlist) > 1)
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
        self.pb_accept.setEnabled(self.value != self.value0)

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
