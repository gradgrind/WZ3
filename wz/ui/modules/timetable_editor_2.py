"""
ui/modules/timetable_editor.py

Last updated:  2023-05-31

Show a timetable grid and allow placement of lesson tiles.


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
    from ui.ui_base import StandalonePage as Page
    start.setup(os.path.join(basedir, 'TESTDATA'))
else:
    from ui.ui_base import StackPage as Page

T = TRANSLATIONS("ui.modules.timetable_editor")

### +++++

from ui.timetable_grid import GridViewRescaling, GridPeriodsDays
from core.basic_data import (
    clear_cache,
    get_days,
    get_periods,
    get_classes,
    get_teachers,
    get_subjects,
    timeslot2index
)
from core.activities import (
    collect_activity_groups,
    LessonInfo,
    CourseWithRoom,
)
from core.classes import GROUP_ALL
from timetable.timetable_base import Timetable, room_split
from ui.ui_base import (
    ### QtWidgets:
    QListWidgetItem,
    QTableWidgetItem,
    QMenu,
    ### QtGui:
    ### QtCore:
    Qt,
#    QEvent,
    Slot,
    ### uic
    uic,
)

### -----

def init():
    MAIN_WIDGET.add_tab(TimetableEditor())


class TimetableEditor(Page):
    def __init__(self):
        super().__init__()
        uic.loadUi(APPDATAPATH("ui/timetable_class_view.ui"), self)

    def enter(self):
        open_database()
        clear_cache()
        self.TT_CONFIG = MINION(DATAPATH("CONFIG/TIMETABLE"))
        self.timetable = (tt := TimetableManager())
        breaks = self.TT_CONFIG["BREAKS_BEFORE_PERIODS"]
        self.grid = WeekGrid(breaks)
        self.table_view.setScene(self.grid)
        tt.set_gui(self)

        ## Set up class list
        self.all_classes = []
        for k, name in get_classes().get_class_list():
            if tt.class_activities[k]:
                self.all_classes.append(k)
                item = QListWidgetItem(f"{k} – {name}")
                self.class_list.addItem(item)
        self.class_list.setCurrentRow(0)

    @Slot(int, int, int, int)
    def on_lessons_currentCellChanged(self, r, c, r0, c0):
#TODO--
        print("&&&>>>", r)


    @Slot(int)
    def on_class_list_currentRowChanged(self, row):
        klass = self.all_classes[row]
        self.grid.remove_tiles()
#        self.timetable.show_class(klass)
        self.timetable.enter_class(klass)
#TODO--
        print("§§§ SELECTED CLASS:", klass,
            get_classes()[klass].divisions.divisions
        )

#TODO
    def selected_tile(self, row, col, row0, col0):
        if row >= 0 and row != row0:
            print("§SELECT", row, row0)
#TODO: Will need all the data to enable a search for possible placements:
# Primarily teachers, groups, rooms
# To calculate penalties also other stuff, including placements of all
# other items.
# Should 100% constraints be included with the primaries?

# Can use set_background on the period cell to mark the possible cells.
# Various colours for various degrees of possibility? E.g. absolute no-go
# if a tile in another class must be moved? Only vie direct, conscious
# removal?

class TimetableManager(Timetable):
    def set_gui(self, gui):
        self.gui = gui

    def enter_class(self, klass):
        grid = self.gui.grid
        self.gui.table_header.setText(get_classes()[klass].name)
        tile_list = self.gui.lessons
        tile_list.clearContents()
        # Sort activities on subject
        class_activities = sorted(
            self.class_activities[klass],
            key=lambda x: self.activities[x].sid
        )
        tile_list.setRowCount(len(class_activities))
#?
        tiledata = []
        tiles = []
        tile_list_hidden = []
#TODO--
#        print("\nCLASS", klass)
        for row, a_index in enumerate(class_activities):
            activity = self.activities[a_index]
#TODO--
#            print("  --", activity)
            lesson_data = activity.lesson_info
            fixed_time = lesson_data.time

#TODO: Keep non-fixed times separate from the database? When would they
# be saved, then?
            if fixed_time:
                d, p = timeslot2index(fixed_time)
#                print("   @", d, p)

            else:
                slot_time = lesson_data.placement
                if slot_time:
                    d, p = timeslot2index(slot_time)
#                    print("   (@)", d, p)

#TODO: display data

#TODO: rooms? Shouldn't the rooms per group be available????
# Via the workload entry ... this can, however, be '$', potentially
# leading to multiple rooms.
            x = False
            groups = set()
            tids = set()
            rooms = set()
            sid = activity.sid
            for c in activity.course_list:
                if c.klass == klass:
                    groups.add(c.group)
                    tids.add(c.teacher)
                    # The rooms are the acceptable ones!
                    rooms.update(room_split(c.room))
                else:
                    x = True
#TODO: tool-tip (or whatever) to show parallel courses?
#TODO: The rooms are part of the allocation data and should be checked!
            t_rooms = lesson_data.rooms
# It could be that not all required rooms have been allocated?
# I would need to compare this with the "roomlists" lists, 
# <activity.roomlists>.
            alloc_rooms = t_rooms.split(',') if t_rooms else []
            print("???", len(activity.roomlists), rooms, alloc_rooms)

            t_tids = ','.join(sorted(tids)) or '–'
            t_groups, tile_divisions = self.tile_division(klass, groups)
            #t_groups = ','.join(sorted(groups))
            if x:
                t_groups += ",+"
#TODO--
#            print("  ...", sid, t_tids, t_groups, t_rooms, tile_divisions)
            
            tile_list.setItem(row, 0, QTableWidgetItem(sid))
            twi = QTableWidgetItem(str(lesson_data.length))
            twi.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tile_list.setItem(row, 1, twi)
            twi = QTableWidgetItem(t_groups)
            twi.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tile_list.setItem(row, 2, twi)
            tile_list.setItem(row, 3, QTableWidgetItem(t_tids))

# Just testing!!! It should actually be based on existing placement
#            if fixed_time:
#                tile_list.hideRow(row)
#            else:
#                tile_list.showRow(row)

# Perhaps placements should be done "normally", i.e. with all checks,
# in case the fixed times have changed (or there is an error in the
# database).

            for i, l, n in tile_divisions:
                tile_index = len(tiles)
                tile = make_tile(
                    grid=grid,
                    tag=tile_index,
                    duration=lesson_data.length,
                    n_parts=l,
                    n_all=n,
                    offset=i,
                    text=sid,
#TODO: Might want to handle the placing of the corners in the configuration?
# Rooms can perhaps only be added when placed, and even then not always ...
                    tl=t_tids,
                    tr=t_groups,
                    br=t_rooms,
                )
                tiles.append(tile)
                if d >= 0:
                    grid.place_tile(tile_index, (d, p))
                    tile_list_hidden.append(True)
                else:
                    tile_list_hidden.append(False)

        tile_list.resizeColumnsToContents()

    def tile_division(self, klass, groups):
        # Gather division components
        g2div = self.group_division[klass]
        divi = -1
        for g in groups:
            i, dgs = g2div[g]
            if i < 0:
                # whole class
                return (GROUP_ALL, [(0, 1, 1)])
            if divi != i:
                if divi >= 0:
                    # groups from multiple divisions, assume whole class
                    return (GROUP_ALL, [(0, 1, 1)])
                else:
                    divi = i
                    dgset = set(dgs)
            else:
                dgset.update(dgs)
        # Construct tile divisions
        div_groups = g2div[f"%{divi}"]
        n = len(div_groups)
        if len(dgset) == n:
            return (GROUP_ALL, [(0, 1, 1)])
        l = 0
        i = 0
        tiles = []
        for g in div_groups:
            if g in dgset:
                if l == 0:
                    p = i
                    l = 1
                else:
                    l += 1
            elif l:
                tiles.append((p, l, n))
                l = 0
            i += 1
        if l:
            tiles.append((p, l, n))
        return (','.join(sorted(groups)), tiles)


def make_tile(
    grid,
    tag,
    duration,
    n_parts,
    n_all,
    offset,
    text,
    tl=None,
    tr=None,
    br=None,
    bl=None
):
    tile = grid.new_tile(
        tag,
        duration=duration,
        nmsg=n_parts,
        offset=offset,
        total=n_all,
        text=text
    )
    if tl:
        tile.set_corner(0, tl)
    if tr:
        tile.set_corner(1, tr)
    if br:
        tile.set_corner(2, br)
    if bl:
        tile.set_corner(3, bl)
    return tile



#TODO--?
def simplify_room_lists(roomlists):
    """Simplify room lists, check for room conflicts."""
    # Collect single room "choices" and remove redundant entries
    singles = set()
    while True:
        extra = False
        singles1 = set()
        roomlists1 = []
        for rl in roomlists:
            rl1 = [r for r in rl if r not in singles]
            if rl1:
                if len(rl1) == 1:
                    if rl1[0] == '+':
                        if not extra:
                            roomlists1.append(rl1)
                            extra = True
                    else:
                        singles1.add(rl1[0])
                else:
                    roomlists1.append(rl1)
            else:
                raise ValueError
        if roomlists1 == roomlists:
            return [[s] for s in sorted(singles)] + roomlists
        singles.update(singles1)
        roomlists = roomlists1


#TODO--?
def simplify_room_lists_(roomlists, klass, tag):
    """Simplify room lists, check for room conflicts."""
    # Collect single room "choices" and remove redundant entries
    singles = set()
    while True:
        extra = False
        singles1 = set()
        roomlists1 = []
        for rl in roomlists:
            rl1 = [r for r in rl if r not in singles]
            if rl1:
                if len(rl1) == 1:
                    if rl1[0] == '+':
                        if not extra:
                            roomlists1.append(rl1)
                            extra = True
                    else:
                        singles1.add(rl1[0])
                else:
                    roomlists1.append(rl1)
            else:
                SHOW_ERROR(
                    T["BLOCK_ROOM_CONFLICT"].format(
                        klass=klass,
                        sid=sid,
                        tag=tag,
                        rooms=repr(roomlists),
                    ),
                )
        if roomlists1 == roomlists:
            return [[s] for s in sorted(singles)] + roomlists
        singles.update(singles1)
        roomlists = roomlists1


class WeekGrid(GridPeriodsDays):
    def __init__(self, breaks):
        super().__init__(
            get_days().key_list(),
            get_periods().key_list(),
            breaks
        )

    def make_context_menu(self):
        self.context_menu = QMenu()
#TODO:
        Action = self.context_menu.addAction("Seek possible placements")
        Action.triggered.connect(self.seek_slots)

    def seek_slots(self):
        print("seek_slots:", self.context_tag)
        #tile = self.tiles[self.context_tag]


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == '__main__':
    from core.db_access import open_database
    from ui.ui_base import run

    widget = TimetableEditor()
    widget.enter()

    widget.resize(1000, 550)
    run(widget)
