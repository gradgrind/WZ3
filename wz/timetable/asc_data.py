"""
timetable/asc_data.py - last updated 2023-05-16

Prepare aSc-timetables input from the database ...

==============================
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
"""

__TEST = False
__TEST = True
__TESTX = False
__TESTY = False

MULTICLASS = "XX"   # class "tag" for lesson items involving more than 1 class

# IMPORTANT: Before importing the data generated here, some setting up of
# the school data is required, especially the setting of the total number
# of lesson slots per day, which seems to be preset to 7 in the program
# and there is no obvious way of changing this via an import.

########################################################################

if __name__ == "__main__":
    # Enable package import if running as module
    import sys, os

    this = sys.path[0]
    appdir = os.path.dirname(this)
    sys.path[0] = appdir
    basedir = os.path.dirname(appdir)
    from core.base import start

    start.setup(os.path.join(basedir, 'TESTDATA'))


# IMPORTANT: Note that some uses of Python dicts here may assume ordered
# entries. If the implementation is altered, this should be taken into
# account.

T = TRANSLATIONS("timetable.asc_data")

### +++++

import re

import xmltodict

from core.db_access import db_read_fields
from core.basic_data import (
    get_days,
    get_periods,
    get_classes,
    get_teachers,
    get_subjects,
    get_rooms,
    sublessons,
    timeslot2index,
)

#from timetable.activities import Courses


def idsub(tag):
    """In aSc, "id" fields may only contain ASCII alphanumeric characters,
    '-' and '_'. Substitute anything else by '_'.
    """
    return re.sub("[^-_A-Za-z0-9]", "_", tag)


WHOLE_CLASS = T["WHOLE_CLASS"]

### -----


def get_days_aSc() -> list[dict]:
    """Return an ordered list of aSc elements for the days."""
    days = get_days()
    nd = len(days)
    i = int(10 ** nd)
    dlist = []
    n = 0
    for tag, name in days:
        n += 1
        i //= 10
        dlist.append(
            {
                "@id": str(n),
                "@name": name,
                "@short": tag,
                "@days": f"{i:0{nd}d}",
            }
        )
    return dlist


def get_periods_aSc() -> list[dict]:
    """Return an ordered list of aSc elements for the periods."""
    vlist = db_read_fields(
        "TT_PERIODS",
        ("N", "TAG", "NAME", "START_TIME", "END_TIME"),
        sort_field="N",
    )
    plist = [
        {
            "@short": tag,
            "@name": name,
            "@starttime": stime,
            "@endtime": etime,
            "@period": str(n),
        }
        for n, tag, name, stime, etime in vlist
    ]
    return plist


def get_rooms_aSc() -> list[dict]:
    """Return an ordered list of aSc elements for the rooms."""
    rooms = [
        {"@id": idsub(rid), "@short": rid, "@name": name}
        for rid, name in get_rooms()
    ]
    rooms.append(
        {
            "@id": CONFIG["EXTRA_ROOM"],
            "@short": CONFIG["EXTRA_ROOM"],
            "@name": T["ROOM_TODO"],
        }
    )
    return rooms


def get_subjects_aSc(subjects) -> list[dict]:
    """Return an ordered list of aSc elements for the subjects."""
    slist = []
    for sid, name in get_subjects():
        sid_ = idsub(sid)
        if sid_ in subjects:
            slist.append({"@id": sid_, "@short": sid, "@name": name})
    return slist


def get_classes_aSc():
    """Return an ordered list of aSc elements for the classes.
    """
    classes = get_classes()
    availables = {
        k: a
        for k, a in db_read_fields(
            "TT_CLASSES",
            ("CLASS", "AVAILABLE")
        )
    }
    return [
        {
            "@id": idsub(klass),
            "@short": klass,
            "@name": name,
            "@classroomids": classes.get_classroom(klass),
            "@timeoff": timeoff_aSc(availables.get(klass) or ""),
        }
        for klass, name in classes.get_class_list()
    ]


