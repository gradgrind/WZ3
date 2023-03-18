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

TEACHER_FIELDS = (
    "TID",
    "FIRSTNAMES",
    "LASTNAMES",
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
            self.TID, self.FIRSTNAMES, self.LASTNAMES,
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
        self.load_teacher_table(0)

    def load_teacher_table(self, table_row=None, tid=None):
        if tid is not None and table_row is not None:
            raise Bug("load_teacher_table: both table_row and tid supplied")
#?
        self.suppress_handlers = True

        fields, records = db_read_full_table(
            "TEACHERS",
            sort_field="SORTNAME",
        )
        # Populate the teachers table
        self.teacher_table.setRowCount(len(records))
        self.teacher_list = []
        for r, rec in enumerate(records):
            rdict = {fields[i]: val for i, val in enumerate(rec)}
            if tid is not None and rdict["TID"] == tid:
                table_row = r
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

        self.teacher_table.setCurrentCell(-1, 0)
        if len(records) > 0:
            if table_row is None:
                table_row = 0
            if table_row >= len(records):
                table_row = len(records) - 1
            self.teacher_table.setCurrentCell(table_row, 0)

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
        else:
            # e.g. when entering an empty table
            raise Bug("No teachers")

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
        tid = db_new_row(
            "TEACHERS",
            **{f: "?" for f in TEACHER_FIELDS}
        )
        print("$NEW", tid)
        self.load_teacher_table(tid=tid)

    @Slot()
    def on_pb_remove_clicked(self):
        """Remove the current teacher."""
        row = self.teacher_table.currentRow()
        if row < 0:
            raise Bug("No teacher selected")
        if not SHOW_CONFIRM(T["REALLY_DELETE"].format(**self.teacher_dict)):
            return
        if db_delete_rows("TEACHERS", TID=self.teacher_id):
#TODO: Check that the db tidying really occurs:
            # The foreign key constraints should tidy up the database.
            # Reload the teacher table
            self.load_teacher_table(row)





    def update_course(self, row, changes):
        if db_update_fields(
            "COURSES",
            [(f, v) for f, v in changes.items()],
            course=self.course_id,
        ):
            self.load_course_table(self.combo_class.currentIndex(), row)
        else:
            raise Bug(f"Course update ({self.course_id}) failed: {changes}")




    def edit_course_fields(self, course_dict):
        if not self.course_field_editor:
            # Initialize dialog
            self.course_field_editor = CourseEditorForm(self.filter_list, self)
        return self.course_field_editor.activate(course_dict)

    def on_lesson_table_itemSelectionChanged(self):
        row = self.lesson_table.currentRow()
        if self.lesson_table_suppress_update:
            return
        print("§§§ on_lesson_table_itemSelectionChanged", row)
        # Populate the form fields
        self.lesson_sub.setEnabled(False)
        if row < 0:
            self.current_lesson = LessonRowData(-2, None, None, None)
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
        print("EDIT", object_name)
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
        ### BLOCK (LESSON_GROUP)
        elif object_name == "block_name":
            lg = self.current_lesson.LESSON_GROUP_INFO
            result = BlockNameDialog.popup(
                blocktag=lg["BlockTag"],
                parent=self
            )
            if result is not None:
                db_update_fields(
                    "LESSON_GROUP",
                    [("BLOCK_SID", result.sid), ("BLOCK_TAG", result.tag)],
                    lesson_group=lg["lesson_group"]
                )
                # Redisplay lessons
                lesson_select_id = self.current_lesson.LESSON_INFO["id"]
                self.display_lessons(lesson_select_id)
        ### NOTES (LESSON_GROUP)
        elif object_name == "notes":
            lg = self.current_lesson.LESSON_GROUP_INFO
            result = TextLineDialog.popup(lg["NOTES"], parent=self)
            if result is not None:
                db_update_field(
                    "LESSON_GROUP",
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
        to this course) or may be completely new. If a simple lesson or
        a new completely new course is added, a single lesson is also
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
        btag = BlockNameDialog.popup(
            workload=workload,
            simple=simple,
            blocks=blockset,
            parent=self,
        )
        if btag:
            if btag.sid:
                lg = db_new_row(
                    "LESSON_GROUP",
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
                    "LESSON_GROUP",
                    NOTES="",
                )
            l = db_new_row(
                "LESSONS",
                lesson_group=lg,
                LENGTH=1,
            )
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
        the element (LESSON_GROUP entry) itself will be deleted.
        """
        cl = self.current_lesson.COURSE_LESSON_INFO["id"]
        lg = self.current_lesson.COURSE_LESSON_INFO["lesson_group"]
        db_delete_rows("COURSE_LESSONS", id=cl)
        records = db_read_full_table("COURSE_LESSONS", lesson_group=lg)[1]
        if len(records) == 0:
            db_delete_rows("LESSON_GROUP", lesson_group=lg)
        self.display_lessons(-1)


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from ui.ui_base import run

    widget = TeacherEditorPage()
    widget.enter()
    widget.resize(1000, 550)
    run(widget)
