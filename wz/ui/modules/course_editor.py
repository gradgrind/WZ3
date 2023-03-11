"""
ui/modules/course_editor.py

Last updated:  2023-03-11

Edit course and blocks+lessons data.


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

    # start.setup(os.path.join(basedir, 'TESTDATA'))
    # start.setup(os.path.join(basedir, "DATA-2023"))
    start.setup(os.path.join(basedir, "DATA-2024"))
else:
    from ui.ui_base import StackPage as Page

T = TRANSLATIONS("ui.modules.course_editor")

### +++++

from typing import NamedTuple
from importlib import import_module
from core.db_access import (
    open_database,
    db_read_fields,
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
from core.classes import Classes
from core.basic_data import (
    Workload,
    clear_cache,
    get_payment_weights,
    get_subjects,
    sublessons,
    get_simultaneous_weighting,
    BlockTag,
)

from ui.ui_base import (
    HLine,
    LoseChangesDialog,
    KeySelector,
    RowSelectTable,
    FormLineEdit,
    FormComboBox,
    ForeignKeyItemDelegate,
    ### QtWidgets:
    QSplitter,
    QFrame,
    QFormLayout,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QDialogButtonBox,
    QTableWidgetItem,
    QTableView,
    QDialog,
    QWidget,
    QStackedLayout,
    QAbstractItemView,
    QCheckBox,
    QHeaderView,
    ### QtGui:
    QIcon,
    ### QtCore:
    Qt,
    QObject,
    QEvent,
    Slot,
    QPoint,
    ### QtSql:
    QSqlTableModel,
    ### uic
    uic,
)

IMPORTS = {
#?
    "course_fields": "ui.dialogs.dialog_course_fields",

    "wish_time": "ui.dialogs.dialog_day_period",
    "wish_room": "ui.dialogs.dialog_room_choice",
    "payment": "ui.dialogs.dialog_workload",
    "block_name": "ui.dialogs.dialog_block_name",
    "parallel": "ui.dialogs.dialog_parallel_lessons",
#?
    "lesson_length": "",
    "notes": "",
}
from ui.dialogs.dialog_course_fields import CourseEditorForm
from ui.dialogs.dialog_day_period import edit_time
from ui.dialogs.dialog_room_choice import edit_room
from ui.dialogs.dialog_workload import edit_workload
from ui.dialogs.dialog_block_name import edit_block
from ui.dialogs.dialog_parallel_lessons import ParallelsDialog

#?
#from ui.course_dialogs import (
#    CourseEditorForm,
#
#
#    set_coursedata,
#    get_coursedata,
#    GroupSelector,
#    #    DurationSelector,
#    #    DayPeriodSelector,
#    #    PartnersSelector,
#    PaymentSelector,
#    RoomSelector,
#    #    partners,
#    #DayPeriodDelegate,
#    DayPeriodDialog,
#    DurationDelegate,
#    #    PartnersDelegate,
#    BlockTagSelector,
#    BlockTagDialog,
#    #    parse_time_field,
#    #    get_time_entry,
#    TableWidget,
#    courses_with_lessontag,
#)

# Course table fields
#TODO: still needed?
COURSE_COLS = [
    (f, T[f])
    for f in (
        "course",
        "CLASS",
        "GRP",
        "SUBJECT",
        "TEACHER",
        "REPORT",
        "GRADES",
        "REPORT_SUBJECT",
        "AUTHORS",
        "NOTES",
    )
]
# SUBJECT, CLASS and TEACHER are foreign keys with:
#  on delete cascade + on update cascade
FOREIGN_FIELDS = ("CLASS", "TEACHER", "SUBJECT")

COURSE_TABLE_FIELDS = ( # the fields shown in the course table
# (db-field name, column-type, horizontal text alignment)
# column-type:
#   -1: checkbox
#    0: db-value
#    1: display-value (from column-dependent map)
# alignment:
#   -1: left
#    0: centre
#    1: right
    ("CLASS", 0, 0),
    ("GRP", 0, 0),
    ("SUBJECT", 1, -1),
    ("TEACHER", 1, -1),
    ("REPORT", -1, 0),
    ("GRADES", -1, 0),
    ("INFO", 0, -1),
)

#FILTER_FIELDS = [cc for cc in COURSE_COLS if cc[0] in FOREIGN_FIELDS]

# Group of fields which determines a course (the tuple must be unique)
#class COURSE_KEY(NamedTuple):
#    CLASS: str
#    GRP: str
#    SUBJECT: str
#    TEACHER: str
#
#    def __str__(self):
#        return f"({self.CLASS}:{self.GRP}:{self.SUBJECT}:{self.TEACHER})"
#COURSE_KEY(*[record.value(f) for f in COURSE_KEY._fields])
# print("§§§§§§§§§§§", COURSE_KEY._fields, str(COURSE_KEY("10G", "*", "Ma", "EA")))

#TODO: deprecated?
BLOCK_COLS = [
    (f, T[f])
    for f in (
        "id",
        "course",
        "PAYMENT",
        "ROOM",
        "LESSON_TAG",
        "NOTES",
    )
]

#TODO: deprecated?
BLOCKCOLS_SHOW = ("LESSON_TAG", "PAYMENT", "NOTES")

class LessonRowData(NamedTuple):
    """ROW_TYPE:
        -2 – no item (all other fields <None>)
        -1 – workload/payment item (only COURSE_LESSON_INFO not <None>)
         0 – "normal" lesson group (not a block)
         1 – block lesson group
    """
    ROW_TYPE: int
    COURSE_LESSON_INFO: dict
    LESSON_GROUP_INFO: dict
    LESSON_INFO: dict

### -----


def init():
    MAIN_WIDGET.add_tab(CourseEditorPage())


class CourseEditorPage(Page):
#?
    name = T["MODULE_NAME"]
    title = T["MODULE_TITLE"]

    def __init__(self):
        super().__init__()
        uic.loadUi(APPDATAPATH("ui/course_editor.ui"), self)
        self.icons = {
            "LESSON": QIcon.fromTheme("lesson"),
            "BLOCK": QIcon.fromTheme("lesson_block"),
            "PAY": QIcon.fromTheme("cash0a"),
        }
        self.course_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        # Set up activation for the editors for the read-only lesson/block
        # fields: 
        for w in (
            self.payment, self.wish_room, self.block_name,
            self.notes,
            self.lesson_length, self.wish_time, self.parallel,
        ):
            w.installEventFilter(self)

    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        """Event filter for the "lesson" fields.
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
#TODO?
        open_database()
        clear_cache()
        self.init_data()
        self.combo_filter.setCurrentIndex(-1)
        self.combo_filter.setCurrentIndex(0)

