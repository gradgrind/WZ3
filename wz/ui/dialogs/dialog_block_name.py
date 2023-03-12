"""
ui/dialogs/dialog_block_name.py

Last updated:  2023-03-12

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

#T = TRANSLATIONS("ui.dialogs.dialog_block_name")

### +++++

from typing import Optional
from core.basic_data import (
    BLOCK_TAG_FORMAT,
    get_subjects,
    get_teachers,
    BlockTag,
)
from core.db_access import (
    db_read_fields,
    db_read_unique_entry,
)
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QTableWidgetItem,
    ### QtGui:
    ### QtCore:
    Qt,
    QRegularExpressionValidator,
    Slot,
    ### other
    uic,
)

### -----

class BlockNameDialog(QDialog):
    """This dialog is evoked from the course editor.
    There are the following scenarios:

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

    2) A block lesson_group is to be renamed. This of course applies to
       all courses connected to the lesson_group. The selected block-name
       mustn't already be in use. The current block-name is passed in as
       parameter <blocktag>.
    """
    @classmethod
    def popup(cls, parent=None, **kargs):
        d = cls(parent)
        return d.activate(**kargs)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_block_name.ui"), self)
        self.table_courses.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )
        validator = QRegularExpressionValidator(BLOCK_TAG_FORMAT)
        self.block_tag.setValidator(validator)

    @Slot(int)
    def on_block_subject_currentIndexChanged(self, i):
        if self.disable_triggers:
            return
        self.only_pay.hide()
        self.disable_triggers = True
        sid = self.sid_list[i]
        self.set_sid(sid)
        if self.block_tag.count():
            self.block_tag.setCurrentIndex(0)
        self.disable_triggers = False
        self.init_courses(self.block_tag.currentText())

    def set_sid(self, sid):
        self.sid = sid
        self.block_tag.clear()
        self.block_tag.clearEditText()
        self.sid_block_map = {}
        if sid:
            self.block_tag.setEnabled(True)
            tags = db_read_fields(
                "LESSON_GROUP",
                ["lesson_group", "BLOCK_TAG"],
                sort_field="BLOCK_TAG",
                BLOCK_SID=sid,
            )
            for i, t in tags:
                self.sid_block_map[t] = i
                self.block_tag.addItem(t)
        else:
            self.block_tag.setEnabled(False)

    @Slot(str)
    def on_block_tag_currentTextChanged(self, text): # show courses
        if self.disable_triggers:
            return
        self.init_courses(text)

    @Slot()
    def on_only_pay_clicked(self):
        self.result = BlockTag("$", "", "") # an illegal value
        super().accept()

    def init_courses(self, btag):
        self.course_map = {}
        self.course_ids = []
        try:
            lesson_group=self.sid_block_map[btag]
        except KeyError:
            # No courses, a new block-name (always acceptable)
            self.table_courses.setRowCount(0)
            self.list_lessons.clear()
            self.pb_accept.setEnabled(True)
            return
        course_refs = db_read_fields(
            "COURSE_LESSONS",
            ["id", "course", "ROOM"],
            lesson_group=lesson_group
        )
        # A block-name change to an existing value is not permitted,
        # otherwise an existing lesson_group is acceptable as long as
        # it is not in <self.blocks>.
        if self.blocktag:
            # Disable the accept button.
            self.pb_accept.setEnabled(False)
        else:
            # Disable the accept button if the block-name is in
            # the <self.blocks> list.
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
            lesson_group=lesson_group
        ):
            text = str(l)
            if t:
                text += f"  @ {t}"
            self.list_lessons.addItem(text)

    def activate(
        self,
        blocktag: BlockTag=None,
        workload: bool=False,
        simple: bool=False,
        blocks: list[BlockTag]=None
    ) -> Optional[BlockTag]:
        """Open the dialog.
        """
        self.result = None
        self.disable_triggers = True
        self.blocktag = blocktag
        if blocktag:
            if simple:
                raise Bug("BlockNameDialog: simple=True with block-tag")
            if workload:
                raise Bug("BlockNameDialog: workload=True with block-tag")
            if blocks:
                raise Bug("BlockNameDialog: blocks supplied with block-tag")
            sid0 = blocktag.sid
            tag0 = blocktag.tag
            self.only_pay.hide()
        else:
            sid0 = ""
            tag0 = ""
            if not workload:
                self.only_pay.hide()
            self.blocks = blocks or []
        ## Populate the subject chooser
        self.sid_list = []
        self.block_subject.clear()
        for sid, name in get_subjects():
            if sid[0] == "-":
                continue
            self.sid_list.append(sid)
            self.block_subject.addItem(name)
        if blocktag:
            i = self.sid_list.index(sid0)
            self.block_subject.setCurrentIndex(i)
        else:
            self.block_subject.setCurrentIndex(-1)
        self.set_sid(sid0)
        self.block_tag.setCurrentText(tag0)
        self.table_courses.setRowCount(0)
        self.list_lessons.clear()
        self.disable_triggers = False
        self.pb_accept.setEnabled(simple)
        if blocktag:
            self.init_courses(tag0)
        self.exec()
        return self.result

    def accept(self):
        i = self.block_subject.currentIndex()
        if i < 0:
            # The "accept" button should only be enabled when this is
            # an acceptable result ...
            self.result = BlockTag("", "", "")
        else:
            s = self.sid_list[i]
            t = self.block_tag.currentText()
            # Invalid values should not be possible here ...
            self.result = BlockTag.build(s, t)
        super().accept()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print("----->", BlockNameDialog.popup())
    print("----->", BlockNameDialog.popup(workload=True))
    print("----->", BlockNameDialog.popup(
        simple=True,
        blocks=[BlockTag.build("KoRa", "")]
    ))
    print("----->", BlockNameDialog.popup(workload=True, simple=True))
    print("----->", BlockNameDialog.popup(
        blocktag=BlockTag.build("KoRa", "")
    ))
    print("----->", BlockNameDialog.popup(
        blocktag=BlockTag.build("ZwE", "09G10G")
    ))
    print("----->", BlockNameDialog.popup(BlockTag.build("Hu", "")))
    print("----->", BlockNameDialog.popup(BlockTag.build("XXX", "")))
