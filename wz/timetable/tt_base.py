"""
timetable/tt_base.py

Last updated:  2023-08-08

Handle the basic information for timetable display and processing.


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

#TODO: This is the new (August 2023) version, under development ...

if __name__ == "__main__":
    import sys, os
    this = sys.path[0]
    appdir = os.path.dirname(this)
    sys.path[0] = appdir
    basedir = os.path.dirname(appdir)
    from core.base import start
    start.setup(os.path.join(basedir, 'TESTDATA'))

#T = TRANSLATIONS("timetable.timetable_base")
#T = TRANSLATIONS("timetable.tt_base")

### +++++

from typing import NamedTuple, Optional
#from dataclasses import dataclass

from core.basic_data_3 import (
    get_classes,
    get_teachers,
    get_subjects,
    get_rooms,
)
from core.classes import NO_CLASS, GROUP_ALL
from core.teachers import NO_TEACHER
from core.activities_3a import (
    collect_activity_groups,
    CourseWithRoom,
)
from core.db_access import db_select, db_query, Record
#from timetable.tt_engine_3a import PlacementEngine


def get_teacher_bits(b):
    """Each teacher gets a unique index, so that integers can be used
    instead of the tag (str) in speed critical code.
    Also a vector of bit-tags is generated so that logical AND can be
    used to test timetable clashes.
    """
    timap = {}
    tvec = []
    for i, tid in enumerate(get_teachers()):
        timap[tid] = i
        if tid == NO_TEACHER:
            tvec.append(0)
        else:
            tvec.append(b)
            b += b
    return timap, tvec, b


def get_class_bits(b):
    """Each class gets a unique index, so that integers can be used
    instead of the tag (str) in speed critical code.
    Also bit-tags are generated for all usable class-groups, so that
    logical AND can be used to test timetable clashes. These are
    organised as a vector of mappings, one mapping per class, the keys
    being the groups, the values the bit-tags.
    """
    cmap = {}
    cimap = {}
    cgvec = []
    crvec = []
    i = 0
    for klass, cdata in get_classes().items():
        #print("?", klass)
        cimap[klass] = i
        i += 1
        gmap = {}
        cgvec.append(gmap)
        crvec.append(cdata.classroom)
        cg = cdata.divisions
        g0 = 0  # whole class / all atomic groups
        for ag in cg.atomic_groups:
            cmap[ag] = b
            g0 |= b
            b += b
        for g, ags in cg.group_atoms().items():
            #print("???", g, ags)
            bg0 = 0
            for ag in ags:
                bg0 |= cmap[ag]
            gmap[g] = bg0
        if g0:
            gmap[GROUP_ALL] = g0
        elif klass == NO_CLASS:
            gmap[GROUP_ALL] = 0
        else:
            gmap[GROUP_ALL] = b
            b += b
    return cimap, cgvec, crvec, b


def get_room_map():
    """Each room gets a unique index, so that integers can be used
    instead of the tag (str) in speed critical code.
    The special room "+" is given index -1.
    """
    rmap = {"+": -1}
    i = 0
    for r, n in get_rooms():
        rmap[r] = i
        i += 1
    return rmap


class TT_DATA(NamedTuple):
    class_i: dict[str, int]
    class_group_bits: list[dict[str, int]]
    class_room: list[str]
    teacher_i: dict[str, int]
    teacher_bits: list[int]
    room_i: dict[str, int]


def get_activity_groups(tt_data: TT_DATA):
    q = """select

        Lesson_group,
        --Lesson_data,
        CLASS,
        GRP,
        SUBJECT,
        TEACHER,
        BLOCK_SID,
        --BLOCK_TAG,
        ROOM

        from COURSE_LESSONS
        inner join COURSES using (Course)
        inner join LESSON_GROUPS using (Lesson_group)
        inner join LESSON_DATA using (Lesson_data)

        where Lesson_group != '0'
    """
    lg_map = {}
    r_map = tt_data.room_i
    for rec in db_select(q):
        lg = rec["Lesson_group"]
        klass = rec["CLASS"]
        ci = tt_data.class_i[klass]
        rm = tt_data.class_room[ci]
        if rm:
            room = rec["ROOM"].replace("$", rm)
        else:
            room = rec["ROOM"]
            assert "$" not in room
        group = rec["GRP"]
        sid = rec["SUBJECT"]
        bsid = rec["BLOCK_SID"]
        tid = rec ["TEACHER"]
        row = (
            klass,
            group,
            sid,
            tid,
            bsid,
            room
        )
# Display sid is: bsid if bsid else sid,

        gbits = tt_data.class_group_bits[ci][group] if group else 0
        ti = tt_data.teacher_i[tid]
        tbits = tt_data.teacher_bits[ti]
        checkbits = gbits | tbits

        rooms = [r_map[r] for r in room_split(room)]
        try:
            lg_data = lg_map[lg]
            lg_data[0] |= checkbits
            if rooms:
                roomlist = lg_data[1]
                if rooms not in roomlist:
                    roomlist.append(rooms)
            lg_data[2].append(row)

        except KeyError:
            lg_map[lg] = [
                checkbits,
                [rooms] if rooms else [],
                [row],
            ]
    return lg_map


def get_lessons():
    q = """select

        Lesson_group,
        Lid,
        LENGTH,
        TIME,
        PLACEMENT,
        ROOMS

        from LESSONS

        where Lesson_group != '0'
    """
    return {r[1]: r for r in db_query(q)}


#TODO: This is the version for "3a", using the PARALLEL_LESSONS table.
# A future version might integrate the info into the LESSONS table.
def get_parallels():
    q = """select

        TAG,
        Lesson_id,
        WEIGHTING

        from PARALLEL_LESSONS

        --where WEIGHTING = '+'
    """
    pmap = {}
    for row in db_query(q):
        tag, lid, w = row
        try:
            ll, w0 = pmap[tag]
            ll.append(lid)
#TODO: ...
            if w != w0:
                print(f"WARNING: // weight mismatch for {tag}: {ll} – '{w0}' vs '{w}'")

                # Take the smaller weight
                if w != '+' and (w0 == '+' or w < w0):
                    pmap[tag][1] = w

        except KeyError:
            pmap[tag] = [[lid], w]

#TODO: ... check > 1 lids
    for tag, ll in pmap.items():
        if len(ll) < 2:
            print(f"WARNING: // missing lesson for {tag}: {ll}")
    return pmap


def collate_lessons(
    lid_map: dict[int, list],
    parallel_map: dict[str, list], # list: lid-list, weight
    lg_map: dict[int, list[int, list[str], list[tuple]]],
    rmap_i: dict[str, int],
):
    # Get 100%-parallel lessons and "combine" them
    combined_list = []

#TODO
    for tag, pdata in parallel_map.items():
        llist = multilesson(tag, pdata, lid_map, lg_map, rmap_i)
#        combined_list.append(llist)

    for ll, w in parallel_map.values():
        if w == '+' and len(ll) > 1:
            # Combine the lessons
            combined_list.append([lid_map.pop(lid) for lid in ll])
    # Collect the allocation items
#TODO
    tlessons = []   # (checkbits, list of room-choice lists, ???)
    # ... first the combined (parallel) ones
    for combined in combined_list:
        checkbits = 0
        rilist = []
        fixed_time = ""
        for l_data in combined:
            lg, lid, l, t, p, rr = l_data
            lg_data = lg_map[lg]
            checkbits |= lg_data[0]
            rilist += lg_data[1]

            if t:
#TODO: Add check when editing time & parallels?
# Or else report here?
                if fixed_time:
                    assert t == fixed_time
                else:
                    fixed_time = t

# lid, length, placement info


        tlessons.append((checkbits, rilist, combined))
    # ... then the single ones
    for l_data in lid_map.values():
        checkbits, rilist, courselist = lg_map[l_data[0]]
        tlessons.append((checkbits, rilist, [l_data]))
    return tlessons


def multilesson(tag, pdata, lid_map, lg_map, rmap_i):
    ll, w = pdata
    if w == '+' and len(ll) > 1:
        # Combine the lessons
#temp:
#        llist = [lid_map.pop(lid) for lid in ll]
        llist = [lid_map[lid] for lid in ll]

        checkbits = 0
        rilist = []
        fixed_time = ""
        length = -1
        p0 = ""
        rrlist = []
        for l_data in llist:
            lg, lid, l, t, p, rr = l_data
            lg_data = lg_map[lg]
            checkbits |= lg_data[0]
            rix = lg_data[1]
            rilist += rix

            if t:
#TODO: Add check when editing time & parallels?
# Or else report here?
                if fixed_time:
                    assert t == fixed_time
                else:
                    fixed_time = t

            if l != length:
                assert length < 0
                length = l

            if p:
                if p0:
                    if p != p0:
                        pass

            if rr:
                rix0 = [rmap_i[r] for r in rr.split(",")]

# lid, placement info
        assert length > 0



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


##########################################


class TimetableActivity(NamedTuple):
    teacher_set: set[str]
    # division_groups: set[str]
    class_atoms: dict[str, set[str]] # {class: {atomic-group. ... }}
    roomlists: list[list[str]]
    lesson_info: Record
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
            sid = act.block_sid if act.block_sid else cwr.subject

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
                #print("???", ldata)
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
    open_database("wz_db.sqlite")

    timap, tvec, b = get_teacher_bits(1)
    l = len(f"{b:b}")
    print("\n TEACHERS\n  bits bytes:", l-1, sys.getsizeof(b))
    for tid, i in timap.items():
        print(f"   -- {tid:5} {tvec[i]:0{l}b}")

    cimap, cgvec, crvec, b = get_class_bits(b)
    l = len(f"{b:b}")
    print("\n CLASS-GROUPS\n  bits bytes:", l-1, sys.getsizeof(b))
    for klass, i in cimap.items():
        gmap = cgvec[i]
        print("***** class", klass, crvec[i])
        for g, bits in gmap.items():
            print(f"   -- {g:5} {bits:0{l}b}")

    print("\n ROOMS:")
    rimap = get_room_map()
    for r, i in rimap.items():
        print(f"   -- {r:5} {i}")

    tt_data = TT_DATA(
        cimap,
        cgvec,
        crvec,
        timap,
        tvec,
        rimap,
    )

    #quit(0)

    lg_map = get_activity_groups(tt_data)

    print("\n LESSONS:")
    l_map = get_lessons()
    for l, ldata in l_map.items():
        print(f"   -- {l:4}:", ldata)

    print("\n PARALLELS:")
    pmap = get_parallels()
    for tag in sorted(pmap):
        print(f"  // {tag:10} : {pmap[tag]}")

    print("\n TLESSONS:")
#TODO:
    tlessons = collate_lessons(l_map, pmap, lg_map, tt_data.room_i)
    for tl in tlessons:
        print("   --", tl)



#???
#    tt = Timetable()

#    rset = {   "R1", "R2/R3", "R1/R5", "R1+", "R2/R5+", "R3" }
#    print("Room set:", rset)
#    print("  -->", simplify_room_lists_(rset))