# ++++++++++++++ The widget implementation fine details ++++++++++++++

    def  init_data(self):
        print("§§§ init_data")

        teachers = Teachers()
        self.filter_list = {
            "CLASS": Classes().get_class_list(skip_null=False),
            "SUBJECT": get_subjects(),
            "TEACHER": [
                (tid, teachers.name(tid))
                for tid, tiddata in teachers.items()
            ]
        }
        self.course_field_editor = None
 
    @Slot(int)
    def on_combo_filter_currentIndexChanged(self, i):
        """Handle a change of filter field for the course table."""
        if i < 0:
            return
        # class, subject, teacher
        self.filter_field = FOREIGN_FIELDS[i]
        # print("§§§ on_combo_filter_currentIndexChanged", i, self.filter_field)
        self.select_list = self.filter_list[self.filter_field]
        self.combo_class.clear()
        for kv in self.select_list:
            self.combo_class.addItem(kv[1])

    @Slot(int)
    def on_combo_class_currentIndexChanged(self, i):
        """View selection changed, reload the course table.
        The method name is a bit of a misnomer, as the selector can be
        class, teacher or subject.
        """
        if i >= 0:
            self.load_course_table(i, 0)

    def load_course_table(self, select_index, table_row):
        self.filter_value = self.select_list[select_index][0]
        self.suppress_handlers = True
        fields, records = db_read_full_table(
            "COURSES", 
            sort_field="SUBJECT", 
            **{self.filter_field: self.filter_value}
        )
        # Populate the course table
        self.course_table.setRowCount(len(records))
        self.courses = []
        for r, rec in enumerate(records):
            rdict = {fields[i]: val for i, val in enumerate(rec)}
            self.courses.append(rdict)
            # print("  --", rdict)
            c = 0
            for cid, ctype, align in COURSE_TABLE_FIELDS:
                cell_value = rdict[cid]
                item = self.course_table.item(r, c)
                if not item:
                    item = QTableWidgetItem()
                    if align == -1:
                        a = Qt.AlignmentFlag.AlignLeft
                    elif align == 1:
                        a = Qt.AlignmentFlag.AlignRight
                    else:
                        a = Qt.AlignmentFlag.AlignHCenter
                    item.setTextAlignment(a | Qt.AlignmentFlag.AlignVCenter)
                    self.course_table.setItem(r, c, item)
                if ctype == 1:
#TODO: rather use a map?
                    for k, v in self.filter_list[cid]:
                        if k == cell_value:
                            item.setText(v)
                            break
                    else:
