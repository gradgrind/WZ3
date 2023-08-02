"""
timetable/fet_data.py - last updated 2023-07-30

Prepare fet-timetables input from the database ...

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

_TEST = False
#_TEST = True
_TEST1 = False
#_TEST1 = True
_SUBJECTS_AND_TEACHERS = False
#_SUBJECTS_AND_TEACHERS = True

FET_VERSION = "6.9.0"

WEIGHTMAP = { '-': None,
    '1': "50", '2': "67", '3': "80", '4': "88", '5': "93",
    '6': "95", '7': "97", '8': "98", '9': "99", '+': "100"
}
NPERIODSMAX = 10    # max. number of periods in constraints
SPECIAL_CONSTRAINTS = {"PAIRGAP", "NOTAFTER"}

########################################################################

import sys, os

if __name__ == "__main__":
    # Enable package import if running as module
    this = sys.path[0]
    appdir = os.path.dirname(this)
    sys.path[0] = appdir
    basedir = os.path.dirname(appdir)
    from core.base import start

    # TODO: Temporary redirection to use real data (there isn't any test data yet!)
    start.setup(os.path.join(basedir, 'TESTDATA'))

from typing import Optional, NamedTuple

T = TRANSLATIONS("timetable.fet_data")

### +++++

from itertools import product

import xmltodict

from core.base import class_group_split
from core.basic_data_3 import (
    get_days,
    get_periods,
    get_classes,
    get_teachers,
    get_subjects,
    get_rooms,
    timeslot2index,
    BlockTag,
)
from core.db_access import (
    db_backup,
    db_update_fields,
    db_read_unique,
    db_read_unique_field,
    db_read_fields,
    NoRecord,
    read_pairs,
    db_read_mappings,
    db_name,
)
from core.activities_3a import collect_activity_groups

LUNCH_BREAK = '^'

### -----


class FetClasses(list):
    """Class data – a mangled list.
    """
    def __init__(self):
        super().__init__()
        self.g2a = {}
        self.a2g = {}

    def append(self, klass, year_entry, g2a, a2g):
        super().append((klass, year_entry))
        self.g2a[klass] = g2a
        self.a2g[klass] = a2g


def get_days_fet() -> list[dict[str, str]]:
    return [{"Name": d[0]} for d in get_days()]


def get_periods_fet() -> list[dict[str, str]]:
    return [{"Name": p[0]} for p in get_periods()]


def get_rooms_fet(virtual_rooms: list[dict]) -> list[dict[str, str]]:
    """Build an ordered list of fet elements for the rooms."""
    rlist = [
        {
            "Name": rid,
            "Building": None,
            "Capacity": "30000",
            "Virtual": "false",
            "Comments": room,
        }
        for rid, room in get_rooms()
    ]
    return rlist + virtual_rooms


def get_subjects_fet(used_set) -> list[dict[str, str]]:
    slist = [
        {"Name": sid, "Comments": name}
        for sid, name in get_subjects()
        if sid in used_set
    ]
    slist.append({"Name": LUNCH_BREAK, "Comments": T["LUNCH_BREAK"]})
    return slist


def get_teachers_fet(used_set) -> list[dict[str, str]]:
    teachers = get_teachers()
    return [
        {
            "Name": tid,
            "Target_Number_of_Hours": "0",
            "Qualified_Subjects": None,
            "Comments": teachers.name(tid),
        }
        for tid in teachers
        if tid in used_set
    ]


def get_classes_fet() -> list[tuple]:
    """Build the structure for the classes definition.
    Return this as a list of tuples (one per class):
        1) class tag (short name)
        2) fet class entry – <dict> representing XML structure
        3) {teaching group -> [atom, ...] (list of "minimal subgroups".
        4) {(atom, ...) -> [group, ...]
    """
    classes = get_classes()
    fet_classes = FetClasses()
    for klass, kname in classes.get_class_list():
        ### Build a fet students_list/year entry for the given class
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
        g2ags = cg.group_atoms()
        atoms = cg.atomic_groups
        # The groups are all the "primary" groups, unless they are atomic
        # groups already defined as subgroups.
        # The "whole-class" entry is not included: g2ags[""] = atoms
        year_entry = {
            "Name": klass,
            "Number_of_Students": "0",
            "Comments": kname,
            "Number_of_Categories": "1" if divs else "0",
            "Separator": ".",
        }
        if divs:
            groups = []
            agset = set()
            pending = set()
            for g, ags in g2ags.items():
                assert g
                if g in atoms:
                    # This group is an atomic group
                    pending.add(g)
                else:
                    agset.update(ags)
                    subgroups = [
                        {
                            "Name": f"{klass}.{ag}",
                            "Number_of_Students": "0",
                            "Comments": None,
                        }
                        for ag in sorted(ags)
                    ]
                    groups.append(
                        {
                            "Name": f"{klass}.{g}",
                            "Number_of_Students": "0",
                            "Comments": None,
                            "Subgroup": subgroups,
                        }
                    )
            # Add any pending groups which haven't been included as subgroups
            for g in pending:
                if g not in agset:
                    groups.append(
                        {
                            "Name": f"{klass}.{g}",
                            "Number_of_Students": "0",
                            "Comments": None,
                        }
                    )
            groups.sort(key=lambda x: x["Name"])
            year_entry["Category"] = {
                "Number_of_Divisions": f"{len(atoms)}",
                "Division": atoms,
            }
            year_entry["Group"] = groups
        # Prepare the <FetClasses> item
        g2a = {
            g: tuple(ags)
            for g, ags in g2ags.items()
        }
        g2a[""] = tuple(atoms)
        # print("&&&&&", klass, g2a)
        a2g = {
            a: g
            for g, a in g2a.items()
        }
        # print("   ~~", a2g)
        fet_classes.append(klass, year_entry, g2a, a2g)
    return fet_classes


def timeoff_fet(available: str) -> tuple[list[dict[str, str]], set[str]]:
    """Build "not available" entries for the given data.
    The period values are from '-' through 1 to 9 and '+'.
    fet, however, only deals with "blocked" "available" values.
    Also collect possible (lunch) break times, sorted by day.
    Return: (
        [{"Day": day, "Hour": period}, ... ],
        {day -> {period, ... }}
    )
    """
    try:
        day_periods = available.split("_")
    except:
        day_periods = ""
    days = get_days().key_list()
    periods = get_periods().key_list()
    blocked_periods = []
    possible_breaks = {}
    i = 0
    for d in days:
        try:
            ddata = day_periods[i]
        except IndexError:
            ddata = ""
        i += 1
        j = 0
        pval = "+"  # default value
        for p in periods:
            try:
                pval = ddata[j]
                if pval != '-':
                    pval = '+'
            except IndexError:
                # No value, use last available
                pass
            j += 1
            if pval == "-":
                blocked_periods.append({"Day": d, "Hour": p})
            else:
                try:
                    possible_breaks[d].add(p)
                except KeyError:
                    possible_breaks[d] = {p}
    return blocked_periods, possible_breaks


class TimetableCourses:
    __slots__ = (
        "TT_CONFIG",
        "timetable_teachers",
        "timetable_subjects",
        "timetable_classes",
        "class_handlers",
        "teacher_handlers",
        "locked_aids",
        "fet_classes",
        "group2atoms",
        "activities",
        "lid_aid",
        "__virtual_room_map",
        "__virtual_rooms",
        "time_constraints",
        "space_constraints",
        "class2sid2ag2aids",
        "fancy_rooms",
        "block_classes",
    )

    def __init__(self, fet_classes):
        self.fet_classes = fet_classes
        self.group2atoms = fet_classes.g2a
        self.TT_CONFIG = MINION(DATAPATH("CONFIG/TIMETABLE"))

    def read_lessons(self, block_classes=None):
        """Produce a list of fet-activity (lesson) items with a
        reference to the id of the source line in the LESSONS table.
        Any blocks with no sublessons are ignored.
        Constraints for time and rooms are added as appropriate.
        If classes are supplied (as a list or set) in <block_classes>,
        no lessons will be generated for them.
        """
        self.block_classes = block_classes or []
        # Collect teachers and subjects with timetable entries:
        self.timetable_teachers = set()
        self.timetable_subjects = set()
        # Collect locked placements:
        self.locked_aids: dict[str, Optional[tuple[str,str]]] = {}
        # Collect more complex room allocations
        self.fancy_rooms = []

        self.time_constraints = {}
        self.space_constraints = {}
        self.activities: list[dict] = []  # fet activities
        self.lid_aid = {}   # map lesson id to activity id
        # Used for managing "virtual" rooms:
        self.__virtual_room_map: dict[str, str] = {}  # rooms hash -> room id
        self.__virtual_rooms: dict[str, dict] = {}  # room id -> fet room
        # For constraints concerning relative placement of individual
        # lessons in the various subjects, collect the "atomic" pupil
        # groups and their activity ids for each subject, divided by class:
        self.class2sid2ag2aids: dict[str, dict[str, dict[str, list[int]]]] = {}

        self.timetable_classes = []
        for klass, year_entry in self.fet_classes:
            self.timetable_classes.append(year_entry)
#TODO: This was <atoms2grouplist> (the value was a list, now it is a
# single group). Has this a negative impact anywhere?
        atoms2group = self.fet_classes.a2g

        ### Collect data for each lesson-group
        lg_map = collect_activity_groups()
        ### Add fet activities
        for lg, act in lg_map.items():
            class_set = set()
            group_sets = {} # {klass -> set of atomic groups}
            teacher_set = set()
            room_set = set()
            for klass, g, sid, tid, room in act.course_list:
                class_set.add(klass)
                if g and klass != "--":
                    # Only add a group "Students" entry if there is a
                    # group and a (real) class
                    if g == "*":
                        g = ""
                    gatoms = self.group2atoms[klass][g]
                    try:
                        group_sets[klass].update(gatoms)
                    except KeyError:
                        group_sets[klass] = set(gatoms)
                if room:
                    room_set.add(room)
                if tid != "--":
                    teacher_set.add(tid)
            # Get "usable" groups
            groups = []
            for klass, aset in group_sets.items():
                # Filter out a class? Also class constraints need to go.
                if klass in self.block_classes:
                    continue
                a2g = atoms2group[klass]
                try:
                    key = tuple(sorted(aset))
                    g = a2g[key]
                    groups.append(f"{klass}.{g}" if g else klass)
                except KeyError:
                    REPORT(
                        "ERROR",
                        T["INVALID_GROUP_LIST"].format(
                            lg=lg, groups=",".join(key)
                        ),
                    )
            # Get the subject-id from the block-tag, if it has a
            # subject, otherwise from the course (of which there
            # should be only one!)
            #print("???", type(act), act)
            if act.block_sid:
                sid = act.block_sid
            ## Handle rooms
            # Simplify room lists, check for room conflicts.
            # Collect room allocations which must remain open (containing
            # '+') and multiple room allocations for possible later
            # manual handling.
            singles = []
            roomlists0 = []
            classes_str = ",".join(sorted(class_set))
            # Collect open allocations (with '+') and multiple room
            # activities. Eliminate open room choices from further
            # consideration here.
            roomlists = []
            for r in room_set:
                rs = r.rstrip('+')
                rl = rs.split('/') if rs else []
                if r[-1] == '+':
                    rl.append('+')
                roomlists.append(rl)
            if len(roomlists) > 1:
                self.fancy_rooms.append((classes_str, lg, roomlists))
                for rl in roomlists:
                    if rl[-1] != '+':
                        if len(rl) == 1:
                            singles.append(rl[0])
                        else:
                            roomlists0.append(rl)
            elif len(roomlists) == 1:
                rl = roomlists[0]
                if rl[-1] == '+':
                    self.fancy_rooms.append((classes_str, lg, roomlists))
                elif len(rl) == 1:
                    singles.append(rl[0])
                else:
                    roomlists0.append(rl)
            # Remove redundant entries
            roomlists1 = []
            for rl in roomlists0:
                _rl = rl.copy()
                for sl in singles:
                    try:
                        _rl.remove(sl)
                    except ValueError:
                        pass
                if _rl:
                    roomlists1.append(_rl)
                else:
                    REPORT(
                        "ERROR",
                        T["ROOM_BLOCK_CONFLICT"].format(
                            classes=classes_str,
                            tag=tag,
                            rooms=repr(roomlists),
                        ),
                    )
            for sl in singles:
                roomlists1.append([sl])
            if len(roomlists1) == 1:
                rooms = roomlists1[0]
            elif len(roomlists1) > 1:
                vroom = self.virtual_room(roomlists1)
                rooms = [vroom]
            else:
                rooms = []
            #            print("§§§", tag, class_set)
            #            print("   +++", teacher_set, groups)
            #            print("   ---", rooms)
            #            if len(roomlists1) > 1:
            #                print(roomlists1)
            #                print(self.__virtual_rooms[rooms[0]])

            ## Add to "used" teachers and subjects
            self.timetable_teachers.update(teacher_set)
            self.timetable_subjects.add(sid)
            ## Generate the activity or activities
            if teacher_set:
                if len(teacher_set) == 1:
                    activity0 = {"Teacher": teacher_set.pop()}
                else:
                    activity0 = {"Teacher": sorted(teacher_set)}
            else:
                activity0 = {}
            if groups:
                activity0["Students"] = (
                    groups[0] if len(groups) == 1 else groups
                )
            activity0["Subject"] = sid
            activity0["Active"] = "true"
            ## Divide lessons up according to duration
            durations = {}
            total_duration = 0
            # Need the LESSONS data: id, length, time
            for ldata in act.lessons:
                #print("???", type(ldata), ldata)
                lid = ldata["Lid"]
                l = ldata["LENGTH"]
                t = ldata["TIME"]
                total_duration += l
                lt = (lid, t)
                try:
                    durations[l].append(lt)
                except KeyError:
                    durations[l] = [lt]
            activity0["Total_Duration"] = str(total_duration)
            id0 = self.next_activity_id()
            activity0["Activity_Group_Id"] = str(
                id0 if len(act.lessons) > 1 else 0
            )
            for l in sorted(durations):
                dstr = str(l)
                for lid, time in durations[l]:
                    id_str = str(id0)
                    self.lid_aid[lid] = id_str
                    activity = activity0.copy()
                    activity["Id"] = id_str
                    activity["Duration"] = dstr
                    activity["Comments"] = str(lid)
                    self.add_placement(id_str, lid, time, rooms)
                    self.activities.append(activity)
                    # print("$$$$$", sid, groups, id_str)
                    self.subject_group_activity(sid, groups, id_str)
                    id0 += 1

        # Defining a set of lessons as an "Activity_Group" / subactivities
        # is a way of grouping activities which are split into a number
        # of lessons (such as English in group 10A for three lessons
        # per week). It is not of much significance for my usage of fet,
        # but it might be useful to have this coupling within the fet gui.
        # Uncoupled activitities are given Activity_Group_Id = '0',
        # a set of coupled activities is given as Activity_Group_Id the
        # (activity) Id of the first member of the set. The other
        # members of the set get the immediately following Id numbers,
        # but the same Activity_Group_Id. The parameter Total_Duration
        # is the sum of the Duration parameters of all the members.

    def add_placement(self, id_str, lesson_group, time, rooms):
        if time:
            if time[0] == "^":
#TODO:
                print("TODO: parallel", id_str, lesson_group, time, rooms)

            else:
                try:
                    d, p = time.split(".", 1)
                except ValueError:
#????
                    raise
                else:
                    # Fixed starting time
                    try:
                        timeslot2index(time)    # This is just a check
                    except ValueError as e:
                        REPORT("ERROR", str(e))
                    else:
                        self.locked_aids[id_str] = (d, p)
                        # Constraint to fix day and period
                        add_constraint(
                            self.time_constraints,
                            "ConstraintActivityPreferredStartingTime",
                            {
                                "Weight_Percentage": "100",
                                "Activity_Id": id_str,
                                "Preferred_Day": d,
                                "Preferred_Hour": p,
                                "Permanently_Locked": "true",
                                "Active": "true",
                                "Comments": None,
                            },
                        )
        ## Lesson room
        n = len(rooms)
        if n > 1:
            # Choice of rooms available
            r_c = "ConstraintActivityPreferredRooms"
            s_c = {
                "Weight_Percentage": "100",
                "Activity_Id": id_str,
                "Number_of_Preferred_Rooms": str(n),
                "Preferred_Room": rooms,
                "Active": "true",
                "Comments": None,
            }
        elif n == 1:
            # Either simple room, or "virtual" room for multiple rooms
            r_c = "ConstraintActivityPreferredRoom"
            room = rooms[0]
            s_c = {
                "Weight_Percentage": "100",
                "Activity_Id": id_str,
                "Room": room,
                "Permanently_Locked": "true",
                "Active": "true",
                "Comments": None,
            }
        else:
            return
        add_constraint(self.space_constraints, r_c, s_c)

    def gen_fetdata(self):
        fet_days = get_days_fet()
        fet_periods = get_periods_fet()
        fet_rooms = get_rooms_fet(self.virtual_room_list())
        fet_subjects = get_subjects_fet(self.timetable_subjects)
        fet_teachers = get_teachers_fet(self.timetable_teachers)

        fet_dict = {
            "@version": f"{FET_VERSION}",
            "Mode": "Official",
            "Institution_Name": f"{CONFIG['SCHOOL_NAME']}",
            "Comments": "Default comments",
            "Days_List": {
                "Number_of_Days": f"{len(fet_days)}",
                "Day": fet_days,
            },
            "Hours_List": {
                "Number_of_Hours": f"{len(fet_periods)}",
                "Hour": fet_periods,
            },
            "Subjects_List": {"Subject": fet_subjects},
            "Activity_Tags_List": None,
            "Teachers_List": {"Teacher": fet_teachers},
            "Students_List": {"Year": self.timetable_classes},
            "Activities_List": {"Activity": self.activities},
            "Buildings_List": None,
            "Rooms_List": {"Room": fet_rooms},
        }
        tc_dict = {
            "ConstraintBasicCompulsoryTime": {
                "Weight_Percentage": "100",
                "Active": "true",
                "Comments": None,
            }
        }
        sc_dict = {
            "ConstraintBasicCompulsorySpace": {
                "Weight_Percentage": "100",
                "Active": "true",
                "Comments": None,
            }
        }
        tc_dict.update(self.time_constraints)
        sc_dict.update(self.space_constraints)
        # TODO ... gui (checkbox list) with memory?
        # Prepare for filtering
        print("\nTIME CONSTRAINTS:")
        tc_block = {
            ### TIME CONSTRAINTS:
            ##"ConstraintBasicCompulsoryTime",
            # "ConstraintActivityPreferredStartingTime",
            # "ConstraintActivityPreferredStartingTimes",
            # "ConstraintStudentsSetNotAvailableTimes",
            # "ConstraintTeacherNotAvailableTimes",
            # "ConstraintTeacherMinHoursDaily",
            # "ConstraintTeacherMaxGapsPerDay",
            # "ConstraintTeacherMaxGapsPerWeek",
            # "ConstraintTeacherMaxHoursContinuously",
            # "ConstraintMinDaysBetweenActivities",
            # "ConstraintStudentsSetMinHoursDaily",
            # "ConstraintStudentsSetMaxGapsPerWeek",
            # "ConstraintTwoActivitiesOrderedIfSameDay",
            # "ConstraintMinGapsBetweenActivities",
            # "ConstraintActivityEndsStudentsDay",
        }
        for c in list(tc_dict):
            if c in tc_block:
                print(f"  – {c:42} ... blocked")
                del tc_dict[c]
            else:
                print(f"  – {c:42}")
        print("\nSPACE CONSTRAINTS:")
        sc_block = {
            ### SPACE CONSTRAINTS:
            ##"ConstraintBasicCompulsorySpace",
            # "ConstraintActivityPreferredRoom",
            # "ConstraintActivityPreferredRooms",
        }
        for c in list(sc_dict):
            if c in sc_block:
                print(f"  – {c:42} ... blocked")
                del sc_dict[c]
            else:
                print(f"  – {c:42}")

        fet_dict["Time_Constraints_List"] = tc_dict
        fet_dict["Space_Constraints_List"] = sc_dict
        return {"fet": fet_dict}

    def virtual_room(self, roomlists: list[list[str]]) -> str:
        """Return a virtual room id for the given list of room lists.
        These virtual rooms are cached so that they can be reused, should
        the <roomlists> argument be repeated.
        """
        # First need a hashable representation of <roomlists>, use a string.
        hashable = "+".join(["|".join(rooms) for rooms in roomlists])
        # print("???????", hashable)
        try:
            return self.__virtual_room_map[hashable]
        except KeyError:
            pass
        # Construct a new virtual room
        roomlist = []
        for rooms in roomlists:
            nrooms = len(rooms)
            roomlist.append(
                {
                    "Number_of_Real_Rooms": str(nrooms),
                    "Real_Room": rooms[0] if nrooms == 1 else rooms,
                }
            )
        name = f"v{len(self.__virtual_rooms) + 1:03}"
        self.__virtual_rooms[name] = {
            "Name": name,
            "Building": None,
            "Capacity": "30000",
            "Virtual": "true",
            "Number_of_Sets_of_Real_Rooms": str(len(roomlist)),
            "Set_of_Real_Rooms": roomlist,
            "Comments": hashable,
        }
        self.__virtual_room_map[hashable] = name
        return name

    def virtual_room_list(self):
        return list(self.__virtual_rooms.values())

    def next_activity_id(self):
        return len(self.activities) + 1

    def class_lunch_breaks(self, klass, possible_breaks, lb):
        """Add activities and constraints for lunch breaks.
        There needs to be a lunch-break activity for every sub-group of
        a class, to be on the safe side.
        Note that the number of periods offered should be at least two,
        because if only one period is possible it would probably be
        better to set the class as "not available" in that period.
        As the breaks are implemented here by means of a lunch-break
        activity, the weight isn't of much use.
        """
        try:
            lbp, lbw = lb.split('%')
            if lbw == '-':
                return
        except ValueError:
            REPORT("ERROR", T["INVALID_CLASS_LUNCHBREAK"].format(
                klass=klass, val=lb
            ))
            return
        pmap = get_periods()
        lbplist = []
        for p in lbp.split(','):
            try:
                i = pmap.index(p)
            except KeyError:
                REPORT("ERROR", T["INVALID_CLASS_LUNCHBREAK"].format(
                    klass=klass, val=lb
                ))
                return
            lbplist.append(p)
        # Get a list of groups (without class). To ensure that also
        # classes with no groups get lunch breaks, add a null string to
        # an empty list.
        atomic_groups = self.group2atoms[klass][""] or [""]
        # print(f"??? {klass}", atomic_groups)
        constraints = []
        for day, periods0 in possible_breaks.items():
            periods = [p for p in lbplist if p in periods0]
            if len(periods) != len(lbplist):
                continue    # free period at lunchtime – don't add constraint
            nperiods = str(len(periods))
            # Add lunch-break activity
            for g in atomic_groups:
                aid_s = str(self.next_activity_id())
                activity = {
                    # no teacher
                    "Subject": LUNCH_BREAK,
                    "Students": f"{klass}.{g}" if g else klass,
                    "Duration": "1",
                    "Total_Duration": "1",
                    "Id": aid_s,
                    "Activity_Group_Id": "0",
                    "Active": "true",
                    "Comments": None,
                }
                self.activities.append(activity)
                # Add constraint
                constraints.append(
                    {
                        "Weight_Percentage": "100",
                        "Activity_Id": aid_s,
                        "Number_of_Preferred_Starting_Times": nperiods,
                        "Preferred_Starting_Time": [
                            {
                                "Preferred_Starting_Day": day,
                                "Preferred_Starting_Hour": p,
                            }
                            for p in periods
                        ],
                        "Active": "true",
                        "Comments": None,
                    }
                )
        add_constraints(
            self.time_constraints,
            "ConstraintActivityPreferredStartingTimes",
            constraints,
        )

    def teacher_lunch_breaks(self, tid, possible_breaks, lb):
        """Add activities and constraints for lunch breaks.
        Note that the number of periods offered should be at least two,
        because if only one period is possible it would probably be
        better to set the teacher as "not available" in that period.
        """
        try:
            lbp, lbw = lb.split('%')
            if lbw == '-':
                return
        except ValueError:
            REPORT("ERROR", T["INVALID_TID_LUNCHBREAK"].format(
                tid=tid, val=lb
            ))
            return
        pmap = get_periods()
        lbplist = []
        for p in lbp.split(','):
            try:
                i = pmap.index(p)
            except KeyError:
                REPORT("ERROR", T["INVALID_TID_LUNCHBREAK"].format(
                    tid=tid, val=lb
                ))
                return
            lbplist.append(p)
        constraints = []
        for day, periods0 in possible_breaks.items():
            periods = [p for p in lbplist if p in periods0]
            if len(periods) != len(lbplist):
                continue    # free period at lunchtime – don't add constraint
            nperiods = str(len(periods))
            # Add lunch-break activity
            aid_s = str(self.next_activity_id())
            activity = {
                "Teacher": tid,
                "Subject": LUNCH_BREAK,
                # no students
                "Duration": "1",
                "Total_Duration": "1",
                "Id": aid_s,
                "Activity_Group_Id": "0",
                "Active": "true",
                "Comments": None,
            }
            self.activities.append(activity)
            # Add constraint
            constraints.append(
                {
                    "Weight_Percentage": "100",
                    "Activity_Id": aid_s,
                    "Number_of_Preferred_Starting_Times": nperiods,
                    "Preferred_Starting_Time": [
                        {
                            "Preferred_Starting_Day": day,
                            "Preferred_Starting_Hour": p,
                        }
                        for p in periods
                    ],
                    "Active": "true",
                    "Comments": None,
                }
            )
        add_constraints(
            self.time_constraints,
            "ConstraintActivityPreferredStartingTimes",
            constraints,
        )

    def subject_group_activity(
        self, sid: str, groups: list[str], activity_id: int
    ) -> None:
        """Add the activity/groups to the collection for the appropriate
        class and subject.
        """
        aids: list[int]
        ag2aids: dict[str, list[int]]
        sid2ag2aids: dict[str, dict[str, list[int]]]

        for group in groups:
            klass, g = class_group_split(group)
            try:
                sid2ag2aids = self.class2sid2ag2aids[klass]
            except KeyError:
                sid2ag2aids = {}
                self.class2sid2ag2aids[klass] = sid2ag2aids
            try:
                ag2aids = sid2ag2aids[sid]
            except KeyError:
                ag2aids = {}
                sid2ag2aids[sid] = ag2aids
            for ag in (self.group2atoms[klass][g] or [None]):
                kg = f"{klass}.{ag}" if ag else klass
                try:
                    ag2aids[kg].append(activity_id)
                except KeyError:
                    ag2aids[kg] = [activity_id]

    def constraint_day_separation(self):
        """Add constraints to ensure that multiple lessons in any subject
        are not placed on the same day.
        """
        constraints: list[dict] = []
        # Use <self.class2sid2ag2aids> to find activities.
        sid2ag2aids: dict[str, dict[str, list[int]]]
        ag2aids: dict[str, list[int]]
        aids: list[int]
        aidset_map: dict[int, set[frozenset[int]]] = {}
        for klass in sorted(self.class2sid2ag2aids):
            try:
                sid2ag2aids = self.class2sid2ag2aids[klass]
            except KeyError:
                continue
            for sid, ag2aids in sid2ag2aids.items():
                for aids in ag2aids.values():
                    # Skip sets with only one element
                    l = len(aids)
                    if l > 1:
                        aids_fs = frozenset(aids)
                        try:
                            aidset_map[l].add(aids_fs)
                        except KeyError:
                            aidset_map[l] = {aids_fs}
        ### Eliminate subsets
        lengths = sorted(aidset_map, reverse=True)
        newsets = aidset_map[lengths[0]]  # the largest sets
        for l in lengths[1:]:
            xsets = set()
            for aidset in aidset_map[l]:
                for s in newsets:
                    if aidset < s:
                        break
                else:
                    xsets.add(aidset)
            newsets.update(xsets)
        ### Sort the sets
        aids_list = sorted([sorted(s) for s in newsets])
        for aids in aids_list:
            for a in aids:
                if a not in self.locked_aids:
                    constraints.append(
                        {
                            "Weight_Percentage": "100",
                            "Consecutive_If_Same_Day": "true",
                            "Number_of_Activities": str(len(aids)),
                            "Activity_Id": aids,
                            "MinDays": "1",
                            "Active": "true",
                            "Comments": None,
                        }
                    )
                    break
        add_constraints(
            self.time_constraints,
            "ConstraintMinDaysBetweenActivities",
            constraints,
        )

    def pair_constraint(
        self, klass, pairs
    ) -> list[tuple[set[tuple[int, int]], str]]:
        """Handle a constraint on a pair of subjects.
        The activity ids are needed.
        The returned pairs share at least one "atomic" group.
        The subject pairs are supplied as parameter <pairs>, a list of
        (sid1, sid2, weight) tuples.
        The result is a list of pairs, (set of activity ids, fet-weighting).
        fet-weighting is a string in the range "0" to "100".
        """
        result: list[tuple[set[tuple[int, int]], str]] = []
        sid2ag2aids = self.class2sid2ag2aids[klass]
        for sid1, sid2, w in pairs:
            percent = WEIGHTMAP[w]
            assert percent, "'-' should have been filtered out previously"
            try:
                ag2aids1 = sid2ag2aids[sid1]
                ag2aids2 = sid2ag2aids[sid2]
            except KeyError:
                continue
            aidpairs = set()
            for ag in ag2aids1:
                if ag in ag2aids2:
                    for aidpair in product(ag2aids1[ag], ag2aids2[ag]):
                        if not (
                            aidpair[0] in self.locked_aids
                            and aidpair[1] in self.locked_aids
                        ):
                            aidpairs.add(aidpair)
            result.append((aidpairs, percent))
        return result

    def constraints_NOTAFTER(self, cv_list):
        """Two subjects should NOT be in the given order, if on
        the same day.
        """
        aidmap: dict[tuple[str, str], str] = {}
        kmap = {}
        for k, v in cv_list:
            try:
                p, w = v.split('%', 1)
                s1, s2 = p.split('-', 1)
                if w == '-':
                    continue
            except ValueError:
                REPORT("ERROR", T["BAD_SUBJECT_PAIR"].format(
                    klass=klass,
                    constraint=self.class_handlers["NOTAFTER"],
                    val=v
                ))
                continue
            val = (s1, s2, w)
            try:
                kmap[k].append(val)
            except KeyError:
                kmap[k] = [val]
            # print("§NOTAFTER", val)
        for klass, pairs in kmap.items():
            for aidpairs, percent in self.pair_constraint(klass, pairs):
                for aidpair in aidpairs:
                    ap = (aidpair[1], aidpair[0])
                    if ap in aidmap:
                        if int(percent) <= int(aidmap[ap]):
                            continue
                    aidmap[ap] = percent
        clist: list[dict] = []
        for aidpair in sorted(aidmap):
            percent = aidmap[aidpair]
            clist.append(
                {
                    "Weight_Percentage": percent,
                    "First_Activity_Id": aidpair[0],
                    "Second_Activity_Id": aidpair[1],
                    "Active": "true",
                    "Comments": None,
                }
            )
            # a1 = self.activities[int(aidpair[0]) - 1]["Subject"]
            # a2 = self.activities[int(aidpair[1]) - 1]["Subject"]
            # print(f" ++ ConstraintTwoActivitiesOrderedIfSameDay:"
            #    f" {a1}/{aidpair[0]} {a2}/{aidpair[1]}")
        return "ConstraintTwoActivitiesOrderedIfSameDay", clist

    def constraints_PAIRGAP(self, cv_list):
        """Two subjects should have at least one lesson in between."""
        aidmap: dict[tuple[str, str], str] = {}
        kmap = {}
        for k, v in cv_list:
            try:
                p, w = v.split('%', 1)
                s1, s2 = p.split('-', 1)
                if w == '-':
                    continue
            except ValueError:
                REPORT("ERROR", T["BAD_SUBJECT_PAIR"].format(
                    klass=klass,
                    constraint=self.class_handlers["PAIRGAP"],
                    val=v
                ))
                continue
            val = (s1, s2, w)
            try:
                kmap[k].append(val)
            except KeyError:
                kmap[k] = [val]
            # print("§PAIRGAP", val)
        for klass, pairs in kmap.items():
            for aidpairs, percent in self.pair_constraint(klass, pairs):
                for aidpair in aidpairs:
                    # Order the pair elements
                    if aidpair[0] > aidpair[1]:
                        aidpair = (aidpair[1], aidpair[0])
                    if aidpair in aidmap:
                        if int(percent) <= int(aidmap[aidpair]):
                            continue
                    aidmap[aidpair] = percent
        clist: list[dict] = []
        for aidpair in sorted(aidmap):
            percent = aidmap[aidpair]
            clist.append(
                {
                    "Weight_Percentage": percent,
                    "Number_of_Activities": "2",
                    "Activity_Id": [str(a) for a in aidpair],
                    "MinGaps": "1",
                    "Active": "true",
                    "Comments": None,
                }
            )
            # a1 = self.activities[int(aidpair[0]) - 1]["Subject"]
            # a2 = self.activities[int(aidpair[1]) - 1]["Subject"]
            # print(f" ++ ConstraintMinGapsBetweenActivities:"
            #     f" {a1}/{aidpair[0]} {a2}/{aidpair[1]}")
        return "ConstraintMinGapsBetweenActivities", clist

    def add_class_constraints(self):
        """Add time constraints according to the entries in the database
        table TT_CLASSES. The default values are in the TIMETABLE
        configuration: CLASS_CONSTRAINT_HANDLERS.
        """
        ### Fetch class constraint data
        self.class_handlers = {
            c: (d, t)   # The "handler" field is not needed here
            for c, h, d, t in self.TT_CONFIG["CLASS_CONSTRAINT_HANDLERS"]
        }
        tt_constraints = {
            cl: (a, c)
            for cl, a, c in db_read_fields(
                "TT_CLASSES",
                ("CLASS", "AVAILABLE", "CONSTRAINTS")
            )
        }
        ### Supported constraints
        tconstraints = {
            # AVAILABLE
            "ConstraintStudentsSetNotAvailableTimes": (blocked := []),
            # MINDAILY
            "ConstraintStudentsSetMinHoursDaily": (constraints_m := []),
            # MAXGAPSWEEKLY
            "ConstraintStudentsSetMaxGapsPerWeek": (constraints_gw := []),
        }
        xconstraints = {}   # collect SPECIAL_CONSTRAINTS
        unsupported = set()
        classes = get_classes()
        for klass, _ in classes.get_class_list():
            if klass in self.block_classes:
                continue
            try:
                available, cstr = tt_constraints[klass]
            except KeyError:
                continue
            constraints = {}
            for c, v in read_pairs(cstr):
                try:
                    d, t = self.class_handlers[c]
                except KeyError:
                    REPORT(
                        "ERROR",
                        T["UNKNOWN_CLASS_CONSTRAINT"].format(
                            klass=klass, c=c
                        )
                    )
                    continue
                if v == '*':
                    v = d
                # For classes some constraints can be multiple!
                if c in SPECIAL_CONSTRAINTS:
                    # These are handled separately
                    xv = (klass, v)
                    try:
                        xconstraints[c].append(xv)
                    except KeyError:
                        xconstraints[c] = [xv]
                elif c in constraints:
                    # All other constraints may only occur once
                    REPORT("ERROR", T["MULTIPLE_CLASS_CONSTRAINT"].format(
                        klass=klass, name=t
                    ))
                else:
                    constraints[c] = v
            # Handle availability
            blocked_periods, possible_breaks = timeoff_fet(available)
            if blocked_periods:
                blocked.append(
                    {
                        "Weight_Percentage": "100",
                        "Students": klass,
                        "Number_of_Not_Available_Times": str(
                            len(blocked_periods)
                        ),
                        "Not_Available_Time": blocked_periods,
                        "Active": "true",
                        "Comments": None,
                    }
                )
            # Lunch breaks
            try:
                lb = constraints.pop("LUNCHBREAK")
            except KeyError:
                pass
            else:
                self.class_lunch_breaks(klass, possible_breaks, lb)
            # Other constraints ...
            try:
                minl = self.nperiods_constraint(
                    constraints, "MINDAILY"
                )
            except ValueError as e:
                REPORT(
                    "ERROR",
                    T["CLASS_CONSTRAINT"].format(
                        klass=klass,
                        constraint=self.class_handlers["MINDAILY"][-1],
                        e=e
                    ),
                )
            else:
                if minl:
                    # print("$$$$$ MINDAILY", klass, minl)
                    constraints_m.append(
                        {
                            "Weight_Percentage": "100",  # necessary!
                            "Minimum_Hours_Daily": minl[0],
                            "Students": klass,
                            "Allow_Empty_Days": "false",
                            "Active": "true",
                            "Comments": None,
                        }
                    )
            try:
                gw = self.nperiods_constraint(
                    constraints, "MAXGAPSWEEKLY"
                )
            except ValueError as e:
                REPORT(
                    "ERROR",
                    T["CLASS_CONSTRAINT"].format(
                        klass=klass,
                        constraint=self.class_handlers["MAXGAPSWEEKLY"][-1],
                        e=e
                    ),
                )
            else:
                if gw:
                    # print("$$$$$ MAXGAPSWEEKLY", klass, gw)
                    constraints_gw.append(
                        {
                            "Weight_Percentage": "100",  # necessary!
                            "Max_Gaps": gw[0],
                            "Students": klass,
                            "Active": "true",
                            "Comments": None,
                        }
                    )
        uc = [self.class_handlers[c][-1] for c in unsupported]
        if uc:
            REPORT(
                "WARNING",
                T["UNSUPPORTED_CLASS_CONSTRAINTS"].format(l="\n".join(uc))
            )
        for c, clist in tconstraints.items():
            add_constraints(self.time_constraints, c, clist)
        for c, xlist in xconstraints.items():
            try:
                func = getattr(self, f"constraints_{c}")
            except AttributeError:
                raise Bug(f"Unknown class constraint: {c}")
            cname, clist = func(xlist)
            add_constraints(self.time_constraints, cname, clist)

    def add_teacher_constraints(self, used):
        """Add time constraints according to the entries in the database
        table TT_TEACHERS. The default values are in the TIMETABLE
        configuration: TEACHER_CONSTRAINT_HANDLERS.
        """
        ### Fetch teacher constraint data
        self.teacher_handlers = {
            c: (d, t)   # The "handler" field is not needed here
            for c, h, d, t in self.TT_CONFIG["TEACHER_CONSTRAINT_HANDLERS"]
        }
        tt_constraints = {
            t: (a, c)
            for t, a, c in db_read_fields(
                "TT_TEACHERS",
                ("TID", "AVAILABLE", "CONSTRAINTS")
            )
        }
        ### Supported constraints
        tconstraints = {
            # AVAILABLE
            "ConstraintTeacherNotAvailableTimes": (blocked := []),
            # MINDAILY
            "ConstraintTeacherMinHoursDaily": (constraints_m := []),
            # MAXGAPSDAILY
            "ConstraintTeacherMaxGapsPerDay": (constraints_gd := []),
            # MAXGAPSWEEKLY
            "ConstraintTeacherMaxGapsPerWeek": (constraints_gw := []),
            # MAXBLOCK
            "ConstraintTeacherMaxHoursContinuously": (constraints_u := []),
        }
        unsupported = set()
        ### Not-available times
        teachers = get_teachers()
        for tid in teachers:
            if tid not in used:
                continue
            try:
                available, cstr = tt_constraints[tid]
            except KeyError:
                continue
            constraints = {}
            for c, v in read_pairs(cstr):
                try:
                    d, t = self.teacher_handlers[c]
                except KeyError:
                    REPORT(
                        "ERROR",
                        T["UNKNOWN_TID_CONSTRAINT"].format(tid=tid, c=c)
                    )
                    continue
                if c in constraints:
                    # All constraints may only occur once
                    REPORT("ERROR", T["MULTIPLE_TID_CONSTRAINT"].format(
                        tid=tid, name=t
                    ))
                    continue
                constraints[c] = d if v == '*' else v
            # Handle availability
            blocked_periods, possible_breaks = timeoff_fet(available)
            if blocked_periods:
                blocked.append(
                    {
                        "Weight_Percentage": "100",
                        "Teacher": tid,
                        "Number_of_Not_Available_Times": str(
                            len(blocked_periods)
                        ),
                        "Not_Available_Time": blocked_periods,
                        "Active": "true",
                        "Comments": None,
                    }
                )
            # Lunch breaks
            try:
                lb = constraints.pop("LUNCHBREAK")
            except KeyError:
                pass
            else:
                self.teacher_lunch_breaks(tid, possible_breaks, lb)
            # Other constraints ...
            try:
                minl = self.nperiods_constraint(
                    constraints, "MINDAILY"
                )
            except ValueError as e:
                REPORT(
                    "ERROR",
                    T["TEACHER_CONSTRAINT"].format(
                        tid=tid,
                        constraint=self.teacher_handlers["MINDAILY"][-1],
                        e=e
                    ),
                )
            else:
                if minl:
                    # print("$$$$$ MINDAILY", tid, minl)
                    constraints_m.append(
                        {
                            "Weight_Percentage": "100",  # necessary!
                            "Teacher_Name": tid,
                            "Minimum_Hours_Daily": minl[0],
                            "Allow_Empty_Days": "true",
                            "Active": "true",
                            "Comments": None,
                        }
                    )
            try:
                gd = self.nperiods_constraint(
                    constraints, "MAXGAPSDAILY"
                )
            except ValueError as e:
                REPORT(
                    "ERROR",
                    T["TEACHER_CONSTRAINT"].format(
                        tid=tid,
                        constraint=self.teacher_handlers["MAXGAPSDAILY"][-1],
                        e=e
                    ),
                )
            else:
                if gd:
                    # print("$$$$$ MAXGAPSDAILY", tid, gd)
                    constraints_gd.append(
                        {
                            "Weight_Percentage": "100",  # necessary!
                            "Teacher_Name": tid,
                            "Max_Gaps": gd[0],
                            "Active": "true",
                            "Comments": None,
                        }
                    )
            try:
                gw = self.nperiods_constraint(
                    constraints, "MAXGAPSWEEKLY"
                )
            except ValueError as e:
                REPORT(
                    "ERROR",
                    T["TEACHER_CONSTRAINT"].format(
                        tid=tid,
                        constraint=self.teacher_handlers["MAXGAPSWEEKLY"][-1],
                        e=e
                    ),
                )
            else:
                if gw:
                    # print("$$$$$ MAXGAPSWEEKLY", tid, gw)
                    constraints_gw.append(
                        {
                            "Weight_Percentage": "100",  # necessary!
                            "Teacher_Name": tid,
                            "Max_Gaps": gw[0],
                            "Active": "true",
                            "Comments": None,
                        }
                    )
            try:
                u = self.nperiods_constraint(
                    constraints, "MAXBLOCK"
                )
            except ValueError as e:
                REPORT(
                    "ERROR",
                    T["TEACHER_CONSTRAINT"].format(
                        tid=tid,
                        constraint=self.teacher_handlers["MAXBLOCK"][-1],
                        e=e
                    ),
                )
            else:
                if u:
                    n, w = u
                    # print("$$$$$ MAXBLOCK", tid, u, WEIGHTMAP[w])
                    if w:
                        constraints_u.append(
                            {
                                "Weight_Percentage": WEIGHTMAP[w],
                                "Teacher_Name": tid,
                                "Maximum_Hours_Continuously": n,
                                "Active": "true",
                                "Comments": None,
                            }
                        )
            unsupported.update(constraints)
        uc = [self.teacher_handlers[c][-1] for c in unsupported]
        if uc:
            REPORT(
                "WARNING",
                T["UNSUPPORTED_TEACHER_CONSTRAINTS"].format(l="\n".join(uc))
            )
        for c, clist in tconstraints.items():
            add_constraints(self.time_constraints, c, clist)

    def nperiods_constraint(
        self, cmap: dict[str, str], constraint: str
    ) -> Optional[tuple[str, str]]:
        try:
            val = cmap.pop(constraint)
        except KeyError:
            return None
        try:
            v, w = val.split('%', 1)
            number = int(v)
            if number >= 0 and number <= NPERIODSMAX and w in WEIGHTMAP:
                return v, w
        except ValueError:
            pass
        raise ValueError(T["INVALID_CONSTRAINT_VALUE"].format(val=val))

    def add_parallels(self):
        """Add constraints for lessons starting at same time.
        """
        parallels = []
        ptags = {}
        for lid, tag, w in db_read_fields(
            "PARALLEL_LESSONS",
            ("lesson_id", "TAG", "WEIGHTING")
        ):
            lid_w = (lid, w)
            try:
                ptags[tag].append(lid_w)
            except KeyError:
                ptags[tag] = [lid_w]
        for tag in sorted(ptags):
            awlist = ptags[tag]
            # print("§PARALLEL:", tag, awlist)
            if (l := len(awlist)) > 1:
                aidlist = []
                # fet doesn't support different weights on the individual
                # linked items. Use the lowest weight here.
                wx = '+'
                for lid, w in awlist:
                    if w == '-':
                        # Suppress constraint
                        aidlist.clear()
                        break
                    aidlist.append(self.lid_aid[lid])
                    if w != '+' and (wx == '+' or w < wx):
                        wx = w
                if aidlist:
                    # print("§PARALLEL +:", wx, aidlist)
                    parallels.append(
                        {
                            "Weight_Percentage": WEIGHTMAP[wx],
                            "Number_of_Activities": str(l),
                            "Activity_Id": aidlist,
                            "Active": "true",
                            "Comments": f"// {tag}",
                        }
                    )
            else:
                REPORT("WARNING", T["PARALLEL_SINGLE"].format(tag=tag))
        add_constraints(
            self.time_constraints,
            "ConstraintActivitiesSameStartingTime",
            parallels,
        )
#TODO: It could be necessary to suppress some min-gap constraints ...
# It would be possible to implement 100% weighting as a block (somehow ...)
# but direct usage of the fet constraint is easier to implemented here,
# so I've left it at that for the time being.

    def add_further_constraints(self):
        """Add any further constraints to deal with particular local
        needs ... .
        """
        #TODO: This is rather random at present!
        double_lesson_start_periods = self.TT_CONFIG.get("DOUBLE_LESSON_START")
        try:
            w = self.TT_CONFIG["DOUBLE_LESSON_START_WEIGHT"]
            weight = WEIGHTMAP[w]
        except KeyError:
            weight = "100"
        # print("\n§§§§§§§§§", weight, double_lesson_start_periods)
        if weight and double_lesson_start_periods:
            plist = []
            for d in get_days().key_list():
                for p in double_lesson_start_periods:
                    plist.append(
                        {
                            "Preferred_Starting_Day": d,
                            "Preferred_Starting_Hour": p,
                        }
                    )
            add_constraint(
                self.time_constraints,
                "ConstraintActivitiesPreferredStartingTimes",
                {
                    "Weight_Percentage": weight,
                    "Teacher_Name": None,
                    "Students_Name": None,
                    "Subject_Name": None,
                    "Activity_Tag_Name": None,
                    "Duration": "2",
                    "Number_of_Preferred_Starting_Times": str(len(plist)),
                    "Preferred_Starting_Time": plist,
                    "Active": "true",
                    "Comments": None,
                },
            )


def add_constraint(constraints, ctype, constraint):
    """Add a constraint of type <ctype> to the master constraint
    list-mapping <constraints> (either time or space constraints).
    """
    try:
        constraints[ctype].append(constraint)
    except KeyError:
        constraints[ctype] = [constraint]


def add_constraints(constraints, ctype, constraint_list):
    """Add a (possibly empty) list of constraints, of type <ctype>, to
    the master constraint list-mapping <constraints> (either time or
    space constraints).
    """
    if constraint_list:
        try:
            constraints[ctype] += constraint_list
        except KeyError:
            constraints[ctype] = constraint_list


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    #dbfile = "wzx.sqlite"
    dbfile = "wz_db.sqlite"
    print("\n DATABASE:", dbfile)
    open_database(dbfile)

    fet_days = get_days_fet()
    if _TEST:
        print("\n*** DAYS ***")
        for _day in get_days():
            print("   ", _day)
        print("\n    ... for fet ...\n   ", fet_days)
        print("\n  ==================================================")

    fet_periods = get_periods_fet()
    if _TEST:
        print("\n*** PERIODS ***")
        for _period in get_periods():
            print("   ", _period)
        print("\n    ... for fet ...\n   ", fet_periods)
        print("\n  ==================================================")

    fet_classes = get_classes_fet()
    if _TEST:
        print("\nCLASSES:")
        for klass, year_entry in fet_classes:
            glist = year_entry.get("Group") or []
            print()
            for k, v in year_entry.items():
                if k != "Group":
                    print(f" ... {k}: {v}")
            if glist:
                print(" ... Group:")
                for g in glist:
                    print("  ---", g["Name"])
                    for sg in g.get("Subgroup") or []:
                        print("     +", sg["Name"])
            print("Group -> Atoms:", fet_classes.g2a[klass])
#TODO: Changed, values are single groups, not lists (was <a2glist>)
            print("Atoms -> Group:", fet_classes.a2g[klass])

    # quit(0)

    courses = TimetableCourses(fet_classes)
    if _TEST:
        print("\n ********** READ LESSON DATA **********\n")
    #courses.read_lessons(["08K"])
    courses.read_lessons()

    # quit(0)

    fet_subjects = get_subjects_fet(courses.timetable_subjects)
    if _SUBJECTS_AND_TEACHERS:
        print("\n *** SUBJECTS ***")
        for item in fet_subjects:
            print(f"{item['Name']:7}: {item['Comments']}")

    fet_teachers = get_teachers_fet(courses.timetable_teachers)
    if _SUBJECTS_AND_TEACHERS:
        print("\n *** TEACHERS ***")
        for item in fet_teachers:
            print(f"{item['Name']:7}: {item['Comments']}")

    fet_rooms = get_rooms_fet(courses.virtual_room_list())
    if _TEST:
        print("\nROOMS:")
        for rdata in fet_rooms:
            print("   ", rdata)

    # Teacher-specific constraints
    print("\nTeacher constraints ...")
    courses.add_teacher_constraints(courses.timetable_teachers)

    # Class-specific constraints
    print("\nClass constraints ...")
    courses.add_class_constraints()

    # quit(0)

    if _TEST1:
        print("\nSubject – activity mapping")
        for klass in sorted(courses.class2sid2ag2aids):
            data = courses.class2sid2ag2aids[klass]
            print(f"\n **** Class {klass}")
            for sid, ag2aids in data.items():
                print(f" ... {sid}: {ag2aids}")
                for ag, aids in ag2aids.items():
                    print(f"     {sid:8}: {ag:10} --> {aids}")

    # quit(0)

    # print("\n§§§ locked_aids:", sorted(courses.locked_aids))

    print("\nSubject day-separation constraints ...")
    courses.constraint_day_separation()

    print("\nParallel activity constraints")
    courses.add_parallels()

    print("\nFurther constraints ...")
    courses.add_further_constraints()

    if _TEST1:
        # Activity info is available thus:
        for _aid in (550,):
            print(f"\n???? {_aid}:", courses.activities[_aid - 1])

    # quit(0)

    outdir = DATAPATH("TIMETABLE/out")
    os.makedirs(outdir, exist_ok=True)
    if True:

        xml_fet = xmltodict.unparse(courses.gen_fetdata(), pretty=True)

        outpath = os.path.join(outdir, "tt_out_3a.fet")
        with open(outpath, "w", encoding="utf-8") as fh:
            fh.write(xml_fet.replace("\t", "   "))
        print("\nTIMETABLE XML ->", outpath)

        # Write unspecified room allocation info
        outpath = os.path.join(outdir, "tt_out_extra_rooms")
        with open(outpath, "w", encoding="utf-8") as fh:
            for fr in courses.fancy_rooms:
                __id = f"{fr[0]:15}   {fr[1]}"
                __rlist = ' / '.join([','.join(rl) for rl in fr[2]])
                fh.write(f"{__id:36}: [{len(fr[2])}] {__rlist}\n")
        print("\nADDITIONAL ROOM DATA ->", outpath)
        print("\nDATA from (database file):", db_name())

    quit(0)

    # ??? tag-lids are gone, and multirooms are now available as virtual rooms
    import json

    outpath = os.path.join(outdir, "tag-lids.json")
    # Save association of lesson "tags" with "lids" and "xlids"
    lid_data = {
        "tag-lids": _classes.tag_lids,
        "lid-xlids": {lids[0]: lids[1:] for lids in _classes.xlids},
    }
    with open(outpath, "w", encoding="utf-8") as fh:
        json.dump(lid_data, fh, indent=4)
    print("\nTag – Lesson associations ->", outpath)

    outpath = os.path.join(outdir, "multiple-rooms")
    with open(outpath, "w", encoding="utf-8") as fh:
        for mr in _classes.multirooms:
            groups = ", ".join(mr["GROUPS"])
            sname = _classes.SUBJECTS[mr["SID"]]
            fh.write(
                f"\nKlasse {mr['CLASS']} ({groups})"
                f" :: {sname}: {mr['NUMBER']}"
            )

    print("\nSubjects with multiple rooms ->", outpath)
