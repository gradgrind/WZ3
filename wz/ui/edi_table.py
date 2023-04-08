"""
ui/edi_table.py

Last updated:  2023-04-08

An editable table widget using QTableWidget as base class. Only text
cells are handled.
Originally inspired by "TableWidget.py" from the "silx" project
(www.silx.org), thanks to P. Knobel, but it is now very different.
Little attention has been paid to efficiency, and especially the
undo-redo mechanism could consume a lot of space – it stacks
complete snapshots of the table (as lists of lists).

=+LICENCE=================================
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

=-LICENCE=================================
"""

from PyQt6.QtWidgets import (
    QApplication,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QSize, QLocale
from PyQt6.QtGui import QKeySequence
from PyQt6.QtGui import QAction      # was in QtWidgets in Qt5


class RangeError(Exception):
    pass

class Bug(Exception):
    pass

#######################################################################

Messages = {
    "en": {
        "SELECT_ALL": "Select all",
        "TTSELECT_ALL": "Select all cells of the table",
        "UNSELECT": "Unselect",
        "TTUNSELECT": "Clear the selection",
        "TOO_MANY_ROWS": "Too many rows to insert",
        "TOO_MANY_COLUMNS": "Too many columns to insert",
        "BAD_PASTE_RANGE": (
            "Clipboard data dimensions incompatible with selected range"
        ),
        "PASTE_PROTECTED": (
            "Some data could not be inserted because"
            " of write-protected cells"
        ),
        "CUTSELECTION": "Cut selection",
        "TTCUTSELECTION": (
            "Cut selection, placing cell values in the clipboard."
        ),
        "COPYSELECTION": "Copy selection",
        "TTCOPYSELECTION": "Copy selected cells into the clipboard.",
        "COPYFAIL": "No cells are selected",
        "PASTE": "Paste",
        "TTPASTE": (
            "Paste data. The selected cell is the top-left corner"
            " of the paste area."
        ),
        "INSERTROW": "Insert Row(s)",
        "TTINSERTROW": "Insert Row(s) after the current row.",
        "ROWOPFAIL": "No rows selected",
        "DELETEROWS": "Delete Row(s)",
        "TTDELETEROWS": "Delete selected Row(s)",
        "DELETEROWSFAIL": "Deleting all rows is not permitted",
        "INSERTCOLUMN": "Insert Column(s)",
        "TTINSERTCOLUMN": "Insert Column(s) after the current column.",
        "DELETECOLUMNS": "Delete Column(s)",
        "TTDELETECOLUMNS": "Delete selected Column(s)",
        "DELETECOLUMNSFAIL": "Deleting all columns is not permitted",
        "COLUMNOPFAIL": "No columns selected",
        "UNDO": "Undo",
        "TTUNDO": "Undo the last change",
        "REDO": "Redo",
        "TTREDO": "Redo the last undone change",
        "VALIDATION_ERROR": "Validation Error",
        "WARNING": "Warning",
    },

    "de": {
        "SELECT_ALL": "Alles auswählen",
        "TTSELECT_ALL": "Ganze Tabelle auswählen",
        "UNSELECT": "Auswahl zurücksetzen",
        "TTUNSELECT": "keine Zellen sollen ausgewählt sein",
        "TOO_MANY_ROWS": "Einfügen nicht möglich – zu viele Zeilen",
        "TOO_MANY_COLUMNS": "Einfügen nicht möglich – zu viele Spalten",
        "BAD_PASTE_RANGE": (
            "Die Dimensionen der einzufügenden Daten sind nicht"
            " kompatibel mit dem ausgewählten Bereich."
        ),
        "PASTE_PROTECTED": (
            "Zellen sind schreibgeschützt – einfügen nicht möglich"
        ),
        "CUTSELECTION": "Auswahl ausschneiden",
        "TTCUTSELECTION": (
            "Auswahl ausschneiden und in die Zwischanablage kopieren."
        ),
        "COPYSELECTION": "Auswahl kopieren",
        "TTCOPYSELECTION": (
            "Ausgewählte Zellen in die Zwischanablage kopieren."
        ),
        "COPYFAIL": "Keine ausgewählten Zellen",
        "PASTE": "Einfügen",
        "TTPASTE": (
            "Daten einfügen. Die ausgewählte Zelle ist oben links"
            " im Bereich, der eingefügt wird."
        ),
        "INSERTROW": "Zeile(n) einfügen",
        "TTINSERTROW": "Zeile(n) einfügen nach der aktuellen Zeile",
        "ROWOPFAIL": "Keine Zeilen sind ausgewählt",
        "DELETEROWS": "Zeile(n) löschen",
        "TTDELETEROWS": "ausgewählte Zeilen löschen",
        "DELETEROWSFAIL": "Das Löschen aller Zeilen ist nicht zulässig",
        "INSERTCOLUMN": "Spalte(n) einfügen",
        "TTINSERTCOLUMN": "Spalte(n) einfügen nach der aktuellen Spalte",
        "DELETECOLUMNS": "Spalte(n) löschen",
        "TTDELETECOLUMNS": "Ausgewählte Spalte(n) löschen",
        "DELETECOLUMNSFAIL": "Das Löschen aller Spalten ist nicht zulässig",
        "COLUMNOPFAIL": "Keine Spalten sind ausgewählt",
        "UNDO": "Rückgängig",
        "TTUNDO": "Die letzte Änderung rückgängig machen",
        "REDO": "Wiederherstellen",
        "TTREDO": "Die letzte rückgängig gemachte Änderung wiederherstellen",
        "VALIDATION_ERROR": "Ungültiger Wert",
        "WARNING": "Warnung",
    }
}

try:
    T = Messages[QLocale().name().split("_", 1)[0]]
except:
    print("Fallback to English messages")
    T = Messages["en"]

### -----


def tsv2table(text):
    """Parse a "tsv" (tab separated value) string into a list of lists
    of strings (a "table").

    The input text is tabulated using tabulation characters to separate
    the fields of a row and newlines to separate columns.

    The output lines are padded with '' values to ensure that all lines
    have the same length.

    Note that only '\n' is acceptable as the newline character. Other
    special whitespace characters will be left untouched.
    """
    rows = text.split("\n")
    # 'splitlines' can't be used as it loses trailing empty lines.
    table_data = []
    max_len = 0
    for row in rows:
        line = row.split("\t")
        l = len(line)
        if l > max_len:
            max_len = l
        table_data.append((line, l))
    result = []
    for line, l in table_data:
        if l < max_len:
            line += [""] * (max_len - l)
        result.append(line)
    return result


def table2tsv(table):
    """Represent a list of lists of strings (a "table") as a "tsv"
    (tab separated value) string.
    """
    return "\n".join(["\t".join(row) for row in table])


class EdiTableWidget(QTableWidget):
    """This adds features to the standard table widget and makes a
    number of assumptions about the usage – specifically to provide a
    useful base for a table editor dealing with string data only.
    """

    def new_action(
        self, text=None, icontext=None, tooltip=None, shortcut=None, function=None
    ):
        action = QAction(self)
        if text:
            action.setText(text)
        if icontext:
            action.setIconText(icontext)
        # The tooltip is not shown in a popup (context) menu ...
        if tooltip:
            if shortcut:
                tooltip += f" – [{shortcut.toString()}]"
            action.setToolTip(tooltip)
        # action.setStatusTip(
        # action.setIcon(
        if shortcut:
            action.setShortcut(shortcut)
        # action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        if function:
            action.triggered.connect(function)
        self.addAction(action)
        return action

    def context_menu_spacer(self):
        # self.sep_rowactions = QAction(self)
        sep = QAction(" ", self)
        sep.setSeparator(True)
        self.addAction(sep)
        return sep

    def __on_selection_state_change(self, sel):
        # print("SELECTION " + ("ON" if sel else "EMPTY"))
        pass

    def set_align_centre(self):
        self.align_centre = True

    def set_on_selection_state_change(self, f):
        self.on_selection_state_change = f

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setItemPrototype(ValidatingWidgetItem())
        self.setSelectionMode(
            QAbstractItemView.SelectionMode.ContiguousSelection
        )
        self.has_selection = False
        self.align_centre = False
        self.on_selection_state_change = self.__on_selection_state_change
        self.undo_stack = []
        self.redo_stack = []

        ### Actions
        # QAction to select all cells.
        # This seems to override the built-in shortcut, but only if the
        # table "has keyboard focus".
        self.select_all = self.new_action(
            text=T["SELECT_ALL"],
            tooltip=T["TTSELECT_ALL"],
            shortcut=QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_A),
            function=self.selectAll,
        )

        # QAction to clear the selection.
        self.unselect = self.new_action(
            text=T["UNSELECT"],
            tooltip=T["TTUNSELECT"],
            shortcut=QKeySequence(
                Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_A
            ),
            function=self.clearSelection,
        )

        self.context_menu_spacer()

        # QAction to copy selected cells to clipboard.
        self.copyCellsAction = self.new_action(
            text=T["COPYSELECTION"],
            tooltip=T["TTCOPYSELECTION"],
            shortcut=QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_C),
            function=self.copyCellsToClipboard,
        )

        # QAction to paste clipboard at selected cell(s).
        self.pasteCellsAction = self.new_action(
            text=T["PASTE"],
            tooltip=T["TTPASTE"],
            shortcut=QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_V),
            function=self.pasteCellFromClipboard,
        )

        # QAction to cut selected cells to clipboard.
        self.cutCellsAction = self.new_action(
            text=T["CUTSELECTION"],
            tooltip=T["TTCUTSELECTION"],
            shortcut=QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_X),
            function=self.cutCellsToClipboard,
        )

        self.sep_rowactions = self.context_menu_spacer()

        # QAction to insert a row or rows of cells.
        self.insertRowAction = self.new_action(
            text=T["INSERTROW"],
            tooltip=T["TTINSERTROW"],
            shortcut=QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_N),
            function=self.insert_row,
        )

        # QAction to delete a row or rows of cells.
        self.deleteRowsAction = self.new_action(
            text=T["DELETEROWS"],
            tooltip=T["TTDELETEROWS"],
            shortcut=QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_U),
            function=self.delete_rows,
        )

        self.sep_colactions = self.context_menu_spacer()

        # QAction to insert a column or columns of cells.
        self.insertColumnAction = self.new_action(
            text=T["INSERTCOLUMN"],
            tooltip=T["TTINSERTCOLUMN"],
            shortcut=QKeySequence(
                Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_N
            ),
            function=self.insert_column,
        )

        # QAction to delete a column or columns of cells.
        self.deleteColumnsAction = self.new_action(
            text=T["DELETECOLUMNS"],
            tooltip=T["TTDELETECOLUMNS"],
            shortcut=QKeySequence(
                Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_U
            ),
            function=self.delete_columns,
        )

        self.sep_undoredo = self.context_menu_spacer()

        # QAction to undo last change
        self.undoAction = self.new_action(
            text=T["UNDO"],
            tooltip=T["TTUNDO"],
            shortcut=QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Z),
            function=self.undo,
        )

        # QAction to redo last undone change
        self.redoAction = self.new_action(
            text=T["REDO"],
            tooltip=T["TTREDO"],
            shortcut=QKeySequence(
                Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_Z
            ),
            function=self.redo,
        )

    def setup(
        self,
        colheaders=None,        # list[str] of column headers
        rowheaders=None,        # list[str] of row headers
        undo_redo=False,        # enable undo/redo actions
        cut=False,              # enable cut action
        paste=False,            # enable paste action
        row_add_del=False,      # enable adding/deleting a table row
        column_add_del=False,   # enable adding/deleting a table column
        on_change=None,         # callback function: table changed
        # <on_change> takes no arguments.
    ):
        """Inizialize the table.
        Only the copy action is enabled by default.
        If column headers are provided, adding/deleting columns is forbidden.
        If row headers are provided, adding/deleting rows is forbidden.
        """
        self.on_change = on_change
        self.colheaders = colheaders
        self.rowheaders = rowheaders
        if colheaders:
            if column_add_del:
                raise Bug(
                    "Changing number of columns is not permitted"
                    " if column headers are provided"
                )
            self.setColumnCount(len(colheaders))
            self.setHorizontalHeaderLabels(colheaders)
        if rowheaders:
            if row_add_del:
                raise Bug(
                    "Changing number of rows is not permitted"
                    " if row headers are provided"
                )
            self.setRowCount(len(rowheaders))
            self.setVerticalHeaderLabels(rowheaders)
        ### Enable desired actions
        self.undoredo_enabled = undo_redo
        self.sep_undoredo.setVisible(undo_redo)
        self.undoAction.setVisible(undo_redo)
        self.redoAction.setVisible(undo_redo)
        self.undoAction.setEnabled(False)
        self.redoAction.setEnabled(False)

        self.cutCellsAction.setVisible(cut)
        # self.cutCellsAction.setEnabled(cut)
        self.pasteCellsAction.setVisible(paste)
        # self.pasteCellsAction.setEnabled(paste)
        self.sep_rowactions.setVisible(row_add_del)

        self.insertRowAction.setVisible(row_add_del)
        self.deleteRowsAction.setVisible(row_add_del)
        self.sep_colactions.setVisible(column_add_del)
        self.insertColumnAction.setVisible(column_add_del)
        self.deleteColumnsAction.setVisible(column_add_del)
        self.insertRowAction.setEnabled(False)
        self.deleteRowsAction.setEnabled(False)
        self.insertColumnAction.setEnabled(False)
        self.deleteColumnsAction.setEnabled(False)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)

        #self.cellChanged.connect(self.cell_changed)
        self.cellClicked.connect(self.cell_clicked)
        #self.cellActivated.connect(self.newline_press)
        #self.cellDoubleClicked.connect(self.newline_press)
        self.cellDoubleClicked.connect(self.click2)

    def init0(self, rows, columns):
        """Set the initial number of rows and columns and check that
        this is not in conflict with headers, if these have been set.
        """
        self.clearContents()
        self.undo_stack.clear()
        self.redo_stack.clear()
        if self.colheaders:
            if columns != len(self.colheaders):
                raise Bug("Number of columns doesn't match header list")
        else:
            self.setColumnCount(columns)
        if self.rowheaders:
            if rows != len(self.rowheaders):
                raise Bug("Number of rows doesn't match header list")
        else:
            self.setRowCount(rows)
        if rows:
            self.insertRowAction.setEnabled(True)
            self.deleteRowsAction.setEnabled(True)
            self.insertColumnAction.setEnabled(True)
            self.deleteColumnsAction.setEnabled(True)
        self.setFocus()

    def init_data(self, data):
        """Set the initial table data from a (complete) list of lists
        of strings.
        """
        self.table_data0 = data
        self.table_data = data
        rows = len(data)
        columns = len(data[0])
        self.init0(rows, columns)
        # Disable change reporting
        self.suppress_change_report = True
        # Enter data
        for r in range(rows):
            for c in range(columns):
                val = data[r][c]
                # print("SET", r, c, repr(val))
                if isinstance(val, str):
                    item = ValidatingWidgetItem(val)
                    if self.align_centre:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.setItem(r, c, item)
                else:
                    raise Bug("Only string data is accepted")
        # Enable change reporting
        self.suppress_change_report = False

    def init_sparse_data(self, rows, columns, data_list):
        """Set the initial table data from a list of cell values.
        data_list is a list of tuples: [(row, column, value), ... ].
        All other cells are empty strings.
        """
        data = [[""] * columns for r in range(rows)]
        # Enter data
        for r, c, val in data_list:
            data[r][c] = val
        self.init_data(data)

    def get_text(self, row, col):
        """Convenience method for reading a cell from the QTableWidget."""
        data_model = self.model()
        return data_model.data(data_model.index(row, col)) or ""

    def set_text(self, row, col, text):
        """Convenience method for writing a cell."""
        data_model = self.model()
        data_model.setData(data_model.index(row, col), text)

    def read_block(self, top, left, width, height):
        """Read a block of data from the table.
        Return list of rows, each row is a list of cell values.
        """
        if width == 0 or height == 0:
            raise Bug("Can't read block with no dimensions")
        r1 = top + height
        c1 = left + width
        rows = []
        while top < r1:
            rowdata = []
            c = left
            while c < c1:
                rowdata.append(self.get_text(top, c))
                c += 1
            top += 1
            rows.append(rowdata)
        return rows

    def set_validator(self, row, col, f_validate):
        """Set a validator on the cell at (row, col).
        This uses the <set_validator> method of the widget item
        (QTableWidgetItem) at the given position. A <ValidatingWidgetItem>
        provides this method.

        <f_validate> is a function taking just the value as argument.
        If this is valid, the function returns <None>. Otherwise it
        returns an error message.
        """
        self.item(row, col).set_validator(f_validate)

    def cell_value_changed(self, r, c, value, v0):
        if self.suppress_change_report:
            return
        self.data_modified()
        # print("§§§", r, c, value, v0)

    def read_all(self):
        """Read all the table data.
        Return list of rows, each row is a list of cell values.
        """
        return self.read_block(0, 0, self.columnCount(), self.rowCount())

    def insert_row(self):
        """Insert an empty row below the currenty selected one(s).
        If multiple rows are selected, the same number of rows will be
        added after the last selected row.
        """
        selected = self.get_selection()
        if selected[0]:
            h = selected[4]
            r = selected[1] + h
        else:
            QMessageBox.warning(self, T["WARNING"], T["ROWOPFAIL"])
            return
        while h > 0:
            self.insertRow(r)
            h -= 1
        self.data_modified()

    def insert_column(self):
        """Insert an empty column after the currently selected one(s).
        If multiple columns are selected, the same number of columns
        will be added after the last selected column.
        """
        selected = self.get_selection()
        if selected[0]:
            w = selected[3]
            c = selected[2] + w
        else:
            QMessageBox.warning(self, T["WARNING"], T["COLUMNOPFAIL"])
            return
        while w > 0:
            self.insertColumn(c)
            w -= 1
        self.data_modified()

    def delete_rows(self):
        """Delete the selected rows."""
        selected = self.get_selection()
        if selected[0]:
            n = selected[4]
            r0 = selected[1]
        else:
            QMessageBox.warning(self, T["WARNING"], T["ROWOPFAIL"])
            return
        if n == self.rowCount():
            QMessageBox.warning(self, T["WARNING"], T["DELETEROWSFAIL"])
            return
        r = r0 + n
        while r > r0:
            r -= 1
            self.removeRow(r)
        self.data_modified()

    def delete_columns(self):
        """Delete the selected columns."""
        selected = self.get_selection()
        if selected[0]:
            n = selected[3]
            c0 = selected[2]
        else:
            QMessageBox.warning(self, T["WARNING"], T["COLUMNOPFAIL"])
            return
        if n == self.columnCount():
            QMessageBox.warning(self, T["WARNING"], T["DELETECOLUMNSFAIL"])
            return
        c = c0 + n
        while c > c0:
            c -= 1
            self.removeColumn(c)
        self.data_modified()

    def click2(self):
        """Double-click"""
        print("click2")
        self.editItem(self.currentItem())
