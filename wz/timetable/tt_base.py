"""
timetable/tt_base.py

Last updated:  2023-08-09

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
    get_rooms,
)
from core.classes import NO_CLASS, GROUP_ALL
from core.teachers import NO_TEACHER
from core.db_access import db_select, db_query


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
    tlessons = []   # (checkbits, list of room-choice lists, ???)
    # Get 100%-parallel lessons and "combine" them
    for tag, pdata in parallel_map.items():
        # This removes processed items from <lid_map>
        tl = multilesson(tag, pdata, lid_map, lg_map, rmap_i)
        if tl:
            tlessons.append(tl)
        # else: weight not '+' or only one lesson-id
    # ... then the single ones
    for l_data in lid_map.values():
        lg, lid, l, t, p, rr = l_data
        lg_data = lg_map[lg]
        if rr:
            rplist = [rmap_i[r] for r in rr.split(",")]
        else:
            rplist = []
        tlessons.append((
            lg_data[0],
            simplify_room_lists(lg_data[1]),
            [(lid, lg, lg_data)],
            t,
            p,
            rplist
        ))
    return tlessons


def multilesson(tag, pdata, lid_map, lg_map, rmap_i):
    ll, w = pdata
    if w != '+' or len(ll) < 2:
        return None
    # Combine the lessons
    llist = [lid_map.pop(lid) for lid in ll]
    lglist = []
    checkbits = 0
    rilist = []     # rooms (indexes – list of lists)
    fixed_time = ""
    length = -1
    p0 = ""
    rplist = []     # previously allocated room list (indexes)
    for l_data in llist:
        lg, lid, l, t, p, rr = l_data
        lg_data = lg_map[lg]
        lglist.append((lid, lg, lg_data))
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
                    p0 = "-"    # flag conflict, later set empty
            else:
                p0 = p
        if rr:
            for r in rr.split(","):
                rplist.append(rmap_i[r])
    assert length > 0
    if p0 == "-":
        p0 = ""
    rooms = simplify_room_lists(rilist)
    return (checkbits, rooms, lglist, fixed_time, p0, rplist)


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


def simplify_room_lists(roomlists: list[list[int]]) -> Optional[
    tuple[
        list[int],          # required single rooms
        list[list[int]],    # fixed room choices
        list[list[int]]     # flexible room choices
    ]
]:
    """Simplify room lists, where possible, and check for room conflicts.

    The basic room specifications for the individual "tlessons" are
    processed into three separate lists (see result type).
    The number of entries in <roomlist> is taken to be the number of
    distinct rooms needed.
    This approach is in some respects not ideal, but given the
    difficulties of specifying concisely the room requirements for
    blocks containing multiple courses, it seemed a reasonable compromise.
    """
    ## Collect single room "choices" and remove redundant entries
    srooms = [] # (single) fixed room
    rooms = []  # "normal" room choice list
    xrooms = [] # "flexible" room choice list (with '+')
    for rchoice in roomlists:
        if rchoice[-1] < 0:
            xrooms.append(rchoice[:-1])
        elif len(rchoice) == 1:
            r = rchoice[0]
            if r in srooms:
                return None     # Internal conflict!
            srooms.append(r)
        else:
            rooms.append(rchoice)
    i = 0
    while i < len(srooms):
        # Filter already-claimed rooms from the choice lists
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
    tlessons = collate_lessons(l_map, pmap, lg_map, tt_data.room_i)
    for tl in tlessons:
        print("   --", tl)


#???
#    tt = Timetable()

#    rset = {   "R1", "R2/R3", "R1/R5", "R1+", "R2/R5+", "R3" }
#    print("Room set:", rset)
#    print("  -->", simplify_room_lists_(rset))
