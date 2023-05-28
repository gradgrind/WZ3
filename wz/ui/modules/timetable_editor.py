"""
ui/modules/timetable_editor.py

Last updated:  2023-05-28

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
        breaks = self.TT_CONFIG["BREAKS_BEFORE_PERIODS"]
        self.grid = WeekGrid(days, periods, breaks)
        self.table_view.setScene(self.grid)
        self.init_data()
        self.timetable = Timetable(self)
        self.class_list.setCurrentRow(0)

    def init_data(self):
        self.all_classes = []
        for k, name in get_classes().get_class_list():
            self.all_classes.append(k)
            item = QListWidgetItem(f"{k} – {name}")
            self.class_list.addItem(item)

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


#class BlockInfo(NamedTuple):
#    course: CourseData
#    block: BlockTag
#    rooms: list[str]
#    payment_data: PaymentData
#    notes: str
#
#class Sublesson(NamedTuple):
#    id: int
#    TAG: str
#    LENGTH: int
#    TIME: str
#    ROOMS: str



class TimetableActivity(NamedTuple):
    teacher_set: set[str]
    group_sets: dict[str, set[str]] # {class: {group. ... }}
    roomlists: list[list[str]]
    lesson_info: LessonInfo
#?
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
        self.class_activities: dict[str, list[int]] = {}
#?
        self.timetable_teachers = set()
        self.timetable_subjects = set()

        # <KeyValueList>s of basic elements
        self.sid_list = get_subjects()
        teachers = get_teachers()
        self.tid_list = KeyValueList(
            (tid, teachers.name(tid)) for tid in teachers
        )
        self.class_list = KeyValueList(
            get_classes().get_class_list(skip_null=False)
        )
        # List of <Activity> items
        self.activities = []

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
                    except KeyError:
                        group_sets[klass] = set(gatoms)
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

            ## Add to "used" teachers and subjects
            self.timetable_teachers.update(teacher_set)
            self.timetable_subjects.add(sid)
            ## Generate the activity or activities
            for ldata in act.lessons:
#TODO: Perhaps split it up into different lists with a common index?
                a = TimetableActivity(
                    teacher_set,
                    group_sets,
                    roomlists,
                    ldata,
                    sid,
                    lg,
                    act.course_list,
                )
                a_index = len(self.activities)
#TODO--
                print(" +++", a_index, a)
                self.activities.append(a)
                for k in group_sets:
                    try:
                        self.class_activities[k].append(a_index)
                    except KeyError:
                        self.class_activities[k] = [a_index]




#TODO: At the moment this is just a collection of sketches ...
    def sort_groups(self):

        self.fullgroup2index = {}
        self.class2group2division = {}
        # Build group/division mappings for some class
        classes = get_classes()
        group_index = 0
        for klass, kname in classes.get_class_list():
            group_info = classes.group_info(klass)
            divisions = group_info["INDEPENDENT_DIVISIONS"]
            self.fullgroup2index[klass] = group_index
            group_index += 1
#? How will the structures be used???
            i = 0
            group2division = {'*': i}
            self.class2group2division[klass] = group2division
            for div in divisions:
                i += 1
                for g in div:
                    group2division[g] = i
# Actually, I could give all groups (in all classes) a unique index
# instead of the string. Would that help?

# An activity has a set/list of groups, which can be the group-indexes.
# To perform a placement check:
#   for each group in the activity:
#      pick up the class entry for the slot(s)
#      if not empty, check that the new group is in the ok-list
# (it is probably ok to assume that the groups in the activity are not
# in conflict with each other – this should be enforced at construction
# time)
# Perhaps it would also be worth considering a bitmap – on a class or
# division basis.

#TODO: A replacement for show_class?
    def enter_class(self, klass):
        grid = self.gui.grid
        tile_list = self.gui.lessons
        tile_list.clearContents()
        # Sort activities on subject
        class_activities = sorted(
            self.class_activities[klass],
            key=lambda x: self.activities[x][4]
        )
        tile_list.setRowCount(len(class_activities))
#?
        tiledata = []
        tiles = []
        tile_list_hidden = []
        print("\nCLASS", klass)
        for row, a_index in enumerate(class_activities):
            activity = self.activities[a_index]
            print("  --", activity)
            lesson_data = activity[3]
            fixed_time = lesson_data[2]

#TODO: Keep non-fixed times separate from the database? When would they
# be saved, then?
            if fixed_time:
                d, p = timeslot2index(fixed_time)
                print("   @", d, p)

            else:
                slot_time = lesson_data[3]
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
            sid = activity[4]
            for c in activity[-1]:  # course list
                if c[0] == klass:
                    groups.add(c[1])
                    tids.add(c[3])
                else:
                    x = True
#TODO: tool-tip (or whatever) to show parallel courses?
            t_rooms = lesson_data[4]
            t_tids = ','.join(sorted(tids)) or '–'
            t_groups = ','.join(sorted(groups))
            print("  ...", t_tids, t_groups, t_rooms)
            
            
            tile_list.setItem(row, 0, QTableWidgetItem(sid))
            twi = QTableWidgetItem(str(lesson_data[1]))
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

            row += 1
            continue
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



    def show_class(self, klass):
        grid = self.gui.grid
        tile_list = self.gui.tile_list
        tile_list.clearContents()
        classes = get_classes()
        group_info = classes.group_info(klass)
        divisions = group_info["INDEPENDENT_DIVISIONS"]
        # atoms = group_info["MINIMAL_SUBGROUPS"]
        group_map = group_info["GROUP_MAP"]
        # group2atoms = atomic_maps(atoms, list(group_map))
#TODO: How to calculate tile offsets ... maybe using independent-divisions?

        # {block-tag -> [BlockInfo, ... ]}
        tag2infolist = self.courses.klass2tags[klass]

        alist = []
        for tag, infolist in tag2infolist.items():
            info_ = infolist[0]
            sid = info_.block.sid or info_.course.sid
            name = self.subjects.map(sid)
            activity = Activity_(sid, name, tag)

            # Get tids and room lists (from which to choose)
            tids_ = set()       # tids for just this class
            groups_ = set()     # groups for just this class
            allgroups = set()   # groups for the activity as a whole
            alltids = set()     # tids for the activity as a whole
            allroomlists_ = []  # rooms for the activity as a whole
            # Room info for just this class is not really useful, it is
            # possible that the actual rooms used for this class cannot
            # be determined accurately.

            for info_ in infolist:
                tid_ = info_.course.tid
                if tid_ != "--":
                    tids_.add(tid_)
                if info_.course.group:
                    groups_.add(info_.course.group)
            activity.set_tids(sorted(tids_))
            activity.set_groups(sorted(groups_))

            # For the other stuff, info from all classes is needed
            for info_ in self.courses.tag2entries[tag]:
                tid_ = info_.course.tid
                if tid_ != "--":
                    alltids.add(tid_)
                cg = info_.course.class_group()
                if cg:
                    allgroups.add(cg)
                if info_.rooms:
                    allroomlists_.append(info_.rooms)
            activity.set_all_tids(alltids)
            activity.set_all_groups(allgroups)
#TODO: This was already done for the Activity!
            activity.set_all_rooms(
                simplify_room_lists_(allroomlists_, klass, tag)
            )
            alist.append(activity)
# Sort lesson names?
        alist.sort(key=lambda a: a.subject)

        tiledata = []
        tiles = []
        tile_list_hidden = []
        for a in alist:
            print("\n§§§", a.groups, a.allgroups, a.tag, a.sid, a.subject, a.tids, a.alltids)
# a.allgroups is a – possibly unoptimized – set of all groups, with class,
# and is needed for clash checking. However, if group clash checking is
# done on a class-by-class basis, I will probably need the groups as in
# chipdata.basic_groups below, but for each involved class.
# Perhaps as an ordered list of (class, group-set) pairs.


# Shouldn't some of this Activity stuff be done just once for all classes?

            chipdata = class_divisions(
                    a.groups,
                    group_map,
                    divisions
                )
# The chipdata stuff covers only the current class
            print("    GROUPS:", chipdata.groups)
            print("    SET:", chipdata.basic_groups)
            print(f"    {chipdata.num}/{chipdata.den} @ {chipdata.offset}")



# a.alltids is a set of all tids and is needed for clash checking

            print("    ALL ROOMS:", a.roomlists)
# a.roomlists will be needed for allocating and reallocating rooms

            lessons = self.tag2lessons.get(a.tag)
            if lessons:
                for l in lessons:
                    print("  +++", l)

                    d, p = timeslot2index(l.TIME)
                    print("   ---", a.sid, d, p)

                    t_tids = ','.join(a.tids)
                    t_groups = '/'.join(a.groups)
                    t_rooms = l.ROOMS
                    tiledata.append( # for the list of tiles, etc.
                        (
                            a.sid,
                            str(l.LENGTH),
                            t_groups,
                            t_tids,
                            l.id,
# The room list is probably needed as a list or set ...
                            t_rooms.split(','),
                            chipdata.groups,
                            chipdata.basic_groups,
                        )
                    )

                    tile_index = len(tiles)
                    tile = make_tile(
                        grid,
                        tile_index,
                        duration=l.LENGTH,
                        n_parts=chipdata.num,
                        n_all=chipdata.den,
                        offset=chipdata.offset,
                        text=a.sid,
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

#TODO: Will need to consider activities which cover more than one class!
# Actually, there is one per tag ... or perhaps those details can be
# left to the lessons/chips?
# Maybe a subclass ClassActivity for class-specific data?
class Activity_:
    __slots__ = (
        "sid",
        "subject",
        "tag",
        "tids",
        "groups",
        "allgroups",
        "roomlists",
        "alltids",
    )

    def __init__(self, sid, subject, tag):
        self.sid = sid
        self.subject = subject
        self.tag = tag

#?
    def set_tids(self, tids):
        self.tids = tids

#?
    def set_groups(self, groups):
        self.groups = groups

    def set_all_groups(self, groups):
        self.allgroups = groups

    def set_all_rooms(self, roomlists):
        self.roomlists = roomlists

    def set_all_tids(self, tids):
        self.alltids = tids


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


class ChipData(NamedTuple):
    groups: list[str]       # should be ordered
    basic_groups: set[str]
    rest_groups: set[str]   # the remaining groups in the division
    offset: int             # lowest possible start index
    num: int                # number of "parts"
    den: int                # total number of "parts"


#?
def tile_dimensions(klass):
    divs = get_classes()[klass].divisions.divisions
    print("\n%DIV%", 13)
    for i, div in enumerate(divs):
        n = 0
        ag = []
        g2ag = {}
        for g, ags in div:
            if ags is None:
                n += 1
                ag.append(g)
            else:
                g2ag[g] = ags
        print(" ===", n, ag, g2ag)
        

def class_divisions(groups, group_map, idivs):
    """Determine the size – as a fraction of the whole class – and an
    offset, for the given <groups>.
    Trim the groups a bit first, removing subsets, so that the list of
    groups doesn't get too long.
    <groups> is a list or other iterable providing the initial groups.
    <group_map> is the "GROUP_MAP" value of the class's group info.
    <idivs> is the "INDEPENDENT_DIVISIONS" value of the class's group info.
    Return the trimmed groups (ordered list) and the corresponding set
    of "basic" groups.
    Also return the information concerning the tile size and placement
    for graphical display purposes.
    The return value is a <ChipData> instance.
    """
    if '*' not in groups:
        group_sets = eliminate_subsets(groups, group_map)
        # print("\n&&&&&&1 ->", group_sets)
        group_divs, group_set = independent_divisions(idivs, group_sets)
        # print("\n&&&&&&2", idivs, "||", group_divs, "-----", group_set)
        if not group_divs:
            raise Bug(f"No groups ... {groups}")
        if len(group_divs) == 1:
            num, offset, den, restset = group_divs[0]
            glist = [gs[0] for gs in group_sets]
            # print(f"GROUPS: {glist}, MIN-OFFSET: {offset} @ {num}/{den}")
            return ChipData(glist, group_set, restset, offset, num, den)
    # print("  ... whole class")
#TODO?
    return ChipData(['*'], {'*'}, set(), 0, 1, 1)






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

#TODO--
    tile_dimensions("13")
    
    widget.resize(1000, 550)
    run(widget)