#        self.activated(self.currentRow(), self.currentColumn())

    def cell_clicked(self, row, col):
        """Ctrl-Click "activates" the cell."""
        if (
            QApplication.keyboardModifiers()
            & Qt.KeyboardModifier.ControlModifier
        ) and self.get_selection()[0] == 1:
            self.activated(row, col)
#        self.editItem(self.item(row, col))

    def activated(self, row, col):
        # This is called when two conditions are fulfilled:
        #   1) the control button is pressed,
        #   2) a cell is left-clicked, or the (single) selected cell
        #      has "Return/Newline" pressed.
        # See 'activate-on-singleclick' below.
        print("ACTIVATED:", row, col)

#    def newline_press(self, row, col):
#        if self.get_selection()[0] == 1:
#            # if self.get_selection()[0] <= 1:
#            self.activated(row, col)

    @staticmethod
    def _get_point(event):
        # PySide2:
        return event.pos()
        # PySide6:
        return event.position().toPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clearSelection()
            self.setCurrentIndex(self.indexAt(self._get_point(event)))
            if (
                QApplication.keyboardModifiers()
                & Qt.KeyboardModifier.ControlModifier
            ):
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and (
                QApplication.keyboardModifiers()
                & Qt.KeyboardModifier.ControlModifier
            )
        ):
            if self.get_selection()[0] == 1:
                ix = self.indexAt(self._get_point(event))
                self.activated(ix.row(), ix.column())
                return
            else:
                self.clearSelection()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self.state() != self.State.EditingState:
            key = event.key()
            if key == Qt.Key.Key_Delete:
                if self.cut_selection() is None:
                    self.set_text(self.currentRow(), self.currentColumn(), "")
                return  # in this case don't call the base class method
            if key == Qt.Key.Key_Return and self.get_selection()[0] == 1:
                if (
                    QApplication.keyboardModifiers()
                    & Qt.KeyboardModifier.ControlModifier
                ):
                    self.activated(self.currentRow(), self.currentColumn())
                else:
                    self.editItem(self.currentItem())
