"""
ui/dialogs/dialog_block_name.py

Last updated:  2023-04-01

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
    db_read_unique_entry,
    db_read_unique_field,
)
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
#TODO ...

    1) A new course/lesson_group connection is to be made.
       In this no <BlockTag> is passed as argument.
       In principle, also a workload/payment-only item can be specified,
       but only if the course currently has no such item: the
       parameter <workload> should in this case be true.
       If the parameter <simple> is true, the accept-button
       will also be enabled on entry, so that a null block-name can
       be returned – allowing a simple lesson_group to be specified.
       An existing block-name may be returned, so that the course is
       added to the block – so long as the course is not already
       connected to this lesson_group.
       A new block-name will cause a new block lesson_group to be built
       and a single lesson will be added to it.

    1a) It is also possible to tag onto an existing WORKLOAD entry by
       selecting an existing JOINT_TAG.

    1b) It may be possible to set a JOINT_TAG on a new entry (it would
       have to be an unused one).

    2) A block lesson_group is to be renamed. This of course applies to
       all courses connected to the lesson_group. The selected block-name
       mustn't already be in use. The current block-name is passed in as
       parameter <blocktag>.

    2a) Any existing entry may have a JOINT_TAG added or an existing one
       changed. The new tag mustn't be in use already. It is probably
       not a good idea to allow an existing tag to be removed – that
       would make it difficult to find the item.

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
    def popup(cls, course_data, parent=None, **kargs):
        d = cls(parent)
        return d.activate(course_data, **kargs)

    def __init__(self, course_data, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_block_name_2.ui"), self)
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

    def set_block_subject_list(self):
        """Populate the subject chooser."""
        self.block_subject.clear()
        self.sid_list = []
        for sid, name in get_subjects():
            if sid[0] == "-":
                continue
            self.sid_list.append(sid)
            self.block_subject.addItem(name)
        self.block_subject.setCurrentIndex(-1)

    @Slot(int)
    def on_block_subject_currentIndexChanged(self, i):
        if self.disable_triggers:
            return
        self.disable_triggers = True
        sid = self.sid_list[i]
        self.set_sid(sid)
        if self.BLOCK_TAG.count():
            self.BLOCK_TAG.setCurrentIndex(0)
        self.disable_triggers = False
        self.init_courses(self.BLOCK_TAG.currentText())

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
            tags = db_read_fields(
                "LESSON_GROUPS",
                ["lesson_group", "BLOCK_TAG"],
                sort_field="BLOCK_TAG",
                BLOCK_SID=sid,
            )
            for i, t in tags:
                self.sid_block_map[t] = i
                self.BLOCK_TAG.addItem(t)
        else:
            self.BLOCK_TAG.setEnabled(False)

    def read_data(self):
        """Read all course/lesson data ...
        """
        self.get_courses(self.course_data["SUBJECT"])
        self.get_lesson_groups()
        self.get_workloads()
        self.get_course_workloads(self.course_data["course"])

    def get_courses(self, course_sid:str):
        """Read all COURSES entries to the mapping <self.course_map>:
            {course: (CLASS, GRP, SUBJECT, TEACHER), ...}.
        All entries with SUBJECT==course_sid are also placed in the
        list <self.same_sid_courses> in the form:
            [(CLASS, GRP, TEACHER, course)]
        """
        self.same_sid_courses = []
        self.course_map = {}
        for course, CLASS, GRP, sid, tid in db_read_fields(
            "COURSES", ("course", "CLASS", "GRP", "SUBJECT", "TEACHER")
        ):
            # print("$Cs$$", course, CLASS, GRP, sid, tid)
            if sid == course_sid:
                self.same_sid_courses.append((CLASS, GRP, tid, course))
            self.course_map[course] = (CLASS, GRP, sid, tid)
        # print("§same_sid_courses:", self.same_sid_courses)

    def get_lesson_groups(self):
        self.noblock_lesson_groups = []
        self.block2lesson_group = {}
        for lg, BLOCK_SID, BLOCK_TAG in db_read_fields(
            "LESSON_GROUPS", ("lesson_group", "BLOCK_SID", "BLOCK_TAG")
        ):
            if BLOCK_SID:
                key = f"{BLOCK_SID}#{BLOCK_TAG}"
                self.block2lesson_group[key] = lg
                # print(f"$LG$$ {key}:", lg)
            else:
                self.noblock_lesson_groups.append(lg)
        # print("$LG$$ {}:", self.noblock_lesson_groups)

    def get_workloads(self):
        self.lesson_group2workloads = {}
        self.workloads = {}
        for workload, lg, PAY_TAG, ROOM in db_read_fields(
            "WORKLOAD", ("workload", "lesson_group", "PAY_TAG", "ROOM")
        ):
            lg = lg or 0
            print("$Wl$$", workload, lg, PAY_TAG, ROOM)
            self.workloads[workload] = (lg, PAY_TAG, ROOM)
            try:
                self.lesson_group2workloads[lg].append(workload)
            except KeyError:
                self.lesson_group2workloads[lg] = [workload]

    def get_course_workloads(self, course_course):
        self.workload2courses = {}
        self.course_workloads = []
#TODO: id not really necessary in this module
        for _id, course, workload in db_read_fields(
            "COURSE_WORKLOAD", ("id", "course", "workload")
        ):
            # print("$CW$$", _id, course, workload)
            try:
                self.workload2courses[workload].append(course)
            except KeyError:
                self.workload2courses[workload] = [course]
            if course == course_course:
                self.course_workloads.append(workload)

#TODO
    def set_courses(self):
#TODO? Maybe rather at the beginning of <show_lesssons>?
        self.list_lessons.clear()

        self.course_table_data = []
        if self.cb_block.isChecked():
            self.table_courses.setSelectionMode(
                QAbstractItemView.SelectionMode.NoSelection
            )
            try:
                lg = self.block2lesson_group[self.block_key]
            except KeyError:
                # the key is new
                wlist = []
#TODO
            else:
                # the key is already defined
                self.show_lessons(lg)
                wlist = self.lesson_group2workloads[lg]
#TODO

        else:
            self.table_courses.setSelectionMode(
                QAbstractItemView.SelectionMode.SingleSelection
            )

            if self.rb_onlypay.isChecked():
#TODO
                wlist = self.lesson_group2workloads[0]

            else:
                # simple lesson
#TODO
                wlist = []
                for lg in self.noblock_lesson_groups:
                    wl = self.lesson_group2workloads[lg]
                    assert(len(wl) == 1)
                    wlist.append(wl[0])

        choose_team = self.choose == CHOOSE.TO_TEAM
        course_sid = self.course_data["SUBJECT"]
        for w in wlist:
            cl = self.workload2courses[w]
            for c in cl:
                cdata = self.course_map[c]
                if choose_team and cdata["SUBJECT"] != course_sid:
                    continue
                self.course_table_data.append((cdata, w))

        self.show_courses()

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
#        elif self.choose_onlypay:
#            lg = 0
#        else:
#            lg = -1 # ??? There are (probably) many






    def show_courses(self):
        """Display the courses corresponding to the "filter" values.
        Their data is stored as a list in <self.course_table_data>.
        """
        self.table_courses.setRowCount(len(self.course_table_data))
        for r, cw in enumerate(self.course_table_data):
            cdata, workload = cw    # cdata: (CLASS, GRP, sid, tid)
            # class field
            if not (tw := self.table_courses.item(r, 0)):
                tw = QTableWidgetItem()
                tw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_courses.setItem(r, 0, tw)
            tw.setText(cdata[1])
            # group field
            if not (tw := self.table_courses.item(r, 1)):
                tw = QTableWidgetItem()
                tw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_courses.setItem(r, 1, tw)
            tw.setText(cdata[2])
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
            # room-choice field
            if not (tw := self.table_courses.item(r, 4)):
                tw = QTableWidgetItem()
                self.table_courses.setItem(r, 4, tw)
            tw.setText(self.workloads[workload][2])

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
        if self.disable_triggers:
            return
        self.do_choose_block()

    def do_choose_block(self):
        block = self.cb_block.isChecked()
#        self.choose_block = block
        self.blockstack.setCurrentWidget(
            self.page_block if block else self.page_noblock
        )
#?


    @Slot(bool)
    def on_rb_onlypay_toggled(self, onlypay:bool):
        if self.disable_triggers:
            return
        print("§rb_onlypay", onlypay)
        self.do_onlypay(onlypay)

    def do_onlypay(self, onlypay:bool):
        self.choose_onlypay = onlypay
        print("§do_onlypay TODO")
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
        self.init_courses(text)

#    @Slot(str)
#    def on_JOINT_TAG_currentTextChanged(self, text): # show courses
#        if self.disable_triggers:
#            return
#        self.init_courses(text)

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

    def activate(
        self,
        course_data: dict,

        blocktag: BlockTag=None,
        workload: bool=False,
        simple: bool=False,
        blocks: set[BlockTag]=None
    ) -> Optional[BlockTag]:
        """Open the dialog. Without <blocktag> a new entry is to be
        created.
        Otherwise a new entry is to be created – in this case also
        <blocktag> must be empty.
        If <workload> is true, a new workload/pay entry is possible.
        If <simple> is true, a new simple lesson item is possible.
        <blocks> can provide a set of <BlockTag> items which are not
        acceptable for joining when adding a new entry.
        """
        self.result = None
        self.course_data = course_data
        self.disable_triggers = True
        self.set_block_subject_list()
        self.read_data()

# Can I know here whether a new simple or pay-only is possible?
        self.rb_new.setChecked(True)
        self.do_choose(CHOOSE.NEW)
        self.rb_simple.setChecked(True)
        self.cb_block.setChecked(False)
        self.do_choose_block()
        self.set_courses()
        self.disable_triggers = False

        self.exec()
        return self.result


        self.existing_lesson_group = -1
        self.disable_triggers = True
        self.blocktag = blocktag

        blocktag_select = True  # flag to enable block-name widgets
        if jointag is None:
            # Create a new entry – or "tag on" to an existing one.
            self.setWindowTitle(T["NEW_ITEM"])
            if not workload:
                pass
                #self.only_pay.hide()
            assert not blocktag, \
                "Creating entry, not expecting existing block-name"
            sid0 = ""
            tag0 = ""
            self.blocks = blocks or set()
            print("TODO1")

        else:
            # Update an existing entry.
            self.setWindowTitle(T["UPDATE_ITEM"])
            self.only_pay.hide()
            assert not simple, \
                "Updating entry, can't change entry type"
            assert not workload, \
                "Updating entry, can't change entry type"
            assert not blocks, \
                "Updating entry, forbidden blocks not expected"
            if blocktag:
                sid0 = blocktag.sid
                tag0 = blocktag.tag
            else:
                # Either a simple entry or a workload/pay entry
                blocktag_select = False
#?
                sid0 = ""
                tag0 = ""

            print("TODO2")

        self.block_subject.setEnabled(blocktag_select)
#TODO: Note that self.set_sid() affects this widget ...
#        self.BLOCK_TAG.setEnabled(blocktag_select)

        self.set_block_subject_list()
#            if blocktag:
#                i = self.sid_list.index(sid0)
#                self.block_subject.setCurrentIndex(i)

        self.set_sid(sid0)
        self.BLOCK_TAG.setCurrentText(tag0)

        self.table_courses.setRowCount(0)
        self.list_lessons.clear()
        self.disable_triggers = False
        self.pb_accept.setEnabled(simple)



#TODO: How to deal with interaction between jointag and blockname?
# When there is a fixed empty blocktag (modifying a non-block),
# all existing jointags should be blocked.
# When modifying a block that is also true.
# When making a new entry, I can attach to an existing jointag.
# However, this will have consequences for the type and blocktag,
# so perhaps this should only be possible when the blocktag is
# null/empty. On the other hand, it might help to use the block
# (and pay-only) info for preselecting possible existing jointags.
# What about a selection:
#   a) new pay-only
#   b) new simple
#   c) new block
#   d) join pay-only
#   e) join simple
#   f) join block
# That could of course be a two-stage selection:
#   A) new entry
#   B) join existing
#       a) pay-only
#       b) simple
#       c) block

## Collect existing jointags:
#        self.joint_map = {}
#        for j, l in db_read_fields(
#            "WORKLOAD",
#            ["JOIN_TAG", "lesson_group"]
#        ):
#            if j:
##                db_read_unique_field("LESSON_GROUPS", field
## Of course, LESSON_GROUPS is also being read elsewhere, for sid ...
#
#                self.joint_map[j] = l
#        print("??? self.joint_map:", self.joint_map)

        if blocktag:
            self.init_courses(tag0)
        self.exec()
        return self.result

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
