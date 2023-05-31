"""
timetable/timetable_base.py

Last updated:  2023-05-31

Collect the basic information for timetable display and processing.


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

T = TRANSLATIONS("timetable.timetable_base")

### +++++

from typing import NamedTuple, Optional

from core.basic_data import (
    get_classes,
    get_teachers,
    get_subjects,
    get_rooms,
)
from core.activities import (
    collect_activity_groups,
    LessonInfo,
    CourseWithRoom,
)
from core.classes import GROUP_ALL
from timetable.tt_engine import PlacementEngine


class TimetableActivity(NamedTuple):
    teacher_set: set[str]
    # division_groups: set[str]
    class_atoms: dict[str, set[str]] # {class: {atomic-group. ... }}
    roomlists: list[list[str]]
    lesson_info: LessonInfo
    sid: str
    lesson_group: int
    course_list: list[CourseWithRoom]


class Places(NamedTuple):
    PERIODS_PER_DAY: int


### -----


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


def room_split(room_choice: str) -> list[str]:
    """Split a room (choice) string into components.
    If there is a '+', it must be the last character, not preceded
    by a '/'.
    """
    rs = room_choice.rstrip('+')
    rl = rs.split('/') if rs else []
    if room_choice and room_choice[-1] == '+':
        rl.append('+')
    return rl


class Timetable:
    def __init__(self):
        self.init()
        ## Set up the placement data
        self.engine = PlacementEngine()
        self.engine.setup_structures(
            classes={
                k: gmap[GROUP_ALL]
                for k, gmap in self.class_group_atoms.items()
                if self.class_activities[k]
            },
            subjects=self.subject_activities,
            teachers=self.teacher_activities,
        )
        self.engine.set_activities(self.activities)

    def init(self):
        self.class_group_atoms = class2group2atoms()
        ### Collect <Activity> items, they are then referenced by index
        self.activities = []
        ### (Ordered dict) Collect activity indexes for each class
        self.class_activities: dict[str, list[int]] = {}
        ### (Ordered dict) Collect activity indexes for each teacher
        self.teacher_activities = {
            t: [] for t in get_teachers()
        }
        ### (Ordered dict) Collect activity indexes for each room
        self.room_activities = {
            r: [] for r in get_rooms().key_list()
        }
        ### (Ordered dict) Collect activity indexes for each subject
        self.subject_activities = {
            s: [] for s in get_subjects().key_list()
        }
        ### group-division map for each class
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

        ### Collect data for each lesson-group
        lg_map = collect_activity_groups()
        ### Add activities
        for lg, act in lg_map.items():
            class_atoms = {}    # {class: {atomic groups}}

# Collect groups, teachers and rooms on a class basis, so that the
# lesson tiles don't try to show too much. A ',+' on the group can
# indicate that other classes are parallel.
# Of course, for teacher and room tables the collection criteria
# would be different! Would it make sense to collect them all in
# one place, or would there be completely separate handlers?

            ## Collect the data needed for timetable placements, etc.
            teacher_set = set()
            room_set = set()
            for cwr in act.course_list:
                klass = cwr.klass
                if cwr.group and klass != "--":
                    # Only add a group entry if there is a
                    # group and a (real) class
                    gatoms = self.class_group_atoms[klass][cwr.group]
                    try:
                        class_atoms[klass].update(gatoms)
                        # pg_sets[klass].add(cwr.group)
                    except KeyError:
                        class_atoms[klass] = set(gatoms)
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
            # The room specification can be a choice rather than a
            # particular room. In this case the choice list can only be
            # used to eliminate certain rooms from consideration ...
#TODO
            # A more sophisticated approach might include a check that at
            # least one of a list of reasonable candidates (based on what?)
            # is available.

            # As there can be multi-room requirements, the data structure is
            # a list of lists (a single requirement potentially being a
            # choice – assumed to be ordered).
            # A '+' entry should always be the last in a choice list.
            
            roomlists = simplify_room_lists_(room_set)
            if roomlists is None:
                REPORT(
                    "ERROR",
                    T["BLOCK_ROOMS_INCOMPATIBLE"].format(
                        classes=",".join(class_atoms),
                        sid=sid,
                        rooms=" & ".join(room_set)
                    )
                )
                roomlists=[]
            # print("???r:", roomlists)

            ## Generate the activity or activities
            for ldata in act.lessons:
#TODO: Perhaps split it up into different lists with a common index?
                a = TimetableActivity(
                    teacher_set,
                    # pg_sets,
                    class_atoms,
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
                for k in class_atoms:
                    self.class_activities[k].append(a_index)
                for t in teacher_set:
                    self.teacher_activities[t].append(a_index)
                self.subject_activities[sid].append(a_index)


def simplify_room_lists_(room_set: set[str]) -> Optional[
    tuple[
        list[str],          # required single rooms
        list[list[str]],    # fixed room choices
        list[list[str]]     # flexible room choices
    ]]:
    """Simplify room lists, where possible, and check for room conflicts.
    
    The room specifications for the individual courses (via the
    "WORKLOAD" entries) are collected as a set – thus eliminating
    textual duplicates.
    The number of entries in <room_set> is taken to be the number of
    distinct rooms needed.
    This approach is in some respects not ideal, but given the
    difficulties of specifying concisely the room requirements for
    blocks containing multiple courses, it seemed a reasonable compromise.
    """
    ## Collect single room "choices" and remove redundant entries
    srooms = [] # (single) fixed room
    rooms = []  # "normal" room choice list
    xrooms = [] # "flexible" room choice list (with '+')
    for r in room_set:
        rlist = room_split(r)
        if rlist[-1] == '+':
            xrooms.append(rlist[:-1])
        elif len(rlist) == 1:
            if r in srooms:
                return None
            srooms.append(r)
        else:
            rooms.append(rlist)
    i = 0
    while i < len(srooms):
        # Filter already claimed rooms from the choice lists
        r = srooms[i]
        i += 1
        rooms_1 = []    # temporary buffer for rebuilding <rooms>
        for rlist in rooms:
            try:
                rlist.remove(r)
            except ValueError:
                rooms_1.append(rlist)
            else:
                if len(rlist) == 1:
                    rx = rlist[0]
                    if rx in srooms:
                        return None
                    # Add to list of single rooms
                    srooms.append(rx)
                else:
                    rooms_1.append(rlist)       
        rooms = rooms_1
        # Filter already claimed rooms from the flexible choices
        for rlist in xrooms:
            try:
                rlist.remove(r)
            except ValueError:
                continue
    # Sort according to list length
    rl1 = [(len(rl), rl) for rl in rooms]
    rl2 = [(len(rl), rl) for rl in xrooms]
    rl1.sort()
    rl2.sort()
    return (
        srooms,
        [rl[1] for rl in rl1],
        [rl[1] for rl in rl2]
    )


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == '__main__':
    from core.db_access import open_database
    open_database()

    tt = Timetable()

    rset = {   "R1", "R2/R3", "R1/R5", "R1+", "R2/R5+", "R3" }
    print("Room set:", rset)
    print("  -->", simplify_room_lists_(rset))
