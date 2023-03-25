"""
ui/wz_main.py

Last updated:  2023-03-25

The main window of the WZ GUI.


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

import sys, os

if __name__ == '__main__':
    # Enable package import if running as module
    #print(sys.path)
    this = sys.path[0]
    appdir = os.path.dirname(this)
    sys.path[0] = appdir
    basedir = os.path.dirname(appdir)
    from core.base import start
    import ui.ui_base
    start.setup(os.path.join(basedir, 'TESTDATA'))

from ui.ui_base import (
    ## QtWidgets
    QAbstractButton,
    QWidget,
    ## extra
    uic,
    run,
    Slot,
)

from ui.modules.class_editor import ClassEditorPage
from ui.modules.course_editor import CourseEditorPage
from ui.modules.teacher_editor import TeacherEditorPage

### -----

#class MainWindow(QMainWindow):
#    def __init__(self, main_widget):
#        super().__init__()
#        self.setWindowTitle(_TITLE)
#        self.statusbar = self.statusBar()
#        self.main_widget = MainWidget()
#        self.setCentralWidget(main_widget)

class MainWidget(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi(APPDATAPATH("ui/wz_main.ui"), self)
        pages = (
            ("ui_class_editor", ClassEditorPage()),
            ("ui_teacher_editor", TeacherEditorPage()),
            ("ui_course_editor", CourseEditorPage()),
        )
        self.pages = {}
        for key, page in pages:
            self.pages[key] = page
            self.stackedWidget.addWidget(page)

    @Slot(QAbstractButton)
    def on_buttonGroup_buttonClicked(self, pb):
        oname = pb.objectName()
        try:
            page = self.pages[oname]
        except KeyError:
            if oname == "ui_info":
                self.stackedWidget.setCurrentIndex(0)
                return
            raise Bug(f"No page for button {oname}")
        self.stackedWidget.setCurrentWidget(page)
        page.enter()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    MAIN_WIDGET = MainWidget()
#    builtins.MAIN_WIDGET = MAIN_WIDGET
#    MAIN_WIDGET.setWindowState(Qt.WindowMaximized)
    MAIN_WIDGET.resize(1000, 550)
    run(MAIN_WIDGET)
