"""
ui/modules/timetable_editor.py

Last updated:  2023-05-29

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

from typing import NamedTuple
from itertools import combinations

from ui.timetable_grid import GridViewRescaling, GridPeriodsDays
from core.db_access import open_database, KeyValueList
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
from timetable.placement_engine import PlacementEngine
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
        days = get_days().key_list()
        periods = get_periods().key_list()
        self.engine = PlacementEngine(days, periods)
        breaks = self.TT_CONFIG["BREAKS_BEFORE_PERIODS"]
        self.grid = WeekGrid(days, periods, breaks)
        self.table_view.setScene(self.grid)
        self.timetable = (tt := Timetable(self))
        self.engine.setup_structures(
            classes={
                k: gmap[GROUP_ALL]
                for k, gmap in tt.class_group_atoms.items()
                if tt.class_activities[k]
            },
            subjects=tt.subject_activities,
            teachers=tt.teacher_activities,
        )
        cmap = self.timetable.class_activities
        self.all_classes = []
        for k, name in get_classes().get_class_list():
            if cmap[k]:
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

class TimetableActivity(NamedTuple):
    teacher_set: set[str]
    # division_groups: set[str]
    group_sets: dict[str, set[str]] # {class: {group. ... }}
    roomlists: list[list[str]]
    lesson_info: LessonInfo
    sid: str
    lesson_group: int
    course_list: list[CourseWithRoom]


def class2group2atoms():
    c2g2ags = {}
    classes = get_classes()
    for klass, name in classes.get_class_list():
        cdata = classes[klass]
        cg = cdata.divisions
        divs = cg.divisions
        g2ags = cg.group_atoms()
        g2ags[GROUP_ALL] = cg.atomic_groups
        c2g2ags[klass] = g2ags
    return c2g2ags


class Timetable:
    def __init__(self, gui):
        self.gui = gui
        self.class_group_atoms = class2group2atoms()
        # Collect <Activity> items, they are then referenced by index
        self.activities = []
        # (Ordered dict) Collect activity indexes on a class basis
        self.class_activities: dict[str, list[int]] = {}
        # (Ordered dict) Collect activity indexes on a teacher basis
        self.teacher_activities = {
            t: [] for t in get_teachers()
        }
        # (Ordered dict) Collect activity indexes on a subject basis
        self.subject_activities = {
            s: [] for s in get_subjects().key_list()
        }
        # group-division map for each class
        self.group_division = {}
        for klass, cdata in get_classes().items():
            self.class_activities[klass] = []
            divs = cdata.divisions.divisions
            g2div = {GROUP_ALL: (-1, GROUP_ALL)}
            self.group_division[klass] = g2div
            for i, div in enumerate(divs):
                dgas = []
                for d, v in div:
                    if v is None:
                        dgas.append(d)
                        g2div[d] = (i, [d])
                    else:
                        g2div[d] = (i, v)
                g2div[f"%{i}"] = dgas
#TODO--
#            print("\n%DIV%", klass, self.group_division[klass])

        # For constraints concerning relative placement of individual
        # lessons in the various subjects, collect the "atomic" pupil
        # groups and their activity ids for each subject, divided by class:
#TODO: If I use this, it should probably use indexes as far as possible
#        self.class2sid2ag2aids: dict[str, dict[str, dict[str, list[int]]]] = {}

#TODO
        ### Collect data for each lesson-group
        lg_map = collect_activity_groups()
        ### Add activities
        for lg, act in lg_map.items():
            # pg_sets = {}    #  {klass -> set of division groups}
            group_sets = {} # {klass -> set of atomic groups}
            teacher_set = set()
            room_set = set()
            for cwr in act.course_list:
                klass = cwr.klass
                if cwr.group and klass != "--":
                    # Only add a group entry if there is a
                    # group and a (real) class
                    gatoms = self.class_group_atoms[klass][cwr.group]
                    try:
                        group_sets[klass].update(gatoms)
                        # pg_sets[klass].add(cwr.group)
                    except KeyError:
                        group_sets[klass] = set(gatoms)
                        # pg_sets[klass] = {cwr.group}
                if cwr.teacher != "--":
                    teacher_set.add(cwr.teacher)
                if cwr.room:
                    room_set.add(cwr.room)

            # Get the subject-id from the block-tag, if it has a
            # subject, otherwise from the course (of which there
            # should be only one!)
            sid = bt.sid if (bt := act.block_tag) else cwr.subject

            ## Handle rooms
            # Room allocations containing '+' should not block anything.
            # It could possibly imply that manual selection is necessary.
#TODO
            # A more sophisticated approach might include a check that at
            # least one of a list of reasonable candidates (based on what?)
            # is available.
            # As there can be multi-room requirements, the data structure is
            # a list of lists (a single requirement potentially being a
            # choice – assumed to be ordered).
            roomlists = []
            for r in room_set:
                rs = r.rstrip('+')
                rl = rs.split('/') if rs else []
                if r[-1] == '+':
                    rl.append('+')
                roomlists.append(rl)

            ## Generate the activity or activities
            for ldata in act.lessons:
#TODO: Perhaps split it up into different lists with a common index?
                a = TimetableActivity(
                    teacher_set,
                    # pg_sets,
                    group_sets,
                    roomlists,
                    ldata,
                    sid,
                    lg,
                    act.course_list,
                )
                a_index = len(self.activities)
#TODO--
#                print(" +++", a_index, a)
                self.activities.append(a)
                for k in group_sets:
                    self.class_activities[k].append(a_index)
                for t in teacher_set:
                    self.teacher_activities[t].append(a_index)
                self.subject_activities[sid].append(a_index)

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
            print("  --", activity)
            lesson_data = activity.lesson_info
            fixed_time = lesson_data.time

#TODO: Keep non-fixed times separate from the database? When would they
# be saved, then?
            if fixed_time:
                d, p = timeslot2index(fixed_time)
                print("   @", d, p)

            else:
                slot_time = lesson_data.placement
                if slot_time:
                    d, p = timeslot2index(slot_time)
                    print("   (@)", d, p)

#TODO: display data

#TODO: rooms? Shouldn't the rooms per group be available????
# Via the workload entry ... this can, however, be '$', potentially
# leading to multiple rooms.
            x = False
            groups = set()
            tids = set()
            sid = activity.sid
            for c in activity.course_list:
                if c.klass == klass:
                    groups.add(c.group)
                    tids.add(c.teacher)
                else:
                    x = True
#TODO: tool-tip (or whatever) to show parallel courses?
            t_rooms = lesson_data.rooms
            t_tids = ','.join(sorted(tids)) or '–'
            t_groups, tile_divisions = self.tile_division(klass, groups)
            #t_groups = ','.join(sorted(groups))
            if x:
                t_groups += ",+"
#TODO--
            print("  ...", sid, t_tids, t_groups, t_rooms, tile_divisions)
            
            
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
        return


# ... I might want lesson placement info (time and rooms) from a
# temporary store here, rather than directly from the database.
        if True:
            lessons = self.tag2lessons.get(activity.tag)
            if lessons:
                for l in lessons:
                    print("  +++", l)

                    d, p = timeslot2index(l.TIME)
                    print("   ---", activity.sid, d, p)

                    t_tids = ','.join(activity.tids)
                    t_groups = '/'.join(activity.groups)
                    t_rooms = l.ROOMS
                    tiledata.append( # for the list of tiles, etc.
                        (
                            activity.sid,
                            str(l.LENGTH),
                            t_groups,
                            t_tids,
                            l.id,
# The room list is probably needed as a list or set ...
                            t_rooms.split(','),

#?
                            chipdata.groups,
                            chipdata.basic_groups,
                        )
                    )

                    tile_index = len(tiles)
                    tile = make_tile(
                        grid,
                        tile_index,
                        duration=l.LENGTH,
#?
                        n_parts=chipdata.num,
                        n_all=chipdata.den,
                        offset=chipdata.offset,

                        text=activity.sid,
# Might want to handle the placing of the corners in the configuration?
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
            else:
                print("\nNO LESSONS:", a.tag)

        tile_list.setRowCount(len(tiledata))
        row = 0
        for tdata in tiledata:
            for col in range(4):
                twi = QTableWidgetItem(tdata[col])
                tile_list.setItem(row, col, twi)
            if tile_list_hidden[row]:
                tile_list.hideRow(row)
            row += 1
        tile_list.resizeColumnsToContents()
        tile_list.resizeRowsToContents()
        # Toggle the stretch on the last section here because of a
        # possible bug in Qt, where the stretch can be lost when
        # repopulating.
        hh = tile_list.horizontalHeader()
        hh.setStretchLastSection(False)
        hh.setStretchLastSection(True)



#TODO
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
class ChipData(NamedTuple):
    groups: list[str]       # should be ordered
    basic_groups: set[str]
    rest_groups: set[str]   # the remaining groups in the division
    offset: int             # lowest possible start index
    num: int                # number of "parts"
    den: int                # total number of "parts"





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

### TESTING
#    from core.db_access import open_database
#    open_database()

#    grid = main(set(sys.path[1:]))

#    tt = Timetable(grid)
##    tt.show_class("09G")
#    tt.show_class("11G")
##    tt.show_class("12K")

#    grid.run_standalone()
#    quit(0)

### PROPER
    from ui.ui_base import run

    widget = TimetableEditor()
    widget.enter()

    widget.resize(1000, 550)
    run(widget)