#                self.newline_press(self.currentRow(), self.currentColumn())
        super().keyPressEvent(event)

    def copyCellsToClipboard(self):
        """Concatenate the text content of all selected cells into a string
        using tabulations and newlines to keep the table structure.
        Put this text into the clipboard.
        """
        n, t, l, w, h = self.get_selection()
        if n:
            rows = self.read_block(t, l, w, h)
            # put this data into clipboard
            qapp = QApplication.instance()
            qapp.clipboard().setText(table2tsv(rows))
        else:
            QMessageBox.warning(self, T["WARNING"], T["COPYFAIL"])

    def cutCellsToClipboard(self):
        """Concatenate the text content of all selected cells into a string
        using tabulations and newlines to keep the table structure.
        Put this text into the clipboard. Clear the selected cells.
        """
        block = self.cut_selection()
        if block is None:
            QMessageBox.warning(self, T["WARNING"], T["COPYFAIL"])
        else:
            # put this data into clipboard
            qapp = QApplication.instance()
            qapp.clipboard().setText(block)

    def cut_selection(self):
        """Cut the selected range, returning the contents as "tsv".
        """
        n, t, l, w, h = self.get_selection()
        if n == 0:
            return None
        changed = False
        self.suppress_change_report = True
        if n == 1:
            text = self.get_text(t, l)
            if text:
                changed = True
                self.set_text(t, l, "")
        else:
            block = self.read_block(t, l, w, h)
            r1 = t + h
            c1 = l + w
            while t < r1:
                c = l
                while c < c1:
                    t0 = self.get_text(t, c)
                    if t0:
                        changed = True
                        self.set_text(t, c, "")
                    c += 1
                t += 1
            text = table2tsv(block)
        self.suppress_change_report = False
        if changed:
            self.data_modified()
        return text

    def get_selection(self):
        """Return the current selection:
        (number of cells, top row, left column, width, height)
        """
        selected = self.selectedRanges()
        if len(selected) > 1:
            raise Bug("Multiple selection is not supported")
        if not selected:
            return (0, -1, -1, 0, 0)
        selrange = selected[0]
        l = selrange.leftColumn()
        w = selrange.rightColumn() - l + 1
        t = selrange.topRow()
        h = selrange.bottomRow() - t + 1
        n = w * h
        assert(n)
        return (n, t, l, w, h)

    def pasteCellFromClipboard(self):
        """Paste text from clipboard into the table.

        Pasting to more than one selected cell is possible if the data
        to be pasted has "compatible" dimensions:
            A single cell can be pasted to any block.
            A single row of cells can be pasted to a single column of cells.
            A single column of cells can be pasted to a single row of cells.
            Otherwise a block of cells can only be pasted to a single cell.

        If the block to be pasted would affect cells outside the grid,
        the pasting will fail.
        """
        nrows = self.rowCount()
        ncols = self.columnCount()
        n, r0, c0, w, h = self.get_selection()
        if n == 0:
            QMessageBox.warning(self, T["WARNING"], T["COPYFAIL"])
            return
        qapp = QApplication.instance()
        clipboard_text = qapp.clipboard().text().rstrip('\n')
        table_data = tsv2table(clipboard_text)
        protected_cells = 0
        ph = len(table_data)
        pw = len(table_data[0])
        try:
            if ph == 1:  # paste a single row
                if w == 1:  # ... to a single column
                    paste_data = table_data * h
                elif pw == 1:  # paste a single cell
                    row = table_data[0] * w
                    paste_data = [row] * h
                else:
                    raise RangeError(T["BAD_PASTE_RANGE"])
            elif pw == 1:  # paste a single column
                if h == 1:  # ... to a single row
                    paste_data = [row * w for row in table_data]
                else:
                    raise RangeError(T["BAD_PASTE_RANGE"])
            elif n == 1:  # paste to a single cell
                paste_data = table_data
            else:
                raise RangeError(T["BAD_PASTE_RANGE"])
            # Check that the data to be pasted will fit into the table.
            if r0 + ph > nrows:
                raise RangeError(T["TOO_MANY_ROWS"])
            if c0 + pw > ncols:
                raise RangeError(T["TOO_MANY_COLUMNS"])
        except RangeError as e:
            QMessageBox.warning(self, T["WARNING"], str(e))
            return
        if protected_cells:
            QMessageBox.warning(self, T["WARNING"], T["PASTE_PROTECTED"])
        # Do the pasting
        self.suppress_change_report = True
        if self.paste_block(r0, c0, paste_data):
            self.data_modified()
        self.suppress_change_report = False

    def paste_block(self, top, left, block):
        """The block must be a list of lists of strings."""
        changed = False
        for row in block:
            c = left
            for cell in row:
                t0 = self.get_text(top, c)
                if cell != t0:
                    changed = True
                    self.set_text(top, c, cell)
                c += 1
            top += 1
        return changed

    def data_modified(self):
        """Handle changes to the table data.
        The new state is added to the undo-stack, if undo/redo is
        enabled. The redo-stack is cleared.
        Call <on_change> function.
        """
        newdata = self.read_all()
        if self.undoredo_enabled:
            self.redo_stack.clear()
            self.redoAction.setEnabled(False)
            if not self.undo_stack:
                self.undoAction.setEnabled(True)
            self.undo_stack.append(self.table_data)
        self.table_data = newdata
        if self.on_change:
            self.on_change()

    def undo(self):
        """Undo the last change.
        This should be "disabled", via its associated "action",
        when there are no changes to undo.
        """
        self.suppress_change_report = True
        try:
            data = self.undo_stack.pop()
            if not self.redo_stack:
                self.redoAction.setEnabled(True)
            self.redo_stack.append(self.table_data)
        except IndexError:
            raise Bug("No undo-data, undo not disabled ...")
        if not self.undo_stack:
            self.undoAction.setEnabled(False)
        rc = self.rowCount()
        cc = self.columnCount()
        drc = len(data)
        dcc = len(data[0])
        if rc != drc:
            self.setRowCount(drc)
        if cc != dcc:
            self.setColumnCount(dcc)
        self.paste_block(0, 0, data)
        self.table_data = data
        self.suppress_change_report = False
        if self.on_change:
            self.on_change()

    def redo(self):
        self.suppress_change_report = True
        try:
            data = self.redo_stack.pop()
            if not self.undo_stack:
                self.undoAction.setEnabled(True)
            self.undo_stack.append(self.table_data)
        except IndexError:
            raise Bug("No redo-data, redo not disabled ...")
        if not self.redo_stack:
            self.redoAction.setEnabled(False)
        rc = self.rowCount()
        cc = self.columnCount()
        drc = len(data)
        dcc = len(data[0])
        if rc != drc:
            self.setRowCount(drc)
        if cc != dcc:
            self.setColumnCount(dcc)
        self.paste_block(0, 0, data)
        self.table_data = data
        self.suppress_change_report = False
        if self.on_change:
            self.on_change()

    def selectionChanged(self, selected, deselected):
        """Override the slot. The parameters are <QItemSelection> items."""
        super().selectionChanged(selected, deselected)
        sel = bool(self.selectedRanges())
        if sel != self.has_selection:
            self.has_selection = sel
            self.on_selection_state_change(sel)
            # TODO: Enable/disable row/column actions? (also delete?)
            if sel:
                # Enable actions
                pass
            else:
                # Disable actions
                pass

    """
    def focusInEvent(self, event):
        self.focussed = True
        print("FOCUSSED TABLE")
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.focussed = False
        print("UNFOCUSSED TABLE")
        super().focusOutEvent(event)
    """


