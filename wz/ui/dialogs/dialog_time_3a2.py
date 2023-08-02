"""
ui/dialogs/dialog_time.py

Last updated:  2023-08-02

Supporting "dialog" for the course editor – handle the TIME field
(LESSONS table):
    - select day & period.
    - select pairing with other lesson (same time)


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
    start.setup(os.path.join(basedir, 'TESTDATA'))

#T = TRANSLATIONS("ui.dialogs.dialog_day_period")

### +++++

from typing import Optional

from core.basic_data_3 import (
    get_days,
    get_periods,
    timeslot2index,
    index2timeslot,
    get_classes,
)
from core.db_access import db_select, db_read_fields
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    ### QtGui:
    ### QtCore:
    ### other
    uic,
    Slot,
)

### -----

class DayPeriodDialog(QDialog):
    @classmethod
    def popup(cls, start_value="", lesson_id=0, parent=None, pos=None):
        d = cls(parent)
        d.init()
        if pos:
            d.move(pos)
        return d.activate(start_value, lesson_id)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_time.ui"), self)
        self.pb_reset = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Reset
        )
        self.pb_reset.clicked.connect(self.reset)
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )

    def accept(self):
        if self.stackedWidget.currentIndex() == 0:
            self.result = index2timeslot(
                (self.daylist.currentRow(), self.periodlist.currentRow())
            )
        else:
            w = self.weight.currentText()
            lid = self.selected_lid
            self.result = f"^{lid}@{w}"
        super().accept()

    def reset(self):
        self.result = ""
        super().accept()

    def init(self):
        self.daylist.clear()
        self.daylist.addItems([d[1] for d in get_days()])
        self.periodlist.clear()
        self.periodlist.addItems([p[1] for p in get_periods()])

    def activate(self, start_value: str, lesson_id: int
    ) -> Optional[str]:
        self.result = None
        self.value = None
        self.lesson_id = lesson_id
        self.selected_lid = 0
        self.start_lid = 0
        self.start_w = ""
        self.suppress_events = True
        self.pb_reset.setVisible(bool(start_value))
        self.dp0 = (-1, -1)
        d, p = 0, 0
        self.stackedWidget.setCurrentIndex(0)
        self.show_classes()
        if start_value.startswith("^"):
            # Parallel
            try:
                lid, self.start_w = start_value[1:].split("@")
                self.start_lid = int(lid)
                q = f"""select
                    Lesson_group,
                    CLASS
                    --GRP,
                    --SUBJECT,
                    --TEACHER,
                    --BLOCK_SID,
                    --BLOCK_TAG

                    from LESSONS
                    inner join COURSE_LESSONS using (Lesson_group)
                    --inner join LESSON_GROUPS using (Lesson_group)
                    inner join COURSES using (Course)
                    where Lid = '{lid}'
                """
                cdlist = db_select(q)
                if cdlist:
                    cdata = cdlist[0]
                else:
                    raise ValueError
                self.select_parallel(
                    cdata["CLASS"], cdata["Lesson_group"], self.start_lid
                )
                self.weight.setCurrentText(self.start_w)
                self.rb_parallel.setChecked(True)
                self.stackedWidget.setCurrentIndex(1)
            except ValueError:
#TODO: T ...?
                REPORT("ERROR", "START VALUE: {val}".format(val=start_value))

        else:
            try:
                d, p = timeslot2index(start_value)
                self.dp0 = (d, p)
                if d < 0:
                    d, p = 0, 0
            except ValueError as e:
                REPORT("ERROR", str(e))
        self.daylist.setCurrentRow(d)
        self.periodlist.setCurrentRow(p)
        self.acceptable()
        self.suppress_events = False
        self.exec()
        return self.result

    def show_classes(self):
        self.classes = []
        self.list_class.clear()
        for k, n in get_classes().get_class_list():
            self.list_class.addItem(n)
            self.classes.append(k)

    def select_parallel(self, klass, lesson_group, lesson_id):
        i = self.classes.index(klass)
        self.list_class.setCurrentRow(i)
        self.on_list_class_currentRowChanged(i)
        i = self.lg_list.index(lesson_group)
        self.list_course.setCurrentRow(i)
        self.on_list_course_currentRowChanged(i)
        i = self.lids.index(lesson_id)
        self.list_lesson.setCurrentRow(i)
        self.on_list_lesson_currentRowChanged(i)

    @Slot(int)
    def on_list_class_currentRowChanged(self, i):
        if i < 0:
            print("!!!", i)
            return
        klass = self.classes[i]
        print("??? CLASS:", klass)
        q = f"""select
            Lesson_group,
            GRP,
            SUBJECT,
            TEACHER,
            BLOCK_SID,
            BLOCK_TAG

            from COURSES
            inner join COURSE_LESSONS using (Course)
            inner join LESSON_GROUPS using (Lesson_group)

            where CLASS = '{klass}' and Lesson_group != '0'
        """
        blocks = set()
        course_list = []
        for data in db_select(q):
            if (bs := data["BLOCK_SID"]):
                # Block
                if (bs in blocks):
                    continue
                blocks.add(bs)
                course_list.append(
                    (f'[]{bs}#{data["BLOCK_SID"]}', data["Lesson_group"])
                )
            else:
                # Normal lesson
                grp = data["GRP"]
                sid = data["SUBJECT"]
                tid = data["TEACHER"]
                course_list.append(
                    (f"{sid} / {tid} ({grp})", data["Lesson_group"])
                )
        self.list_course.clear()
        self.lg_list = []
        for c, lg in sorted(course_list):
            self.list_course.addItem(f"{c}  -- [{lg}]")
            self.lg_list.append(lg)

    @Slot(int)
    def on_list_course_currentRowChanged(self, i):
        self.selected_lid = 0
        self.list_lesson.clear()
        if i < 0: return
        lg = self.lg_list[i]
        self.lids = []
        for lid, l, t in db_read_fields(
            "LESSONS",
            ("Lid", "LENGTH", "TIME"),
            Lesson_group=lg
        ):
            if lid == self.lesson_id: continue
            tx = f" @ {t}" if t else ""
            self.list_lesson.addItem(f"{l}{tx}  -- [{lid}]")
            self.lids.append(lid)

    @Slot(int)
    def on_list_lesson_currentRowChanged(self, i):
        if i >= 0:
            self.selected_lid = self.lids[i]
        if not self.suppress_events:
            self.acceptable()

    @Slot(bool)
    def on_rb_day_period_toggled(self, on):
        if self.suppress_events: return
        self.stackedWidget.setCurrentIndex(0 if on else 1)
        self.acceptable()

    @Slot(int)
    def on_daylist_currentRowChanged(self, i):
        if self.suppress_events: return
        self.acceptable()

    @Slot(int)
    def on_periodlist_currentRowChanged(self, i):
        if self.suppress_events: return
        self.acceptable()

    @Slot(int)
    def on_weight_currentIndexChanged(self, i):
        self.acceptable()

    def acceptable(self):
        if self.stackedWidget.currentIndex() == 0:
            dp = (self.daylist.currentRow(), self.periodlist.currentRow())
            self.pb_accept.setEnabled(dp != self.dp0)
        else:
            lid = self.selected_lid
            self.pb_accept.setEnabled(
                bool(lid)
                and (
                    lid != self.start_lid
                    or self.weight.currentText() != self.start_w
                )
            )


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database("wz_db.sqlite")
    print("----->", DayPeriodDialog.popup("^12@7", 13))
    print("----->", DayPeriodDialog.popup())
    print("----->", DayPeriodDialog.popup("Di.4"))
    print("----->", DayPeriodDialog.popup("Di.9"))
