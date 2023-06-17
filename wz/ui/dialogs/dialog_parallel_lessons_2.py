"""
ui/dialogs/dialog_parallel_lessons.py

Last updated:  2023-06-17

Supporting "dialog" for the course editor – handle wishes for lessons
starting at the same time.


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

#T = TRANSLATIONS("ui.dialogs.dialog_parallel_lessons")

### +++++

from typing import Optional
from core.basic_data import (
    TAG_FORMAT,
    BlockTag,
    ParallelTag,
#TODO: ?
    #get_subjects,
)
from core.db_access import (
    db_read_fields,
    db_read_unique,
    db_read_unique_field,
)
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    ### QtGui:
    ### QtCore:
    QRegularExpressionValidator,
    Slot,
    ### other
    uic,
)

### -----

#TODO: How to organize the tags when there are many?
# The simple list might become difficult to navigate.
# What about splitting on the first '.' and using the
# first part as a combobox selector?

# The data is stored in the db table PARALLEL_LESSONS, with fields
#   (id: primary key)
#   lesson_id: foreign key -> LESSONS.id (unique, non-null)
#   TAG: The tag used to join a group of lessons
#   WEIGHTING: -, 1, 2, 3, ... 9, +

class ParallelsDialog(QDialog):
    @classmethod
    def popup(cls, lesson_id, start_value, parent=None):
        d = cls(parent)
        return d.activate(lesson_id, start_value)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_parallel_lessons_2.ui"), self)
        self.pb_reset = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Reset
        )
        self.pb_reset.clicked.connect(self.reset)
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )
        validator = QRegularExpressionValidator(TAG_FORMAT)
        self.tag.setValidator(validator)

    @Slot(str)
    def on_tag_currentTextChanged(self, text): # show courses
        if self.disable_triggers:
            return
        self.value_changed()
        self.lesson_list.clear()
        try:
            ref_list = self.tag_map[text] # [[id, lesson-id, weight], ...]
        except KeyError:
            # no references
            return
        print("§ref_list:", ref_list)
        for r in ref_list:
            lid = r[1]
            lg_id, ll, lt = db_read_unique(
                "LESSONS",
                ["lesson_group", "LENGTH", "TIME"],
                lid=lid,
            )
            bsid, btag = db_read_unique(
                "LESSON_GROUPS",
                ["BLOCK_SID", "BLOCK_TAG"],
                lesson_group=lg_id,
            )
            courses = []
            if bsid:
                bname = str(BlockTag.build(bsid, btag))
            else:
            # There can be multiple WORKLOAD entries
                wlist = [
                    row[0]for row in db_read_fields(
                        "WORKLOAD",
                        ["workload"],
                        lesson_group=lg_id
                    )
                ]
                assert wlist
                bname = None
                for wl in wlist:
                    # There can be multiple COURSE_WORKLOAD entries
                    for row in db_read_fields(
                        "COURSE_WORKLOAD",
                        ["course"],
                        workload=wl,
                    ):
                        cdata = db_read_unique(
                            "COURSES",
                            ["CLASS", "GRP", "SUBJECT", "TEACHER"],
                            course=row[0],
                        )
                        n = f"{cdata[0]}.{cdata[1]}:{cdata[2]}/{cdata[3]}"
                        if bname is None:
                            bname = n
                        else:
                            courses.append(n)
                assert bname
            self.lesson_list.addItem(
                f"{lid}: {bname} || {ll}@{lt or '-'} %{r[2]}"
            )
            for c in courses:
                self.lesson_list.addItem(f"  + {c}")

    @Slot(str)
    def on_weight_currentTextChanged(self, i):
        if self.disable_triggers:
            return
        self.value_changed()

    def value_changed(self):
        t = self.tag.currentText()
        if t:
            w = self.weight.currentText()
            self.pb_accept.setEnabled(
                t != self.value0.TAG or w != self.value0.WEIGHTING
            )
        else:
            self.pb_accept.setEnabled(False) 

    def activate(self, lesson_id: int, start_value:ParallelTag
    ) -> Optional[ParallelTag]:
        """Open the dialog.
        """
        self.result = None
        self.disable_triggers = True
        self.value0 = start_value
        if start_value.TAG:
            w = start_value.WEIGHTING
        else:
            w = '+'
            self.pb_reset.hide()
        ## Populate the tag chooser
        self.tag_map = {}
        records = db_read_fields(
            "PARALLEL_LESSONS",
            ["TAG", "id", "lesson_id", "WEIGHTING"]
        )
#TODO--  just for testing!
#        records = [
#            ("TAG2", 2, 1, 8),
#            ("TAG1", 3, 3, 5),
#            ("TAG1", 4, 8, 5),
#            ("TAG3", 5, 4, 6),
#        ]
        for r in records:
            tag = r[0]
            data = r[1:]
            try:
                self.tag_map[tag].append(data)
            except KeyError:
                self.tag_map[tag] = [data]
        self.tag.clear()
        self.tag.addItems(sorted(self.tag_map))
        self.tag.setCurrentIndex(-1)
        self.weight.setCurrentText(w)
        self.pb_accept.setEnabled(False)
        self.disable_triggers = False
        self.tag.setCurrentText(start_value.TAG)
        self.exec()
        return self.result

    def reset(self):
        self.result = ParallelTag("", 0)
        super().accept()

    def accept(self):
        t = self.tag.currentText()
        w = self.weight.currentText()
        self.result = ParallelTag(t, w)
        super().accept()


#TODO: Wouldn't I rather go from the courses of a class?
# For all courses in the class, find the lesson-ids and – in the case
# of blocks the block tag/name.
# On the other hand, when the popup is entered, there may be an existing
# target. If so, we would need to find its class, to decide which class
# to show initially.
# Does that apply to teacher and subject view too?
# Actually, I think this is most useful for class view, so I see no
# problem in concentrating on that.
    def test(self, lesson_id: int, target_id: Optional[int]):
        # Get lesson-group and block-info for a lesson-id
        q = f"""
            select
                Lesson_group,
                BLOCK_SID,
                BLOCK_TAG
            from LESSONS
            inner join LESSON_GROUPS using (Lesson_group)
            where Lid = {lesson_id}
        """
        records = db_query(q)
        assert len(records) == 1
        lg = (r := records[0])["Lesson_group"]
        if (bsid := r["BLOCK_SID"]):
            # Use the block subject/tag
#TODO: Do I want the full subject?
# get_subjects().map(bsid)
            field1 = BlockTag.to_string(bsid, r["BLOCK_TAG"])
        else:
            # Get the course subject(s) and teacher(s)for a lesson-group:
            q = f"""
                select
                    --Workload,
                    SUBJECT,
                    TEACHER
                from WORKLOAD
                inner join COURSE_WORKLOAD using (Workload)
                inner join COURSES using (Course)
                where Lesson_group = {lg}
            """
            records = db_query(q)
            # If no block lesson-groups are used, there may be multiple
            # teachers (team-teaching), but the subject should be the same!
            sid = None
            for r in records:
                if sid:
                    assert r["SUBJECT"] == sid
                else:
                    sid = r["SUBJECT"]
                tid = r["TEACHER"]
            assert sid
#TODO: Do I want the full subject?
# get_subjects().map(bsid)
            field1 = f"{sid} ({tid})"

        pass
# Shouldn't I be starting from the COURSES table here (CLASS)? I want to
# populate an activity list  for a particular class!


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print("----->", ParallelsDialog.popup(ParallelTag("", '+')))
    print("----->", ParallelsDialog.popup(ParallelTag("TAG1", '7')))