def asc_group(klass, group):
    return idsub(f"{klass}-{group}")


def get_groups_aSc():
    """Return an ordered list of aSc elements for the groups within the classes.
    """
    group_list = []
    classes = get_classes()
    for klass, _ in classes.get_class_list():
        g = WHOLE_CLASS
        group_list.append(
            {
                "@id": asc_group(klass, g),
                "@classid": klass,
                "@name": g,
                "@entireclass": "1",
                "@divisiontag": "0",
            }
        )

#TODO

        # See which groups are used – seek dotted groups
        g1, gn = set(), set()
        for row in db_read_fields("COURSES", ["GRP"], CLASS=klass):
            g = row[0]
            if g:
                if g == '*':
                    continue
                if '.' in g:
                    gn.add(g)
                else:
                    g1.add(g)
        
        print("§§§§", klass, g1, gn)
        cdata = classes[klass]
        cg = cdata.divisions
        divs = cg.divisions
        print("  +", divs)
        g2d = {}
        for i, d in enumerate(divs):
            for g in d:
                g2d[g] = i
        print("  #", g2d)
#TODO ... 
        if gn:
            dx = {}
            for gg in gn:
                gl = gg.split('.')
                ds = {g2d[g] for g in gl}
                for i in ds:
                    pass



                for g in gs:
                    try:
                        dx[g]
                    except KeyError:
                        continue

        continue
    quit(0)
    if False:

        # Sort out the divisions ...
#def get_classes_fet() -> list[tuple]:
        """Build the structure for the classes definition.
        Return this as a list of tuples (one per class):
            1) class tag (short name)
            2) fet class entry – <dict> representing XML structure
            3) {teaching group -> [atom, ...] (list of "minimal subgroups".
            4) {(atom, ...) -> [group, ...]
        """
#    classes = get_classes()
#    fet_classes = FetClasses()
#    for klass, kname in classes.get_class_list():
#        ### Build a fet students_list/year entry for the given class
        cdata = classes[klass]
        cg = cdata.divisions
        # Essentially, fet deals with "minimal subgroups". These are
        # groups with no shared members. In WZ these have sometimes
        # been called "atomic groups".
        # For convenience fet provides (at the user interface level)
        # higher level groups, which it calls "Year" (in WZ "class"),
        # "Category" (which can correspond to a "division" in WZ),
        # "Division" (which can correspond to a group within a division
        # in WZ) and "Group" (a group of pupils – within a class –
        # which can be assigned to a "course").
        # For each Year-Group combination there needs to be a list of
        # (minimal) subgroups.
        # The following is an attempt to reduce the "categories" to 0
        # or 1, all the minimal subgroups being the fet "divisions".
        divs = cg.divisions
        g2a = {
            cg.set2group(gg): tuple(
                sorted(cg.set2group(g) for g in a)
            ) for gg, a in cg.group2atoms.items()
        }
        g2a[""] = g2a.pop("*")
        a2g = {
            tuple(
                sorted(cg.set2group(g) for g in a)
            ): "" if (ggg := cg.set2group(gg)) == "*" else ggg
            for a, gg in cg.atoms2group.items()
        }
        atoms = tuple(
            sorted(cg.set2group(g) for g in cg.filtered_atomic_groups)
        )





        divisions = classes.group_info(klass)["INDEPENDENT_DIVISIONS"]
        dix = 0
        for div in divisions:
            dix += 1
            for grp in div:
                group_list.append(
                    {
                        "@id": asc_group(klass, grp),
                        "@classid": klass,
                        "@name": grp,
                        "@entireclass": "0",
                        "@divisiontag": str(dix),
                    }
                )
    return group_list


def timeoff_aSc(available: str) -> str:
    """Return a "timeoff" entry for the given "AVAILABLE" data.
    """
    weektags = []
    nperiods = len(get_periods())
    for d in range(len(get_days())):
        default = "1"
        try:
            ddata = available[d]
        except IndexError:
            ddata = ""
        daytags = []
        for p in range(nperiods):
            try:
                px = "0" if ddata[p] == "-" else "1"
                default = px
            except IndexError:
                px = default
            daytags.append(px)
        weektags.append("." + "".join(daytags))
    return ",".join(weektags)