class ValidatingWidgetItem(QTableWidgetItem):
    def __init__(self, value=""):
        self.set_validator(None)
        super().__init__(value)

    def set_validator(self, validate):
        self.__validate = validate

    def clone(self):
        return ValidatingWidgetItem()

    def setData(self, role, value):
        if role != Qt.ItemDataRole.EditRole:
            super().setData(role, value)
            return
        if self.__validate:
            v = self.__validate(value)
            if v:
                QMessageBox.warning(
                    self.tableWidget(),
                    T["WARNING"],
                    T["VALIDATION_ERROR"] +
                    f" @({self.row()}, {self.column()}): {value}",
                )
                return
        v0 = self.data(role)
        if v0 == value:
            return
        tw = self.tableWidget()
        assert(tw)
        r, c = self.row(), self.column()
        #print(f"CHANGED @({r}, {c}): {v0} -> {value}")
        super().setData(role, value)
        tw.cell_value_changed(r, c, value, v0)


class VerticalTextDelegate(QStyledItemDelegate):
    """A <QStyledItemDelegate> for vertical text. It can be set on a
    row or column (or the whole table), not on single cells.
    """

    def paint(self, painter, option, index):
        optionCopy = QStyleOptionViewItem(option)
        rectCenter = QPointF(QRectF(option.rect).center())
        painter.save()
        painter.translate(rectCenter.x(), rectCenter.y())
        painter.rotate(-90.0)
        painter.translate(-rectCenter.x(), -rectCenter.y())
        optionCopy.rect = painter.worldTransform().mapRect(option.rect)

        # Call the base class implementation
        super().paint(painter, optionCopy, index)

        painter.restore()

    def sizeHint(self, option, index):
        val = QSize(super().sizeHint(option, index))
        return QSize(val.height(), val.width())


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    app = QApplication([])
    # This seems to deactivate activate-on-single-click
    # (presumably elsewhere as well?)
    #    app.setStyleSheet("QAbstractItemView { activate-on-singleclick: 0; }")
    def is_modified1():
        print("MODIFIED1")

    def is_modified2():
        print("MODIFIED2")

    def validate(value):
        if value == "v":
            return "invalid value"
        return None

    cols = ["Column %02d" % n for n in range(10)]
    rows = ["Row %02d" % n for n in range(7)]
    tablewidget = EdiTableWidget()
    tablewidget.set_align_centre()

