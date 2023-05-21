"""
ui/grid_support.py

Last updated:  2023-05-21

Support functions for table-grids using the QGraphicsView framework.

* Manage allocation of style resources, using caches.
* Provide a grid-based rectangle for use as a selection marker.


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

The coordinate system is such that rectangle borders are roughly
centred on the given coordinates. Regard a coordinate as a line without
width before the pixel which is actually drawn.
Given a coordinate x = 5:
    border = 1 => pixel 5
    border = 2 => pixels 4/5
    border = 3 => pixels 4/5/6
If a grid is drawn (separately from the tiles), it might be necessary
to adjust the coordinates of the tile so as not to paint over the grid.
Alternatively, putting the grid lines on top might be an easier solution.

"When rendering with a pen with an even number of pixels, the pixels will
be rendered symmetrically around the mathematically defined points, while
rendering with a pen with an odd number of pixels, the spare pixel will
be rendered to the right and below the mathematical point.
"

The grid area can be covered by boxes of predefined width and height.
I would suggest an optional box border of fixed width (but what does
"fixed width" mean here, e.g fixed pixels or fixed points/mm? As I am
aiming for a point/mm based specification, I would suggest the latter).
If there is no border there will be an empty gap – thus making the
geometry independent of the border. That would mean that "no border"
would need a transparent pen.
"""

##### Configuration #####################
GRID_COLOUR = "888800"  # rrggbb
SELECT_COLOUR = "2370ff"
FONT_SIZE_DEFAULT = 12
SELECT_WIDTH = 3
# FONT_DEFAULT = "Droid Sans"
FONT_DEFAULT = ""   # use system default

#####################################################

#T = TRANSLATIONS("ui.grid_support")

### +++++

from ui.ui_base import (
    ## QtWidgets
    QGraphicsRectItem,
    ## QtGui
    QFont,
    QPen,
    QColor,
    QBrush,
    ## QtCore
    Qt,
)

### -----

class StyleCache:
    """Manage allocation of style resources using caches."""

    __fonts = {}  # cache for QFont items
    __brushes = {}  # cache for QBrush items
    __pens = {}  # cache for QPen items

    @classmethod
    def getPen(cls, width: int, colour: str = "") -> QPen:
        """Manage a cache for pens of different width and colour.
        <width> should be a small integer.
        <colour> is a colour in the form 'RRGGBB'.
        """
        if width:
            # A temporary bodge to allow a transparent border
            if colour is None:
                wc = (width, None)
            else:
                wc = (width, colour or GRID_COLOUR)
            try:
                return cls.__pens[wc]
            except KeyError:
                pass
            # A temporary bodge to allow a transparent border
            if colour is None:
                pen = QPen(QColor("#00FFFFFF"))
            else:
                pen = QPen(QColor("#FF" + wc[1]))
            pen.setWidth(wc[0])
            cls.__pens[wc] = pen
            return pen
        else:
            try:
                return cls.__pens["*"]
            except KeyError:
                pen = QPen()
                pen.setStyle(Qt.PenStyle.NoPen)
                cls.__pens["*"] = pen
                return pen

    @classmethod
    def getBrush(cls, colour: str = "") -> QBrush:
        """Manage a cache for brushes of different colour.
        <colour> is a colour in the form 'RRGGBB'.
        """
        try:
            return cls.__brushes[colour or "*"]
        except KeyError:
            pass
        if colour:
            brush = QBrush(QColor("#FF" + colour))
            cls.__brushes[colour] = brush
        else:
            brush = QBrush()  # no fill
            cls.__brushes["*"] = brush
        return brush

    @classmethod
    def getFont(
        cls,
        fontFamily: str = FONT_DEFAULT,
        fontSize: int = FONT_SIZE_DEFAULT,
        fontBold: bool = False,
        fontItalic: bool = False,
    ) -> QFont:
        """Manage a cache for fonts. The font parameters are passed as
        arguments.
        """
        ftag = (fontFamily, fontSize, fontBold, fontItalic)
        try:
            return cls.__fonts[ftag]
        except KeyError:
            pass
        font = QFont()
        if fontFamily:
            font.setFamily(fontFamily)
        if fontSize:
            font.setPointSizeF(fontSize)
        if fontBold:
            font.setBold(True)
        if fontItalic:
            font.setItalic(True)
        cls.__fonts[ftag] = font
        return font


class Selection(QGraphicsRectItem):
    """A rectangle covering one or more cells.
    """
    def __init__(self, grid, parent=None):
        super().__init__(parent=parent)
        self.xmarks = grid.xmarks
        self.ymarks = grid.ymarks
        self.setPen(StyleCache.getPen(grid.pt2px(SELECT_WIDTH), SELECT_COLOUR))
        self.setZValue(20)
        grid.scene().addItem(self)
        self.clear()

    def on_context_menu(self):
        """Return false value to indicate that the selection context menu
        should be shown.
        This method will only be called when the selection is active
        (shown) and at the top of the item stack at the cursor position.
        """
        return False

    def clear(self):
        self.start_cellrc = (-1, -1)
        self.end_cellrc = (-1, -1)
        self.__range = (-1, -1, 0, 0)
        self.hide()

    def range(self):
        return self.__range

    def is_active(self):
        return self.isVisible()

    def set_pending(self, cellrc):
        """This is called on left-mouse-down. The actual selection only
        occurs after a small mouse movement.
        """
        self.start_cellrc = cellrc

    def is_primed(self):
        """Test whether a start cell is pending (or already set)."""
        return self.start_cellrc[0] >= 0

    def set_end_cell(self, cellrc):
        if self.end_cellrc != cellrc:
            self.end_cellrc = cellrc
            self.expose()

    def expose(self):
        r0, c0 = self.start_cellrc
        r1, c1 = self.end_cellrc
        # Ensure that r0 <= r1 and c0 <= c1
        if r0 > r1:
            r0, r1 = r1, r0
        if c0 > c1:
            c0, c1 = c1, c0
        self.__range = (r0, c0, r1 - r0 + 1, c1 - c0 + 1)
        # Get the coordinate boundaries
        x0 = self.xmarks[c0]
        y0 = self.ymarks[r0]
        x1 = self.xmarks[c1 + 1]
        y1 = self.ymarks[r1 + 1]
        self.setRect(x0, y0, x1 - x0, y1 - y0)
        self.show()
