"""
ui/dialogs/dialog_course_fields.py

Last updated:  2023-07-10

Supporting "dialog", for the course editor – edit course fields.

To test this, activate it in the course editor (ui/modules/course_editor).


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

T = TRANSLATIONS("ui.dialogs.dialog_course_fields")

### +++++

from core.db_access import (
    db_check_unique_entry,
)
from core.basic_data import get_classes
from core.classes import GROUP_ALL
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    ### QtGui:
    ### QtCore:
    Slot,
    ### other
    uic,
    YesOrNoDialog,
)

### -----


class CourseEditorForm(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_course_fields.ui"), self)
        self.classes = data["CLASS"]
        self.teachers = data["TEACHER"]
        self.subjects = data["SUBJECT"]
        self.groups = None
        self.callback_enabled = False
        self.cb_class.addItems([s[1] for s in self.classes])
        self.cb_subject.addItems([s[1] for s in self.subjects])
        self.cb_teacher.addItems([s[1] for s in self.teachers])
        self.callback_enabled = True

    def activate(self, course_data):
        """"Open the dialog with the given data, a <dict> containing
        the data from the current course.
        """
        self.setWindowTitle(
            T["EDIT_COURSE_FIELDS"] if course_data["Course"]
            else T["NEW_COURSE"]
        )
        self.changes = None
        self.callback_enabled = False
        self.course_data = course_data
        c = course_data["CLASS"]
        for i, cdata in enumerate(self.classes):
            if c == cdata[0]:
                # print("§CLASS:", cdata)
                self.class0 = i
                self.cb_class.setCurrentIndex(i)
                self.init_groups(c, course_data["GRP"])
                break
        else:
            raise Bug(f"Unknown class: '{c}'")
        c = course_data["SUBJECT"]
        for i, cdata in enumerate(self.subjects):
            if c == cdata[0]:
                self.subject0 = i
                self.cb_subject.setCurrentIndex(i)
                break
        else:
            raise Bug(f"Unknown subject: '{c}'")
        c = course_data["TEACHER"]
        for i, cdata in enumerate(self.teachers):
            if c == cdata[0]:
                self.teacher0 = i
                self.cb_teacher.setCurrentIndex(i)
                break
        else:
            raise Bug(f"Unknown teacher: '{c}'")
        self.grade_report.setChecked(bool(course_data["GRADES"]))
        self.text_report.setChecked(bool(course_data["REPORT"]))
        self.le_subject_title.setText(course_data["REPORT_SUBJECT"])
        self.le_signature.setText(course_data["AUTHORS"])
        self.le_info.setText(course_data["INFO"])
        self.callback_enabled = True
        self.exec() # == QDialog.DialogCode.Accepted:
        return self.changes

    def get_changes(self):
        changes = {}
        ci = self.cb_class.currentIndex()
        if ci != self.class0:
            changes["CLASS"] = self.classes[ci][0]
        si = self.cb_subject.currentIndex()
        if si != self.subject0:
            changes["SUBJECT"] = self.subjects[si][0]
        ti = self.cb_teacher.currentIndex()
        if ti != self.teacher0:
            changes["TEACHER"] = self.teachers[ti][0]
        grp = self.cb_group.currentText()
        if grp != self.course_data["GRP"]:
            changes["GRP"] = grp
        gr = self.grade_report.isChecked()
        if bool(self.course_data["GRADES"]) != gr:
            changes["GRADES"] = "X" if gr else ""
        tr = self.text_report.isChecked()
        if bool(self.course_data["REPORT"]) != tr:
            changes["REPORT"] = "X" if tr else ""
        st = self.le_subject_title.text()
        if st != self.course_data["REPORT_SUBJECT"]:
            changes["REPORT_SUBJECT"] = st
        sg = self.le_signature.text()
        if sg != self.course_data["AUTHORS"]:
            changes["AUTHORS"] = sg
        it = self.le_info.text()
        if it != self.course_data["INFO"]:
            changes["INFO"] = it
        return changes

    @Slot(int)
    def on_cb_class_currentIndexChanged(self, i:int):
        if self.callback_enabled:
            self.init_groups(self.classes[i][0], "")

    def init_groups(self, klass, group):
        self.cb_group.clear()
        self.cb_group.addItem("")
        if klass != "--":
            # N.B. The null class should have no groups.
            class_groups = get_classes()[klass].divisions
            # <groups> is a mapping of the primary groups to the atomic groups
            groups = class_groups.group_atoms()
            self.cb_group.addItem(GROUP_ALL)
            if groups:
                self.cb_group.addItems(groups)
            if group and group != GROUP_ALL:
                if group not in groups:
                    REPORT(
                        "ERROR",
                        T["UNKNOWN_GROUP"].format(klass=klass, g=group)
                    )
                    group = ""
            self.cb_group.setCurrentText(group)

    def accept(self):
        changes = self.get_changes()
        if changes:
            ckey = {}
            test = False
            for f in "CLASS", "GRP", "SUBJECT", "TEACHER":
                try:
                    ckey[f] = changes[f]
                    test = True
                except KeyError:
                    ckey[f] = self.course_data[f]
            if test:
                if db_check_unique_entry("COURSES", **ckey):
                    REPORT("ERROR", T["COURSE_NOT_UNIQUE"])
                    return
            elif not self.course_data["Course"]:
                # A new entry – the key fields have not been changed
                REPORT("ERROR", T["COURSE_NOT_UNIQUE"])
                return
            self.changes = changes
            super().accept()
        else:
            y = YesOrNoDialog(T["NO_CHANGES"], T["NO_CHANGES_TITLE"])
            if y:
                self.reject()

    def closeEvent(self, event):
        """Prevent dialog closure if there are changes."""
        if self.get_changes():
            y = YesOrNoDialog(T["LOSE_CHANGES"], T["LOSE_CHANGES_TITLE"])
            if not y:
                event.ignore()
                return
        event.accept()