#TODO: T ...
                        REPORT(
                            "ERROR",
                            f"UNKNOWN VALUE IN FIELD '{cid}': '{cell_value}'"
                        )
                else:
                    item.setText(cell_value)
                c += 1
        self.suppress_handlers = False
        self.course_table.setCurrentCell(-1, 0)
        self.course_dict = None
        self.pb_delete_course.setEnabled(False)
        self.pb_edit_course.setEnabled(False)
        self.frame_r.setEnabled(False)
        if len(records) > 0:
            if table_row >= len(records):
                table_row = len(records) - 1
            self.course_table.setCurrentCell(table_row, 0)

    def on_course_table_itemSelectionChanged(self):
        row = self.course_table.currentRow()
        print("§§§ on_course_table_itemSelectionChanged", row)

#TODO
#    def course_selected(self, row):
#?        self.current_row = row
        if row >= 0:
            self.pb_delete_course.setEnabled(True)
            self.pb_edit_course.setEnabled(True)
            self.course_dict = self.courses[row]
            self.set_course(self.course_dict["course"])
#?            set_coursedata(
#                COURSE_KEY(*[record.value(f) for f in COURSE_KEY._fields])
#            )
            self.frame_r.setEnabled(True)
        else:
            # e.g. when entering an empty table
            print("EMPTY TABLE")

#TODO
    def set_course(self, course: int):
        print("SET COURSE:", repr(course))
#?        self.course_id = course

        fields, records = db_read_full_table(
            "COURSE_LESSONS", course=course
        )
        print("§§§ COURSE_LESSONS:", fields)

        self.lesson_table.setRowCount(0)
        self.course_lessons = []
        row = 0
        ### Build a list of entries
        ## First loop through entries in COURSE_LESSONS
#NOTE: There should be only one COURSE_LESSONS entry for "lesson"
# types and "payment" types. For "block" types there can be more than
# one entry, but they should be connected with LESSON_GROUP entries
# with distinct (non-empty) BLOCK_x values.
# If violations are discovered, there should be an error report. It
# might be helpful to delete the offending entries, but as they are
# really not expected – and should not be possible – it is perhaps
# better to report the offending entries, but not to delete them, so
# that they are available for debugging purposes – the report could
# be via a bug exception?

#TODO: I could use the trash function to remove the current course
# from the selected block – or to remove a lesson from the block.
# Instead of just removing somthing without asking (like with the
# other types), it could ask which sort of removal is desired:
#    remove course from block
#    remove lesson from block
#    cancel
# The add button could offer the choice of adding a lesson to the current
# block (if one is selected), or adding the course to another existing
# block, or starting a new block (initially with one lesson), or of
# cancelling the request.

# Also note how the parameters are set in various tables. The room
# wish and pay details apply to all lesson components as they are set in
# COURSE_LESSONS. Only the time wish is set in the lesson component.
# This may be a bit restrictive, but is perhaps reasonable for most
# cases. If it is really essential to have a particular room for a
# particular lesson (and another one, or a choice, for another lesson),
# perhaps some additional constraint could be added ...

#?
#        self.course_lesson_map = {}
        # key = block name; value = display row
        self.course_lesson_payment = 0 # for payment-only entries

        for rec in records:
            cldict = {fields[i]: val for i, val in enumerate(rec)}
            # <cldict> contains workload/payment and room-wish fields
            lg = cldict["lesson_group"]
            if lg:
                lgfields, lgrecord = db_read_unique_entry(
                    "LESSON_GROUP", lesson_group=lg
                )
                lgdata = {
                    lgfields[i]: val for i, val in enumerate(lgrecord)
                }
                # This contains the block-name, if any
                block_sid = lgdata["BLOCK_SID"]
                block_tag = lgdata["BLOCK_TAG"]

#?
#                # Check uniqueness
#                if block_name in self.course_lesson_map:
#                    raise Bug("Multiple entries in COURSE_LESSONS"
#                        f"for block '{block_name}', course {course}"
#                    )
#                    self.course_lesson_map[block_name] = row
                if block_sid:
                    etype = 1
                    icon = self.icons["BLOCK"]
                    bt = BlockTag.build(block_sid, block_tag)
                    lgdata["BlockTag"] = bt
                else:
                    etype = 0
                    icon = self.icons["LESSON"]
                lfields, lrecords = db_read_full_table(
                    "LESSONS", lesson_group=lg
                )
                lgdata["nLessons"] = len(lrecords)
                for lrec in lrecords:
                    self.lesson_table.insertRow(row)
                    ldata = {lfields[i]: val for i, val in enumerate(lrec)}
                    w = QTableWidgetItem(icon, "")
                    self.lesson_table.setItem(row, 0, w)
                    ln = ldata["LENGTH"]
                    w = QTableWidgetItem(str(ln))
                    self.lesson_table.setItem(row, 1, w)
                    if etype == 1:
                        w = QTableWidgetItem(bt.subject)
                        self.lesson_table.setItem(row, 2, w)
                    self.course_lessons.append(
                        LessonRowData(etype, cldict, lgdata, ldata)
                    )
                    row += 1
            else:
                # payment item
                if self.course_lesson_payment != 0:
                    raise Bug("Multiple entries in COURSE_LESSONS"
                        f"for payment-only item, course {course}"
                    )