def get_teachers_aSc(teachers):
    """Return an ordered list of aSc elements for the teachers."""
    return [
        {
            "@id": idsub(tdata.tid),
            "@short": tdata.tid,
            "@name": tdata.signed,
            # TODO: "@gender": "M" or "F"?
            "@firstname": tdata.firstname,
            "@lastname": tdata.lastname,
            "@timeoff": timeoff_aSc(tdata.tt_data),
        }
        for tdata in get_teachers().values()
        if tdata.tid in teachers
    ]


#class TimetableCourses(Courses):
class TimetableCourses:
    def read_class_lessons(self):
        """Organize the data according to classes.
        Produce a list of aSc-lesson items with item identifiers
        including the class of the lesson – to aid sorting and searching.
        Lessons involving more than one class are collected under the
        class "tag" <MULTICLASS>.
        Any blocks with no sublessons are ignored.
        Any sublessons which have (time) placements are added to a list
        of aSc-card items.
        """
        # Collect teachers and subjects with timetable entries:
        self.timetable_teachers = set()
        self.timetable_subjects = set()

        # Collect aSc-lesson items and aSc-card items
        self.asc_lesson_list = []
        self.asc_card_list = []
        # For counting items within the classes:
        self.class_counter = {}  # {class -> number}

        # tag2entries: {block-tag -> [BlockInfo, ... ]}
        for tag, blocklist in self.tag2entries.items():
            lessons = sublessons(tag)
            if not lessons:
                continue
            class_set = set()
            group_set = set()
            teacher_set = set()
            room_list = []
            extra_room = False
            for blockinfo in blocklist:
                course = blockinfo.course
                class_set.add(course.klass)
                kgroup = full_group(course.klass, course.group)
                group_set.update(kgroup)
                teacher_set.add(course.tid)
                # Add rooms, retaining order
                for room in blockinfo.rooms:
                    if room == "+":
                        extra_room = True
                    elif room not in room_list:
                        room_list.append(room)
            # Get the subject-id from the block-tag, if it has a
            # subject, otherwise from the course
            sid = blockinfo.block.sid or course.sid
            if extra_room:
                room_list.append(CONFIG["EXTRA_ROOM"])
            # Divide lessons up according to duration
            durations = {}
            for sl in lessons:
                l = sl.LENGTH
                try:
                    durations[l].append(sl)
                except KeyError:
                    durations[l] = [sl]
            # Build aSc lesson items
            for l in sorted(durations):
                self.aSc_lesson(
                    classes=class_set,
                    sid=idsub(sid),
                    groups=group_set,
                    tids=teacher_set,
                    sl_list=durations[l],
                    duration=l,
                    rooms=room_list,
                )
        self.asc_lesson_list.sort(key=lambda x: x["@id"])
        # TODO: ? extend sorting?
        # Am I doing this right with multiple items? Should it be just one card?
        self.asc_card_list.sort(key=lambda x: x["@lessonid"])

    def aSc_lesson(self, classes, sid, groups, tids, sl_list, duration, rooms):
        """Given the data for an aSc-lesson item, build the item and
        add it to the list: <self.asc_lesson_list>.
        If any of its sublessons have a placement, add aSc-card items
        to the list <self.asc_card_list>.
        """
        if tids:
            tids.discard("--")
            self.timetable_teachers.update(tids)
        classes.discard("--")
        if groups and classes:
            __classes = sorted(classes)
        else:
            __classes = []
        if sid:
            if sid == "--":
                raise Bug("sid = '--'")
            self.timetable_subjects.add(sid)
        klass = MULTICLASS if len(__classes) != 1 else idsub(__classes[0])
        i = (self.class_counter.get(klass) or 0) + 1
        self.class_counter[klass] = i
        # It is not likely that there will be >99 lesson items for a class:
        asc_id = f"{klass}_{i:02}"
        asc_rooms = ",".join(rooms)
        number = len(sl_list)
        self.asc_lesson_list.append(
            {
                "@id": asc_id,
                "@classids": ",".join(__classes),
                "@subjectid": sid,
                "@groupids": ",".join(sorted(groups)),
                "@teacherids": ",".join(sorted(tids)),
                "@durationperiods": str(duration),
                # Note that in aSc the number of periods per week means
                # the total number of _single_ periods:
                "@periodsperweek": str(number * duration),
                "@classroomids": asc_rooms,
            }
        )

        # Now add aSc-card items for the sublessons which have placements.
        # The identifier must be the same as the corresponding aSc-lesson item.
        # The rooms should be taken from the aSc-lesson item if the
        # sublesson has none.
        for sl in sl_list:
            timefield = sl.TIME
            placement_field = sl.PLACEMENT
            fixed_time = False
            d, p = None, None
            if placement_field:
                try:
                    d, p = timeslot2index(placement_field)
                except ValueError as e:
                    REPORT("ERROR", f"[PLACEMENT] {str(e)}")
            if timefield:
                try:
                    d0, p0 = timeslot2index(timefield)
                    if d is None:
                        d, p = d0. p0
                        fixed_time = True
                    elif (d0 == d) and (p0 == p):
                        fixed_time = True
                    else:
                        d, p = d0. p0
                except ValueError:
                    pass
            if d is None:
                continue
            self.asc_card_list.append(
                {
                    "@lessonid": asc_id,
                    "@period": str(p + 1),
                    "@day": str(d + 1),
                    "@classroomids": sl.ROOMS if sl.ROOMS else asc_rooms,
                    "@locked": "1" if fixed_time else "0",
                }
            )


