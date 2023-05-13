"""
ui/modules/class_editor.py

Last updated:  2023-05-13

Edit class data.


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

########################################################################

if __name__ == "__main__":
    import sys, os

    this = sys.path[0]
    appdir = os.path.dirname(os.path.dirname(this))
    sys.path[0] = appdir
    basedir = os.path.dirname(appdir)
    from core.base import start
    from ui.ui_base import StandalonePage as Page
    start.setup(os.path.join(basedir, 'TESTDATA'))
else:
    from ui.ui_base import StackPage as Page

T = TRANSLATIONS("ui.modules.class_editor")

### +++++

#from typing import NamedTuple
from core.basic_data import clear_cache, get_rooms
from core.db_access import (
    open_database,
    db_read_unique,
    db_read_full_table,
    db_update_field,
    db_new_row,
    db_delete_rows,
    NoRecord,
    read_pairs,
    write_pairs,
)
from ui.ui_base import (
    ### QtWidgets:
    QLineEdit,
    QTableWidgetItem,
    QWidget,
    QHeaderView,
    ### QtGui:
    ### QtCore:
    Qt,
    QEvent,
    Slot,
    ### uic
    uic,
)
from ui.dialogs.dialog_choose_one_item_pair import ChooseOneItemDialog
from ui.dialogs.dialog_class_groups import ClassGroupsDialog
from ui.dialogs.dialog_text_line import TextLineDialog
from ui.week_table import WeekTable
import ui.constraint_editors as CONSTRAINT_HANDLERS

CLASS_FIELDS = (
    "CLASS",
    "NAME",
    "CLASSROOM",
    "DIVISIONS",
)

### -----

class ClassEditorPage(Page):
    def __init__(self):
        super().__init__()
        uic.loadUi(APPDATAPATH("ui/class_editor.ui"), self)
        self.class_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.constraints.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        # Set up editor-activation for the class fields:
        for w in CLASS_FIELDS:
            getattr(self, w).installEventFilter(self)

    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        """Event filter for the text-line fields.
        Activate the appropriate editor on mouse-left-press or return-key.
        """
        if not obj.isEnabled():
            return False
        if (event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ) or (event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Return
        ):
            # oname = obj.objectName()
            self.field_editor(obj) #, obj.mapToGlobal(QPoint(0,0)))
            return True
        else:
            # standard event processing
            return super().eventFilter(obj, event)

    def enter(self):
        open_database()
        clear_cache()
        self.week_table = WeekTable(self.AVAILABLE, self.week_table_changed)
        TT_CONFIG = MINION(DATAPATH("CONFIG/TIMETABLE"))
        self.constraint_handlers = {
            c: (h, d, name)
            for c, h, d, name in TT_CONFIG["CLASS_CONSTRAINT_HANDLERS"]
        }
        self.init_data()

    def  init_data(self):
        self.load_class_table()
        self.set_row(0)

    def load_class_table(self):
        fields, records = db_read_full_table(
            "CLASSES",
            sort_field="CLASS",
        )
        # Populate the classes table
        self.class_table.setRowCount(len(records))
        self.class_list = []
        self.class2row = {}
        for r, rec in enumerate(records):
            rdict = {fields[i]: val for i, val in enumerate(rec)}
            self.class2row[rdict["CLASS"]] = r
            self.class_list.append(rdict)
            c = 0
            for field in CLASS_FIELDS:
                cell_value = rdict[field]
                item = self.class_table.item(r, c)
                if not item:
                    item = QTableWidgetItem()
                    self.class_table.setItem(r, c, item)
                item.setText(cell_value)
                c += 1
        self.class_dict = None

    def set_class_id(self, klass):
        self.set_row(self.class2row[klass])

    def set_row(self, row):
        nrows = self.class_table.rowCount()
        self.class_table.setCurrentCell(-1, 0)
        if nrows > 0:
            if row >= nrows:
                row = nrows - 1
            self.class_table.setCurrentCell(row, 0)

    def on_class_table_itemSelectionChanged(self):
        row = self.class_table.currentRow()
        if row >= 0:
            self.class_dict = self.class_list[row]
            self.set_class()
        self.pb_remove.setEnabled(row > 0)
        self.frame_r.setEnabled(row > 0)

    def set_class(self):
        self.class_id = self.class_dict["CLASS"]
        for k, v in self.class_dict.items():
            getattr(self, k).setText(v)
        # Constraints
        try:
            self.tt_available, tt_constraints = db_read_unique(
                "TT_CLASSES",
                ("AVAILABLE", "CONSTRAINTS"),
                CLASS=self.class_id
            )
        except NoRecord:
            db_new_row("TT_CLASSES", CLASS=self.class_id)
            self.tt_available, tt_constraints = "", ""
        self.week_table.setText(self.tt_available)
        clist = []
        for c, v in read_pairs(tt_constraints):
            try:
                hdt = self.constraint_handlers[c]
#TODO: Can the validity of the value be checked?
                clist.append([c, v])
            except KeyError:
                REPORT(
                    "ERROR",
                    T["UNKNOWN_CLASS_CONSTRAINT"].format(c=c, v=v)
                )
        self.constraint_list = clist
        self.set_constraints()

    def set_constraints(self):
        """Handle the constraints from the CONSTRAINTS field of TT_CLASSES.
        """
        cdata = self.constraint_handlers
        self.constraints.setRowCount(len(self.constraint_list))
        for r, cv in enumerate(self.constraint_list):
            c, v = cv
            item = self.constraints.item(r, 0)
            if not item:
                item = QTableWidgetItem()
                self.constraints.setItem(r, 0, item)
            item.setText(cdata[c][-1])
            item = self.constraints.item(r, 1)
            if not item:
                item = QTableWidgetItem()
                self.constraints.setItem(r, 1, item)
            item.setText(v)
        self.pb_remove_constraint.setEnabled(bool(self.constraint_list))

    @Slot(int, int)
    def on_constraints_cellActivated(self, row, col):
        c, v = self.constraint_list[row]
        newval = self.call_constraint_editor(c, v)
        if newval is not None:
            v = newval if newval else '*'
            self.constraint_list[row][1] = v
            self.write_constraints()
            self.set_constraints()  # display

    def call_constraint_editor(self, constraint, value):
        h, d, t = self.constraint_handlers[constraint]
        # Call an editor (pop-up) for the constraint.
        # Pass the current value, or the default if the current value is '*'.
        # Also pass the description field to be used as a label.
        # If the default is not null (""), it should be possible to "reset"
        # the constraint value, which means setting it to '*'.
        # Actual empty values should not really be supported, it would
        # be more sensible to remove the constraint altogether.
        # A constraint can be retained in the database but disabled by
        # setting the weight to '-'.
        try:
            handler = getattr(CONSTRAINT_HANDLERS, constraint)
        except AttributeError:
            REPORT("ERROR", T["NO_CONSTRAINT_HANDLER"].format(h=h, t=t))
            return
        if value == '*':
            val = d
            reset = False
        else:
            val = value
            reset = bool(d)
        return handler(val, label=t, empty_ok=reset)

    def write_constraints(self):
        self.constraint_list.sort()
        db_update_field(
            "TT_CLASSES",
            "CONSTRAINTS",
            write_pairs(self.constraint_list),
            CLASS=self.class_id
        )

    @Slot()
    def on_pb_new_constraint_clicked(self):
        c = ChooseOneItemDialog.popup(
            [(c, hdt[-1]) for c, hdt in self.constraint_handlers.items()],
            "",
            empty_ok=False,
        )
        if not c:
            return
        if self.constraint_handlers[c][1]:
            # Start new constraint with default value
            v = '*'
        else:
            # Pop up constraint editor to get initial value
            v = self.call_constraint_editor(c, "")
            if v is None:
                return
        self.constraint_list.append([c, v])
        self.write_constraints()    # save new list
        self.set_constraints()      # display

    @Slot()
    def on_pb_remove_constraint_clicked(self):
        r = self.constraints.currentRow()
        if r >= 0:
            del self.constraint_list[r]
        self.write_constraints()    # save new constraint list
        self.set_constraints()      # display

    @Slot()
    def on_pb_new_clicked(self):
        """Add a new class.
        The fields will initially have dummy values.
        """
        e = db_new_row(
            "CLASSES",
            CLASS = "?",
            NAME="???",
        )
        self.load_class_table()
        self.set_class_id("?")

    @Slot()
    def on_pb_remove_clicked(self):
        """Remove the current class."""
        row = self.class_table.currentRow()
        if row < 0:
            raise Bug("No class selected")
        if (
            self.class_dict["CLASS"] != "?"
            and not SHOW_CONFIRM(
                T["REALLY_DELETE"].format(**self.class_dict)
            )
        ):
            return
        if db_delete_rows("CLASSES", CLASS=self.class_id):
#TODO: Check that the db tidying really occurs:
            # The foreign key constraints should tidy up the database.
            # Reload the class table
            self.load_class_table()
            self.set_row(row)

    def field_editor(self, obj: QLineEdit):
        row = self.class_table.currentRow()
        object_name = obj.objectName()
        ### CLASSES fields
        if object_name in CLASS_FIELDS:
            if object_name == "CLASSROOM":
                result = ChooseOneItemDialog.popup(
                    get_rooms(),
                    self.class_dict[object_name],
                    parent=self
                )
            elif object_name == "DIVISIONS":
                result = ClassGroupsDialog.popup(
                    self.class_dict[object_name],
                    parent=self
                )
            else:
                result = TextLineDialog.popup(
                    self.class_dict[object_name],
                    parent=self
                )
            if result is not None:
                db_update_field(
                    "CLASSES",
                    object_name,
                    result,
                    CLASS=self.class_id
                )
                # redisplay
                self.load_class_table()
                self.set_row(row)
        else:
            Bug(f"unknown field: {object_name}")

    def week_table_changed(self):
        """Handle changes to the week table.
        """
        result = self.week_table.text()
        db_update_field(
            "TT_CLASSES",
            "AVAILABLE",
            result,
            CLASS=self.class_id
        )


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from ui.ui_base import run

    widget = ClassEditorPage()
    widget.enter()
    widget.resize(1000, 550)
    run(widget)
