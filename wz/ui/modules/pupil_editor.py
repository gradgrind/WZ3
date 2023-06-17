"""
ui/modules/pupil_editor.py

Last updated:  2023-06-17

Edit pupil data.


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
    from ui.ui_base import StandalonePage as Page
    start.setup(os.path.join(basedir, 'TESTDATA'))
else:
    from ui.ui_base import StackPage as Page

T = TRANSLATIONS("ui.modules.pupil_editor")

### +++++

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
from ui.dialogs.dialog_text_line_message import TextLineDialog
from ui.dialogs.dialog_text_line_offer import TextLineOfferDialog
from ui.dialogs.dialog_choose_class import ClassSelectDialog
from ui.dialogs.dialog_pupil_groups import PupilGroupsDialog
from ui.dialogs.dialog_constraint_number import NumberConstraintDialog
from local.name_support import asciify, tvSplit
from local.pupil_support import pupil_name, check_pid_valid
from core.basic_data import get_classes, clear_cache

TABLE_FIELDS = ( # fields displayed in class table
    "FIRSTNAME",
    "LASTNAME",
    "LEVEL",
    "GROUPS",
)

#TODO:
PUPIL_FIELD_INFOS: {
# Diese werden im Programm verwendet:
#TODO: Perhaps a warning/info? (the entry will disappear if the class is changed!)
    "CLASS":        ("CLASS_CHOICE", "", True),
#TODO: T  ...
    "PID":          ("LINE", "", True),
    "SORT_NAME":    ("SORT_NAME?", "", True), #???
    "LASTNAME":     ("LINE", "", True),
    "FIRSTNAMES":   ("LINE", "", True),
    "FIRSTNAME":    ("LINE", "", True),
    "GROUPS":       ("GROUPS", "", False),
    "DATE_EXIT":    ("DATE_OR_EMPTY", "", False),
#TODO: The values must be in config!
    "LEVEL":        ("CHOICE", ["", "Gym", "RS", "HS"], False),
}

### -----

class PupilEditorPage(Page):
    def __init__(self):
        super().__init__()
        uic.loadUi(APPDATAPATH("ui/pupil_editor.ui"), self)
        self.pupil_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.extra_field2editor = {}
        for field, name, editor, choice, required in CONFIG["PUPILS_FIELDS"]:
            try:
                ed = getattr(self, field)
            except AttributeError:
                # Need to add field to <self.extra_fields>
                ed = QLineEdit()
                self.extra_fields.addRow(name, ed)
                ed.setReadOnly(True)
                ed.setObjectName(field)
                self.extra_field2editor[field] = ed
            ed.installEventFilter(self)

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
#            oname = obj.objectName()
            self.field_editor(obj) #, obj.mapToGlobal(QPoint(0,0)))
            return True
        else:
            # standard event processing
            return super().eventFilter(obj, event)

    def enter(self):
        open_database()
        clear_cache()
        self.init_data()

    def  init_data(self):
        self.class_list = get_classes().get_class_list()
        self.select_class.clear()
        self.select_class.addItems([c[1] for c in self.class_list])
        self.load_pupil_table()
        self.set_row(0)

    @Slot(int)
    def on_select_class_currentIndexChanged(self, i):
        self.load_pupil_table()
        self.set_row(0)

    def load_pupil_table(self):
        self.current_class = self.class_list[
            self.select_class.currentIndex()
        ][0]
        fields, records = db_read_full_table(
            "PUPILS",
            sort_field="SORT_NAME",
            CLASS=self.current_class,
        )
        # Populate the pupils table
        self.pupil_table.setRowCount(len(records))
        self.pupil_list = []
        self.pid2row = {}
        for r, rec in enumerate(records):
            rdict = {fields[i]: val for i, val in enumerate(rec)}
            self.pid2row[rdict["PID"]] = r
            self.pupil_list.append(rdict)
            c = 0
            for field in TABLE_FIELDS:
                cell_value = rdict[field]
                item = self.pupil_table.item(r, c)
                if not item:
                    item = QTableWidgetItem()
                    self.pupil_table.setItem(r, c, item)
                item.setText(cell_value)
                c += 1
        self.pupil_dict = None

    def set_pid(self, pid):
        self.set_row(self.pid2row[pid])

    def set_row(self, row):
        self.suppress_pupil_change = True
        nrows = self.pupil_table.rowCount()
        if nrows > 0:
            if row >= nrows:
                row = nrows - 1
            self.pupil_table.setCurrentCell(row, 0)
        self.suppress_pupil_change = False
        self.set_pupil()

    @Slot()
    def on_pupil_table_itemSelectionChanged(self):
        if self.suppress_pupil_change:
            return
        self.set_pupil()

    def set_pupil(self):
        row = self.pupil_table.currentRow()
        if row >= 0:
            self.pupil_dict = (pdata := self.pupil_list[row])
            self.pupil_id = pdata["PID"]
            self.pb_remove.setEnabled(True)
            self.frame_r.setEnabled(True)
        else:
            self.pupil_dict = None
            pdata = {}
            self.pupil_id = None
            self.pb_remove.setEnabled(False)
            self.frame_r.setEnabled(False)
        for pfline in CONFIG["PUPILS_FIELDS"]:
            k = pfline[0]
            v = pdata.get(k, "")
            try:
                getattr(self, k).setText(v)
            except AttributeError:
                self.extra_field2editor[k].setText(v)

    @Slot()
    def on_pb_new_clicked(self):
        """Add a new pupil.
        The fields will initially have dummy values.
        """
        raise TODO
        db_new_row(
            "PUPILS",
            **{f: "?" for f in TEACHER_FIELDS}
        )
        self.load_teacher_table()
        self.set_tid("?")

    @Slot()
    def on_pb_remove_clicked(self):
        """Remove the current pupil."""
# Warn that this is not normally the correct approach ... rather set
# an exit date.
        raise TODO
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
        row = self.pupil_table.currentRow()
        object_name = obj.objectName()
        val = self.pupil_dict[object_name]
        ### PUPIL fields
#TODO
        if object_name == "CLASS":
            result = ClassSelectDialog.popup(val)
            if result is not None:
                SHOW_INFO(T["CHANGED_CLASS"].format(
                    pname=pupil_name(self.pupil_dict),
                    klass=result
                ))
# ...                

        elif object_name == "SORT_NAME":
            f, t, l = tvSplit(
                self.pupil_dict["FIRSTNAME"],
                self.pupil_dict["LASTNAME"]
            )
            result = TextLineOfferDialog.popup(
                self.pupil_dict["SORT_NAME"],
                asciify(f"{l}_{t}_{f}" if t else f"{l}_{f}"),
                parent=self
            )
# ...                

        elif object_name == "GROUPS":
            result = PupilGroupsDialog.popup(val)
# ...                

        elif object_name == "PID":
            result = TextLineDialog.popup(
                val,
                message=T["CHANGE_PUPIL_ID_WARNING"],
                title=T["PUPIL_ID"]
            )
            if result is not None:
                if (e := check_pid_valid(result)):
                    SHOW_ERROR(e)
                    result = None
                elif not SHOW_CONFIRM(T["PID_CONFIRM"]):
                    result = None
# ...                

#    "LASTNAME":     ("LINE", "", True),
#    "FIRSTNAMES":   ("LINE", "", True),
#    "FIRSTNAME":    ("LINE", "", True),
#    "DATE_EXIT":    ("DATE_OR_EMPTY", "", False),
##TODO: The values must be in config!
#    "LEVEL":        ("CHOICE", ["", "Gym", "RS", "HS"], False),


#TODO
        print("§§§ RESULT:", result)
        return

### Was:

        if object_name in (
            "TID", "FIRSTNAMES", "LASTNAME", "SIGNED", "SORTNAME"
        ):
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
            # The timetable-constraint fields
            if object_name in (
                "MIN_LESSONS_PER_DAY",
                "MAX_GAPS_PER_DAY",
                "MAX_GAPS_PER_WEEK",
                "MAX_CONSECUTIVE_LESSONS",
            ):
                result = NumberConstraintDialog.popup(
                    obj.text(),
                    parent=self
                )
                if result is not None:
                    db_update_field(
                        "TT_TEACHERS",
                        object_name,
                        result,
                        TID=self.teacher_id
                    )
                    obj.setText(result)
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

    @Slot(str)
    def on_LUNCHBREAK_currentTextChanged(self, weight):
        if weight == '-':
            self.LUNCHBREAK.setCurrentIndex(-1)
            return
        if self.current_lunchbreak != weight:
            db_update_field(
                "TT_TEACHERS",
                "LUNCHBREAK",
                weight,
                TID=self.teacher_id
            )
            self.current_lunchbreak = weight


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from ui.ui_base import run

    widget = PupilEditorPage()
    widget.enter()
    widget.resize(1000, 550)
    run(widget)