#?
                self.course_lesson_payment = row

                self.lesson_table.insertRow(row)
                w = QTableWidgetItem(self.icons["PAY"], "")
                self.lesson_table.setItem(row, 0, w)
                w = QTableWidgetItem("–")
                self.lesson_table.setItem(row, 1, w)
                self.course_lessons.append(
                    LessonRowData(-1, cldict, None, None)
                )
                row += 1
        self.on_lesson_table_itemSelectionChanged()
#TODO: Is something like this needed?
# Toggle the stretch on the last section because of a possible bug in
# Qt, where the stretch can be lost when repopulating.
#        hh = table.horizontalHeader()
#        hh.setStretchLastSection(False)
#        hh.setStretchLastSection(True)


    @Slot()
    def on_pb_delete_course_clicked(self):
        """Delete the current course."""
        print("§DELETE COURSE")
#TODO
        row = self.course_table.currentRow()
        if row < 0:
            SHOW_ERROR("BUG: No course, delete button should be disabled")
            return
        if not SHOW_CONFIRM(T["REALLY_DELETE"]):
            return
        
        course_id = self.course_dict["course"]
        if db_delete_rows("COURSES", course=course_id):
#TODO: Check that the db tidying really occurs:
            # The foreign key constraints should tidy up the database.
            # Reload the course table
            self.load_course_table(self.combo_class.currentIndex(), row)

    @Slot(int,int)
    def on_course_table_cellDoubleClicked(self, r, c):
        self.edit_course(r)

    @Slot()
    def on_pb_edit_course_clicked(self):
        self.edit_course(self.course_table.currentRow())

    def edit_course(self, row):
        """Activate the course field editor."""
        changes = self.edit_course_fields(self.course_dict)
        if changes:
