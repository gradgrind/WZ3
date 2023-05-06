"""
ui/dialogs/dialog_text_line.py

Last updated:  2023-05-03

Supporting "dialog" for the editors – enter/modify a text field.


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

#T = TRANSLATIONS("ui.dialogs.dialog_text_line")

### +++++

from typing import Optional
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

class TextLineDialog(QDialog):
    @classmethod
    def popup(cls, start_value, message=None, title=None, parent=None):
        d = cls(parent)
        if title:
            d.setWindowTitle(title)
        return d.activate(start_value, message)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_text_line_message.ui"), self)
        self.pb_accept = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok
        )

    @Slot(str)
    def on_textline_textEdited(self, text):
        self.pb_accept.setEnabled(text != self.value0)

    def activate(self, start_value:str, message:str) -> Optional[str]:
        """Open the dialog.
        """
        self.result = None
        self.value0 = start_value
        if message[-1] == "!":
            message = f'<p style="color:#d50000;">{message}</p>'
        self.label.setText(message)
        self.textline.setText(start_value)
        self.pb_accept.setEnabled(False)
        self.exec()
        return self.result

    def accept(self):
        self.result = self.textline.text()
        super().accept()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    print("----->", TextLineDialog.popup("", "Write something here:"))
    print("----->", TextLineDialog.popup("A note.", "You can change this:"))
    print("----->", TextLineDialog.popup(
        "IMPORTANT",
        "Normally this should not be changed!",
        title="Custom Title"
    ))
