"""
ui/dialogs/dialog_courses_field_mod.py

Last updated:  2023-04-15

Supporting "dialog", for the course editor – change all occurrences of
a class or teacher in a courses display page.

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

#T = TRANSLATIONS("ui.dialogs.dialog_courses_field_mod")

### +++++

from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    ### QtGui:
    ### QtCore:
    Slot,
    ### other
    uic,
)

### -----


class FieldChangeForm(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_courses_field_mod.ui"), self)
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )
        self.classes = data["CLASS"]
        self.teachers = data["TEACHER"]

    def activate(self, course_data, field):
        """"Open the dialog with the given data, a <dict> containing
        the data from the current course.
        """
        self.callback_enabled = False
        self.cid = course_data["CLASS"]
        self.tid = course_data["TEACHER"]
        for cid, cname in self.classes:
            if cid == self.cid:
                self.le_class.setText(cname)
                break
        for tid, tname in self.teachers:
            if tid == self.tid:
                self.le_teacher.setText(tname)
                break
        if field == "TEACHER":
            # teacher page, change a class by default
            self.rb_class.setChecked(True)
        else:
            # otherwise change a teacher by default
            self.rb_teacher.setChecked(True)
        self.set_chooser()
        self.callback_enabled = True
        self.exec() # == QDialog.DialogCode.Accepted:
        return self.change

    @Slot(bool)
    def on_rb_class_toggled(self, on):
        if self.callback_enabled:
            self.set_chooser()

    def set_chooser(self):
        cbe = self.callback_enabled
        self.callback_enabled = False
        self.new_value.clear()
        if self.rb_class.isChecked():
            self.new_value.addItems([s[1] for s in self.classes])
        else:
            assert self.rb_teacher.isChecked()
            self.new_value.addItems([s[1] for s in self.teachers])
        self.get_result()
        self.callback_enabled = cbe

    @Slot(int)
    def on_new_value_currentIndexChanged(self, i:int):
        if self.callback_enabled:
            self.get_result()

    def get_result(self):
        i = self.new_value.currentIndex()
        if i < 0:
            self.change = None
        elif self.rb_class.isChecked():
            newval = self.classes[i][0]
            if newval == self.cid:
                self.change = None
            else:
                self.change = (self.cid, self.tid, "CLASS", newval)
        else:
            newval = self.teachers[i][0]
            if newval == self.tid:
                self.change = None
            else:
                self.change = (self.cid, self.tid, "TEACHER", newval)
        self.pb_accept.setEnabled(bool(self.change))
