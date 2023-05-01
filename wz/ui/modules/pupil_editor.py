"""
ui/modules/pupil_editor.py

Last updated:  2023-05-01

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

#TODO: just copied from teacher editor ...
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

T = TRANSLATIONS("ui.modules.pupil_editor")

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
from ui.dialogs.dialog_text_line_offer import TextLineOfferDialog
from ui.dialogs.dialog_number_constraint import NumberConstraintDialog
from local.name_support import asciify, tvSplit
from core.basic_data import get_classes

PUPIL_FIELDS = ( # fields displayed in class table
    "FIRSTNAME",
    "LASTNAME",
    "LEVEL",
    "GROUPS",
)

### -----

class PupilEditorPage(Page):
    def __init__(self):
        super().__init__()
        uic.loadUi(APPDATAPATH("ui/pupil_editor.ui"), self)
        self.pupil_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        # Set up activation for the editors for the read-only lesson/block
        # fields:
        for w in (
            self.PID, #self.CLASS,
            self.FIRSTNAME, self.FIRSTNAMES,
            self.LASTNAME, self.SORT_NAME,
            self.GROUPS, #self.LEVEL,
            #self.SEX, self.DATE_BIRTH, self.DATE_ENTRY,
            self.BIRTHPLACE, self.HOME,
            self.DATE_EXIT, self.DATE_QPHASE,
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
        print("§CLASS INDEX", i)
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
            for field in PUPIL_FIELDS:
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
        nrows = self.pupil_table.rowCount()
        self.pupil_table.setCurrentCell(-1, 0)
        if nrows > 0:
            if row >= nrows:
                row = nrows - 1
            self.pupil_table.setCurrentCell(row, 0)

    def on_pupil_table_itemSelectionChanged(self):
        row = self.pupil_table.currentRow()
        if row >= 0:
            self.pupil_dict = self.pupil_list[row]
            self.set_pupil()
            self.pb_remove.setEnabled(row > 0)
            self.frame_r.setEnabled(row > 0)

    def set_pupil(self):
        self.pupil_id = self.pupil_dict["PID"]
        for k, v in self.pupil_dict.items():
            getattr(self, k).setText(v)

    @Slot()
    def on_pb_new_clicked(self):
        """Add a new teacher.
        The fields will initially have dummy values.
        """
        raise TODO
        db_new_row(
            "TEACHERS",
            **{f: "?" for f in TEACHER_FIELDS}
        )
        self.load_teacher_table()
        self.set_tid("?")

    @Slot()
    def on_pb_remove_clicked(self):
        """Remove the current teacher."""
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
        row = self.teacher_table.currentRow()
        object_name = obj.objectName()
        ### TEACHER fields
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
