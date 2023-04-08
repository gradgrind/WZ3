"""
ui/modules/course_editor.py

Last updated:  2023-04-08

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
from core.basic_data import (
    get_classes,
    Workload,
    clear_cache,
    get_subjects,
    ParallelTag,
    get_payment_weights,
    DECIMAL_SEP,
)
from core.course_data import (
    filtered_courses,
    course_activities,
    teacher_workload,
    class_workload,
)
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

'''
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
'''

### -----

class CourseEditorPage(Page):
    def __init__(self):
        super().__init__()
        uic.loadUi(APPDATAPATH("ui/course_editor.ui"), self)
        self.icons = {
            "LESSON": QIcon.fromTheme("lesson"),
            "BLOCK": QIcon.fromTheme("lesson_block"),
            "PAY": QIcon.fromTheme("cash"),
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
        pb.setChecked(True)
        self.set_combo(self.filter_field)

# ++++++++++++++ The widget implementation fine details ++++++++++++++

    def  init_data(self):
        teachers = Teachers()
        self.filter_list = {
            "CLASS": get_classes().get_class_list(skip_null=False),
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
        # Note: not called when <setChecked> is called on a member button
        oname = pb.objectName() 
        self.set_combo(oname.split("_", 1)[1])

    def set_combo(self, field):
        """Handle a change of filter field for the course table.
        Choose the initial value selection on the basis of the last
        selected course.
        """
        fv = self.last_course.get(field) if self.last_course else None
        self.filter_field = field
        # class, subject, teacher
        self.select_list = self.filter_list[self.filter_field]
        self.suppress_handlers = True
        self.combo_class.clear()
        self.select2index.clear()
        for n, kv in enumerate(self.select_list):
            self.select2index[kv[0]] = n
            self.combo_class.addItem(kv[1])
        self.combo_class.setCurrentIndex(
            self.select2index.get(fv, 0)
        )
        self.suppress_handlers = False
        self.on_combo_class_currentIndexChanged(
            self.combo_class.currentIndex()
        )

    @Slot(int)
    def on_combo_class_currentIndexChanged(self, i):
        """View selection changed, reload the course table.
        The method name is a bit of a misnomer, as the selector can be
        class, teacher or subject.
        """
        if self.suppress_handlers or i < 0: return
        self.load_course_table(i, 0)

    def load_course_table(self, select_index, table_row):
        self.filter_value = self.select_list[select_index][0]
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
        self.course_table.setCurrentCell(-1, 0)
        self.course_dict = None
        self.pb_delete_course.setEnabled(False)
        self.pb_edit_course.setEnabled(False)
        self.frame_r.setEnabled(False)
        if len(self.courses) > 0:
            if table_row >= len(self.courses):
                table_row = len(self.courses) - 1
            self.course_table.setCurrentCell(table_row, 0)
        self.total_calc()

    def on_course_table_itemSelectionChanged(self):
        row = self.course_table.currentRow()
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
        self.course_id = course
        self.display_lessons(-1)

    def display_lessons(self, lesson_select_id: int):
        """Fill the lesson table for the current course (<self.course_id>).
        If <lesson_select_id> is 0, select the workload/payment element.
        If <lesson_select_id> is above 0, select the lesson with the given id.
        Otherwise select no element.
        """
        def is_shared_workload(key:int) -> str:
            """Determine whether a WORKLOAD entry is used by multiple courses.
            """
            clist = db_values("COURSE_WORKLOAD", "course", workload=key)
            return f"[{key}] " if len(clist) > 1 else ""

        self.suppress_handlers = True
        self.lesson_table.setRowCount(0)
        self.course_lessons = []
        ### Build a list of entries
        (   pay_only_l,
            simple_lesson_l,
            block_lesson_l
        ) = course_activities(self.course_id)
        row = 0
        row_to_select = -1
        for pay_only in pay_only_l:
            # payment/workload item
            if lesson_select_id == row:
                row_to_select = row
            self.lesson_table.insertRow(row)
            w = QTableWidgetItem(self.icons["PAY"], "")
            self.lesson_table.setItem(row, 0, w)
            w = QTableWidgetItem("–")
            self.lesson_table.setItem(row, 1, w)
            w = QTableWidgetItem(is_shared_workload(pay_only["workload"]))
            self.lesson_table.setItem(row, 2, w)
            self.course_lessons.append((-1, pay_only, -1))
            row += 1
        for simple_lesson in simple_lesson_l:
            lessons = simple_lesson["lessons"]
            simple_lesson["nLessons"] = len(lessons)
            shared = is_shared_workload(simple_lesson["workload"])
            # Add a line for each lesson
            for i, ldata in enumerate(lessons):
                self.lesson_table.insertRow(row)
                w = QTableWidgetItem(self.icons["LESSON"], "")
                self.lesson_table.setItem(row, 0, w)
                ln = ldata["LENGTH"]
                w = QTableWidgetItem(str(ln))
                self.lesson_table.setItem(row, 1, w)
                w = QTableWidgetItem(shared)
                self.lesson_table.setItem(row, 2, w)
                self.course_lessons.append((0, simple_lesson, i))
                if ldata["id"] == lesson_select_id:
                    row_to_select = row
                row += 1
        for bl in block_lesson_l:
            # Additional info used by the course editor
            lessons = bl["lessons"]
            bl["nLessons"] = len(lessons)
            shared = is_shared_workload(bl["workload"])
            # Add a line for each lesson
            for i, ldata in enumerate(lessons):
                self.lesson_table.insertRow(row)
                w = QTableWidgetItem(self.icons["BLOCK"], "")
                self.lesson_table.setItem(row, 0, w)
                ln = ldata["LENGTH"]
                w = QTableWidgetItem(str(ln))
                self.lesson_table.setItem(row, 1, w)
                w = QTableWidgetItem(f"{shared}{bl['blocktag'].subject}")
                self.lesson_table.setItem(row, 2, w)
                self.course_lessons.append((1, bl, i)
                )
                if ldata["id"] == lesson_select_id:
                    row_to_select = row
                row += 1
        self.lesson_table.setCurrentCell(row_to_select, 0)
        self.suppress_handlers = False
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
            del cdict["course"]     # necessary for new entry
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
        if self.suppress_handlers:
            return
        # Populate the form fields
        self.lesson_sub.setEnabled(False)
        row = self.lesson_table.currentRow()
        if row < 0:
            self.current_lesson = (-2, None, -1)
            self.lesson_add.setEnabled(False)
            self.remove_element.setEnabled(False)
            self.payment.setEnabled(False)
            self.payment.clear()
            self.block_name.setEnabled(False)
            wl = ""
        else:
            self.remove_element.setEnabled(True)
            self.payment.setEnabled(True)
            self.current_lesson = self.course_lessons[row]
            data = self.current_lesson[1]
            self.payment.setText(data["PAY_TAG"])
            self.block_name.setEnabled(True)
            wl = f'[{data["workload"]}]'
        if self.current_lesson[0] < 0:
            # payment entry or nothing selected
            self.lesson_length.setCurrentIndex(-1)
            self.lesson_length.setEnabled(False)
            self.wish_room.clear()
            self.wish_room.setEnabled(False)
            self.wish_time.clear()
            self.wish_time.setEnabled(False)
            self.parallel.clear()
            self.parallel.setEnabled(False)
            self.notes.clear()
            self.notes.setEnabled(False)
        else:
            llist = data["lessons"]
            lthis = llist[self.current_lesson[2]]
            if self.current_lesson[0] > 0:
                wl = f'{wl} {str(data["blocktag"])}'
            self.lesson_add.setEnabled(True)
            if data["nLessons"] > 1:
                self.lesson_sub.setEnabled(True)
            self.lesson_length.setCurrentText(
                str(lthis["LENGTH"])
            )
            self.lesson_length.setEnabled(True)
            self.wish_room.setText(
                data["ROOM"]
            )
            self.wish_room.setEnabled(True)
            self.wish_time.setText(lthis["TIME"])
            self.wish_time.setEnabled(True)
            try:
                t, w = db_read_unique(
                    "PARALLEL_LESSONS",
                    ["TAG", "WEIGHTING"],
                    lesson_id=lthis["id"]
                )
            except NoRecord:
                self.current_parallel_tag = ParallelTag.build("", 0)
                self.parallel.clear()
            else:
                self.current_parallel_tag = ParallelTag.build(t, w)
                self.parallel.setText(str(self.current_parallel_tag))
            self.parallel.setEnabled(True)
            self.notes.setText(data["NOTES"])
            self.notes.setEnabled(True)
        self.block_name.setText(wl)

    def field_editor(self, obj: QLineEdit):
        object_name = obj.objectName()
        ### PAYMENT (COURSE_LESSONS)
        if object_name == "payment":
            cl = self.current_lesson[1]
            result = WorkloadDialog.popup(
                start_value=cl["PAY_TAG"], parent=self
            )
            if result is not None:
                # Update the db, no redisplay necessary
                db_update_field(
                    "WORKLOAD",
                    "PAY_TAG",
                    result,
                    workload=cl["workload"]
                )
                cl["PAY_TAG"] = result
                obj.setText(result)
                self.total_calc()
        ### ROOM (COURSE_LESSONS)
        elif object_name == "wish_room":
            cl = self.current_lesson[1]
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
                    "WORKLOAD",
                    "ROOM",
                    result,
                    workload=cl["workload"]
                )
                cl["ROOM"] = result
                obj.setText(result)
        ### BLOCK (LESSON_GROUPS)
        elif object_name == "block_name":
            row = self.lesson_table.currentRow()
            assert(row >= 0)
            result = BlockNameDialog.popup(
                course_data=self.course_dict,
                course_lessons=self.course_lessons,
                lesson_row=row,
                parent=self
            )
            if result is not None:
                assert(result["type"] == "CHANGE_BLOCK")
                lg = self.current_lesson[1]
                db_update_fields(
                    "LESSON_GROUPS",
                    [(r, result[r]) for r in ("BLOCK_SID", "BLOCK_TAG")],
                    lesson_group=lg["lesson_group"]
                )
                # Redisplay lessons
                llist = lg["lessons"]
                lthis = llist[self.current_lesson[2]]
                lesson_select_id = lthis["id"]
                self.display_lessons(lesson_select_id)
        ### NOTES (LESSON_GROUPS)
        elif object_name == "notes":
            lg = self.current_lesson[1]
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
            lg = self.current_lesson[1]
            llist = lg["lessons"]
            lthis = llist[self.current_lesson[2]]
            result = DayPeriodDialog.popup(
                start_value=lthis["TIME"],
                parent=self
            )
            if result is not None:
                db_update_field(
                    "LESSONS",
                    "TIME",
                    result,
                    id=lthis["id"]
                )
                lthis["TIME"] = result
            if result is not None:
                obj.setText(result)
        ### PARALLEL (LESSONS)
        elif object_name == "parallel":
            result = ParallelsDialog.popup(
                self.current_parallel_tag, parent=self
            )
            if result is not None:
                lg = self.current_lesson[1]
                llist = lg["lessons"]
                lthis = llist[self.current_lesson[2]]
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
                            lesson_id = lthis["id"],
                        )
                    else:
                        # Remove the record
                        db_delete_rows(
                            "PARALLEL_LESSONS",
                            lesson_id = lthis["id"],
                        )
                else:
                    assert(result.TAG)
                    # Make a new parallel record
                    db_new_row(
                        "PARALLEL_LESSONS",
                        lesson_id = lthis["id"],
                        TAG=result.TAG,
                        WEIGHTING=result.WEIGHTING,
                    )
                obj.setText(str(result))
                self.current_parallel_tag = result
        else:
            raise Bug(f"Click event on object {object_name}")

    def total_calc(self):
        """For teachers and classes determine the total workload.
        For classes, the (sub-)groups will be taken into consideration.
        """
        if self.filter_field == "CLASS":
            activities = []
            for c in self.courses:
                g = c["GRP"]
                if not g: continue  # No pupils involved
                for ctype in course_activities(c["course"]):
                    for data in ctype:
                        activities.append((g, data))
            totals = class_workload(self.filter_value, activities)
            self.total.setText(
                " ;  ".join((f"{g}: {n}") for g, n in totals)
            )
            self.total.setEnabled(True)
        elif self.filter_field == "TEACHER":
            activities = []
            for c in self.courses:
                for ctype in course_activities(c["course"]):
                    for data in ctype:
                        activities.append(data)
            nlessons, total = teacher_workload(activities)
            self.total.setText(T["TEACHER_TOTAL"].format(
                n=nlessons, total=str(total).replace('.', DECIMAL_SEP)
            ))
            self.total.setEnabled(True)
        else:
            self.total.clear()
            self.total.setEnabled(False)

    @Slot(str)
    def on_lesson_length_textActivated(self, i):
        ival = int(i)
        lg = self.current_lesson[1]
        llist = lg["lessons"]
        lthis = llist[self.current_lesson[2]]
        if lthis["LENGTH"] != ival:
            lesson_select_id = lthis["id"]
            db_update_field(
                "LESSONS",
                "LENGTH", ival,
                id=lesson_select_id
            )
            # Redisplay lessons
            self.display_lessons(lesson_select_id)
            self.total_calc()

    @Slot()
    def on_new_element_clicked(self):
        """Add an item type: block, simple lesson or workload/payment.
        The item can be completely new or share a LESSON_GROUP (block
        only) or WORKLOAD entry.
        All the fiddly details are taken care of in <BlockNameDialog>.
        This should only return valid results.
        If a completely new simple or block lesson is added, a single
        lesson is also added to the LESSONS table.
        """
        bn = BlockNameDialog.popup(
            course_data=self.course_dict,
            course_lessons=self.course_lessons,
            lesson_row=-1,
            parent=self
        )
        if not bn:
            return
        wld = None
        l = -1
        tp = bn["type"]
        if tp == "NEW":
            bsid = bn["BLOCK_SID"]
            btag = bn["BLOCK_TAG"]
            if bsid:
                # new block
                lesson_group = db_new_row(
                    "LESSON_GROUPS",
                    BLOCK_SID=bsid,
                    BLOCK_TAG=btag,
                    NOTES="",
                )
            elif btag == "$":
                # new payment-only
                lesson_group = None
                wld = db_new_row(
                    "WORKLOAD",
                    PAY_TAG="",
                )
            else:
                assert(not btag)
                # new simple lesson
                lesson_group = db_new_row(
                    "LESSON_GROUPS",
                    NOTES="",
                )
            if lesson_group:
                l = db_new_row(
                    "LESSONS",
                    lesson_group=lesson_group,
                    LENGTH=1,
                )
            else:
                l = 0
        elif tp == "ADD2BLOCK":
            lesson_group = bn["lesson_group"]
        else:
            assert(tp == "ADD2TEAM")
            lesson_group = None
            wld = bn["workload"]
        if lesson_group:
            wld = db_new_row(
                "WORKLOAD",
                lesson_group=lesson_group,
                PAY_TAG=f".*{get_payment_weights()[0][0]}",
            )
        assert(wld)
        assert(self.course_id)
        cw = db_new_row(
            "COURSE_WORKLOAD",
            course=self.course_id,
            workload=wld,
        )
        # Redisplay lessons
        self.display_lessons(l)
        self.total_calc()

    @Slot()
    def on_lesson_add_clicked(self):
        """Add a lesson to the current element. If this is a block, that
        of course applies to the other participating courses as well.
        If no element (or a workload element) is selected, this button
        should be disabled.
        """
        lg = self.current_lesson[1]
        llist = lg["lessons"]
        lthis = llist[self.current_lesson[2]]
        newid = db_new_row(
            "LESSONS",
            lesson_group=lg["lesson_group"],
            LENGTH=lthis["LENGTH"]
        )
        self.display_lessons(newid)
        self.total_calc()

    @Slot()
    def on_lesson_sub_clicked(self):
        """Remove a lesson from the current element. If this is a block,
        the removal of course applies to the other participating courses
        as well. If no element, a workload element or an element with
        only one lesson is selected, this button should be disabled.
        """
        lg = self.current_lesson[1]
        llist = lg["lessons"]
        lthis = llist[self.current_lesson[2]]
        if lg["nLessons"] < 2:
            raise Bug(
                f"Tried to delete LESSON with id={lthis['id']}"
                " although it is the only one for this element"
            )
        db_delete_rows("LESSONS", id=lthis["id"])
        newid = db_values(
            "LESSONS",
            "id",
            lesson_group=lg["lesson_group"]
        )[-1]
        self.display_lessons(newid)
        self.total_calc()

    @Slot()
    def on_remove_element_clicked(self):
        """Remove the current element from the current course –
        that is the COURSE_WORKLOAD entry.
        If no other courses reference the WORKLOAD entry, this will
        also be deleted. That can lead to an unreferenced LESSON_GROUPS
        entry, which must also be removed.
        """
        lg = self.current_lesson[1]
        db_delete_rows("COURSE_WORKLOAD", id=lg["id"])
        if not db_values(
            "COURSE_WORKLOAD",
            "course",
            workload=lg["workload"]
        ):
            db_delete_rows(
                "WORKLOAD",
                workload=lg["workload"]
            )
            if not db_values(
                "WORKLOAD",
                "lesson_group",
                lesson_group=lg["lesson_group"]
            ):
                db_delete_rows(
                    "LESSON_GROUPS",
                    lesson_group=lg["lesson_group"]
                )
        self.display_lessons(-1)
        self.total_calc()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from ui.ui_base import run

    widget = CourseEditorPage()
    widget.enter()
    widget.resize(1000, 550)
    run(widget)
