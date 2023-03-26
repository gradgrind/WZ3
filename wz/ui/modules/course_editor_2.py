"""
ui/modules/course_editor.py

Last updated:  2023-03-26

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
    start.setup(os.path.join(basedir, "DATA-2024"))
else:
    from ui.ui_base import StackPage as Page

T = TRANSLATIONS("ui.modules.course_editor")

### +++++

from typing import NamedTuple
from core.db_access import (
    open_database,
    db_read_unique,
    db_read_full_table,
    db_update_field,
    db_update_fields,
    db_new_row,
    db_delete_rows,
    db_values,
    NoRecord,
)
from core.teachers import Teachers
from core.classes import Classes
from core.basic_data import (
    Workload,
    clear_cache,
    get_subjects,
    ParallelTag,
)
from core.course_data import filtered_courses, course_activities
from ui.ui_base import (
    ### QtWidgets:
    QLineEdit,
    QTableWidgetItem,
    QWidget,
    QHeaderView,
    QAbstractButton,
    ### QtGui:
    QIcon,
    ### QtCore:
    Qt,
    QEvent,
    Slot,
    ### uic
    uic,
)
from ui.dialogs.dialog_course_fields import CourseEditorForm
from ui.dialogs.dialog_day_period import DayPeriodDialog
from ui.dialogs.dialog_room_choice import RoomDialog
from ui.dialogs.dialog_workload import WorkloadDialog
from ui.dialogs.dialog_block_name import BlockNameDialog
from ui.dialogs.dialog_parallel_lessons import ParallelsDialog
from ui.dialogs.dialog_text_line import TextLineDialog

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

class LessonRowData(NamedTuple):
    """ROW_TYPE:
        -2 – no item (all other fields <None>)
        -1 – workload/payment item (only COURSE_LESSON_INFO not <None>)
         0 – "normal" lesson group (not a block)
         1 – block lesson group
    """
    ROW_TYPE: int
    WORKLOAD_INFO: Workload
    COURSE_LESSON_INFO: dict
    LESSON_GROUP_INFO: dict
    LESSON_INFO: dict

### -----

class CourseEditorPage(Page):
    def __init__(self):
        super().__init__()
        uic.loadUi(APPDATAPATH("ui/course_editor_2.ui"), self)
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
            #self.lesson_length,
            self.wish_time, self.parallel,
        ):
            w.installEventFilter(self)
        self.filter_field = "CLASS"
        self.last_course = None
        self.select2index = {}

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
        open_database()
        clear_cache()
        self.init_data()
        if self.filter_field == "CLASS": pb = self.pb_CLASS
        elif self.filter_field == "TEACHER": pb = self.pb_TEACHER
        else: pb = self.pb_SUBJECT
        self.disable_action = True
        pb.setChecked(True)
        self.disable_action = False
        self.set_combo(self.filter_field)

# ++++++++++++++ The widget implementation fine details ++++++++++++++

    def  init_data(self):
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

    @Slot(QAbstractButton)
    def on_buttonGroup_buttonClicked(self, pb):
        # CLASS, SUBJECT or TEACHER
        if self.disable_action: return
        oname = pb.objectName() 
        self.set_combo(oname.split("_", 1)[1])

    def set_combo(self, field):
        """Handle a change of filter field for the course table.
        Choose the initial value selection on the basis of the last
        selected course.
        """
        try:
            fv = self.last_course.get(field)
        except AttributeError:
            fv = None
        self.filter_field = field
        # class, subject, teacher
        self.select_list = self.filter_list[self.filter_field]
        self.combo_class.clear()
        self.select2index.clear()
        for n, kv in enumerate(self.select_list):
            self.select2index[kv[0]] = n
            self.combo_class.addItem(kv[1])
        self.combo_class.setCurrentIndex(
            self.select2index.get(fv, 0)
        )

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
        self.courses = filtered_courses(self.filter_field, self.filter_value)
        ## Populate the course table
        self.course_table.setRowCount(len(self.courses))
        for r, _course in enumerate(self.courses):
            c = 0
            for cid, ctype, align in COURSE_TABLE_FIELDS:
                cell_value = _course[cid]
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
                    for k, v in self.filter_list[cid]:
                        if k == cell_value:
                            item.setText(v)
                            break
                    else:
                        REPORT(
                            "ERROR",
                            T["UNKNOWN_VALUE_IN_FIELD"].format(
                                cid=cid, cell_value=cell_value
                            )
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
        if len(self.courses) > 0:
            if table_row >= len(self.courses):
                table_row = len(self.courses) - 1
            self.course_table.setCurrentCell(table_row, 0)

    def on_course_table_itemSelectionChanged(self):
        row = self.course_table.currentRow()
        # print("§§§ on_course_table_itemSelectionChanged", row)
        if row >= 0:
            self.pb_delete_course.setEnabled(True)
            self.pb_edit_course.setEnabled(True)
            self.course_dict = self.courses[row]
            self.last_course = self.course_dict     # for restoring views
            self.set_course(self.course_dict["course"])
            self.frame_r.setEnabled(True)
        else:
            # e.g. when entering an empty table
            self.lesson_table.setRowCount(0)
            self.course_dict = None
            self.course_id = None

    def set_course(self, course: int):
        # print("SET COURSE:", repr(course))
        self.course_id = course
        self.display_lessons(-1)

    def display_lessons(self, lesson_select_id: int):
        """Fill the lesson table for the current course (<self.course_id>).
        If <lesson_select_id> is 0, select the workload/payment element.
        If <lesson_select_id> is above 0, select the lesson with the given id.
        Otherwise select no element.
        """
        self.lesson_table_suppress_update = True
        self.lesson_table.setRowCount(0)
        self.course_lessons = []
        ### Build a list of entries
        pay_only, simple_lessons, block_lessons = course_activities(
            self.course_id
        )
        row = 0
        row_to_select = -1
        if pay_only:
            # payment/workload item
            if lesson_select_id == 0:
                row_to_select = row
            self.lesson_table.insertRow(row)
            w = QTableWidgetItem(self.icons["PAY"], "")
            self.lesson_table.setItem(row, 0, w)
            w = QTableWidgetItem("–")
            self.lesson_table.setItem(row, 1, w)
            self.course_lessons.append(
                LessonRowData(-1, *pay_only, None, None)
            )
            row += 1
        if simple_lessons:
            workload_data, cldict, lgdata, lessons = simple_lessons
            lgdata["nLessons"] = len(lessons)
            # Add a line for each lesson
            for ldata in lessons:
                self.lesson_table.insertRow(row)
                w = QTableWidgetItem(self.icons["LESSON"], "")
                self.lesson_table.setItem(row, 0, w)
                ln = ldata["LENGTH"]
                w = QTableWidgetItem(str(ln))
                self.lesson_table.setItem(row, 1, w)
                self.course_lessons.append(
                    LessonRowData(0, workload_data, cldict, lgdata, ldata)
                )
                if ldata["id"] == lesson_select_id:
                    row_to_select = row
                row += 1
        for bl in block_lessons:
            workload_data, cldict, lgdata, lessons, btag = bl
            # Additional info used by the course editor
            lgdata["nLessons"] = len(lessons)
            lgdata["BlockTag"] = btag
            # Add a line for each lesson
            for ldata in lessons:
                self.lesson_table.insertRow(row)
                w = QTableWidgetItem(self.icons["BLOCK"], "")
                self.lesson_table.setItem(row, 0, w)
                ln = ldata["LENGTH"]
                w = QTableWidgetItem(str(ln))
                self.lesson_table.setItem(row, 1, w)
                w = QTableWidgetItem(btag.subject)
                self.lesson_table.setItem(row, 2, w)
                self.course_lessons.append(
                    LessonRowData(1, workload_data, cldict, lgdata, ldata)
                )
                if ldata["id"] == lesson_select_id:
                    row_to_select = row
                row += 1
        self.lesson_table.setCurrentCell(row_to_select, 0)
        self.lesson_table_suppress_update = False
        self.on_lesson_table_itemSelectionChanged()

    @Slot()
    def on_pb_delete_course_clicked(self):
        """Delete the current course."""
        row = self.course_table.currentRow()
        if row < 0:
            raise Bug("No course, delete button should be disabled")
        if not SHOW_CONFIRM(T["REALLY_DELETE"]):
            return
        if db_delete_rows("COURSES", course=self.course_id):
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
            self.update_course(row, changes)

    def update_course(self, row, changes):
        if db_update_fields(
            "COURSES",
            [(f, v) for f, v in changes.items()],
            course=self.course_id,
        ):
            self.load_course_table(self.combo_class.currentIndex(), row)
        else:
            raise Bug(f"Course update ({self.course_id}) failed: {changes}")

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
        if self.lesson_table_suppress_update:
            return
        # print("§§§ on_lesson_table_itemSelectionChanged", row)
        # Populate the form fields
        self.lesson_sub.setEnabled(False)
        if row < 0:
            self.current_lesson = LessonRowData(-2, None, None, None, None)
            self.lesson_add.setEnabled(False)
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
            self.lesson_length.setCurrentIndex(-1)
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
            if self.current_lesson.ROW_TYPE > 0:
                self.block_name.setText(
                    str(self.current_lesson.LESSON_GROUP_INFO["BlockTag"])
                )
                self.block_name.setEnabled(True)
            else:
                self.block_name.clear()
                self.block_name.setEnabled(False)
            self.lesson_add.setEnabled(True)
            if self.current_lesson.LESSON_GROUP_INFO["nLessons"] > 1:
                self.lesson_sub.setEnabled(True)
            self.lesson_length.setCurrentText(
                str(self.current_lesson.LESSON_INFO["LENGTH"])
            )
            self.lesson_length.setEnabled(True)
            self.wish_room.setText(
                self.current_lesson.COURSE_LESSON_INFO["ROOM"]
            )
            self.wish_room.setEnabled(True)
            self.wish_time.setText(self.current_lesson.LESSON_INFO["TIME"])
            self.wish_time.setEnabled(True)
            try:
                t, w = db_read_unique(
                    "PARALLEL_LESSONS",
                    ["TAG", "WEIGHTING"],
                    lesson_id=self.current_lesson.LESSON_INFO["id"]
                )
            except NoRecord:
                self.current_parallel_tag = ParallelTag.build("", 0)
                self.parallel.clear()
            else:
                self.current_parallel_tag = ParallelTag.build(t, w)
                self.parallel.setText(str(self.current_parallel_tag))
            self.parallel.setEnabled(True)
            self.notes.setText(self.current_lesson.LESSON_GROUP_INFO["NOTES"])
            self.notes.setEnabled(True)

    def field_editor(self, obj: QLineEdit):
        object_name = obj.objectName()
        # print("EDIT", object_name)
        ### PAYMENT (COURSE_LESSONS)
        if object_name == "payment":
            cl = self.current_lesson.COURSE_LESSON_INFO
            result = WorkloadDialog.popup(start_value=cl, parent=self)
            if result is not None:
                # Update the db, no redisplay necessary
                udmap = [
                    (f, getattr(result, f))
                    for f in ("WORKLOAD", "PAY_FACTOR", "WORK_GROUP")
                ]
                db_update_fields(
                    "COURSE_LESSONS",
                    udmap,
                    id=cl["id"]
                )
                cl.update(dict(udmap))
                obj.setText(str(result))
        ### ROOM (COURSE_LESSONS)
        elif object_name == "wish_room":
            cl = self.current_lesson.COURSE_LESSON_INFO
            classroom = Classes().get_classroom(
                self.course_dict["CLASS"], null_ok=True
            )
            result = RoomDialog.popup(
                start_value=cl["ROOM"],
                classroom=classroom,
                parent=self
            )
            if result is not None:
                db_update_field(
                    "COURSE_LESSONS",
                    "ROOM",
                    result,
                    id=cl["id"]
                )
                cl["ROOM"] = result
                obj.setText(result)
        ### BLOCK (LESSON_GROUPS)
        elif object_name == "block_name":
            lg = self.current_lesson.LESSON_GROUP_INFO
            result = BlockNameDialog.popup(
                blocktag=lg["BlockTag"],
                parent=self
            )
            if result is not None:
                btag, lgnew = result
                assert(lgnew < 0)
                db_update_fields(
                    "LESSON_GROUPS",
                    [("BLOCK_SID", btag.sid), ("BLOCK_TAG", btag.tag)],
                    lesson_group=lg["lesson_group"]
                )
                # Redisplay lessons
                lesson_select_id = self.current_lesson.LESSON_INFO["id"]
                self.display_lessons(lesson_select_id)
        ### NOTES (LESSON_GROUPS)
        elif object_name == "notes":
            lg = self.current_lesson.LESSON_GROUP_INFO
            result = TextLineDialog.popup(lg["NOTES"], parent=self)
            if result is not None:
                db_update_field(
                    "LESSON_GROUPS",
                    "NOTES",
                    result,
                    lesson_group=lg["lesson_group"]
                )
                obj.setText(result)
        ### LENGTH (LESSONS) --- own handler: on_lesson_length_ ...
        ### TIME (LESSONS)
        elif object_name == "wish_time":
            l = self.current_lesson.LESSON_INFO
            result = DayPeriodDialog.popup(
                start_value=l["TIME"],
                parent=self
            )
            if result is not None:
                db_update_field(
                    "LESSONS",
                    "TIME",
                    result,
                    id=l["id"]
                )
                l["TIME"] = result
            if result is not None:
                obj.setText(result)
        ### PARALLEL (LESSONS)
        elif object_name == "parallel":
            result = ParallelsDialog.popup(
                self.current_parallel_tag, parent=self
            )
            if result is not None:
                lid=self.current_lesson.LESSON_INFO["id"]
                if self.current_parallel_tag.TAG:
                    # There is already a parallel record
                    if result.TAG:
                        # Change the tag and/or weighting
                        db_update_fields(
                            "PARALLEL_LESSONS",
                            [
                                ("TAG", result.TAG),
                                ("WEIGHTING", result.WEIGHTING),
                            ],
                            lesson_id = lid,
                        )
                    else:
                        # Remove the record
                        db_delete_rows(
                            "PARALLEL_LESSONS",
                            lesson_id = lid,
                        )
                else:
                    assert(result.TAG)
                    # Make a new parallel record
                    db_new_row(
                        "PARALLEL_LESSONS",
                        lesson_id = lid,
                        TAG=result.TAG,
                        WEIGHTING=result.WEIGHTING,
                    )
                obj.setText(str(result))
                self.current_parallel_tag = result
        else:
            raise Bug(f"Click event on object {object_name}")

    @Slot(str)
    def on_lesson_length_textActivated(self, i):
        ival = int(i)
        if self.current_lesson.LESSON_INFO["LENGTH"] != ival:
            lesson_select_id = self.current_lesson.LESSON_INFO["id"]
            db_update_field(
                "LESSONS",
                "LENGTH", ival,
                id=lesson_select_id
            )
            # Redisplay lessons
            self.display_lessons(lesson_select_id)

    @Slot()
    def on_new_element_clicked(self):
        """Add an item type: block, simple lesson or workload/payment.
        The item can only be added when its type is not already present
        for the course. A block may already exist (just add a reference
        to this course) or it may be completely new. If a simple lesson
        or a new completely new course is added, a single lesson is also
        added, together with the other necessary db table entries.
        """
        workload = True
        simple = True
        blockset = set()
        for cl in self.course_lessons:
            if cl.ROW_TYPE == -1:
                workload = False
            elif cl.ROW_TYPE == 0:
                simple = False
            elif cl.ROW_TYPE > 0:
                blockset.add(cl.LESSON_GROUP_INFO["BlockTag"])
        bn = BlockNameDialog.popup(
            workload=workload,
            simple=simple,
            blocks=blockset,
            parent=self,
        )
        if bn:
            btag, lg = bn
            if lg < 0:
                if btag.sid:
                    lg = db_new_row(
                        "LESSON_GROUPS",
                        BLOCK_SID=btag.sid,
                        BLOCK_TAG=btag.tag,
                        NOTES="",
                    )
                elif btag.tag == "$":
                    # Workload/payment, no lesson_group
                    cl = db_new_row(
                        "COURSE_LESSONS",
                        course=self.course_id,
                    )
                    # Redisplay lessons
                    self.display_lessons(0)
                    return
                else:
                    # "Simple" lesson_group
                    lg = db_new_row(
                        "LESSON_GROUPS",
                        NOTES="",
                    )
                l = db_new_row(
                    "LESSONS",
                    lesson_group=lg,
                    LENGTH=1,
                )
            else:
                l = -1
            cl = db_new_row(
                "COURSE_LESSONS",
                course=self.course_id,
                lesson_group=lg,
            )
            # Redisplay lessons
            self.display_lessons(l)

    @Slot()
    def on_lesson_add_clicked(self):
        """Add a lesson to the current element. If this is a block, that
        of course applies to the other participating courses as well.
        If no element (or a workload element) is selected, this button
        should be disabled.
        """
        li = self.current_lesson.LESSON_INFO
        newid = db_new_row(
            "LESSONS",
            lesson_group=li["lesson_group"],
            LENGTH=li["LENGTH"]
        )
        self.display_lessons(newid)

    @Slot()
    def on_lesson_sub_clicked(self):
        """Remove a lesson from the current element. If this is a block,
        the removal of course applies to the other participating courses
        as well. If no element, a workload element or an element with
        only one lesson is selected, this button should be disabled.
        """
        li = self.current_lesson.LESSON_INFO
        lid = li["id"]
        if self.current_lesson.LESSON_GROUP_INFO["nLessons"] < 2:
            raise Bug(
                f"Tried to delete LESSON with id={lid} although it is"
                " the only one for this element"
            )
        db_delete_rows("LESSONS", id=lid)
        newid = db_values(
            "LESSONS",
            "id",
            lesson_group=li["lesson_group"]
        )[-1]
        self.display_lessons(newid)

    @Slot()
    def on_remove_element_clicked(self):
        """Remove the current element from the current course.
        If no other courses reference the element (which is always
        the case for simple lessons and workload/payment elements),
        the element (LESSON_GROUPS entry) itself will be deleted.
        """
        cl = self.current_lesson.COURSE_LESSON_INFO["id"]
        lg = self.current_lesson.COURSE_LESSON_INFO["lesson_group"]
        db_delete_rows("COURSE_LESSONS", id=cl)
        records = db_read_full_table("COURSE_LESSONS", lesson_group=lg)[1]
        if len(records) == 0:
            db_delete_rows("LESSON_GROUPS", lesson_group=lg)
        self.display_lessons(-1)


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from ui.ui_base import run

    widget = CourseEditorPage()
    widget.enter()
    widget.resize(1000, 550)
    run(widget)
