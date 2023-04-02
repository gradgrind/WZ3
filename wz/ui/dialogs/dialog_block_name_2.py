"""
ui/dialogs/dialog_block_name.py

Last updated:  2023-04-02

Supporting "dialog" for the course editor – handle blocks.


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

T = TRANSLATIONS("ui.dialogs.dialog_block_name")

### +++++

from typing import Optional
from enum import Enum
from core.basic_data import (
    BLOCK_TAG_FORMAT,
    get_subjects,
    get_teachers,
    BlockTag,
)
from core.db_access import (
    db_read_fields,
)
from core.course_data import CourseLessonData
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QTableWidgetItem,
    QAbstractItemView,
    ### QtGui:
    ### QtCore:
    Qt,
    QRegularExpressionValidator,
    Slot,
    ### other
    uic,
)

class CHOOSE(Enum):
    NEW = 1
    TO_BLOCK = 2
    TO_TEAM = 3

### -----

class BlockNameDialog(QDialog):
    """This dialog is evoked from the course editor.
    There are the following scenarios:

    1) A new course/lesson_group connection is to be made.
       In principle there is the choice between a simple lesson,
       a block lesson and a payment-only item. However, a simple
       lesson or a payment-only item may only be added if the course
       in question currently has no such item.
       The new item consists of a new WORKLOAD entry and an entry in
       COURSE_WORKLOAD linking the course to the workload. Unless the
       new item is payment-only, there will also be a new LESSON_GROUPS
       entry (linked from the WORKLOAD entry), and a single entry in
       LESSONS for the lesson_group.
       Note that further lessons may be added to existing
       lesson_groups in the course editor, using the "+" button.
       A payment-only item doesn't have a lesson group.

    2) A course may "join" an existing block (named lesson_group),
       as long as it is not already a member.

    3) A course may "join" an existing workload. All members must have
       the same subject. This covers simple cases of team-teaching and
       mixed pupil groups where only one room (at most) is specified
       and the payment details for all the teachers are the same.
       
    4) The "linkages" of the current course/workload/lesson group can
       be shown.
       In this case the workload (primary key) is passed as argument.
       In the case of a block member, the name of the block may be
       changed (to a completely new one), otherwise no changes are possible.


