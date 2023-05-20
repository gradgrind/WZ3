"""
ui/dialogs/dialog_class_groups.py

Last updated:  2023-05-19

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
import math

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

DUMMY_GROUP = '?'

### -----

class ClassGroupsDialog(QDialog):
    @classmethod
    def popup(cls, start_value, parent=None, pos=None):
        d = cls(parent)
        if pos:
            d.move(pos)
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

    def activate(self, start_value:str) -> Optional[str]:
        """Open the dialog.
        """
        self.result = None
        self.value0 = start_value
        self.pb_reset.setVisible(bool(start_value))
        self.edit_division.setStyleSheet("")
        self.class_groups = ClassGroups(start_value)
        # Set up the initial data
        self.init_division_list(0)
        self.set_value()
        self.exec()
        return self.result

    def init_division_list(self, row):
        """Fill the divisions list widget.
        Subsequently the other display widgets are set up.
        """
        self.disable_triggers = True
        self.divisions.clear()
        divlist = self.class_groups.division_lines(with_extras=False)
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
        self.disable_triggers = False
        self.division_selected()

    def division_selected(self):
        self.disable_triggers = True
        self.set_line_error("")
        row = self.divisions.currentRow()
        divs = self.class_groups.divisions
        # print("§division_selected", row, divs)
        self.primary_groups.clear()
        if row >= len(divs):
            # Empty or pending item
            self.current_division = None
            self.edit_division.setText("")
            self.extra_groups.setRowCount(0)
            self.extra_frame.setEnabled(False)
            self.disable_triggers = False
            return
        self.current_division = divs[row]
        self.edit_division.setText(self.divisions.currentItem().text())
        self.pgroups, self.xgroups = [], []
        for g_v in self.current_division:
            if g_v[1] is None:
                self.pgroups.append(g_v[0])
            else:
                self.xgroups.append(g_v)
        # Add primary groups to check-list
        for g in self.pgroups:
            item = QListWidgetItem(g)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.primary_groups.addItem(item)
        if (lp := len(self.pgroups)) > 2:
            self.extra_frame.setEnabled(True)
            # Calculate the max. number of extra groups
            self.xgmax = sum(math.comb(lp, n) for n in range(2, lp))
            self.set_extra_groups(0)
        else:
            self.extra_groups.setRowCount(0)
            self.extra_frame.setEnabled(False)
        self.disable_triggers = False

    def set_extra_groups(self, row):
        self.remove_extra.setEnabled(bool(self.xgroups))
        nx = len(self.xgroups)
        self.new_extra.setEnabled(nx < self.xgmax)
        self.extra_groups.setRowCount(len(self.xgroups))
        for r, g_v in enumerate(self.xgroups):
            item = self.extra_groups.item(r, 0)
            if not item:
                item = QTableWidgetItem()
                self.extra_groups.setItem(r, 0, item)
            item.setText(g_v[0])
            item = self.extra_groups.item(r, 1)
            if not item:
                item = QTableWidgetItem()
                self.extra_groups.setItem(r, 1, item)
            item.setText('+'.join(g_v[1]))
        if row < nx:
            self.extra_groups.setCurrentCell(row, 0)
            self.extra_group_selected()
            self.primary_groups.setEnabled(nx < self.xgmax)
        else:
            self.primary_groups.setEnabled(False)
            self.edit_extra_group.setEnabled(False)
            self.edit_extra_group.clear()

    def extra_group_selected(self):
        xrow = self.extra_groups.currentRow()
        xg, plist = self.xgroups[xrow]
        self.set_x_error("")
        self.edit_extra_group.setText(xg)
        dt = self.disable_triggers
        self.disable_triggers = True
        for i, g in enumerate(self.pgroups):
            self.primary_groups.item(i).setCheckState(
                Qt.CheckState.Checked if g in plist
                else Qt.CheckState.Unchecked
            )
        self.disable_triggers = dt

    def set_value(self):
        self.value = self.class_groups.text_value()
        self.pb_accept.setEnabled(self.value != self.value0)

    def reset(self):
        self.result = ""
        super().accept()

    def accept(self):
        self.result = self.value
        super().accept()

    def set_line_error(self, e:str):
        self.analysis.setText(e)
        self.edit_division.setStyleSheet(
            "color: #d50000;" if e else ""
        )

    def set_x_error(self, e:str):
        self.analysis.setText(e)
        if e:
            self.edit_extra_group.setStyleSheet("color: #d50000;")
        else:
            self.edit_extra_group.setStyleSheet("")

    @Slot(int,int,int,int)
    def on_extra_groups_currentCellChanged(self, r, c, r0, c0):
        if self.disable_triggers:
            return
        self.extra_group_selected()

    @Slot(QListWidgetItem)
    def on_primary_groups_itemChanged(self, item):
        if self.disable_triggers:
            return
        xrow = self.extra_groups.currentRow()
        xgroup = self.xgroups[xrow]
        xg = xgroup[0]
        glist = []
        for i, g in enumerate(self.pgroups):
            item = self.primary_groups.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                glist.append(g)
        l = len(glist)
        if l < 2:
            e = T["AT_LEAST_TWO"]
        elif l == len(self.pgroups):
            e = T["NOT_ALL"]
        else:
            # Check that the group list is not a duplicate
            for i, xg_plist in enumerate(self.xgroups):
                if xg_plist[1] == glist:
                    if i == xrow: # no change
                        e = ""
                    else:
                        e = T["DUPLICATE_EXTRA"].format(g=xg_plist[0])
                    break
            else:
                e = ""
                xgroup[1] = glist
                # The xgroup items are references to those in the main
                # division list, so the main list needs no additional
                # changes – except for new items, which are only entered
                # into the main list when they are valid.
                if xg == DUMMY_GROUP:
                    # Add the extra group to the division in the main list
                    xgn = self.edit_extra_group.text()
                    xgroup[0] = xgn
                    self.current_division.append(xgroup)
                    # Do a redisplay here, to ensure that the '+' button
                    # is correctly enabled/disabled.
                    self.set_extra_groups(xrow)
                    self.extra_groups.setEnabled(True)
                else:
                    self.extra_groups.item(xrow, 1).setText('+'.join(glist))
                self.set_value()
        self.set_x_error(e)
        self.edit_extra_group.setEnabled(xg == DUMMY_GROUP or not e)

    @Slot(str)
    def on_edit_extra_group_textEdited(self, text):
        if text.isalnum() and text.isascii():
            # Update the table and value if the new value is no repeat
            xrow = self.extra_groups.currentRow()
            xgroup = self.xgroups[xrow]
            xg0 = xgroup[0]
            if text == xg0: # no change
                self.set_x_error("")
                self.primary_groups.setEnabled(True)
                return
            divs = self.class_groups.divisions
            for div in divs:
                for g, v in div:
                    if g == text:
                        self.set_x_error(T["NAME_IN_USE"])
                        self.primary_groups.setEnabled(False)
                        return
            # I am assuming here that the extra groups are not sorted.
            # If they are, a redisplay would be needed!
            if xg0 == DUMMY_GROUP:
                # A valid name for the new group has been entered.
                # Now valid members must be selected.
                self.on_primary_groups_itemChanged(None)
                self.primary_groups.setEnabled(True)
                return
            xgroup[0] = text
            # The xgroup items are references to those in the main
            # division list, so the main list needs no additional
            # changes.
            self.extra_groups.item(xrow, 0).setText(text)
            self.set_x_error("")
            self.primary_groups.setEnabled(len(self.xgroups) < self.xgmax)
            self.set_value()
        else:
            self.set_x_error(T["INVALID_GROUP_NAME"])
            self.primary_groups.setEnabled(False)

    @Slot()
    def on_new_extra_clicked(self):
        # Add an extra group with no subgroups and illegal name to
        # the extra groups table – not yet to the main divisions list.
        self.new_extra.setEnabled(False)
        nrow = len(self.xgroups)
        self.xgroups.append([DUMMY_GROUP, []])
        self.extra_groups.setEnabled(False)
        self.extra_groups.insertRow(nrow)
        item = QTableWidgetItem(DUMMY_GROUP)
        self.extra_groups.setItem(nrow, 0, item)
        item = QTableWidgetItem("")
        self.extra_groups.setItem(nrow, 1, item)
        self.edit_extra_group.setText(DUMMY_GROUP)
        self.extra_groups.setCurrentCell(nrow, 0)
        self.on_edit_extra_group_textEdited(DUMMY_GROUP)
        self.edit_extra_group.setEnabled(True)

    @Slot()
    def on_remove_extra_clicked(self):
        xrow = self.extra_groups.currentRow()
        xg = self.xgroups[xrow][0]
        del self.xgroups[xrow]
        if xg != DUMMY_GROUP:
            # The entry in the main list must be removed
            n = 0
            for i, g_v in enumerate(self.current_division):
                if g_v[1] is None:
                    continue
                if xrow == n:
                    del self.current_division[i]
                    break
                n += 1
            self.set_value()
        if xrow > 0:
            xrow -= 1
        self.set_extra_groups(xrow)

    @Slot(int)
    def on_divisions_currentRowChanged(self, row):
        if self.disable_triggers:
            return
        self.division_selected()

    @Slot(str)
    def on_edit_division_textEdited(self, text):
        cg = self.class_groups
        print("$$$$", cg.divisions)
        ## Check just structure of division text
        div, e = cg.check_division(text, set())
        self.set_line_error(e)
        if e:
            self.extra_frame.setEnabled(False)
            self.pb_accept.setEnabled(False)
            return
        ## Update division list
        row = self.divisions.currentRow()
        divlines = cg.division_lines()
        if row < len(divlines):
            divlines[row] = text
        else:
            # new line
            divlines.append(text)
        e = cg.init_divisions(divlines, report_errors=False)
        if e:
            self.set_line_error(e)
            self.extra_frame.setEnabled(False)
            self.pb_accept.setEnabled(False)
            return
        self.extra_frame.setEnabled(True)
        self.init_division_list(row)
        self.set_value()

    @Slot()
    def on_new_division_clicked(self):
        self.divisions.setEnabled(False)
        self.divisions.addItem("")
        self.new_division.setEnabled(False)
        self.divisions.setCurrentRow(self.divisions.count() - 1)

    @Slot()
    def on_remove_division_clicked(self):
        row = self.divisions.currentRow()
        cg = self.class_groups
        divlines = cg.division_lines()
        del divlines[row]
        self.class_groups.init_divisions(divlines, report_errors=True)
        n = len(self.class_groups.divisions)
        self.init_division_list(row if row < n else n-1)
        self.set_value()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
#    from core.db_access import open_database
#    open_database()
    print("----->", ClassGroupsDialog.popup("A+BG+R/G=A+BG/B=BG+R"))
    print("----->", ClassGroupsDialog.popup("A+BG+R;I+II+III"))
    print("----->", ClassGroupsDialog.popup(""))
    print("----->", ClassGroupsDialog.popup("A+B"))
    print("----->", ClassGroupsDialog.popup("A+B;G+R;B+A"))
    print("----->", ClassGroupsDialog.popup("A+B;G+r:I+II+III"))
