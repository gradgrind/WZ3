"""
ui/modules/class_editor.py

Last updated:  2023-03-23

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
from core.basic_data import clear_cache
from core.db_access import (
    open_database,
    db_read_unique,
    db_read_full_table,
    db_update_field,
    db_new_row,
    db_delete_rows,
    NoRecord,
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
from ui.dialogs.dialog_text_line import TextLineDialog
from ui.dialogs.dialog_number_constraint import NumberConstraintDialog
from ui.dialogs.dialog_class_groups import ClassGroupsDialog
from ui.week_table import WeekTable

CLASS_FIELDS = (
    "CLASS",
    "NAME",
    "CLASSROOM",
    "DIVISIONS",
)

TT_FIELDS = (
    "AVAILABLE",
    "MIN_LESSONS_PER_DAY",
    "MAX_GAPS_PER_WEEK",
    "LUNCHBREAK",
)

### -----

class ClassEditorPage(Page):
    def __init__(self):
        super().__init__()
        uic.loadUi(APPDATAPATH("ui/class_editor.ui"), self)
        self.class_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        # Set up activation for the editors for the read-only lesson/block
        # fields:
        for w in (
            self.CLASS, self.NAME, self.CLASSROOM,
            self.DIVISIONS,
            self.MIN_LESSONS_PER_DAY, self.MAX_GAPS_PER_WEEK,
            self.constraints,
        ):
            w.installEventFilter(self)

    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        """Event filter for the text-line fields.
        Activate the appropriate editor on mouse-left-press or return-key.
        """
        if not obj.isEnabled():
            return False
        if (event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ) or (event.type() == QEvent.KeyPress
            and event.key() == Qt.Key.Key_Return
        ):
#            oname = obj.objectName()
            self.field_editor(obj) #, obj.mapToGlobal(QPoint(0,0)))
            return True
        else:
            # standard event processing
            return super().eventFilter(obj, event)

    def enter(self):
        open_database()
        clear_cache()
        self.week_table = WeekTable(self.AVAILABLE, self.week_table_changed)
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
            # print("  --", rdict)
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
        # print("§§§ on_course_table_itemSelectionChanged", row)
        if row >= 0:
            self.class_dict = self.class_list[row]
            self.set_class()
        self.pb_remove.setEnabled(row > 0)
        self.frame_r.setEnabled(row > 0)

    def set_class(self):
        self.class_id = self.class_dict["CLASS"]
        for k, v in self.class_dict.items():
            getattr(self, k).setText(v)
        try:
            record = db_read_unique(
                "TT_CLASSES",
                TT_FIELDS,
                CLASS=self.class_id
            )
            ttdict = {f: record[i] for i, f in enumerate(TT_FIELDS)}
        except NoRecord:
            ttdict = {f: "" for f in TT_FIELDS}
            db_new_row("TT_CLASSES", CLASS=self.class_id)
        self.tt_available = ttdict.pop("AVAILABLE")
        self.week_table.setText(self.tt_available)
        lb = ttdict.pop("LUNCHBREAK")
        lbi = self.LUNCHBREAK.findText(lb)
        if lbi < 0:
            if lb:
                db_update_field(
                    "TT_CLASSES",
                    "LUNCHBREAK",
                    '',
                    CLASS=self.class_id
                )
        self.current_lunchbreak = lb
        self.LUNCHBREAK.setCurrentIndex(lbi)
        for k, v in ttdict.items():
            getattr(self, k).setText(v)

    @Slot()
    def on_pb_new_clicked(self):
        """Add a new class.
        The fields will initially have dummy values.
        """
        db_new_row(
            "CLASSES",
            **{f: "?" for f in CLASS_FIELDS}
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
        print("EDIT", object_name)
        ### CLASSES fields
        if object_name in (
            "CLASS", "NAME", "CLASSROOM", "DIVISIONS"
        ):
#TODO
            if object_name == "SORTNAME":
                pass
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
            # The timetable-constraint fields
            if object_name in (
                "MIN_LESSONS_PER_DAY",
                "MAX_GAPS_PER_WEEK",
            ):
                result = NumberConstraintDialog.popup(
                    obj.text(),
                    parent=self
                )
                if result is not None:
                    db_update_field(
                        "TT_CLASSES",
                        object_name,
                        result,
                        CLASS=self.class_id
                    )
                    obj.setText(result)
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

    @Slot(str)
    def on_LUNCHBREAK_currentTextChanged(self, weight):
        if weight == '-':
            self.LUNCHBREAK.setCurrentIndex(-1)
            return
        if self.current_lunchbreak != weight:
            print("§UPDATE LUNCHBREAK:", weight)
            db_update_field(
                "TT_CLASSES",
                "LUNCHBREAK",
                weight,
                CLASS=self.class_id
            )
            self.current_lunchbreak = weight


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from ui.ui_base import run

    widget = ClassEditorPage()
    widget.enter()
    widget.resize(1000, 550)
    run(widget)