??? Maybe the changes should be done here!
    This dialog itself causes no database changes, that must be done by
    the calling code on the basis of the returned value.
    If the dialog is cancelled, <None> is returned and there should be
    no changes to the database.
    Otherwise a tuple is returned:
        (<BlockTag> item, lesson_group key or -1)
    The block tag can be empty, indicating that a simple-lesson group
    is to be added. The second tuple element is -1.
    Alternatively, the block tag can be invalid (sid="", tag="$"), in
    which case a workload/payment-only entry is to be added. The
    second tuple element is -1.
    Otherwise a valid, non-empty block tag is returned.
    If the second tuple element is -1, the block tag is new.
    If the second tuple element > 0, this is the lesson_group key of
    the existing LESSON_GROUPS entry for the block tag.
    """
    @classmethod
    def popup(cls, course_data:dict, workload:int=None, parent=None):
        d = cls(parent)
        return d.activate(course_data, workload)

    def __init__(self, course_data, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_block_name_2.ui"), self)
        self.rb_inspect.hide()
        self.table_courses.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )
        validator = QRegularExpressionValidator(BLOCK_TAG_FORMAT)
        self.BLOCK_TAG.setValidator(validator)
        self.choose_group.setId(self.rb_new, CHOOSE.NEW.value)
        self.choose_group.setId(self.rb_add2block, CHOOSE.TO_BLOCK.value)
        self.choose_group.setId(self.rb_add2team, CHOOSE.TO_TEAM.value)

    def activate(
        self,
        this_course: dict,
        workload: int
#TODO: return value???
    ) -> Optional[BlockTag]:
        """Open the dialog.
        Without <workload> a new entry is to be created.
        """
        self.result = None
        cdata = CourseLessonData(this_course)
        self.this_course_data = cdata
        self.this_workload = workload
        self.disable_triggers = True
        self.set_block_subject_list()
        if workload:
#TODO?
            self.rb_inspect.setChecked(True)
            self.type_chooser.setEnabled(False)
            self.cb_block.setEnabled(False)
            lg = cdata.workloads[workload][0]
            if lg:
                if lg in cdata.noblock_lesson_groups:
                    self.rb_simple.setChecked(True)
                else:
                    bsid, btag = cdata.lesson_group2blockname[lg]
                    self.cb_block.setChecked(True)
                    self.block_subject.setCurrentIndex(self.sid_index[bsid])
                    self.BLOCK_TAG.setCurrentText(btag)
            else:
                self.rb_payonly.setChecked(True)
#TODO
        else:
            self.rb_new.setChecked(True)
            self.type_chooser.setEnabled(True)
            simple, payonly = self.this_course_data.can_add_nonblock()
            self.rb_simple.setEnabled(simple)
            self.rb_payonly.setEnabled(payonly)
            self.rb_simple.setChecked(simple)
            if simple or payonly:
                self.cb_block.setChecked(not simple)
                self.cb_block.setEnabled(True)
            else:
                self.cb_block.setChecked(True)
                self.cb_block.setEnabled(False)
        self.disable_triggers = False
        self.set_courses()
        self.exec()
        return self.result
            
    def set_block_subject_list(self):
        """Populate the subject chooser."""
        self.block_subject.clear()
        self.sid_list = []
        self.sid_index = {}
        for sid, name in get_subjects():
            if sid[0] == "-":
                continue
            self.sid_index[sid] = len(self.sid_list)
            self.sid_list.append(sid)
            self.block_subject.addItem(name)
        self.block_subject.setCurrentIndex(-1)

#TODO
    def set_courses(self):
#TODO? Maybe rather at the beginning of <show_lesssons>?
        self.list_lessons.clear()

        self.course_table_data = []
        cdata = self.this_course_data
        if self.cb_block.isChecked():
            self.BLOCK_TAG.setEditable(self.rb_new.isChecked())
# add workload field to course table?
            self.table_courses.setSelectionMode(
                QAbstractItemView.SelectionMode.SingleSelection
                if self.rb_add2team.isChecked() and not self.this_workload
                else QAbstractItemView.SelectionMode.NoSelection
            )
            sidi = self.block_subject.currentIndex()
            sid = self.sid_list[sidi] if sidi >= 0 else ""
            block_key = f"{sid}#{self.BLOCK_TAG.currentText()}"
            try:
                lg = cdata.block2lesson_group[block_key]
            except KeyError:
                # the key is new
                wlist = []
#TODO
            else:
                # the key is already defined
                self.show_lessons(lg)
                wlist = cdata.lesson_group2workloads[lg]
#TODO

        else:
            self.table_courses.setSelectionMode(
                QAbstractItemView.SelectionMode.NoSelection
                if self.this_workload
                else QAbstractItemView.SelectionMode.SingleSelection
            )

            if self.rb_payonly.isChecked():
#TODO
                wlist = cdata.lesson_group2workloads[0]

            else:
                # simple lesson
#TODO
                wlist = []
                for lg in cdata.noblock_lesson_groups:
                    wl = cdata.lesson_group2workloads[lg]
                    assert(len(wl) == 1)
                    wlist.append(wl[0])
#???
        if self.this_workload:
            wlist = [self.this_workload]
        else:
            # If adding to a team, only courses with the same subject
            # are relevant
            choose_team = self.rb_add2team.isChecked()
            course_sid = cdata.this_course["SUBJECT"]
        for w in wlist:
            cl = cdata.workload2courses[w]
            for c in cl:
                cfields = cdata.course_map[c]
                if choose_team and cfields["SUBJECT"] != course_sid:
                    continue
                self.course_table_data.append((cfields, w))

        self.show_courses()

    def show_courses(self):
        """Display the courses corresponding to the "filter" values.
        Their data is stored as a list in <self.course_table_data>.
        """
        self.table_courses.setRowCount(len(self.course_table_data))
        for r, cw in enumerate(self.course_table_data):
            print("???~~", cw)
            cdata, workload = cw    # cdata: (CLASS, GRP, sid, tid)
            # class field
            if not (tw := self.table_courses.item(r, 0)):
                tw = QTableWidgetItem()
                tw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_courses.setItem(r, 0, tw)
            tw.setText(cdata[0])
            # group field
            if not (tw := self.table_courses.item(r, 1)):
                tw = QTableWidgetItem()
                tw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_courses.setItem(r, 1, tw)
            tw.setText(cdata[1])
            # subject field
            if not (tw := self.table_courses.item(r, 2)):
                tw = QTableWidgetItem()
                self.table_courses.setItem(r, 2, tw)
            tw.setText(get_subjects().map(cdata[2]))
            # teacher field
            if not (tw := self.table_courses.item(r, 3)):
                tw = QTableWidgetItem()
                self.table_courses.setItem(r, 3, tw)
            tw.setText(get_teachers().name(cdata[3]))
            # workload (key)
            if not (tw := self.table_courses.item(r, 4)):
                tw = QTableWidgetItem()
                tw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_courses.setItem(r, 4, tw)
            tw.setText(str(workload))
            # room-choice field
            if not (tw := self.table_courses.item(r, 5)):
                tw = QTableWidgetItem()
                self.table_courses.setItem(r, 5, tw)
            tw.setText(self.this_course_data.workloads[workload][2])

    def show_lessons(self, lesson_group:int):
        """Display the individual lessons for the given <lesson_group> value.
        """
        for l, t in db_read_fields(
            "LESSONS",
            ["LENGTH", "TIME"],
            lesson_group=lesson_group
        ):
            text = str(l)
            if t:
                text += f"  @ {t}"
            self.list_lessons.addItem(text)




# Need subject (sid) of course for which the entry is to be made!
# self.course_sid?
# Maybe on-demand and cached?
#        self.course_sid = "Ma"
#        for course, CLASS, GRP, TEACHER in db_read_fields(
#            "COURSES", ("course", "CLASS", "GRP", "TEACHER"),
#            SUBJECT=self.course_sid 
#        ):
#            print("$Cs$$", course, CLASS, GRP, TEACHER)
# and actually only those with corresponding entries ...
# What about getting the possible workloads first?

        # Which lesson-group?
#        if self.choose_block:
#            lg = db_read_unique_field("LESSON_GROUPS", "lesson_group",
#                BLOCK_SID=self.block_sid,
#                BLOCK_TAG=self.block_tag!,
#            )
#        elif self.choose_payonly:
#            lg = 0
#        else:
#            lg = -1 # ??? There are (probably) many









    @Slot(int)
    def on_block_subject_currentIndexChanged(self, i):
        if self.disable_triggers:
            return
        self.disable_triggers = True
        sid = self.sid_list[i]
        self.set_sid(sid)
#?
        if self.BLOCK_TAG.count():
            self.BLOCK_TAG.setCurrentIndex(0)
        self.disable_triggers = False
        self.set_courses()

    def set_sid(self, sid):
        """Set up the block-tag widget according to the given subject.
        If <sid> is null the block-tag widget will be disabled.
        Otherwise the drop-down list will be filled with existing
        BLOCK_TAG values for BLOCK_SID=sid.
        """
        self.sid = sid
        self.BLOCK_TAG.clear()
        self.BLOCK_TAG.clearEditText()
        self.sid_block_map = {}
        if sid:
            self.BLOCK_TAG.setEnabled(True)
            for t, lg in self.this_course_data.blocksid2tags[sid]:
                self.sid_block_map[t] = lg
                self.BLOCK_TAG.addItem(t)
        else:
            self.BLOCK_TAG.setEnabled(False)
        print("???", self.sid_block_map)






    def on_table_courses_currentItemChanged(self, newitem, olditem):
        print("TODO: COURSE ROW", newitem.row())
        if self.cb_block.isChecked():
            print("TODO: Unexpected <on_table_courses_currentItemChanged>")
            return
        cdata = self.course_table_data[newitem.row()]
        self.show_lessons(cdata["lesson_group"])


    @Slot(int)
    def on_choose_group_idClicked(self, i:int):
        if self.disable_triggers:
            return
        print("§choose_group", CHOOSE(i))
        self.do_choose(CHOOSE(i))

    def do_choose(self, choose:CHOOSE):
        self.choose = choose
        self.BLOCK_TAG.setEditable(choose == CHOOSE.NEW)
        if choose == CHOOSE.TO_BLOCK:
            self.cb_block.setEnabled(False)
#dangerous? ... if called at initialization
            self.disable_triggers = True
            self.cb_block.setChecked(True)
            self.disable_triggers = False
            self.do_choose_block(True)
        else:
            self.cb_block.setEnabled(True)
        self.set_courses()
#?

    @Slot(bool)
    def on_cb_block_toggled(self, block:bool):
        print("§cb_block", block)
        self.blockstack.setCurrentWidget(
            self.page_block if block else self.page_noblock
        )
        if self.disable_triggers:
            return
        self.do_choose_block()

    def do_choose_block(self):
        block = self.cb_block.isChecked()
#        self.choose_block = block
#?


    @Slot(bool)
    def on_rb_payonly_toggled(self, payonly:bool):
        if self.disable_triggers:
            return
        print("§rb_payonly", payonly)
        self.do_payonly(payonly)

    def do_payonly(self, payonly:bool):
        self.choose_payonly = payonly
        print("§do_payonly TODO")
#?

        return
#null/empty result
        self.result = (
            BlockTag("", "$", ""), # an illegal value
            -1
        )
        super().accept()

    @Slot(str)
    def on_BLOCK_TAG_currentTextChanged(self, text): # show courses
        if self.disable_triggers:
            return
        self.set_courses()

    def acceptable(self):
#TODO
        # If "new", empty, editable combobox. Existing joint-tags are not
        # acceptable (-> red, disable accept). Null is acceptable.
        # If "existing", populate non-editable combobox with tags from
        # WORKLOAD with no lesson_group. Null is not acceptable.
# However, null IS acceptble for blocks – then just the block-tag would
# be from the existing ones ... the choice of joint_tags depends on
# the chosen block_tag ...

#self.sid
#self.current_block_tag
#self.current_joint_tag

        if self.cb_block.isChecked():
            if not self.sid:
                self.pb_accept.setEnabled(False)
                return

# set up block_tag choice if not "new"

#            if self.choose_new:
## check that block-name is new

#                if self.current_joint_tag in self.joint_map:
#                    self.pb_accept.setEnabled(False)
#                    return

#            else:
## check that block-name exists

#                if not self.current_joint_tag:
#                    self.pb_accept.setEnabled(False)
#                    return



        else:
            ## Not a block
            assert(not self.sid)
            assert(not self.current_block_tag)
#            if self.choose_new:
#                if self.current_joint_tag in self.joint_map:
#                    self.pb_accept.setEnabled(False)
#                    return
#            else:
#                if not self.current_joint_tag:
#                    self.pb_accept.setEnabled(False)
#                    return


        self.pb_accept.setEnabled(True)



#TODO ...
    def init_courses(self, btag:str):
        self.block_tag = btag




        self.current_blocktag = btag
        self.course_map = {}
        self.course_ids = []
        try:
            self.existing_lesson_group=self.sid_block_map[btag]
        except KeyError:
            # No courses, a new block-name
            self.existing_lesson_group = -1
            self.table_courses.setRowCount(0)
            self.list_lessons.clear()
            self.pb_accept.setEnabled(True)
            return

#TODO: Fix this! There is no COURSE_LESSONS table any more ...
        course_refs = db_read_fields(
            "COURSE_LESSONS",
            ["id", "course", "ROOM"],
            lesson_group=self.existing_lesson_group
        )
        # A block-name change to an existing value is not permitted,
        # otherwise an existing lesson_group is acceptable as long as
        # it is not in <self.blocks>.
        if self.blocktag:
            # Disable the accept button.
            self.pb_accept.setEnabled(False)
        else:
            # Disable the accept button if the block-name is in
            # the <self.blocks> set.
            for bt in self.blocks:
                if bt.sid == self.sid and bt.tag == btag:
                    self.pb_accept.setEnabled(False)
                    break
            else:
                self.pb_accept.setEnabled(True)
        self.table_courses.setRowCount(len(course_refs))
        for r, c in enumerate(course_refs):
            cid = c[1]
            self.course_ids.append(cid)
            cdata = dict(zip(*db_read_unique_entry("COURSES", course=cid)))
            # class field
            if not (tw := self.table_courses.item(r, 0)):
                tw = QTableWidgetItem()
                tw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_courses.setItem(r, 0, tw)
            tw.setText(cdata["CLASS"])
            # group field
            if not (tw := self.table_courses.item(r, 1)):
                tw = QTableWidgetItem()
                tw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_courses.setItem(r, 1, tw)
            tw.setText(cdata["GRP"])
            # subject field
            if not (tw := self.table_courses.item(r, 2)):
                tw = QTableWidgetItem()
                self.table_courses.setItem(r, 2, tw)
            tw.setText(get_subjects().map(cdata["SUBJECT"]))
            # teacher field
            if not (tw := self.table_courses.item(r, 3)):
                tw = QTableWidgetItem()
                self.table_courses.setItem(r, 3, tw)
            tw.setText(get_teachers().name(cdata["TEACHER"]))
            # room-choice field
            if not (tw := self.table_courses.item(r, 4)):
                tw = QTableWidgetItem()
                self.table_courses.setItem(r, 4, tw)
            tw.setText(c[2])
        ## Show lessons
        self.list_lessons.clear()
        for l, t in db_read_fields(
            "LESSONS",
            ["LENGTH", "TIME"],
            lesson_group=self.existing_lesson_group
        ):
            text = str(l)
            if t:
                text += f"  @ {t}"
            self.list_lessons.addItem(text)

#?
    def accept(self):
        i = self.block_subject.currentIndex()
        if i < 0:
            # The "accept" button should only be enabled when this is
            # an acceptable result ...
            self.result = (BlockTag("", "", ""), -1)
        else:
            s = self.sid_list[i]
            t = self.BLOCK_TAG.currentText()
            # Invalid values should not be possible here ...
            self.result = (BlockTag.build(s, t), self.existing_lesson_group)
        super().accept()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    course_data = {
        "course": 0,  # invalid
        "CLASS": "10G",
        "GRP": "*",
        "SUBJECT": "Ma",
        "TEACHER": "AE",
    }
    print("----->", BlockNameDialog.popup(course_data))
    print("----->", BlockNameDialog.popup(course_data, workload=True))
    print("----->", BlockNameDialog.popup(
        course_data,
        simple=True,
        blocks=[BlockTag.build("KoRa", "")]
    ))
    print("----->", BlockNameDialog.popup(
        course_data,
        workload=True,
        simple=True
    ))
    print("----->", BlockNameDialog.popup(
        course_data,
        blocktag=BlockTag.build("KoRa", ""), jointag=""
    ))
    print("----->", BlockNameDialog.popup(
        course_data,
        blocktag=BlockTag.build("ZwE", "09G10G"), jointag=""
    ))
    print("----->", BlockNameDialog.popup(
        course_data,
        blocktag=BlockTag.build("Hu", ""), jointag=""
    ))
    print("----->", BlockNameDialog.popup(
        course_data,
        blocktag=BlockTag.build("XXX", ""), jointag=""
    ))
