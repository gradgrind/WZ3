"""
ui/timetable_grid.py

Last updated:  2023-05-29

A grid widget for the timetable displays.


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
    appdir = os.path.dirname(this)
    sys.path[0] = appdir
    basedir = os.path.dirname(appdir)
    from core.base import start
    start.setup(os.path.join(basedir, 'TESTDATA'))

#TODO ...
from ui.ui_base import (
    APP,
    # QtWidgets
    QGraphicsScene,
    QGraphicsRectItem,
    QGraphicsLineItem,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QMenu,
    # QtCore
    Qt,
    # QtGui
    QIcon,
    QPainter,
    QTransform,
)
from ui.grid_support import StyleCache

### +++++

MM2PT = 2.83464549
PT2MM = 0.3527778

# Sizes in points
A4 = (841.995, 595.35)
A3 = (1190.7, 841.995)
PAGE_SIZE = A4

_MARGIN_LEFT = 30
_MARGIN_RIGHT = 30
_MARGIN_TOP = 50
_MARGIN_BOTTOM = 50
_HEADER = 40
_FOOTER = 25

_TIMEWIDTH = 82
_BOXWIDTH = 142
_BOXHEIGHT = 51
_LINEWIDTH = 2
_TITLEHEIGHT = 30
_TITLEWIDTH = 82

_SUBTEXTGAP = 10    # minimum horizontal space between tile "subtexts"

# Fonts
FONT_HEADER_SIZE = 14
FONT_CENTRE_SIZE = 18
FONT_CORNER_SIZE = 11

# Colours (rrggbb)
BORDER_COLOUR = 'b0b0b0' # '12c6f8'
HEADER_COLOUR = 'f0f0f0'
MARGIN_LINE_COLOUR = '000000'
BREAK_COLOUR = '606060' # '6060d0'
#CELL_HIGHLIGHT_COLOUR = 'a0a0ff'
SELECT_COLOUR = 'ff0000'

# Tile corner enum
TILE_TOP_LEFT = 0
TILE_TOP_RIGHT = 1
TILE_BOTTOM_RIGHT = 2
TILE_BOTTOM_LEFT = 3

SIZES = {}

### -----

class GridView(QGraphicsView):
    """This is the "view" widget for the grid.
    The actual grid is implemented as a "scene".
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Change update mode: The default, MinimalViewportUpdate, seems
        # to cause artefacts to be left, i.e. it updates too little.
        # Also BoundingRectViewportUpdate seems not to be 100% effective.
        # self.setViewportUpdateMode(
        #     QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate
        # )
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.FullViewportUpdate
        )
        # self.setRenderHints(
        #     QPainter.RenderHint.Antialiasing
        #     | QPainter.RenderHint.SmoothPixmapTransform
        # )
        self.setRenderHints(QPainter.RenderHint.Antialiasing)
        # self.setRenderHints(QPainter.RenderHint.TextAntialiasing)
        self.ldpi = self.logicalDpiX()
        self.pdpi = self.physicalDpiX()
        #print("LDPI:", self.ldpi)
        #print("PDPI:", self.pdpi)
# Scaling the scene by pdpi/ldpi should display the correct size ...
        #self.MM2PT = self.ldpi / 25.4
#        self.scene = QGraphicsScene()
#        self.setScene(self.scene)

        ### Set up sizes (globally)
        SIZES["TITLEHEIGHT"] = self.pt2px(_TITLEHEIGHT)
        SIZES["TITLEWIDTH"] = self.pt2px(_TITLEWIDTH)
        SIZES["LINEWIDTH"] = self.pt2px(_LINEWIDTH)
        SIZES["SUBTEXTGAP"] = self.pt2px(_SUBTEXTGAP)

        SIZES["MARGIN_LEFT"] = self.pt2px(_MARGIN_LEFT)
        SIZES["MARGIN_RIGHT"] = self.pt2px(_MARGIN_RIGHT)
        SIZES["MARGIN_TOP"] = self.pt2px(_MARGIN_TOP)
        SIZES["MARGIN_BOTTOM"] = self.pt2px(_MARGIN_BOTTOM)
        SIZES["HEADER"] = self.pt2px(_HEADER)
        SIZES["FOOTER"] = self.pt2px(_FOOTER)

        SIZES["TABLEHEIGHT"] = (
            self.pt2px(
                PAGE_SIZE[1]) - SIZES["MARGIN_TOP"]
                - SIZES["MARGIN_BOTTOM"] - SIZES["HEADER"]
                - SIZES["FOOTER"]
        )
        SIZES["TABLEWIDTH"] = (
            self.pt2px(PAGE_SIZE[0]) - SIZES["MARGIN_LEFT"]
            - SIZES["MARGIN_RIGHT"]
        )
        print("§TABLE SIZE (pixels):", SIZES["TABLEWIDTH"], SIZES["TABLEHEIGHT"])

    def pt2px(self, pt) -> int:
        px = int(self.ldpi * pt / 72.0 + 0.5)
        # print(f"pt2px: {pt} -> {px} (LDPI: {self.ldpi})")
        return px

    def px2mm(self, px):
        mm = px * 25.4 / self.ldpi
        # print(f"px2mm: {px} -> {mm} (LDPI: {self.ldpi})")
        return mm