#TODO--
            print("§COURSE CHANGED:", changes)
            self.update_course(row, changes)

    def update_course(self, row, changes):
        course_id = self.course_dict["course"]
        if db_update_fields(
            "COURSES", 
            [(f, v) for f, v in changes.items()], 
            course=course_id,
        ):
            self.load_course_table(self.combo_class.currentIndex(), row)
        else:
            raise Bug(f"Course update ({course_id}) failed: {changes}")

    @Slot()
    def on_pb_new_course_clicked(self):
        """Add a new course.
        The fields of the current course, if there is one, will be taken
        as "template".
        """
        if self.course_dict:
            cdict = self.course_dict.copy()
        else:
            cdict = {
                "CLASS": "",
                "GRP": "",
                "SUBJECT": "",
                "TEACHER": "",
                "REPORT": "",
                "GRADES": "",
                "REPORT_SUBJECT": "",
                "AUTHORS": "",
                "INFO": "",
            }
            cdict[self.filter_field] = self.filter_value
        cdict["course"] = 0
        changes = self.edit_course_fields(cdict)
        if changes:
            cdict.update(changes)
            db_new_row("COURSES", **cdict)
            self.load_course_table(
                self.combo_class.currentIndex(), 
                self.course_table.currentRow()
            )

    def edit_course_fields(self, course_dict):
        if not self.course_field_editor:
            # Initialize dialog
            self.course_field_editor = CourseEditorForm(self.filter_list, self)
        return self.course_field_editor.activate(course_dict)

    def on_lesson_table_itemSelectionChanged(self):
        row = self.lesson_table.currentRow()
        print("§§§ on_lesson_table_itemSelectionChanged", row)
        # Populate the form fields
        if row < 0:
            self.current_lesson = LessonRowData(-2, None, None, None)
            self.lesson_add.setEnabled(False)
            self.lesson_sub.setEnabled(False)
            self.remove_element.setEnabled(False)
            self.payment.setEnabled(False)
            self.payment.clear()
        else:
            self.remove_element.setEnabled(True)
            self.payment.setEnabled(True)
            self.current_lesson = self.course_lessons[row]
            wd = Workload(**self.current_lesson.COURSE_LESSON_INFO)
            self.payment.setText(str(wd))
        if self.current_lesson.ROW_TYPE < 0:
            # payment entry or nothing selected
            self.lesson_length.clear()
            self.lesson_length.setEnabled(False)
            self.wish_room.clear()
            self.wish_room.setEnabled(False)
            self.block_name.clear()
            self.block_name.setEnabled(False)
            self.wish_time.clear()
            self.wish_time.setEnabled(False)
            self.parallel.clear()
            self.parallel.setEnabled(False)
            self.notes.clear()
            self.notes.setEnabled(False)
        else:
            self.lesson_add.setEnabled(True)
            if self.current_lesson.LESSON_GROUP_INFO["nLessons"] > 1:
                self.lesson_sub.setEnabled(True)
            self.lesson_length.setText(
                str(self.current_lesson.LESSON_INFO["LENGTH"])
            )
            self.lesson_length.setEnabled(True)
            self.wish_room.setText(
                self.current_lesson.COURSE_LESSON_INFO["ROOM"]
            )
            self.wish_room.setEnabled(True)
            self.block_name.setText(
                str(self.current_lesson.LESSON_GROUP_INFO["BlockTag"])
            )
            self.block_name.setEnabled(True)
            self.wish_time.setText(self.current_lesson.LESSON_INFO["TIME"])
            self.wish_time.setEnabled(True)
            try:
                t, w = db_read_unique(
                    "PARALLEL_LESSONS",
                    ["TAG", "WEIGHTING"], 
                    lesson_id=self.current_lesson.LESSON_INFO["id"]
                )
            except NoRecord:
                self.parallel.clear()
            else:
                self.parallel.setText(f'{t} @ {w}')
            self.parallel.setEnabled(True)
            self.notes.setText(self.current_lesson.LESSON_GROUP_INFO["NOTES"])
            self.notes.setEnabled(True)
            
    def field_editor(self, obj: QLineEdit):
        object_name = obj.objectName()
        print("EDIT", object_name)
        ### PAYMENT (COURSE_LESSONS)
        if object_name == "payment":
            result = edit_workload(self.current_lesson.COURSE_LESSON_INFO)
            if result is not None:
                obj.setText(result)
        ### ROOM (COURSE_LESSONS)
        elif object_name == "wish_room":
            result = edit_room(
                self.current_lesson.COURSE_LESSON_INFO,
                Classes().get_classroom(
                    self.course_dict["CLASS"], null_ok=True
                )
            )
            if result is not None:
                obj.setText(result)
        ### BLOCK (LESSON_GROUP)
        elif object_name == "block_name":
            result = edit_block(self.current_lesson.LESSON_GROUP_INFO)
            if result is not None:
                obj.setText(result)
#TODO: This will need a redisplay, because of the entry in the lesson
# table.
# What about displaying the full block subject name (+ tag?)
# The subject could appear in the lesson table?, short form + tag
# in the "Kennung" field?

#TODO ...
        ### NOTES (LESSON_GROUP)
        elif object_name == "notes":
            pass
        ### LENGTH (LESSONS)
        elif object_name == "lesson_length":
            pass
#redisplay?
        ### TIME (LESSONS)
        elif object_name == "wish_time":
            result = edit_time(self.current_lesson.LESSON_INFO)
            if result is not None:
                obj.setText(result)
        ### PARALLEL (LESSONS)
        elif object_name == "parallel":
            pass


    @Slot()
    def on_new_element_clicked(self):
#TODO
        print("§NEW ELEMENT")
        """Add a block course or a block lesson.
        If no block entry is selected, add a new course reference.
        This can be an existing course, in which case entries are added
        for each lesson in the block. If it is a really new course,
        add the necessary LESSON_GROUP and COURSE_LESSONS entries
        before adding a lesson for this new block.
        If a block entry is selected, add a lesson to the block.
        """
        if self.current_lesson.ROW_TYPE <= 0:
            # No block entry selected
            pass

    @Slot()
    def on_lesson_add_clicked(self):
#TODO
        print("§ADD LESSON")
        """Add a simple lesson or a block lesson to the current element.
        If no element is selected, this button should be disabled.
        """

    @Slot()
    def on_lesson_sub_clicked(self):
#TODO
        print("§SUB LESSON")

    @Slot()
#TODO
    def on_remove_element_clicked(self):
        print("§REMOVE ELEMENT")


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from ui.ui_base import run

    widget = CourseEditorPage()
    widget.enter()
    widget.resize(1000, 550)
    run(widget)
