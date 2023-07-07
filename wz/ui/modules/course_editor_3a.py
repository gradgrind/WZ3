"""
ui/modules/course_editor.py

Last updated:  2023-07-07

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
    start.setup(os.path.join(basedir, 'TESTDATA'))
else:
    from ui.ui_base import StackPage as Page

T = TRANSLATIONS("ui.modules.course_editor")

### +++++

from core.db_access import (
    open_database,
    db_select,
    db_read_unique,
    db_update_field,
    db_update_fields,
    db_new_row,
    db_delete_rows,
    db_values,
    NoRecord,
)
from core.teachers import Teachers
from core.basic_data_3 import (
    get_classes,
    clear_cache,
    get_subjects,
    ParallelTag,
    get_payment_weights,
    DECIMAL_SEP,
    BlockTag,
)
from core.course_data_3a import (
    filter_activities,
    workload_teacher,
    workload_class,
    lesson_pay_display,
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
from ui.dialogs.dialog_courses_field_mod import FieldChangeForm
from ui.dialogs.dialog_day_period import DayPeriodDialog
from ui.dialogs.dialog_room_choice import RoomDialog
from ui.dialogs.dialog_workload_3 import WorkloadDialog
from ui.dialogs.dialog_new_course_lesson_3a import NewCourseLessonDialog
from ui.dialogs.dialog_block_name_3a import BlockNameDialog
from ui.dialogs.dialog_parallel_lessons import ParallelsDialog
from ui.dialogs.dialog_text_line import TextLineDialog
from ui.dialogs.dialog_make_course_tables import ExportTable

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
        #open_database("wz.sqlite")
        #open_database("wz3.sqlite")
        open_database("wz_db.sqlite")
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
        self.course_field_changer = None

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
        fv = self.last_course[field] if self.last_course else None
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

    def load_course_table(self, select_index=-1, table_row=-1, lesson_id=-1):
        self.lesson_restore_id = lesson_id
        if select_index >= 0:
            self.filter_value = self.select_list[select_index][0]
        if table_row < 0:
            table_row = self.course_table.currentRow()
        self.course_activities = filter_activities(
            self.filter_field, self.filter_value
        )
        ## Populate the course table
        _sh = self.suppress_handlers
        self.suppress_handlers = True
        self.course_table.setRowCount(len(self.course_activities))
        self.course_list = []
        for r, course in enumerate(self.course_activities):
            self.course_list.append(
                cdatalist := self.course_activities[course]
            )
            #print("\n&&&")
            #for cd in cdatalist:
            #    print("  ++", cd)
            c = 0
            for cid, ctype, align in COURSE_TABLE_FIELDS:
                cell_value = cdatalist[0][cid]
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
        self.course_data = None
        self.pb_delete_course.setEnabled(False)
        self.pb_edit_course.setEnabled(False)
        self.frame_r.setEnabled(False)
        if (rn := len(self.course_activities)) > 0:
            if table_row >= rn:
                table_row = rn - 1
            self.course_table.setCurrentCell(table_row, 0)
        else:
            self.course_table.setCurrentCell(-1, 0)
        self.suppress_handlers = _sh
        self.on_course_table_itemSelectionChanged()
        self.lesson_restore_id = -1
        self.total_calc()

    def on_course_table_itemSelectionChanged(self):
        if self.suppress_handlers: return
        row = self.course_table.currentRow()
        lesson_id = self.lesson_restore_id
        if row >= 0:
            self.pb_delete_course.setEnabled(True)
            self.pb_edit_course.setEnabled(True)
            self.course_data = self.course_list[row][0]
            self.last_course = self.course_data     # for restoring views
            self.course_id = self.course_data["Course"]
            self.display_lessons(lesson_id)
            self.frame_r.setEnabled(True)
        else:
            # e.g. when entering an empty table
            self.lesson_table.setRowCount(0)
            self.course_data = None
            self.course_id = None

    def display_lessons(self, lesson_select_id: int):
        """Fill the lesson table for the current course (<self.course_id>).
        If <lesson_select_id> is 0, select the workload/payment element.
        If <lesson_select_id> is above 0, select the lesson with the given id.
        Otherwise select the first element (if there is one).
        """

        def is_shared_pay(key:int) -> str:
            """Determine whether a PAY_TAGS entry is used by multiple courses.
            """
            clist = db_values("COURSE_LESSONS", "Lesson_data", Lesson_data=key)
            return f"[{key}] " if len(clist) > 1 else ""

        self.suppress_handlers = True
        self.lesson_table.setRowCount(0)
        self.course_lessons = []
        ### Build a list of entries
        alist = self.course_activities[self.course_id]
        pay_only_l, simple_lesson_l, block_lesson_l = [], [], []
        subjects = get_subjects()
        for a in alist:
            lg = a["Lesson_group"]
            if lg == 0: # pay-only
                pay_only_l.append(a)
            elif lg > 0:
                #print("???", a)
                if (sid := a["BLOCK_SID"]): # block
                    blocksub = subjects.map(sid)
                    block_lesson_l.append((a, blocksub))
                else: # simple
                    simple_lesson_l.append(a)
        row = 0
        row_to_select = -1
        for pay_only in pay_only_l:
            # payment/workload item
            if lesson_select_id == row:
                row_to_select = row
            self.lesson_table.insertRow(row)
            w = QTableWidgetItem(self.icons["PAY"], "")
            w.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lesson_table.setItem(row, 0, w)
            w = QTableWidgetItem("–")
            w.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lesson_table.setItem(row, 1, w)
            w = QTableWidgetItem(
                is_shared_pay(pay_only["Lesson_data"])
            )
            self.lesson_table.setItem(row, 2, w)
            self.course_lessons.append((-1, pay_only))
            row += 1
        for simple_lesson in simple_lesson_l:
            shared = is_shared_pay(simple_lesson["Lesson_data"])
            # Add a lesson line
            self.lesson_table.insertRow(row)
            w = QTableWidgetItem(self.icons["LESSON"], "")
            w.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lesson_table.setItem(row, 0, w)
            ln = simple_lesson["LENGTH"]
            assert ln != 0
            w = QTableWidgetItem(str(ln))
            w.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lesson_table.setItem(row, 1, w)
            w = QTableWidgetItem(shared)
            self.lesson_table.setItem(row, 2, w)
            self.course_lessons.append((0, simple_lesson))
            if simple_lesson["Lid"] == lesson_select_id:
                row_to_select = row
            row += 1
        for bl, blocksub in block_lesson_l:
            shared = is_shared_pay(bl["Lesson_data"])
            # Add a lesson line
            self.lesson_table.insertRow(row)
            w = QTableWidgetItem(self.icons["BLOCK"], "")
            w.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lesson_table.setItem(row, 0, w)
            ln = bl["LENGTH"]
            w = QTableWidgetItem(str(ln))
            w.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lesson_table.setItem(row, 1, w)
            w = QTableWidgetItem(f"{shared}{blocksub}")
            self.lesson_table.setItem(row, 2, w)
            self.course_lessons.append((1, bl)
            )
            if bl["Lid"] == lesson_select_id:
                row_to_select = row
            row += 1
        if row_to_select < 0 and row > 0:
            row_to_select = 0
        self.lesson_table.setCurrentCell(row_to_select, 0)
        self.suppress_handlers = False
        self.on_lesson_table_itemSelectionChanged()

#TODO
    @Slot()
    def on_pb_delete_course_clicked(self):
        """Delete the current course."""
        row = self.course_table.currentRow()
        if row < 0:
            raise Bug("No course, delete button should be disabled")
        if not SHOW_CONFIRM(T["REALLY_DELETE"]):
            return
        if db_delete_rows("COURSES", course=self.course_id):
            # The foreign key constraints should tidy up the database to
            # a certain extent.
            # However, when the last reference to a WORKLOAD entry goes,
            # that entry must be removed here. If the removed entry contains
            # the last reference to a LESSON_GROUPS entry, also this entry
            # must be removed.
            q1 = """select
                    Workload,
                    Lesson_group
                from LESSON_GROUPS
                left join WORKLOAD using (Lesson_group)
                left join COURSE_WORKLOAD using (Workload)
                where Cw is null
            """
            for record in db_select(q1):
                w = record["Workload"]
                lg = record["Lesson_group"]
                # Then, on the basis of this query:
                q2 = f"""select
                        Workload,
                        Lesson_group
                    from LESSON_GROUPS
                    left join WORKLOAD using (Lesson_group)
                    where Lesson_group = {lg} and Workload != {w}
                """
                # ... decide whether to delete the LESSON_GROUPS or
                # the WORKLOAD entry.
                if db_select(q2):
                    # Just delete the WORKLOAD entry.
                    db_delete_rows("WORKLOAD", Workload=w)
                else:
                    # Delete the LESSON_GROUPS entry, and – via the foreign
                    # key constraint – also the WORKLOAD entry.
                    db_delete_rows("LESSON_GROUPS", Lesson_group=lg)
            # Reload the course table
            self.load_course_table(self.combo_class.currentIndex(), row)

    @Slot(int,int)
    def on_course_table_cellDoubleClicked(self, r, c):
        self.edit_course(r)

    @Slot()
    def on_pb_edit_course_clicked(self):
        self.edit_course(self.course_table.currentRow())

    @Slot()
    def on_pb_change_all_clicked(self):
        """Either all teacher fields or all class fields for the current
        teacher+class are to be changed to a new value.
        """
        if not self.course_data:
            return
        if not self.course_field_changer:
            # Initialize dialog
            self.course_field_changer = FieldChangeForm(
                self.filter_list, self
            )
        changes = self.course_field_changer.activate(
            self.course_data, self.filter_field
        )
        if changes:
            cid, tid, field, newval = changes
            chlist = []
            for cdatalist in self.course_list:
                cdata = cdatalist[0]
                if cdata["CLASS"] == cid and cdata["TEACHER"] == tid:
                    chlist.append(cdata["Course"])
            for course in chlist:
                #print("CHANGE", field, newval, course)
                db_update_field("COURSES", field, newval, course=course)
            self.load_course_table(
                self.combo_class.currentIndex(),
                self.course_table.currentRow()
            )

    def edit_course(self, row):
        """Activate the course field editor."""
        changes = self.edit_course_fields(self.course_data)
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
        if self.course_data:
            cdict0 = self.course_data.todict()
        else:
            cdict0 = {self.filter_field: self.filter_value}
        cdict = {
            k: cdict0.get(k, "")
            for k in (
                "CLASS",
                "GRP",
                "SUBJECT",
                "TEACHER",
                "REPORT",
                "GRADES",
                "REPORT_SUBJECT",
                "AUTHORS",
                "INFO",
            )
        }
        cdict["Course"] = 0
        changes = self.edit_course_fields(cdict)
        if changes:
            cdict.update(changes)
            del cdict["Course"]     # necessary for new entry
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
        if self.suppress_handlers: return
        # Populate the form fields
        self.lesson_sub.setEnabled(False)
        row = self.lesson_table.currentRow()
        bt = ""
        if row < 0:
            self.current_lesson = (-2, None)
            self.remove_element.setEnabled(False)
            self.payment.setEnabled(False)
            self.payment.clear()
            self.block_name.setEnabled(False)
        else:
            self.remove_element.setEnabled(True)
            self.payment.setEnabled(True)
            self.current_lesson = self.course_lessons[row]
            data = self.current_lesson[1]   # the Record object
            self.payment.setText(lesson_pay_display(data, with_value=True))
            self.block_name.setEnabled(True)
        if self.current_lesson[0] < 0:
            # payment entry or nothing selected
            self.lesson_add.setEnabled(False)
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
            if self.current_lesson[0] > 0:
                bt = BlockTag.to_string(data["BLOCK_SID"], data["BLOCK_TAG"])
            self.lesson_add.setEnabled(True)
            # Enable sub-lesson removal if there is more than one
            # lesson entry in the lesson-group.
            lg = data["Lesson_group"]
            for a in self.course_activities[self.course_id]:
                if a["Lesson_group"] == lg:
                    if a["Lid"] != data["Lid"]:
                        self.lesson_sub.setEnabled(True)
            self.lesson_length.setCurrentText(
                str(data["LENGTH"])
            )
            self.lesson_length.setEnabled(True)
            self.wish_room.setText(
                data["ROOM"]
            )
            self.wish_room.setEnabled(True)
            self.wish_time.setText(data["TIME"])
            self.wish_time.setEnabled(True)
            try:
                t, w = db_read_unique(
                    "PARALLEL_LESSONS",
                    ["TAG", "WEIGHTING"],
                    lesson_id=data["Lid"]
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
        self.block_name.setText(bt)

    def field_editor(self, obj: QLineEdit):
        object_name = obj.objectName()
        lthis = self.current_lesson[1] # the Record object
        lid = lthis["Lid"]
        ### PAYMENT (COURSE_LESSONS)
        if object_name == "payment":
            result = WorkloadDialog.popup(
                start_value=lthis, parent=self
            )
            if result is not None:
                # Update the db. A redisplay is only necessary because
                # all loaded "activities" with the same pay data must
                # be updated.
#TODO xxxxxxxxxxxxxxxxxxxxxx
                db_update_fields(
                    "PAY_TAGS",
                    result,
                    Lesson_data=lthis["Lesson_data"]
                )
                self.load_course_table(lesson_id=lid)
        ### ROOM (COURSE_LESSONS)
        elif object_name == "wish_room":
            classroom = get_classes().get_classroom(
                self.course_data["CLASS"], null_ok=True
            )
            result = RoomDialog.popup(
                start_value=lthis["ROOM"],
                classroom=classroom,
                parent=self
            )
            if result is not None:
                db_update_field(
                    "WORKLOAD",
                    "ROOM",
                    result,
                    workload=lthis["Workload"]
                )
                self.load_course_table(lesson_id=lid)
        ### BLOCK (LESSON_GROUPS)
        elif object_name == "block_name":
            row = self.lesson_table.currentRow()
            assert(row >= 0)
            result = BlockNameDialog.popup(
                # <course_data> is necessary for courses with no "lessons"
                # Otherwise the data could be taken from <course_lessons>.
                course_lessons=self.course_lessons,
                lesson_row=row,
                parent=self
            )
            if result is not None:
                assert(result["type"] == "CHANGE_BLOCK")
                bsid = result["BLOCK_SID"]
                btag = result["BLOCK_TAG"]
                db_update_fields(
                    "LESSON_GROUPS",
                    #[(r, result[r]) for r in ("BLOCK_SID", "BLOCK_TAG")],
                    [("BLOCK_SID", bsid), ("BLOCK_TAG", btag)],
                    lesson_group=lthis["Lesson_group"]
                )
                # Redisplay
                self.load_course_table(lesson_id=lid)
        ### NOTES (LESSON_GROUPS)
        elif object_name == "notes":
            result = TextLineDialog.popup(lthis["NOTES"], parent=self)
            if result is not None:
                db_update_field(
                    "LESSON_GROUPS",
                    "NOTES",
                    result,
                    lesson_group=lthis["Lesson_group"]
                )
                self.load_course_table(lesson_id=lid)
        ### LENGTH (LESSONS) --- own handler: on_lesson_length_ ...
        ### TIME (LESSONS)
        elif object_name == "wish_time":
            result = DayPeriodDialog.popup(
                start_value=lthis["TIME"],
                parent=self
            )
            if result is not None:
                db_update_field(
                    "LESSONS",
                    "TIME",
                    result,
                    lid=lid
                )
                self.load_course_table(lesson_id=lid)
        ### PARALLEL (LESSONS)
        else:
            assert object_name == "parallel", (
                f"Click event on object {object_name}"
            )
            result = ParallelsDialog.popup(
                self.current_parallel_tag, parent=self
            )
            if result is not None:
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
                self.current_parallel_tag = result
                self.load_course_table(lesson_id=lid)

    def total_calc(self):
        """For teachers and classes determine the total workload.
        For classes, the (sub-)groups will be taken into consideration, so
        that groups with differing total will be shown.
        """
        if self.filter_field == "CLASS":
            activities = []
            for alist in self.course_list:
                for a in alist:
                    g = a["GRP"]
                    if g:   # pupils involved
                        activities.append((g, a))
            totals = workload_class(self.filter_value, activities)
            if len(totals) == 1:
                g, n = totals[0]
                assert not g, f"unexpected single group: {g}"
                text = str(n)
            else:
                text = " ;  ".join((f"{g}: {n}") for g, n in totals)
            self.total.setText(text)
            self.total.setEnabled(True)
        elif self.filter_field == "TEACHER":
            activities = []
            for alist in self.course_list:
                for a in alist:
                    activities.append(a)
            nlessons, total = workload_teacher(activities)
            self.total.setText(T["TEACHER_TOTAL"].format(
                n=nlessons, total=f"{total:.2f}".replace('.', DECIMAL_SEP)
            ))
            self.total.setEnabled(True)
        else:
            self.total.clear()
            self.total.setEnabled(False)

    @Slot(str)
    def on_lesson_length_textActivated(self, i):
        ival = int(i)
        lthis = self.current_lesson[1]
        if lthis["LENGTH"] != ival:
            lid = lthis["Lid"]
            db_update_field(
                "LESSONS",
                "LENGTH", ival,
                lid=lid
            )
            # Redisplay
            self.load_course_table(lesson_id=lid)

#TODO
    @Slot()
    def on_new_element_clicked(self):
        """Add an item type: block, simple lesson or workload/payment.
        The item can be completely new or share a LESSON_GROUP (block
        only) or WORKLOAD entry.
        All the fiddly details are taken care of in <NewCourseLessonDialog>,
        which should only return valid results.
        If a completely new simple or block lesson is added, a single
        lesson is also added to the LESSONS table.
        """
        # <self.course_data> is – effectively – a random record for the
        # current course, the first one in the list returned by
        # <filter_activities(...)>.
        # It is not necessarily that of the currently selected "lesson".
        bn = NewCourseLessonDialog.popup(
            course_data=self.course_data,
# Is the next one necessary?
            course_lessons=self.course_lessons,
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
                lesson_group = 0
                wld = db_new_row(
                    "WORKLOAD",
                    lesson_group=lesson_group,
                    PAY_TAG=f"1*{get_payment_weights()[0][0]}",
                    ROOM="$"
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
                ROOM="$"
            )
        assert(wld)
        assert(self.course_id)
        cw = db_new_row(
            "COURSE_WORKLOAD",
            course=self.course_id,
            workload=wld,
        )
        # Redisplay
        self.load_course_table(lesson_id=l)

    @Slot()
    def on_lesson_add_clicked(self):
        """Add a lesson to the current element. If this is a block, that
        of course applies to the other participating courses as well.
        If no element (or a pay-only element) is selected, this button
        should be disabled.
        """
        lthis = self.current_lesson[1]
        newid = db_new_row(
            "LESSONS",
            lesson_group=lthis["Lesson_group"],
            LENGTH=lthis["LENGTH"]
        )
        self.load_course_table(lesson_id=newid)

    @Slot()
    def on_lesson_sub_clicked(self):
        """Remove a lesson from the current element. If this is a block,
        the removal of course applies to the other participating courses
        as well. If no element, a pay-only element or an element with
        only one lesson is selected, this button should be disabled.
        """
        lthis = self.current_lesson[1]
        newids = db_values(
            "LESSONS",
            "lid",
            lesson_group=lthis["Lesson_group"]
        )
        newids.remove(lid := lthis["Lid"])
        assert newids, (
            f"Tried to delete LESSON with lid={lid}"
            " although it is the only one for this element"
        )
        db_delete_rows("LESSONS", lid=lid)
        self.load_course_table(lesson_id=newids[-1])

    @Slot()
    def on_remove_element_clicked(self):
        """Remove the current element (pay-only or lesson-group) from
        the current course – that is the COURSE_LESSONS entry.
        If there are no other COURSE_LESSONS entries with the same
        lesson-group, the associated lessons will also be deleted.
        """
        cldata = self.current_lesson[1]
        lg = cldata["Lesson_group"]
        Lesson_data = cldata["Lesson_data"]
        # Delete COURSE_LESSONS entry
        db_delete_rows("COURSE_LESSONS", cl_id=cldata["Cl_id"])
        # Delete associated lessons if they are no longer referenced
        if not db_values(
            "COURSE_LESSONS",
            "cl_id",
            lesson_group=lg
        ):
            db_delete_rows("PAY_TAGS", lesson_group=lg)
        # Delete PAY_TAGS entry if it is no longer referenced
        if not db_values(
            "COURSE_LESSONS",
            "cl_id",
            Lesson_data=Lesson_data
        ):
            db_delete_rows("PAY_TAGS", Lesson_data=Lesson_data)
        # Reload course data
        self.load_course_table()

    @Slot()
    def on_make_tables_clicked(self):
        ExportTable(parent=self).activate()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from ui.ui_base import run

    widget = CourseEditorPage()
    widget.enter()
    widget.resize(1000, 550)
    run(widget)
