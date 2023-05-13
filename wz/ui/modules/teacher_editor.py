"""
ui/modules/teacher_editor.py

Last updated:  2023-05-13

Edit teacher data.


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

T = TRANSLATIONS("ui.modules.teacher_editor")

### +++++

#from typing import NamedTuple
from core.basic_data import clear_cache
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
from ui.dialogs.dialog_text_line import TextLineDialog
from ui.dialogs.dialog_text_line_offer import TextLineOfferDialog
from ui.week_table import WeekTable
from local.name_support import asciify, tvSplit
import ui.constraint_editors as CONSTRAINT_HANDLERS

TEACHER_FIELDS = (
    "TID",
    "FIRSTNAMES",
    "LASTNAME",
    "SIGNED",
    "SORTNAME",
)

### -----

class TeacherEditorPage(Page):
    def __init__(self):
        super().__init__()
        uic.loadUi(APPDATAPATH("ui/teacher_editor.ui"), self)
        self.teacher_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.constraints.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        # Set up editor-activation for the teacher fields:
        for w in TEACHER_FIELDS:
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
            for c, h, d, name in TT_CONFIG["TEACHER_CONSTRAINT_HANDLERS"]
        }
        self.init_data()

    def  init_data(self):
        self.load_teacher_table()
        self.set_row(0)

    def load_teacher_table(self):
        fields, records = db_read_full_table(
            "TEACHERS",
            sort_field="SORTNAME",
        )
        # Populate the teachers table
        self.teacher_table.setRowCount(len(records))
        self.teacher_list = []
        self.tid2row = {}
        for r, rec in enumerate(records):
            rdict = {fields[i]: val for i, val in enumerate(rec)}
            self.tid2row[rdict["TID"]] = r
            self.teacher_list.append(rdict)
            c = 0
            for field in TEACHER_FIELDS:
                cell_value = rdict[field]
                item = self.teacher_table.item(r, c)
                if not item:
                    item = QTableWidgetItem()
                    self.teacher_table.setItem(r, c, item)
                item.setText(cell_value)
                c += 1
        self.teacher_dict = None

    def set_tid(self, tid):
        self.set_row(self.tid2row[tid])

    def set_row(self, row):
        nrows = self.teacher_table.rowCount()
        self.teacher_table.setCurrentCell(-1, 0)
        if nrows > 0:
            if row >= nrows:
                row = nrows - 1
            self.teacher_table.setCurrentCell(row, 0)

    def on_teacher_table_itemSelectionChanged(self):
        row = self.teacher_table.currentRow()
        if row >= 0:
            self.teacher_dict = self.teacher_list[row]
            self.set_teacher()
        self.pb_remove.setEnabled(row > 0)
        self.frame_r.setEnabled(row > 0)

    def set_teacher(self):
        self.teacher_id = self.teacher_dict["TID"]
        for k, v in self.teacher_dict.items():
            getattr(self, k).setText(v)
        # Constraints
        try:
            self.tt_available, tt_constraints = db_read_unique(
                "TT_TEACHERS",
                ("AVAILABLE", "CONSTRAINTS"),
                TID=self.teacher_id
            )
        except NoRecord:
            db_new_row("TT_TEACHERS", TID=self.teacher_id)
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
                    T["UNKNOWN_TEACHER_CONSTRAINT"].format(c=c, v=v)
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
            "TT_TEACHERS",
            "CONSTRAINTS",
            write_pairs(self.constraint_list),
            TID=self.teacher_id
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
        """Add a new teacher.
        The fields will initially have dummy values.
        """
        db_new_row(
            "TEACHERS",
            **{f: "?" for f in TEACHER_FIELDS}
        )
        self.load_teacher_table()
        self.set_tid("?")

    @Slot()
    def on_pb_remove_clicked(self):
        """Remove the current teacher."""
        row = self.teacher_table.currentRow()
        if row < 0:
            raise Bug("No teacher selected")
        if (
            self.teacher_dict["TID"] != "?"
            and not SHOW_CONFIRM(
                T["REALLY_DELETE"].format(**self.teacher_dict)
            )
        ):
            return
        if db_delete_rows("TEACHERS", TID=self.teacher_id):
#TODO: Check that the db tidying really occurs:
            # The foreign key constraints should tidy up the database.
            # Reload the teacher table
            self.load_teacher_table()
            self.set_row(row)

    def field_editor(self, obj: QLineEdit):
        row = self.teacher_table.currentRow()
        object_name = obj.objectName()
        ### TEACHER fields
        if object_name in TEACHER_FIELDS:
            if object_name == "SORTNAME":
                f, t, l = tvSplit(
                    self.teacher_dict["FIRSTNAMES"],
                    self.teacher_dict["LASTNAME"]
                )
                result = TextLineOfferDialog.popup(
                    self.teacher_dict["SORTNAME"],
                    asciify(f"{l}_{t}_{f}" if t else f"{l}_{f}"),
                    parent=self
                )
            else:
                result = TextLineDialog.popup(
                    self.teacher_dict[object_name],
                    parent=self
                )
            if result is not None:
                db_update_field(
                    "TEACHERS",
                    object_name,
                    result,
                    TID=self.teacher_id
                )
                # redisplay
                self.load_teacher_table()
                self.set_row(row)
        else:
            Bug(f"unknown field: {object_name}")

    def week_table_changed(self):
        """Handle changes to the week table.
        """
        result = self.week_table.text()
        db_update_field(
            "TT_TEACHERS",
            "AVAILABLE",
            result,
            TID=self.teacher_id
        )


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from ui.ui_base import run

    widget = TeacherEditorPage()
    widget.enter()
    widget.resize(1000, 550)
    run(widget)
