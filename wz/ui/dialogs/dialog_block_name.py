"""
ui/dialogs/dialog_room_choice.py

Last updated:  2023-03-03

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

#TODO ...

from typing import Optional
from core.basic_data import (
    PAYMENT_FORMAT,
    PAYMENT_TAG_FORMAT,
    WorkloadData,
    get_payment_weights,
    course_lesson2workload,
)
from ui.ui_base import (
    ### QtWidgets:
    QDialog,
    QDialogButtonBox,
    ### QtGui:
    ### QtCore:
    QRegularExpressionValidator,
    ### other
    uic,
)

### -----

class BlockNameDialog(QDialog):
    @classmethod
    def popup(cls, start_value):
        d = cls()
        return d.activate(start_value)

    def __init__(self):
        super().__init__()
        uic.loadUi(APPDATAPATH("ui/dialog_block_name.ui"), self)
        pb = self.buttonBox.button(QDialogButtonBox.StandardButton.Reset)

    def activate(self, start_value:dict) -> Optional[WorkloadData]:
        """Open the dialog.
        """
        self.exec()
        return "?"

    def accept(self):
        super().accept()
        

# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    print("----->", BlockNameDialog.popup("XXX#"))

    quit(0)

    print("----->", widget.activate("XXX#"))
    print("----->", widget.activate("ZwE#09G10G"))
    print("----->", widget.activate("Hu#"))
    print("----->", widget.activate("NoSubject"))