#    tablewidget.installEventFilter(tablewidget)
    tablewidget.setup(colheaders=cols, rowheaders=rows, on_change=is_modified1)

    tablewidget.setWindowTitle("EdiTableWidget")

    # setItemDelegate doesn't take ownership of the custom delegates,
    # so I retain references (otherwise there will be a segfault).
    idel1 = VerticalTextDelegate()
    #    idel2 = MyDelegate()
    tablewidget.setItemDelegateForRow(2, idel1)
    #    tablewidget.setItemDelegateForRow(1, idel2)

    sparse_data = []
    r, c = 2, 3
    sparse_data.append((r, c, "R%02d:C%02d" % (r, c)))
    r, c = 1, 4
    sparse_data.append((r, c, "R%02d:C%02d" % (r, c)))
    tablewidget.init_sparse_data(len(rows), len(cols), sparse_data)

    tablewidget.resizeRowToContents(1)
    tablewidget.resizeRowToContents(2)
    tablewidget.resizeColumnToContents(3)
    tablewidget.resize(600, 400)
    tablewidget.show()

    tw2 = EdiTableWidget()
    tw2.setup(
        undo_redo=True,
        cut=True,
        paste=True,
        row_add_del=True,
        column_add_del=True,
        on_change=is_modified2,
    )
    tw2.init_data([["1", "2", "3", "4"], [""] * 4])
    tw2.set_validator(1, 0, validate)
    tw2.resize(400, 300)
    tw2.show()

    app.exec()
