"""
ui/dialogs/dialog_make_course_tables.py

Last updated:  2023-04-23

Supporting "dialog", for the course editor – allow the export of teacher
and class data, etc., in table form.

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

T = TRANSLATIONS("ui.dialogs.dialog_make_course_tables")

### +++++

import os

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
from core.list_activities import (
    read_db,
    make_teacher_table_pay,
    make_teacher_table_room,
    make_class_table_pdf,
    make_teacher_table_xlsx,
    make_class_table_xlsx,
    write_xlsx,
)

### -----


class ExportTable(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        uic.loadUi(APPDATAPATH("ui/dialog_make_course_tables.ui"), self)

    def activate(self):
        """"Open the dialog.
        """
        self.output_box.clear()
        self.cl_lists, self.t_lists, self.lg_2_c = read_db()
        self.exec()

    def output(self, text):
        self.output_box.appendPlainText(text)

    @Slot()
    def on_pb_pay_clicked(self):
        """Export a pdf file with a table for each teacher detailing
        the workload and giving some pay-related information.
        """
        pdfbytes = make_teacher_table_pay(self.t_lists)
        filepath = SAVE_FILE("pdf-Datei (*.pdf)", T["teacher_workload_pay"])
        if filepath and os.path.isabs(filepath):
            if not filepath.endswith(".pdf"):
                filepath += ".pdf"
            with open(filepath, "wb") as fh:
                fh.write(pdfbytes)
            self.output(f"---> {filepath}")

    @Slot()
    def on_pb_teachers_clicked(self):
        """Export a pdf file with a table for each teacher detailing
        the lessons, etc.
        """
        pdfbytes = make_teacher_table_room(self.t_lists)
        filepath = SAVE_FILE("pdf-Datei (*.pdf)", T["teacher_activities"])
        if filepath and os.path.isabs(filepath):
            if not filepath.endswith(".pdf"):
                filepath += ".pdf"
            with open(filepath, "wb") as fh:
                fh.write(pdfbytes)
            self.output(f"---> {filepath}")

    @Slot()
    def on_pb_classes_clicked(self):
        """Export a pdf file with a table for each class detailing
        the lessons, etc.
        """
        pdfbytes = make_class_table_pdf(self.cl_lists, self.lg_2_c)
        filepath = SAVE_FILE("pdf-Datei (*.pdf)", T["class_lessons"])
        if filepath and os.path.isabs(filepath):
            if not filepath.endswith(".pdf"):
                filepath += ".pdf"
            with open(filepath, "wb") as fh:
                fh.write(pdfbytes)
            self.output(f"---> {filepath}")

    @Slot()
    def on_pb_teachers_xlsx_clicked(self):
        """Export an xlsx (Excel) file with a table for each teacher
        detailing the workload and giving some pay-related information.
        The data is rather more "raw" than in the corresponding pdf files.
        """
        tdb = make_teacher_table_xlsx(self.t_lists)
        filepath = SAVE_FILE(
            "Excel-Datei (*.xlsx)", T["teacher_workload_pay"]
        )
        if filepath and os.path.isabs(filepath):
            if not filepath.endswith(".xlsx"):
                filepath += ".xlsx"
            write_xlsx(tdb, filepath)
            self.output(f"---> {filepath}")
    
    @Slot()
    def on_pb_classes_xlsx_clicked(self):
        """Export an xlsx (Excel) file with a table for each class
        detailing the lessons, etc.
        The data is rather more "raw" than in the corresponding pdf file.
        """
        cdb = make_class_table_xlsx(self.cl_lists)
        filepath = SAVE_FILE(
            "Excel-Datei (*.xlsx)", T["class_lessons"]
        )
        if filepath and os.path.isabs(filepath):
            if not filepath.endswith(".xlsx"):
                filepath += ".xlsx"
            write_xlsx(cdb, filepath)
            self.output(f"---> {filepath}")
            