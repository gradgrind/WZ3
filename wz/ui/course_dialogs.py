"""
ui/course_dialogs.py

Last updated:  2022-10-30

Supporting "dialogs", etc., for various purposes within the course editor.


=+LICENCE=============================
Copyright 2022 Michael Towers

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

########################################################################

if __name__ == "__main__":
    import sys, os

    this = sys.path[0]
    appdir = os.path.dirname(this)
    sys.path[0] = appdir
    basedir = os.path.dirname(appdir)
    from core.base import start

    #    start.setup(os.path.join(basedir, 'TESTDATA'))
    #    start.setup(os.path.join(basedir, 'DATA'))
    start.setup(os.path.join(basedir, "DATA-2023"))

T = TRANSLATIONS("ui.modules.course_editor")

### +++++

from typing import NamedTuple

from core.db_access import (
    open_database,
    db_read_table,
    db_values,
    db_read_unique_field,
    NoRecord,
)
from core.basic_data import (
    get_days,
    get_periods,
    get_subjects,
    get_rooms,
    get_payment_weights,
    sublessons,
    get_simultaneous_weighting,
    read_payment,
    read_block_tag,
    SHARED_DATA,
    timeslot2index,
    index2timeslot,
    TAG_FORMAT,
    #
    PAYMENT_FORMAT,
    PAYMENT_TAG_FORMAT,
)
from core.classes import Classes
from ui.ui_base import (
    GuiError,
    HLine,
    KeySelector,
    ### QtWidgets:
    APP,
    QStyle,
    QDialog,
    QLabel,
    QListWidget,
    QAbstractItemView,
    QComboBox,
    QDialogButtonBox,
    QLayout,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QCheckBox,
    QToolButton,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QStyledItemDelegate,
    QCompleter,
    QSpinBox,
    ### QtGui:
    QRegularExpressionValidator,
    QIcon,
    ### QtCore:
    Qt,
    QSize,
    QRegularExpression,
    QTimer,
)

DECIMAL_SEP = CONFIG["DECIMAL_SEP"]
COUNT_FORMAT = QRegularExpression(
    "[1-9]?[0-9](?:$[0-9]{1,3})?|".replace("$", DECIMAL_SEP)
)


def set_coursedata(coursedata: dict):
    SHARED_DATA["COURSE"] = coursedata


def get_coursedata():
    return SHARED_DATA["COURSE"]


### -----


class DayPeriodDialog(QDialog):
    @classmethod
    def popup(cls, start_value="", parent=None, pos=None):
        d = cls(parent)
        d.init()
        if pos:
            d.move(pos)
        return d.activate(start_value)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        vbox0 = QVBoxLayout(self)
        vbox0.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        hbox1 = QHBoxLayout()
        vbox0.addLayout(hbox1)
        self.daylist = ListWidget()
        #        self.daylist.setMinimumWidth(30)
        self.daylist.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        hbox1.addWidget(self.daylist)

        self.periodlist = ListWidget()
        #        self.daylist.setMinimumWidth(30)
        self.periodlist.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        hbox1.addWidget(self.periodlist)

        self.fixed_time = QCheckBox(T["TIME_FIXED"])
        self.fixed_time.stateChanged.connect(self.fix_unfix)
        vbox0.addWidget(self.fixed_time)

        pbox = QFormLayout()
        vbox0.addLayout(pbox)
        self.simultaneous_tag = QComboBox()
        self.simultaneous_tag.setEditable(True)
        self.simultaneous_tag.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.simultaneous_tag.currentTextChanged.connect(
            self.select_simultaneous_tag
        )
        pbox.addRow(T["SIMULTANEOUS_TAG"], self.simultaneous_tag)
        self.weighting = QSpinBox()
        self.weighting.setMinimum(0)
        self.weighting.setMaximum(10)
        self.weighting.setValue(10)
        pbox.addRow(T["WEIGHTING"], self.weighting)

        buttonBox = QDialogButtonBox()
        vbox0.addWidget(buttonBox)
        bt_save = buttonBox.addButton(QDialogButtonBox.StandardButton.Save)
        bt_cancel = buttonBox.addButton(QDialogButtonBox.StandardButton.Cancel)
        bt_clear = buttonBox.addButton(QDialogButtonBox.StandardButton.Discard)
        bt_clear.setText(T["Clear"])

        bt_save.clicked.connect(self.do_accept)
        bt_cancel.clicked.connect(self.reject)
        bt_clear.clicked.connect(self.do_clear)

    def fix_unfix(self, state):
        if state == Qt.CheckState.Unchecked:
            self.daylist.setEnabled(False)
            self.periodlist.setEnabled(False)
            self.simultaneous_tag.setEnabled(True)
            self.weighting.setEnabled(True)
        else:
            self.daylist.setEnabled(True)
            self.periodlist.setEnabled(True)
            self.simultaneous_tag.setEnabled(False)
            self.simultaneous_tag.setCurrentIndex(-1)
            self.weighting.setEnabled(False)
            if self.daylist.currentRow() < 0:
                self.daylist.setCurrentRow(0)
                self.periodlist.setCurrentRow(0)

    def do_accept(self):
        if self.fixed_time.isChecked():
            self.result = index2timeslot(
                (self.daylist.currentRow(), self.periodlist.currentRow())
            )
        else:
            self.result = self.simultaneous_tag.currentText()
            if self.result:
                if '.' in self.result or '@' in self.result:
                    SHOW_WARNING(T["TAG_WITH_DOT_OR_AT"])
                    return
                self.result += f"@{self.weighting.value()}"
        self.accept()

    def do_clear(self):
        self.result = ""
        self.accept()

    def init(self):
        self.daylist.clear()
        self.daylist.addItems([d[1] for d in get_days()])
        self.periodlist.clear()
        self.periodlist.addItems([p[1] for p in get_periods()])

    def activate(self, start_value=None):
        self.result = None
        try:
            d, p = timeslot2index(start_value)
            fixed = True
            if d < 0:
                d, p = 0, 0
        except ValueError as e:
            if '.' in start_value:
                SHOW_ERROR(str(e))
                d, p, fixed = 0, 0, True
            else:
                # <start_value> is a "simultaneous" tag
                d, p, fixed = -1, -1, False
        self.daylist.setCurrentRow(d)
        self.periodlist.setCurrentRow(p)
        # Enter "simultaneous" tags into combobox
        self.simultaneous_tag.clear()
        self.simultaneous_tag.addItems(
            db_values("PARALLEL_LESSONS", "TAG", sort_field="TAG")
        )
        # Toggle "fixed" flag to ensure callback activated
        self.fixed_time.setChecked(not fixed)
        self.fixed_time.setChecked(fixed)
        if (not fixed) and start_value:
            # If the tag has a weighting, strip this off (the weighting
            # field will be fetched by callback <select_simultaneous_tag>)
            self.simultaneous_tag.setCurrentText(
                start_value.split('@', 1)[0]
            )
        self.exec()
        return self.result

    def select_simultaneous_tag(self, tag):
        self.weighting.setValue(get_simultaneous_weighting(tag))


class ListWidget(QListWidget):
    def sizeHint(self):
        s = QSize()
        s.setHeight(super().sizeHint().height())
        scrollbarwidth = APP.style().pixelMetric(QStyle.PM_ScrollBarExtent)
        # The scroll-bar width alone is not quite enough ...
        s.setWidth(self.sizeHintForColumn(0) + scrollbarwidth + 5)
        # print("???", s, scrollbarwidth)
        return s


class CourseKeyFields(NamedTuple):
    CLASS: str
    GRP: str
    SUBJECT: str
    TEACHER: str


def get_course_info(course):
    flist, clist = db_read_table(
        "COURSES", CourseKeyFields._fields, course=course
    )
    if len(clist) > 1:
        raise Bug(f"COURSE {course}: multiple entries")
    # TODO: Perhaps not found is an error?
    return CourseKeyFields(*clist[0]) if clist else None


class Partner(NamedTuple):
    id: int
    course: int  # When the field is null this gets set to an empy string
    TIME: str
    PLACE: str


# ?
def partners(tag):
    if tag.replace(" ", "") != tag:
        SHOW_ERROR(f"Bug: Spaces in partner tag: '{tag}'")
        return []
    if not tag:
        return []
    flist, plist = db_read_table("LESSONS", Partner._fields, TIME=f"={tag}")
    return [Partner(*p) for p in plist]


def courses_with_lessontag(tag):
    return db_values("BLOCKS", "course", LESSON_TAG=tag)


# ?
def placements(xtag):
    """Return a list of <Partner> tuples with the given prefixed (full)
    tag in the PLACE field.
    """
    flist, plist = db_read_table("LESSONS", Partner._fields, PLACE=xtag)
    pl = []
    for p in plist:
        pp = Partner(*p)
        if pp.course:
            SHOW_ERROR(f"Bug: invalid placement (course={pp.course})")
        else:
            pl.append(pp)
    return pl


# TODO: How to include partners is not yet clear ...
class PartnersDialog(QDialog):
    @classmethod
    def popup(cls, start_value="", pos=None):
        d = cls()
        if pos:
            d.move(pos)
        return d.activate(start_value)

    def __init__(self):
        super().__init__()
        hbox1 = QHBoxLayout(self)

        vbox1 = QVBoxLayout()
        hbox1.addLayout(vbox1)
        self.identifier = QComboBox(editable=True)
        self.identifier.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.identifier.currentTextChanged.connect(self.show_courses)
        validator = QRegularExpressionValidator(TAG_FORMAT)
        self.identifier.setValidator(validator)
        vbox1.addWidget(self.identifier)

        self.identifier.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        #        bn_validator = BlocknameValidator()
        #        self.identifier.setValidator(bn_validator)

        self.course_list = QListWidget()
        hbox1.addWidget(self.course_list)

        buttonBox = QDialogButtonBox()
        buttonBox.setOrientation(Qt.Orientation.Vertical)
        vbox1.addWidget(buttonBox)
        self.bt_save = buttonBox.addButton(QDialogButtonBox.StandardButton.Save)
        bt_cancel = buttonBox.addButton(QDialogButtonBox.StandardButton.Cancel)
        self.bt_clear = buttonBox.addButton(
            QDialogButtonBox.StandardButton.Discard
        )
        self.bt_clear.setText(T["Clear"])
        # vbox1.addStretch(1)

        self.bt_save.clicked.connect(self.do_accept)
        bt_cancel.clicked.connect(self.reject)
        self.bt_clear.clicked.connect(self.do_clear)

    def do_accept(self):
        val = self.identifier.currentText()
        if not val:
            SHOW_ERROR(T["EMPTY_PARTNER_TAG"])
            return
        if val != self.value0:
            self.result = val
        if self.identifier.findText(val) < 0:
            self.result = "+" + val
        self.accept()

    def do_clear(self):
        if self.value0:
            self.result = "-"
        self.accept()

    def show_courses(self, text):
        """Populate the list widget with all courses sharing the given tag
        (i.e. "partners").
        """
        self.bt_save.setEnabled(text != self.value0)
        # Including the currently selected one (which we can't identify here!)?
        self.course_list.clear()
        plist = partners(text)
        dlist = []
        for p in plist:
            if p.course:
                # Present info about the course
                ci = get_course_info(p.course)
                # dlist.append(str(ci))
                dlist.append(
                    f"{ci.CLASS}.{ci.GRP}: {ci.SUBJECT} ({ci.TEACHER})"
                )

            else:
                # This is a block lesson
                dlist.append(f"[BLOCK] {p.PLACE}")
        self.course_list.addItems(dlist)

    def activate(self, start_value=""):
        self.bt_clear.setEnabled(bool(start_value))
        self.value0 = start_value
        self.result = None
        self.identifier.clear()
        # TODO ...
        taglist = db_values(
            "LESSONS",
            "PLACE",
            "PLACE LIKE '=_%'",  # "=" + at least one character
            # distinct=True,
            sort_field="PLACE",
        )
        self.identifier.addItems(
            [t[1:] for t in taglist if t.replace(" ", "") == t]
        )
        self.identifier.setCurrentText(self.value0)
        self.exec()
        return self.result


class DurationSelector(QComboBox):
    """A combobox for selecting lesson duration."""

    def __init__(self, modified=None, parent=None):
        super().__init__(parent)
        self.__callback = modified
        self.__report_changes = False
        self.currentTextChanged.connect(self.__changed)

    def setText(self, number):
        """Initialize the list of options and select the given one."""
        # print("(DurationSelector.setText)", repr(number))
        self.__report_changes = False
        self.clear()
        self.addItems([str(i) for i in range(1, len(get_periods()) + 1)])
        self.setCurrentText(number)
        if self.__callback:
            self.__report_changes = True

    def __changed(self, text):
        # print("(DurationSelector.__changed)", text)
        if self.__report_changes and self.__callback:
            self.__callback(text)
        self.clearFocus()


class GroupSelector(QComboBox):
    """A special combobox, offering the groups defined for the
    current class. This list must be set up from the <setText> call.
    """

    """A specialized combobox for use in the editor form for a
    "RowSelectTable" table view. This combobox offers the groups defined
    for the current class. This list must be set up from the <setText> call.

    The constructor receives the name of the field and a function which
    is to be called when the selected value is changed. This function
    takes the field name and a boolean (value != initial value, set by
    the "setText" method).
    """

    def __init__(self, field, modified, parent=None):
        super().__init__(parent)
        self.__modified = modified
        self.__field = field
        self.text0 = None
        self.currentTextChanged.connect(self.__changed)

    def setText(self, group):
        """Initialize the list of options and select the given one."""
        # print("(GroupSelector.setText)", repr(group))
        self.callback_enabled = False
        self.clear()
        self.addItem("")
        __klass = get_coursedata().CLASS
        if __klass != "--":
            # N.B. The null class should have no groups.
            self.addItem("*")
            groups = Classes().group_info(__klass)["GROUP_MAP"]
            if groups:
                self.addItems(groups)
        self.setCurrentText(group)
        if self.__modified:
            self.callback_enabled = True

    def text(self):
        return self.currentText()

    def __changed(self, text):
        if self.callback_enabled:
            self.__modified(self.__field, text != self.text0)
        # self.clearFocus()


class FormComboBox(QComboBox):
    """A specialized combobox for use in the editor form for a
    "RowSelectTable" table view. This combobox is used for editing
    foreign key fields by offering the available values to choose from.

    The constructor receives the name of the field and a function which
    is to be called when the selected value is changed. This function
    takes the field name and a boolean (value != initial value, set by
    the "setText" method).

    Also the "setup" method must be called to initialize the contents.
    """

    def __init__(self, field, modified, parent=None):
        super().__init__(parent)
        self.__modified = modified
        self.__field = field
        self.text0 = None
        self.currentIndexChanged.connect(self.change_index)

    def setup(self, key_value):
        """Set up the indexes required for the table's item delegate
        and the combobox (<editwidget>).

        The argument is a list [(key, value), ... ].
        """
        self.keylist = []
        self.key2i = {}
        self.clear()
        i = 0
        self.callback_enabled = False
        for k, v in key_value:
            self.key2i[k] = i
            self.keylist.append(k)
            self.addItem(v)
            i += 1
        self.callback_enabled = True

    def text(self):
        """Return the current "key"."""
        return self.keylist[self.currentIndex()]

    def setText(self, text):
        """<text> is the "key"."""
        if text:
            try:
                i = self.key2i[text]
            except KeyError:
                raise Bug(
                    f"Unknown key for editor field {self.__field}: '{text}'"
                )
            self.text0 = text
            self.setCurrentIndex(i)
        else:
            self.text0 = self.keylist[0]
            self.setCurrentIndex(0)

    def change_index(self, i):
        if self.callback_enabled:
            self.__modified(self.__field, self.keylist[i] != self.text0)


class DayPeriodSelector(QLineEdit):
    def __init__(self, modified=None, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.__callback = modified

    def mousePressEvent(self, event):
        result = DayPeriodDialog.popup(start_value=self.text())
        if result:
            if result == "-":
                self.text_edited("")
            else:
                self.text_edited(result)

    def text_edited(self, text):
        if self.__callback and not self.__callback(text):
            return
        self.setText(text)


class PartnersSelector(QLineEdit):
    def __init__(self, modified=None, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.__callback = modified

    def mousePressEvent(self, event):
        result = PartnersDialog.popup(start_value=self.text())
        if result:
            if self.__callback and not self.__callback(result):
                return
            self.setText(result.lstrip("+-"))


class PaymentSelector(QLineEdit):
    def __init__(self, modified=None, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.__callback = modified

    def mousePressEvent(self, event):
        result = PaymentDialog.popup(start_value=self.text())
        if result is not None:
            self.text_edited(result)

    def text_edited(self, text):
        if self.__callback and not self.__callback(text):
            return
        self.setText(text)


class RoomSelector(QLineEdit):
    def __init__(self, modified=None, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.__callback = modified

    def mousePressEvent(self, event):
        classroom = db_read_unique_field(
            "CLASSES", "CLASSROOM", CLASS=get_coursedata().CLASS
        )
        result = RoomDialog.popup(start_value=self.text(), classroom=classroom)
        if result:
            if result == "-":
                self.text_edited("")
            else:
                self.text_edited(result)

    def text_edited(self, text):
        if self.__callback and not self.__callback(text):
            return
        self.setText(text)


class DurationDelegate(QStyledItemDelegate):
    def __init__(self, table, modified=None):
        super().__init__(parent=table)
        self.__table = table
        self.__modified = modified

    class Editor(DurationSelector):
        def showEvent(self, event):
            QTimer.singleShot(0, self.showPopup)

    def createEditor(self, parent, option, index):
        e = self.Editor(parent=parent)
        return e

    def setEditorData(self, editor, index):
        self.val0 = index.data()
        editor.setText(self.val0)

    def setModelData(self, editor, model, index):
        text = editor.currentText()
        #        self.__table.clearFocus()
        # print("?-------", text, text != self.val0)
        if text != self.val0:
            if (not self.__modified) or self.__modified(index.row(), text):
                model.setData(index, text)
        self.__table.setFocus()


class DayPeriodDelegate(QStyledItemDelegate):
    def __init__(self, table, modified=None):
        super().__init__(parent=table)
        self.__table = table
        self.__modified = modified

    class Editor(QLineEdit):
        # The line-edit is not used, but it has the necessary properties ...
        def showEvent(self, event):
            QTimer.singleShot(0, self.clearFocus)

    def createEditor(self, parent, option, index):
        return self.Editor(parent)

    def setModelData(self, editor, model, index):
        # This gets called on activation (thanks to the <showEvent>
        # method in <Editor>).
        old_value = model.data(index)  # or editor.text()
        # print("§§§ old:", old_value)
        rect = self.__table.visualRect(index)
        pos = self.__table.viewport().mapToGlobal(rect.bottomLeft())
        result = DayPeriodDialog.popup(old_value, pos=pos)
        if result is not None:
#            if (not self.__modified) or self.__modified(index.row(), result):
#                model.setData(index, result)

            if self.__modified:
                val = self.__modified(index.row(), result)
                if val is not None:
                    model.setData(index, val)
            else:
                model.setData(index, result)
        self.__table.setFocus()


class PartnersDelegate(QStyledItemDelegate):
    def __init__(self, table, modified=None):
        super().__init__(parent=table)
        self.__table = table
        self.__modified = modified

    class Editor(QLineEdit):
        # The line-edit is not used, but it has the necessary properties ...
        def showEvent(self, event):
            QTimer.singleShot(0, self.clearFocus)

    def createEditor(self, parent, option, index):
        return self.Editor(parent)

    def setModelData(self, editor, model, index):
        # This gets called on activation (thanks to the <showEvent>
        # method in <Editor>).
        old_value = model.data(index)  # or editor.text()
        # print("§§§ old:", old_value)

        rect = self.__table.visualRect(index)
        pos = self.__table.viewport().mapToGlobal(rect.bottomLeft())
        result = PartnersDialog.popup(old_value, pos=pos)
        # <result> can be empty -> no action,
        # it can be an existing "partners" entry,
        # it can have a +-prefix -> new entry,
        # it can be '-' -> clear it.
        if result:
            if (not self.__modified) or self.__modified(index.row(), result):
                model.setData(index, result.lstrip("+-"))
        self.__table.setFocus()
        # print("§§§ new", result)


class TableWidget(QTableWidget):
    def __init__(self, parent=None, changed_callback=None):
        self.changed_callback = changed_callback
        super().__init__(parent=parent)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.AnyKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked  # this one has a delay!
        )
        # Note that the <Return> key doesn't cause the editor to be opened,
        # so there is an event handling that ... see method <keyPressEvent>.

        # Change stylesheet to make the selected cell more visible
        self.setStyleSheet(
            """QTableView {
               selection-background-color: #f0e0ff;
               selection-color: black;
            }
            QTableView::item:focus {
                selection-background-color: #d0ffff;
            }
            """
        )

    def keyPressEvent(self, e):
        e.accept()
        key = e.key()
        if key == Qt.Key_Return:
            if self.state() != self.EditingState:
                self.editItem(self.currentItem())
        else:
            super().keyPressEvent(e)


class BlockTagDialog(QDialog):
    """Select the block tag (subject + identifier) for a block. The
    identifier may be empty.

    A block tag is associated with multiple "course-lessons", though
    each tag should only occur once in any particular course.

    The "lessons" belonging to the currently shown  block tag are
    displayed. In addition a list of associated courses is shown. These
    displays are only for informational purposes, they are not editable.
    """

    @classmethod
    def popup(cls, block_tag, force_changed=False):
        d = cls()
        return d.activate(block_tag, force_changed)

    @staticmethod
    def sidtag2value(sid, tag):
        """Encode a block tag, given the subject-id and identifier-tag."""
        if sid and sid != "--":
            return f"{sid}#{tag}"
        else:
            return tag

    def __init__(self):
        super().__init__()
        vbox0 = QVBoxLayout(self)
        hbox1 = QHBoxLayout()
        vbox0.addLayout(hbox1)

        vbox1 = QVBoxLayout()
        hbox1.addLayout(vbox1)
        vbox1.addWidget(QLabel(f'{T["Block_name"]}:'))
        self.subject = KeySelector(changed_callback=self.sid_changed)
        vbox1.addWidget(self.subject)

        vbox1.addWidget(QLabel(f'{T["Block_tag"]}:'))
        self.identifier = QComboBox(editable=True)
        self.identifier.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.identifier.currentTextChanged.connect(self.show_courses)
        vbox1.addWidget(self.identifier)
        self.identifier.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        validator = QRegularExpressionValidator(TAG_FORMAT)
        self.identifier.setValidator(validator)

        vbox1.addWidget(HLine())

        self.lesson_table = TableWidget()  # Read-only, no focus, no selection
        self.lesson_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.lesson_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.lesson_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        vbox1.addWidget(self.lesson_table)
        self.lesson_table.setColumnCount(3)

        self.lesson_table.setHorizontalHeaderLabels(
            (T["LENGTH"], T["TIME"], T["ROOMS"])
        )
        Hhd = self.lesson_table.horizontalHeader()
        Hhd.setMinimumSectionSize(60)
        self.lesson_table.resizeColumnsToContents()
        Hhd.setStretchLastSection(True)

        self.course_list = QListWidget()  # Read-only, no focus, no selection
        self.course_list.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.course_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hbox1.addWidget(self.course_list)

        buttonBox = QDialogButtonBox()
        vbox0.addWidget(buttonBox)
        self.bt_save = buttonBox.addButton(QDialogButtonBox.StandardButton.Save)
        bt_cancel = buttonBox.addButton(QDialogButtonBox.StandardButton.Cancel)
        self.bt_save.clicked.connect(self.do_accept)
        bt_cancel.clicked.connect(self.reject)

    def activate(self, block_tag, force_changed=False):
        self.value0 = "***" if force_changed else str(block_tag)
        self.result = None
        try:
            __blocktag = read_block_tag(block_tag)
        except ValueError as e:
            SHOW_ERROR(str(e))
            return
        sid = __blocktag.sid
        if not sid:
            SHOW_ERROR(T["BLOCK_NO_SUBJECT"])
            return
        # N.B. the following line assumes the null subject ("--") is
        # the first entry in the complete subject list!
        subjects = get_subjects()[1:]
        self.subject.set_items(subjects)
        try:
            self.subject.reset(sid)
        except GuiError:
            SHOW_ERROR(T["UNKNOWN_SUBJECT_TAG"].format(sid=sid))
            sid = subjects[0][0]
        self.sid_changed(sid, __blocktag.tag)
        self.exec()
        return self.result

    def sid_changed(self, sid, tag=""):
        # print("sid changed:", sid)
        taglist = db_values(
            "BLOCKS",
            "LESSON_TAG",
            f"LESSON_TAG LIKE '{sid}#%'",
            distinct=True,
            sort_field="LESSON_TAG",
        )
        # Disable show_courses callbacks here ...
        self.__block_show = True
        self.identifier.clear()
        self.identifier.addItems([t.split("#", 1)[1] for t in taglist])
        # ... until here, to avoid a spurious call
        self.__block_show = False
        # Set a dummy tag before initializing the tag editor, to ensure
        # that there is a call to <show_courses>.
        self.identifier.setEditText("*")
        self.identifier.setEditText(tag)
        return True  # accept

    def do_accept(self):
        tag = self.identifier.currentText()
        # An invalid tag should not be possible at this stage ...
        sid = self.subject.selected()
        tag_field = self.sidtag2value(sid, tag)
        # print("OK", time_field)
        # An unchanged value should not be possible here, but just in case
        if tag_field != self.value0:
            self.result = tag_field
        self.accept()

    def show_courses(self, identifier):
        """Populate the list widget with all courses having a lesson entry
        in the block.
        """
        if self.__block_show:
            return
        self.course_list.clear()
        sid = self.subject.selected()
        tag = f"{sid}#{identifier}"
        # print("§§§ tag:", tag, self.value0)
        self.bt_save.setEnabled(tag != self.value0)
        courselist = courses_with_lessontag(tag)
        dlist = []
        for c in courselist:
            # Present info about the course
            ci = get_course_info(c)
            dlist.append(f"{ci.CLASS}.{ci.GRP}: {ci.SUBJECT} ({ci.TEACHER})")
        self.course_list.addItems(dlist)
        lesson_list = sublessons(tag)
        # print("§§§ LENGTHS:", lesson_list)
        ltable = self.lesson_table
        ltable.clearContents()
        nrows = len(lesson_list)
        ltable.setRowCount(nrows)
        for r in range(nrows):
            lessonfields = lesson_list[r]
            # print("???", lessonfields)
            ltable.setItem(r, 0, QTableWidgetItem(str(lessonfields.LENGTH)))
            ltable.setItem(r, 1, QTableWidgetItem(lessonfields.TIME))
            ltable.setItem(r, 2, QTableWidgetItem(lessonfields.ROOMS))


class BlockTagSelector(QLineEdit):
    def __init__(self, parent=None, modified=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.__callback = modified

    def set_block(self, block_tag):
        """Check the value and display it appropriately:
        empty                   -> empty
        with subject and tag    -> subject #tag
        with subject, no tag    -> subject
        only tag                -> = tag
        """
        try:
            self.block_tag = read_block_tag(block_tag)
        except ValueError as e:
            SHOW_ERROR(str(e))
            self.set_result("")
            return
        if self.block_tag.sid:
            if self.block_tag.tag:
                self.setText(f"{self.block_tag.subject} #{self.block_tag.tag}")
            else:
                self.setText(self.block_tag.subject)
        elif self.block_tag.isNone():
            self.clear()
        else:
            self.setText(f"= {self.block_tag.tag}")

    def get_block(self):
        return str(self.block_tag)

    def mousePressEvent(self, event):
        if not self.block_tag.sid:
            # No subject => either payment-only or plain lesson
            return
        result = BlockTagDialog.popup(str(self.block_tag))
        # print("--->", result)
        if result is None:
            return
        self.set_result(result)

    def set_result(self, result):
        if self.__callback and not self.__callback(result):
            return
        # print("§ set:", result)
        self.set_block(result)


class RoomDialog(QDialog):
    @classmethod
    def popup(cls, start_value="", classroom=""):
        d = cls()
        d.init()
        return d.activate(start_value, classroom)

    def __init__(self):
        super().__init__()
        vbox0 = QVBoxLayout(self)
        hbox1 = QHBoxLayout()
        vbox0.addLayout(hbox1)
        vboxl = QVBoxLayout()
        hbox1.addLayout(vboxl)

        self.roomchoice = QTableWidget()
        self.roomchoice.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.roomchoice.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.roomchoice.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.roomchoice.setColumnCount(2)
        vboxl.addWidget(self.roomchoice)

        vboxm = QVBoxLayout()
        hbox1.addLayout(vboxm)

        bt_up = QToolButton()
        bt_up.setToolTip(T["Move_up"])
        bt_up.clicked.connect(self.move_up)
        vboxm.addWidget(bt_up)
        bt_up.setArrowType(Qt.ArrowType.UpArrow)
        bt_up.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        bt_down = QToolButton()
        bt_down.setToolTip(T["Move_down"])
        bt_down.clicked.connect(self.move_down)
        vboxm.addWidget(bt_down)
        bt_down.setArrowType(Qt.ArrowType.DownArrow)

        vboxm.addStretch(1)
        bt_left = QToolButton()
        vboxm.addWidget(bt_left)
        bt_left.setArrowType(Qt.ArrowType.LeftArrow)
        bt_left.setToolTip(T["Add_to_choices"])
        bt_left.clicked.connect(self.add2choices)
        bt_right = QToolButton()
        vboxm.addWidget(bt_right)
#        bt_right.setIcon(QIcon.fromTheme("trash"))
        bt_right.setIcon(QIcon.fromTheme("icon_edit-delete"))
        bt_right.setToolTip(T["Remove_from_choices"])
        bt_right.clicked.connect(self.discard_choice)
        vboxm.addStretch(1)

        vboxr = QVBoxLayout()
        hbox1.addLayout(vboxr)

        self.roomlist = QTableWidget()
        self.roomlist.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.roomlist.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.roomlist.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.roomlist.setColumnCount(2)
        vboxr.addWidget(self.roomlist)

        self.roomtext = QLineEdit()
        self.roomtext.editingFinished.connect(self.text_edited)
        vboxl.addWidget(self.roomtext)

        self.home = QPushButton(f"+ {T['CLASSROOM']}")
        self.home.clicked.connect(self.add_classroom)
        vboxl.addWidget(self.home)
        self.extra = QCheckBox(T["OTHER_ROOMS"])
        self.extra.stateChanged.connect(self.toggle_extra)
        vboxl.addWidget(self.extra)

        vbox0.addWidget(HLine())
        buttonBox = QDialogButtonBox()
        vbox0.addWidget(buttonBox)
        bt_save = buttonBox.addButton(QDialogButtonBox.StandardButton.Save)
        bt_cancel = buttonBox.addButton(QDialogButtonBox.StandardButton.Cancel)
        bt_clear = buttonBox.addButton(QDialogButtonBox.StandardButton.Discard)
        bt_clear.setText(T["Clear"])

        bt_save.clicked.connect(self.do_accept)
        bt_cancel.clicked.connect(self.reject)
        bt_clear.clicked.connect(self.do_clear)

    def text_edited(self):
        self.set_choices(self.roomtext.text())

    def checkroom(self, roomid, choice_list):
        """Check that the given room-id is valid.
        If there is a "classroom", "$" may be used as a short-form.
        A valid room-id is added to the list <self.choices>, <None> is returned.
        Otherwise an error message is returned (a string).
        """
        is_classroom = False
        if roomid == "$":
            if self.classroom:
                rid = self.classroom
                is_classroom = True
            else:
                return T["NO_CLASSROOM_DEFINED"]
        else:
            rid = roomid
            if rid == self.classroom:
                is_classroom = True
        if rid in choice_list or (is_classroom and "$" in choice_list):
            if is_classroom:
                return T["CLASSROOM_ALREADY_CHOSEN"]
            else:
                return f"{T['ROOM_ALREADY_CHOSEN']}: '{rid}'"
        if rid in self.room2line:
            return None
        return f"{T['UNKNOWN_ROOM_ID']}: '{rid}'"

    def add2choices(self, roomid=None):
        if not roomid:
            # Not the most efficient handler, but it uses shared code ...
            row = self.roomlist.currentRow()
            riditem = self.roomlist.item(row, 0)
            roomid = riditem.text()
        e = self.checkroom(roomid, self.choices)
        if e:
            SHOW_ERROR(e)
            return
        self.add_valid_room_choice(roomid)
        self.write_choices()

    def discard_choice(self):
        row = self.roomchoice.currentRow()
        if row >= 0:
            self.choices.pop(row)
            self.roomchoice.removeRow(row)
            self.write_choices()

    def add_classroom(self):
        self.add2choices("$")

    def toggle_extra(self, state):
        self.write_choices()

    def move_up(self):
        row = self.roomchoice.currentRow()
        if row <= 0:
            return
        row1 = row - 1
        item = self.roomchoice.takeItem(row, 0)
        self.roomchoice.setItem(row, 0, self.roomchoice.takeItem(row1, 0))
        self.roomchoice.setItem(row1, 0, item)
        item = self.roomchoice.takeItem(row, 1)
        self.roomchoice.setItem(row, 1, self.roomchoice.takeItem(row1, 1))
        self.roomchoice.setItem(row1, 1, item)

        t = self.choices[row]
        self.choices[row] = self.choices[row1]
        self.choices[row1] = t
        self.write_choices()
        self.roomchoice.selectRow(row1)

    def move_down(self):
        row = self.roomchoice.currentRow()
        row1 = row + 1
        if row1 == len(self.choices):
            return
        item = self.roomchoice.takeItem(row, 0)
        self.roomchoice.setItem(row, 0, self.roomchoice.takeItem(row1, 0))
        self.roomchoice.setItem(row1, 0, item)
        item = self.roomchoice.takeItem(row, 1)
        self.roomchoice.setItem(row, 1, self.roomchoice.takeItem(row1, 1))
        self.roomchoice.setItem(row1, 1, item)

        t = self.choices[row]
        self.choices[row] = self.choices[row1]
        self.choices[row1] = t
        self.write_choices()
        self.roomchoice.selectRow(row1)

    def write_choices(self):
        text = "/".join(self.choices)
        if self.extra.isChecked():
            text += "+"
        self.roomtext.setText(text)

    def do_accept(self):
        val = self.roomtext.text()
        if val != self.value0:
            if val:
                self.result = val
            else:
                self.result = "-"
        self.accept()

    def do_clear(self):
        if self.value0:
            self.result = "-"
        self.accept()

    def init(self):
        self.room2line = {}
        rooms = get_rooms()
        n = len(rooms)
        self.roomlist.setRowCount(n)
        for i in range(n):
            rid = rooms[i][0]
            self.room2line[rid] = i
            item = QTableWidgetItem(rid)
            self.roomlist.setItem(i, 0, item)
            item = QTableWidgetItem(rooms[i][1])
            self.roomlist.setItem(i, 1, item)
        completer = QCompleter(list(self.room2line))
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.roomtext.setCompleter(completer)
        self.roomlist.resizeColumnsToContents()
        Hhd = self.roomlist.horizontalHeader()
        Hhd.hide()
        # Hhd.setMinimumSectionSize(20)
        # A rather messy attempt to find an appropriate size for the table
        Vhd = self.roomlist.verticalHeader()
        Vhd.hide()
        Hw = Hhd.length()
        # Vw = Vhd.sizeHint().width()
        fixed_width = Hw + 20  # + Vw, if vertical headers in use
        self.roomlist.setFixedWidth(fixed_width)
        self.roomchoice.setFixedWidth(fixed_width)
        Hhd.setStretchLastSection(True)
        hh = self.roomchoice.horizontalHeader()
        hh.hide()
        # Check that this doesn't need toggling after a clear() ...
        hh.setStretchLastSection(True)
        self.roomchoice.verticalHeader().hide()

    def activate(self, start_value="", classroom=None):
        self.value0 = start_value
        self.result = None
        self.classroom = classroom
        if classroom:
            self.home.show()
        else:
            self.home.hide()
        self.set_choices(start_value)
        self.roomlist.selectRow(0)
        self.roomtext.setFocus()
        self.exec()
        return self.result

    def set_choices(self, text):
        if text.endswith("+"):
            extra = True
            text = text[:-1]
        else:
            extra = False
        rids = text.split("/")
        errors = []
        _choices = []
        for rid in rids:
            if not rid:
                continue
            e = self.checkroom(rid, _choices)
            if e:
                if len(errors) > 3:
                    errors.append("  ...")
                    break
                errors.append(e)
            else:
                _choices.append(rid)
        else:
            # Perform changes only if not too many errors
            self.choices = []
            self.roomchoice.setRowCount(0)

            if _choices:
                for rid in _choices:
                    self.add_valid_room_choice(rid)
                self.roomchoice.selectRow(0)
            self.extra.setCheckState(
                Qt.CheckState.Checked if extra else Qt.CheckState.Unchecked
            )
        if errors:
            elist = "\n".join(errors)
            SHOW_ERROR(f"{T['INVALID_ROOM_IDS']}:\n{elist}")
        self.write_choices()

    def add_valid_room_choice(self, rid):
        """Append the room with given id to the choices table.
        This assumes that the validity of <rid> has already been checked!
        """
        self.choices.append(rid)
        if rid == "$":
            rid = self.classroom
        row = self.room2line[rid]
        at_row = self.roomchoice.rowCount()
        self.roomchoice.insertRow(at_row)
        self.roomchoice.setItem(at_row, 0, self.roomlist.item(row, 0).clone())
        self.roomchoice.setItem(at_row, 1, self.roomlist.item(row, 1).clone())
        self.roomchoice.resizeColumnsToContents()


class SingleRoomDialog(QDialog):
    @classmethod
    def popup(cls, start_value="", classroom=""):
        d = cls()
        d.init()
        return d.activate(start_value, classroom)

    def __init__(self):
        super().__init__()
        vbox0 = QVBoxLayout(self)

        self.roomlist = QTableWidget()
        self.roomlist.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.roomlist.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.roomlist.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.roomlist.setColumnCount(2)
        self.roomlist.itemSelectionChanged.connect(self.selection_changed)
        vbox0.addWidget(self.roomlist)

        self.button_group = QButtonGroup(self)
        self.button_group.buttonClicked.connect(self.set_special)
        self.home = QRadioButton(T["CLASSROOM"])
        self.button_group.addButton(self.home)
        self.home.setFocusPolicy(Qt.NoFocus)
        vbox0.addWidget(self.home)
        self.extra = QRadioButton(T["SOME_ROOM"])
        self.button_group.addButton(self.extra)
        self.extra.setFocusPolicy(Qt.NoFocus)
        vbox0.addWidget(self.extra)
        self.noroom = QRadioButton(T["NO_ROOM"])
        self.button_group.addButton(self.noroom)
        self.noroom.setFocusPolicy(Qt.NoFocus)
        vbox0.addWidget(self.noroom)

        vbox0.addWidget(HLine())
        buttonBox = QDialogButtonBox()
        vbox0.addWidget(buttonBox)
        bt_save = buttonBox.addButton(QDialogButtonBox.StandardButton.Save)
        bt_cancel = buttonBox.addButton(QDialogButtonBox.StandardButton.Cancel)
        bt_save.clicked.connect(self.do_accept)
        bt_cancel.clicked.connect(self.reject)

    def selection_changed(self):
        if self.roomlist.selectedItems():
            bt = self.button_group.checkedButton()
            if bt:
                self.button_group.setExclusive(False)
                bt.setChecked(False)
                self.button_group.setExclusive(True)

    def set_special(self, button):
        self.roomlist.clearSelection()
        self.roomlist.clearFocus()

    def do_accept(self):
        if self.home.isChecked():
            val = "$"
        elif self.extra.isChecked():
            val = "+"
        elif self.noroom.isChecked():
            val = "-"
        else:
            row = self.roomlist.currentItem().row()
            val = self.roomlist.item(row, 0).text()
        if val != self.value0:
            if val:
                self.result = val
            else:
                self.result = "-"
        self.accept()

    def init(self):
        self.room2line = {}
        rooms = get_rooms()
        n = len(rooms)
        self.roomlist.setRowCount(n)
        for i in range(n):
            rid = rooms[i][0]
            self.room2line[rid] = i
            item = QTableWidgetItem(rid)
            self.roomlist.setItem(i, 0, item)
            item = QTableWidgetItem(rooms[i][1])
            self.roomlist.setItem(i, 1, item)
        self.roomlist.resizeColumnsToContents()
        Hhd = self.roomlist.horizontalHeader()
        Hhd.hide()
        # Hhd.setMinimumSectionSize(20)
        # A rather messy attempt to find an appropriate size for the table
        Vhd = self.roomlist.verticalHeader()
        Vhd.hide()
        Hw = Hhd.length()
        # Vw = Vhd.sizeHint().width()
        fixed_width = Hw + 20  # + Vw, if vertical headers in use
        self.roomlist.setFixedWidth(fixed_width)
        Hhd.setStretchLastSection(True)

    def activate(self, start_value="", classroom=None):
        self.value0 = start_value
        self.result = None
        self.classroom = classroom
        self.home.setVisible(bool(classroom))
        self.roomlist.clearSelection()
        self.roomlist.clearFocus()
        if start_value == "$":
            if classroom:
                self.home.setChecked(True)
            else:
                SHOW_ERROR(T["NO_CLASSROOM"])
                self.noroom.setChecked(True)
        elif start_value == "+":
            self.extra.setChecked(True)
        elif start_value:
            try:
                row = self.room2line[start_value]
                self.roomlist.selectRow(row)
                # Clear check-buttons from previous activation:
                self.selection_changed()
            except KeyError:
                SHOW_ERROR(f"{T['UNKNOWN_ROOM_ID']}: '{start_value}'")
                self.noroom.setChecked(True)
        else:
            self.noroom.setChecked(True)
        self.exec()
        return self.result


class PaymentDialog(QDialog):
    @classmethod
    def popup(cls, start_value=""):
        d = cls()
        return d.activate(start_value)

    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.number = QLineEdit()
        form.addRow(T["NUMBER"], self.number)
        v = QRegularExpressionValidator(PAYMENT_FORMAT)
        self.number.setValidator(v)
        self.factor = KeySelector()
        form.addRow(T["FACTOR"], self.factor)
        self.factor.set_items(
            [("--", "0")]
            + [(k, f"{k} ({v})") for k, v in get_payment_weights()]
        )
        self.ptag = QLineEdit()
        form.addRow(T["PARALLEL_TAG"], self.ptag)
        v = QRegularExpressionValidator(PAYMENT_TAG_FORMAT)
        self.ptag.setValidator(v)
        form.addRow(HLine())
        buttonBox = QDialogButtonBox()
        form.addRow(buttonBox)
        bt_save = buttonBox.addButton(QDialogButtonBox.StandardButton.Save)
        bt_cancel = buttonBox.addButton(QDialogButtonBox.StandardButton.Cancel)
        bt_clear = buttonBox.addButton(QDialogButtonBox.StandardButton.Discard)
        bt_clear.setText(T["Clear"])
        bt_save.clicked.connect(self.do_accept)
        bt_cancel.clicked.connect(self.reject)
        bt_clear.clicked.connect(self.do_clear)

    def do_accept(self):
        n = self.number.text()
        f = self.factor.selected()
        t = self.ptag.text()
        if f == "--":
            if n or t:
                SHOW_ERROR(T["NULL_FACTOR_NOT_CLEAN"])
                return
            text = ""
        else:
            if t:
                if not n:
                    SHOW_ERROR(T["PAYTAG_WITH_NO_NUMBER"])
                    return
                t = "/" + t
            text = n + "*" + f + t
            try:
                # Check final value
                read_payment(text)
            except ValueError as e:
                SHOW_ERROR(str(e))
                return
        if text != self.text0:
            self.result = text
        self.accept()

    def do_clear(self):
        if self.text0:
            self.result = ""
        self.accept()

    def activate(self, start_value=""):
        self.result = None
        self.text0 = start_value
        try:
            pdata = read_payment(start_value)
            if pdata.isNone():
                self.number.setText("")
                self.factor.setCurrentIndex(0)
                self.ptag.setText("")
            else:
                if pdata.tag and not pdata.number:
                    SHOW_ERROR(T["PAYTAG_WITH_NO_NUMBER"])
                    self.ptag.setText("")
                else:
                    self.ptag.setText(pdata.tag)
                self.number.setText(pdata.number)
                self.factor.reset(pdata.factor)
        except ValueError as e:
            SHOW_ERROR(str(e))
            self.number.setText("1")
            self.factor.setCurrentIndex(1)
            self.ptag.setText("")
        self.exec()
        return self.result


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    open_database()

    #    for p in placements(">ZwE#09G10G"):
    #        print("!!!!", p)

    #    for p in partners("sp03"):
    #        print("??????", p)

    widget = DayPeriodDialog()
    widget.init()
    #    widget.resize(1000, 550)
    #    widget.exec()

    print("----->", widget.activate(""))
    print("----->", widget.activate("Di.4"))
    print("----->", widget.activate("Di.9"))

    widget = PaymentDialog()
    print("----->", widget.activate(start_value="2*HuEp"))
    print("----->", widget.activate(start_value=""))
    print("----->", PaymentDialog.popup(start_value="0,5*HuEp/tag1"))
    print("----->", widget.activate(start_value="Fred*HuEp"))

    #    quit(0)

    widget = BlockTagDialog()
    print("----->", widget.activate("XXX#"))
    print("----->", widget.activate("ZwE#09G10G"))
    print("----->", widget.activate("Hu#"))
    print("----->", widget.activate("NoSubject"))

    #    quit(0)

    #    widget = PartnersDialog()
    #    print("----->", widget.activate("huO"))

    #    quit(0)

    widget = RoomDialog()
    widget.init()
    print("----->", widget.activate(start_value="$/rPh+", classroom="r10G"))

    #    quit(0)

    widget = SingleRoomDialog()
    widget.init()
    print("----->", widget.activate(start_value="rPh", classroom="r10G"))
    print("----->", widget.activate(start_value="rCh", classroom="r10G"))
    print("----->", widget.activate(start_value="+", classroom="r10G"))
    print("----->", widget.activate(start_value="$"))
    print("----->", widget.activate(start_value="r11G", classroom="r10G"))
