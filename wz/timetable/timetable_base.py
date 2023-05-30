"""
timetable/timetable_base.py

Last updated:  2023-05-30

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

#T = TRANSLATIONS("timetable.timetable_base")

### +++++

from typing import NamedTuple
from itertools import combinations

from core.db_access import open_database, KeyValueList
from core.basic_data import (
    get_days,
    get_periods,
    get_classes,
    get_teachers,
    get_subjects,
    get_rooms,
    timeslot2index
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


#NEW: info for the timetable views ...
# Maybe I should defer all of this to the presentation code. The
# course items are passed to that, so it should be possible, and it
# is not relevant for placement, etc.
#            teacher_data = {}   # {tid: [{cd-groups}, {rids}]}
            # As the room specification can be a choice rather than a
            # particular room, this can only be used to eliminate certain
            # rooms from consideration ...
#            room_data = {}      # {rid: [{cd-groups}, {tids}]}
# The (c)d-groups were previously built later, I think (when showing a
# class?). Is there a problem with building them here?

#            # pg_sets = {}    #  {klass -> set of division groups}

# Collect groups, teachers and rooms on a class basis, so that the
# lesson tiles don't try to show too much. A ',+' on the group can
# indicate that other classes are parallel.
# Of course, for teacher and room tables the collection criteria
# would be different! Would it make sense to collect them all in
# one place, or would there be completely separate handlers?

            ## Collect the data needed for timtable placements, etc.
            class_data = {}     # {class: [{d-groups}, {tids}, {rids}]}
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
#TODO
            # A more sophisticated approach might include a check that at
            # least one of a list of reasonable candidates (based on what?)
            # is available.
            # As there can be multi-room requirements, the data structure is
            # a list of lists (a single requirement potentially being a
            # choice – assumed to be ordered).
            roomlists = [room_split(r) for r in room_set]
            # print("???", roomlists)

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


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == '__main__':
    from core.db_access import open_database
    open_database()

    tt = Timetable()