class GridViewRescaling(GridView):
    """An QGraphicsView that automatically adjusts the scaling of its
    scene to fill the viewing window.
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Disable the scrollbars when using this resizing scheme. They
        # should not appear anyway, but this might avoid problems.
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

    def resizeEvent(self, event):
        self.rescale()
        return super().resizeEvent(event)

    def rescale(self):
        #qrect = self._sceneRect
        scene = self.scene()
        if scene:
            qrect = scene.sceneRect()
            self.fitInView(qrect, Qt.AspectRatioMode.KeepAspectRatio)


# Experimental!
class GridViewHFit(GridView):
    """A QGraphicsView that automatically adjusts the scaling of its
    scene to fill the width of the viewing window.
    """
    def __init__(self):
        super().__init__()
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        # Avoid problems at on/off transition:
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )

    def resizeEvent(self, event):
        self.rescale()
        return super().resizeEvent(event)

    def rescale(self):
        #qrect = self._sceneRect
        qrect = self.scene().sceneRect()
        size = self.size()
        vsb = self.verticalScrollBar()
        w = size.width()
# This might be problematic at the point where the scrollbar appears or
# disappears ...
# Initially the scrollbar is reported as invisible, even when it is
# clearly visible, so the calculation is wrong.
        if vsb.isVisible():
            w -= vsb.size().width()
        scale = w / qrect.width()
        t = QTransform().scale(scale, scale)
        self.setTransform(t)
#        self.fitInView(qrect, Qt.AspectRatioMode.KeepAspectRatio)


class GridPeriodsDays(QGraphicsScene):
    font_header = StyleCache.getFont(fontSize = FONT_HEADER_SIZE)

    def __init__(self, days, periods, breaks):
        self.tiles = {}
        super().__init__()
        SIZES["BOXWIDTH"] = (
            SIZES["TABLEWIDTH"] - SIZES["TITLEWIDTH"]
        ) / len(days)
        SIZES["BOXHEIGHT"] = (
            SIZES["TABLEHEIGHT"] - SIZES["TITLEHEIGHT"]
        ) / len(periods)
        self.xslots = [0]    # x-coordinate of column left side
        self.yslots = [0]    # y-coordinate of row top side
        # Cell at top left-hand corner
        self.addItem(Cell(0, 0, SIZES["TITLEWIDTH"], SIZES["TITLEHEIGHT"], -1, -1))
        # Add column headers
        x = SIZES["TITLEWIDTH"]
        icol = 0
        for col_header in days:
            self.xslots.append(x)
            cell = Cell(x, 0, SIZES["BOXWIDTH"], SIZES["TITLEHEIGHT"], -1, icol)
            cell.set_text(col_header, self.font_header)
            cell.set_background(HEADER_COLOUR)
            self.addItem(cell)
            icol += 1
            x += SIZES["BOXWIDTH"]
        self.grid_width = x
        # Add row headers and rows
        self.cell_matrix = []
        irow = 0
        y = SIZES["TITLEHEIGHT"]
        for row_header in periods:
            if row_header in breaks:
                line = QGraphicsLineItem(0, y, self.grid_width, y)
                line.setPen(StyleCache.getPen(SIZES["LINEWIDTH"], BREAK_COLOUR))
                self.addItem(line)
                line.setZValue(1)
            day_list = []
            self.cell_matrix.append(day_list)
            self.yslots.append(y)
            # row header
            cell = Cell(0, y, SIZES["TITLEWIDTH"], SIZES["BOXHEIGHT"], irow, -1)
            cell.set_text(row_header, self.font_header)
            cell.set_background(HEADER_COLOUR)
            self.addItem(cell)
            # day cells
            for i in range(icol):
                cell = Cell(self.xslots[i + 1], y, SIZES["BOXWIDTH"], SIZES["BOXHEIGHT"], irow, i)
                day_list.append(cell)
                self.addItem(cell)
            irow += 1
            y += SIZES["BOXHEIGHT"]
        self.grid_height = y
        # Set colour of main border lines
        for y in 0, SIZES["TITLEHEIGHT"], self.grid_height:
            line = QGraphicsLineItem(0, y, self.grid_width, y)
            line.setPen(StyleCache.getPen(SIZES["LINEWIDTH"], MARGIN_LINE_COLOUR))
            self.addItem(line)
            line.setZValue(10)
        for x in *self.xslots, self.grid_width:
            line = QGraphicsLineItem(x, 0, x, self.grid_height)
            line.setPen(StyleCache.getPen(SIZES["LINEWIDTH"], MARGIN_LINE_COLOUR))
            self.addItem(line)
            line.setZValue(10)

# Not using the selection rectangle from grid_support?
        # Make a rectangle for the "selected" marking
        self.select = QGraphicsRectItem(0, 0, SIZES["BOXWIDTH"], SIZES["BOXHEIGHT"])
        self.select.setPen(StyleCache.getPen(SIZES["LINEWIDTH"]*2, SELECT_COLOUR))
        self.select.setZValue(20)
        self.select.hide()
        self.addItem(self.select)

        self.make_context_menu()

    def make_context_menu(self):
        self.context_menu = QMenu()
        Action = self.context_menu.addAction("I am context Action 1")
        Action.triggered.connect(self.context_1)

    def get_cell(self, row, col):
        return self.cell_matrix[row][col]

    def mousePressEvent(self, event):
        point = event.scenePos()
        items = self.items(point)
        if items:
            if event.button() == Qt.MouseButton.LeftButton:
#TODO ...
                kbdmods = APP.keyboardModifiers()
                shift = (
                    " + SHIFT"
                    if kbdmods & Qt.KeyboardModifier.ShiftModifier
                    else ""
                )
                alt = (
                    " + ALT"
                    if kbdmods & Qt.KeyboardModifier.AltModifier
                    else ""
                )
                ctrl = (
                    " + CTRL"
                    if kbdmods & Qt.KeyboardModifier.ControlModifier
                    else ""
                )
                cell = None
                tiles = []
                item0 = None
                for item in items:
                    try:
                        cell = item.cell
                        item0 = item
                    except AttributeError:
                        tiles.append(item)
                for tile in tiles:
                    # Give all tiles at this point a chance to react, starting
                    # with the topmost. An item can break the chain by
                    # returning a false value.
                    try:
                        if not tile.leftclick():
                            return
                    except AttributeError:
                        pass
                if cell:
                    print (f"Cell – left press{shift}{ctrl}{alt} @ {item.cell}")
# Note that ctrl-click is for context menu on OSX ...
                    if shift:
#???
                        self.place_tile("T2", cell)
                    if alt:
                        self.select_cell(cell)

    def contextMenuEvent(self, event):
        point = event.scenePos()
        items = self.items(point)
        if items:
            for item in items:
                try:
                    # See if the topmost item is a tile
                    self.context_tag = item.tag
                except AttributeError:
                    # Not a tile. Otherwise there should only be a cell,
                    # but give all items a chance to react. An item can
                    # break the chain by returning a false value.
                    try:
                        fn = item.contextmenu
                    except AttributeError:
                        continue
                    if not fn(event.screenPos()):
                        return
                else:
                    self.context_menu.exec(event.screenPos())
#                    self.tile_context_menu(event.screenPos())
                    return

    def context_1(self):
        print(self.context_tag)

    def new_tile(self, tag, duration, nmsg, offset, total, text, colour=None):
        t = Tile(tag, duration, nmsg, offset, total, text, colour)
        self.addItem(t)
        self.tiles[tag] = t
        return t

    def remove_tiles(self):
        for tag, tile in self.tiles.items():
            self.removeItem(tile)
        self.tiles.clear()

    def place_tile(self, tag, cell):
        tile = self.tiles[tag]
        col, row = cell
        x = self.xslots[col + 1]    # first cell is header
        y = self.yslots[row + 1]    # first cell is header
        tile.set_cell(x, y)
#TODO: It might be useful for a tile to know where it is placed.
#        tile.cell = cell

    def select_cell(self, cell):
        x = self.xslots[cell[0] + 1]    # first cell is header
        y = self.yslots[cell[1] + 1]    # first cell is header
        self.select.setPos(x, y)
        self.select.show()


class Tile(QGraphicsRectItem):
    __slots__ = (
        "tag",
        "duration",
        "width",
        "height",
        "x",
        "text_item",
    )
    font_centre = StyleCache.getFont(fontSize=FONT_CENTRE_SIZE)
    font_corner = StyleCache.getFont(fontSize=FONT_CORNER_SIZE)

    def __init__(self, tag, duration, nmsg, offset, total, text, colour):
        #   duration: number of periods
        #   nmsg: number of "minimal subgroups"
        #   total: number of all "minimal subgroups"
        # Thus nmsg / total builds a fraction of the total box width.
        #   offset: starting offset as number of "minimal subgroups"
        # Thus offset + nmsg must be smaller than or equal to total.
        #   text: the text for the central position
        #   colour: the box background colour (<None> => white)
        self.tag = tag
        self.duration = duration
#        self.width = SIZES["BOXWIDTH"] * nmsg / total - SIZES["SIZES["LINEWIDTH"]"]
        self.width = (SIZES["BOXWIDTH"] - SIZES["LINEWIDTH"]) * nmsg / total
        self.x = SIZES["BOXWIDTH"] * offset / total + SIZES["LINEWIDTH"]/2
        self.height = SIZES["BOXHEIGHT"] * duration # can vary on placement
        super().__init__(
            self.x,
            SIZES["LINEWIDTH"]/2,
            self.width,
            self.height - SIZES["LINEWIDTH"]
        )
#TODO? Set "ffffff" for a white (opaque) background, which hides grid lines.
# Leaving it as <None> would make the background transparent.
        if not colour:
            colour = "ffffff"
        self.setBrush(StyleCache.getBrush(colour))
        self.text_item = QGraphicsSimpleTextItem(self)
        self.text_item.setFont(self.font_centre)
        self.set_text(text)
        self.setZValue(5)
        self.hide()
        self.corners = [None] * 4

    def set_text(self, text):
        self.text_item.setText(text)
        text_rect = self.text_item.boundingRect()
        text_width = text_rect.width()
        part = text_width / (self.width - SIZES["LINEWIDTH"])
        if part > 1:
            self.text_item.setScale(1 / part)
            text_rect = self.text_item.mapRectToParent(text_rect)
            text_width = text_rect.width()
        text_height = text_rect.height()
        xshift = self.x + (self.width - text_width) / 2
        yshift = (self.height - text_height) / 2
        self.text_item.setPos(xshift, yshift)

    def set_cell(self, x, y):
        self.setPos(x, y)
        self.show()

    def set_corner(self, corner, text):
        """Place a text item in one of the four corners.
        """
        text_item = self.corners[corner]
        if not text_item:
            text_item = QGraphicsSimpleTextItem(self)
            text_item.setFont(self.font_corner)
            self.corners[corner] = text_item
        text_item.setText(text)
        if corner == TILE_TOP_LEFT:
            self.fit_corners(text_item, self.corners[TILE_TOP_RIGHT], True)
        elif corner == TILE_TOP_RIGHT:
            self.fit_corners(self.corners[TILE_TOP_LEFT], text_item, True)
        elif corner == TILE_BOTTOM_RIGHT:
            self.fit_corners(self.corners[TILE_BOTTOM_LEFT], text_item, False)
        elif corner == TILE_BOTTOM_LEFT:
            self.fit_corners(text_item, self.corners[TILE_BOTTOM_RIGHT], False)
        else:
            raise Bug(f"Invalid Tile Corner: {corner}")

#TODO: I might need some sort of line wrapping if the text is very long ...
    def fit_corners(self, left, right, is_top):
        width = self.width - SIZES["LINEWIDTH"] - SIZES["SUBTEXTGAP"]
        if left:
            br = left.boundingRect()
            left_width = br.width()
            left_height = br.height()
        else:
            left_width = 0
            left_height = 0
        if right:
            br = right.boundingRect()
            right_width = br.width()
            right_height = br.height()
        else:
            right_width = 0
            right_height = 0
        part = (left_width + right_width) / width
        scale = 1 / part if part > 1 else 1
        if left:
            left.setScale(scale)
            left_width *= scale
            if is_top:
                left.setPos(self.x + SIZES["LINEWIDTH"], SIZES["LINEWIDTH"])
            else:
                left.setPos(
                    self.x + SIZES["LINEWIDTH"],
                    self.height - SIZES["LINEWIDTH"] - left_height
                )
        if right:
            right.setScale(scale)
            right_width *= scale
            if is_top:
                right.setPos(
                    self.x + self.width - SIZES["LINEWIDTH"] - right_width,
                    SIZES["LINEWIDTH"]
                )
            else:
                right.setPos(
                    self.x + self.width - SIZES["LINEWIDTH"] - right_width,
                    self.height - SIZES["LINEWIDTH"] - right_height
                )

#TODO: May be useful (to get screen coordinates)?
#def get_pos(view, item, point):
#        scenePos = item.mapToScene(point)
#        viewportPos = view.mapFromScene(scenePos)
#        viewPos = view.viewport().mapToParent(viewportPos)
#        globalViewPos = view.mapToGlobal(QPoint(0, 0))
#        return globalViewPos.x + viewPos.x, globalViewPos.y + viewPos.y

#TODO
#    def printName(self):
#        print("Action triggered from {}".format(self.tag))


class Box(QGraphicsRectItem):
    """A rectangle with adjustable borderwidth.
    The item's coordinate system starts at (0, 0), fixed by passing
    this origin to the <QGraphicsRectItem> constructor.
    The box is then moved to the desired location using <setPos>.
    """
    __slots__ = (
        "text_item",
    )
    def __init__(self, x, y, w, h, width=None, colour=None):
        super().__init__(0, 0, w, h)
        self.setPos(x, y)
        self.setPen(StyleCache.getPen(width, colour or BORDER_COLOUR))
#
    def set_text(self, text, font=None):
        """Set a centred text item. Calling the function a second time
        updates the text.
        """
        try:
            item = self.text_item
        except AttributeError:
            item = QGraphicsSimpleTextItem(self)
            self.text_item = item
        if font:
            item.setFont(font)
        item.setText(text)
        bdrect = item.boundingRect()
        #print("§§§", text, bdrect)
        wt = bdrect.width()
        ht = bdrect.height()
        rect = self.rect()
        xshift = (rect.width() - wt) / 2
        yshift = (rect.height() - ht) / 2
        item.setPos(xshift, yshift)

    def set_background(self, colour):
        """Set the cell background colour.
        <colour> can be <None> ("no fill") or a colour in the form 'RRGGBB'.
        """
        self.setBrush(StyleCache.getBrush(colour))

###

class Cell(Box):
    """This is a rectangle representing a single period slot. It is used
    to construct the basic timetable grid.
    It is a <Box> whose background colour is settable and which supports
    hover events.
    """
    __slots__ = (
        "x0",
        "y0",
        "cell",
    )
#TODO: highlighting by emphasizing the border:
#    selected = None

#    @classmethod
#    def setup(cls):
#        cls.nBrush = StyleCache.getBrush(None)
#        cls.hBrush = StyleCache.getBrush(CELL_HIGHLIGHT_COLOUR)
#        cls.nPen = StyleCache.getPen(SIZES["SIZES["LINEWIDTH"]"] + 2, BORDER_COLOUR)
#        cls.sPen = StyleCache.getPen(SIZES["SIZES["LINEWIDTH"]"] + 2, SELECT_COLOUR)

#    @classmethod
#    def select(cls, cell):
#        if cls.selected:
#            cls.selected.setPen(cls.nPen)
#            cls.selected.setZValue(0)
#            cls.selected = None
#        if cell:
#            cell.setPen(cls.sPen)
#            cell.setZValue(20)
#            cls.selected = cell

    def __init__(self, x, y, w, h, irow, icol):
        """Create a box at scene coordinates (x, y) with width w and
        height h. irow and icol are row and column indexes.
        """
        super().__init__(x, y, w, h, width=SIZES["LINEWIDTH"])
        self.x0 = x
        self.y0 = y
        self.cell = (icol, irow)
#        self.setAcceptHoverEvents(True)
#        print ("Cell", icol, irow, x, y)

#TODO
    def contextmenu(self, event):
        print(f"CONTEXT MENU @ (col: {self.cell[0]} | row: {self.cell[1]})")
        return True # propagate down (though a <Cell> should be the lowest ...)

#TODO: It may be more appropriate to have the hover events handled in
# <Tile>.
#    def hoverEnterEvent(self, event):
#        print("Enter", self.cell)

#    def hoverLeaveEvent(self, event):
#        print("Leave", self.cell)


#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

def main(args):
#TODO: Will need various font sizes ...
# And playing around with the app font may not be such a good idea!
#    font = APP.font()
    #print("FONT:", font.pointSize())
#    font.setPointSize(12)
#    APP.setFont(font)

    #from qtpy.QtGui import QFontInfo
    #qfi = QFontInfo(font)
    #print("FONT PIXELS / POINTS:", qfi.pixelSize(), qfi.pointSize())
    WINDOW = GridViewRescaling()
    #WINDOW = GridViewHFit()
    #WINDOW = GridView()

    # Set up grid
    grid = GridPeriodsDays(DAYS, PERIODS, BREAKS)
    WINDOW.setScene(grid)

#### Actually, I'm not sure what sort of scaling makes sense ...
#### Probably best to use GridViewRescaling
#    # Scaling: only makes sense if using basic, unscaled GridView
#    scale = WINDOW.pdpi / WINDOW.ldpi
#    print("§SCALING", WINDOW.pdpi, WINDOW.ldpi, scale)
#    t = QTransform().scale(scale, scale)
##    WINDOW.setTransform(t)

#TODO: Only standalone!
    APP.setWindowIcon(QIcon(APPDATAPATH("icons/tt.svg")))
    screen = APP.primaryScreen()
    screensize = screen.availableSize()
    print("§screensize =", screensize)
    WINDOW.resize(int(screensize.width()*0.6), int(screensize.height()*0.75))
    WINDOW.show()

    return WINDOW


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == '__main__':
    from core.db_access import open_database
    open_database()

    DAYS = ('Mo', 'Di', 'Mi', 'Do', 'Fr')
    PERIODS = ('A', 'B', '1', '2', '3', '4', '5', '6', '7')
    BREAKS = ('1', '3', '5')

    WINDOW = main(set(sys.path[1:]))
    grid = WINDOW.scene()

    t1 = grid.new_tile("T1", duration=1, nmsg=1, offset=1, total=4, text="De p1 xx", colour="FFFF44")
    grid.place_tile("T1", (2, 3))
    t2 = grid.new_tile("T2", duration=2, nmsg=1, offset=0, total=4, text="tg B", colour="FFE0F0")
    t2.set_corner(0, "AB / CD / EF / GH / IJ")
    t2.set_corner(1, "B")
    grid.place_tile("T2", (0, 2))
    t3 = grid.new_tile("T3", duration=2, nmsg=1, offset=0, total=4, text="---", colour="E0F0FF")
    grid.place_tile("T3", (2, 3))
    t4 = grid.new_tile("T4", duration=1, nmsg=2, offset=2, total=4, text="Ma")
    t4.set_corner(0, "AB / CD / EF / GH / IJ")
    t4.set_corner(1, "B")
    grid.place_tile("T4", (2, 3))
    t5 = grid.new_tile("T5", duration=2, nmsg=1, offset=0, total=1, text="Hu")
    t5.set_corner(0, "BTH / WS\nAR / PQ")
    t5.set_corner(1, "alle")
    grid.place_tile("T5", (4, 0))
    t6 = grid.new_tile("T6", duration=1, nmsg=1, offset=0, total=2, text="Ta")
    t6.set_corner(0, "BMW")
    t6.set_corner(1, "A")
    t6.set_corner(2, "r10G")
    t6.set_corner(3, "?")
    grid.place_tile("T6", (3, 5))

    grid.select_cell((1,6))

    #for k, v in SIZES.items():
    #    print(f"SIZE (mm) {k:16}: {WINDOW.px2mm(v)}")

    sys.exit(APP.exec())