def full_group(klass, group):
    """Return the group as a "full group" – also containing the class.
    As some groups need to be represented as "compounds", return the
    result as a set.
    """
    if klass and klass != "--":
        if group:
            if group == "*":
                return {asc_group(klass, WHOLE_CLASS)}
            # Some groups are compounds – I need to get the components!
            groups = get_classes().group_info(klass)["GROUP_MAP"][group]
            return {asc_group(klass, g) for g in groups}
    return set()


########################################################################


def build_dict(
    ROOMS, PERIODS, TEACHERS, SUBJECTS, CLASSES, GROUPS, LESSONS, CARDS
):
    BASE = {
        "timetable": {
            "@importtype": "database",
            "@options": "idprefix:WZ,daynumbering1",
            # 'daysdefs' seems unnecessary, there are sensible defaults
            #            'daysdefs':
            #                {   '@options': 'canadd,canremove,canupdate,silent',
            #                    '@columns': 'id,name,short,days',
            #                    'daysdef':
            #                        [   {'@id': 'any', '@name': 'beliebigen Tag', '@short': 'X', '@days': '10000,01000,00100,00010,00001'},
            #                            {'@id': 'every', '@name': 'jeden Tag', '@short': 'A', '@days': '11111'},
            #                            {'@id': '1', '@name': 'Montag', '@short': 'Mo', '@days': '10000'},
            #                            {'@id': '2', '@name': 'Dienstag', '@short': 'Di', '@days': '01000'},
            #                            {'@id': '3', '@name': 'Mittwoch', '@short': 'Mi', '@days': '00100'},
            #                            {'@id': '4', '@name': 'Donnerstag', '@short': 'Do', '@days': '00010'},
            #                            {'@id': '5', '@name': 'Freitag', '@short': 'Fr', '@days': '00001'},
            #                        ]
            #                },
            "periods": {
                "@options": "canadd,canremove,canupdate,silent",
                "@columns": "period,name,short,starttime,endtime",
                "period": PERIODS,
            },
            "teachers": {
                "@options": "canadd,canremove,canupdate,silent",
                "@columns": "id,short,name,firstname,lastname,timeoff",
                "teacher": TEACHERS,
            },
            "classes": {
                "@options": "canadd,canremove,canupdate,silent",
                "@columns": "id,short,name,classroomids,timeoff",
                "class": CLASSES,
            },
            "groups": {
                "@options": "canadd,canremove,canupdate,silent",
                "@columns": "id,classid,name,entireclass,divisiontag",
                "group": GROUPS,
            },
            "subjects": {
                "@options": "canadd,canremove,canupdate,silent",
                "@columns": "id,name,short",
                "subject": SUBJECTS,
            },
            "classrooms": {
                "@options": "canadd,canremove,canupdate,silent",
                "@columns": "id,name,short",
                "classroom": ROOMS,
            },
            "lessons":
            # Use durationperiods instead of periodspercard (deprecated)
            # As far as I can see, the only way in aSc to make lessons
            # parallel is to combine them to a single subject.
            {
                "@options": "canadd,canremove,canupdate,silent",
                "@columns": "id,classids,groupids,subjectid,durationperiods,periodsperweek,teacherids,classroomids",
                "lesson": LESSONS,
            },
            # Initial (fixed?) placements
            "cards": {
                "@options": "canadd,canremove,canupdate,silent",
                "@columns": "lessonid,period,day,classroomids,locked",
                "card": CARDS,
            },
        }
    }
    return BASE


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()

    days = get_days_aSc()
    if __TEST:
        print("\n*** DAYS ***")
        for d in days:
            print(f"   {d}")
        print("\n  ==================================================")

    periods = get_periods_aSc()
    if __TEST:
        print("\n*** PERIODS ***")
        for p in periods:
            print(f"   {p}")
        print("\n  ==================================================")

    allrooms = get_rooms_aSc()
    if __TEST:
        print("\n*** ROOMS ***")
        for rdata in allrooms:
            print("   ", rdata)
        print("\n  ==================================================")

    classes = get_classes_aSc()
    if __TEST:
        print("\n*** CLASSES ***")
        for cdata in classes:
            print("   ", cdata)

    groups = get_groups_aSc()
    if __TEST:
        print("\n*** CLASS-GROUPS ***")
        for gdata in groups:
            print("   ", gdata)

    quit(0)

    courses = TimetableCourses()
    courses.read_class_lessons()

    #    quit(0)

    #    lessons, cards = get_lessons()

    # Must be after collecting lessons:
    allsubjects = get_subjects_aSc(courses.timetable_subjects)
    if __TEST:
        print("\n*** SUBJECTS ***")
        for sdata in allsubjects:
            print("   ", sdata)

    # Must be after collecting lessons:
    teachers = get_teachers_aSc(courses.timetable_teachers)
    if __TEST:
        print("\n*** TEACHERS ***")
        for tdata in teachers:
            print("   ", tdata)

    #    quit(0)

    if __TESTX:
        print("\n*** LESSON ITEMS ***")
        for l in courses.asc_lesson_list:
            print("  +++", l)

    if __TESTY:
        print("\n*** CARDS ***")
        for c in courses.asc_card_list:
            print("  !!!", c)

    #    quit(0)

    outdir = DATAPATH("TIMETABLE/out")
    os.makedirs(outdir, exist_ok=True)

    xml_aSc = xmltodict.unparse(
        build_dict(
            ROOMS=allrooms,
            PERIODS=periods,
            TEACHERS=teachers,
            SUBJECTS=allsubjects,
            CLASSES=classes,
            GROUPS=groups,
            LESSONS=courses.asc_lesson_list,
            CARDS=courses.asc_card_list,
            #            CARDS = [],
        ),
        pretty=True,
    )

    outpath = os.path.join(outdir, "tt_out.xml")
    with open(outpath, "w", encoding="utf-8") as fh:
        fh.write(xml_aSc.replace("\t", "   "))
    print("\nTIMETABLE XML ->", outpath)
