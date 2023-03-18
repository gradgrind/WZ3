"""
ui/modules/teacher_editor.py

Last updated:  2023-03-18

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
from core.db_access import (
    open_database,
    db_read_unique,
    db_read_full_table,
    db_update_field,
    db_update_fields,
    db_new_row,
    db_delete_rows,
    db_values,
    db_read_unique_entry,
    NoRecord,
)
from core.teachers import Teachers
from ui.ui_base import (
    ### QtWidgets:
    QLineEdit,
    QTableWidgetItem,
    QWidget,
    QHeaderView,
    ### QtGui:
    QIcon,
    ### QtCore:
    Qt,
    QEvent,
    Slot,
    ### uic
    uic,
)
from ui.dialogs.dialog_text_line import TextLineDialog
from ui.dialogs.dialog_text_line_offer import TextLineOfferDialog
from local.name_support import asciify, tvSplit

TEACHER_FIELDS = (
    "TID",
    "FIRSTNAMES",
    "LASTNAME",
    "SIGNED",
    "SORTNAME",
)

TT_FIELDS = (
    "AVAILABLE",
    "MIN_LESSONS_PER_DAY",
    "MAX_GAPS_PER_DAY",
    "MAX_GAPS_PER_WEEK",
    "MAX_CONSECUTIVE_LESSONS",
)

### -----

class TeacherEditorPage(Page):
    def __init__(self):
        super().__init__()
        uic.loadUi(APPDATAPATH("ui/teacher_editor.ui"), self)
        self.teacher_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        # Set up activation for the editors for the read-only lesson/block
        # fields:
        for w in (
            self.TID, self.FIRSTNAMES, self.LASTNAME,
            self.SIGNED, self.SORTNAME,
            self.MIN_LESSONS_PER_DAY, self.MAX_GAPS_PER_DAY,
            self.MAX_GAPS_PER_WEEK, self.MAX_CONSECUTIVE_LESSONS,
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
#?
#         clear_cache()
        self.init_data()

# ++++++++++++++ The widget implementation fine details ++++++++++++++

    def  init_data(self):
        self.load_teacher_table()
        self.set_row(0)

    def load_teacher_table(self):
#?
        self.suppress_handlers = True

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
            # print("  --", rdict)
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
#?
        self.suppress_handlers = False

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
#        if self.suppress_handlers:
#            return
        row = self.teacher_table.currentRow()
        print("§§§ on_course_table_itemSelectionChanged", row)
        if row >= 0:
            self.teacher_dict = self.teacher_list[row]
            self.set_teacher()
        self.pb_remove.setEnabled(row > 0)
        self.frame_r.setEnabled(row > 0)

    def set_teacher(self):
        self.teacher_id = self.teacher_dict["TID"]
        for k, v in self.teacher_dict.items():
            getattr(self, k).setText(v)
        try:
            record = db_read_unique(
                "TT_TEACHER",
                TT_FIELDS,
                TID=self.teacher_id
            )
            ttdict = {f: record[i] for i, f in enumerate(TT_FIELDS)}
        except NoRecord:
            ttdict = {f: "" for f in TT_FIELDS}
        self.tt_available = ttdict.pop("AVAILABLE")
        for k, v in ttdict.items():
            getattr(self, k).setText(v)

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
        print("EDIT", object_name)
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
            if object_name == "MIN_LESSONS_PER_DAY":
                pass
            elif object_name == "MAX_GAPS_PER_DAY":
                pass
            elif object_name == "MAX_GAPS_PER_WEEK":
                pass
            elif object_name == "MAX_CONSECUTIVE_LESSONS":
                pass
            else:
                Bug(f"unknown field: {object_name}")

#TODO: AVAILABILITY ...


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from ui.ui_base import run

    widget = TeacherEditorPage()
    widget.enter()
    widget.resize(1000, 550)
    run(widget)
