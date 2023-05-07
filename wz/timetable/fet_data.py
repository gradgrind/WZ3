"""
timetable/fet_data.py - last updated 2023-05-07

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

#TODO: freshly copied over from WZ

_TEST = False
#_TEST = True
_TEST1 = False
#_TEST1 = True
_SUBJECTS_AND_TEACHERS = False
_SUBJECTS_AND_TEACHERS = True

FET_VERSION = "6.9.0"

WEIGHTS = [None, "50", "67", "80", "88", "93", "95", "97", "98", "99", "100"]

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

from typing import Optional

T = TRANSLATIONS("timetable.fet_data")

### +++++

from itertools import product

import xmltodict

from core.base import class_group_split
from core.basic_data import (
    get_days,
    get_periods,
    get_classes,
    get_teachers,
    get_subjects,
    get_rooms,
    sublessons,
    get_simultaneous_weighting,
    timeslot2index,
)
from core.db_access import (
    db_backup,
    db_update_fields,
    db_read_unique,
    NoRecord,
)
from core.classes import ClassGroups
from core.list_activities import read_db
from timetable.activities import Courses


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
    sid, name = T["LUNCH_BREAK"].split(":", 1)
    slist.append({"Name": sid, "Comments": name})
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
        # The groups are all the "elemental" groups plus any dotted groups
        # which are used, excluding any "atomic" groups already defined
        # as subgroups.
        year_entry = {
            "Name": klass,
            "Number_of_Students": "0",
            "Comments": kname,
            "Number_of_Categories": "1" if divs else "0",
            "Separator": ".",
        }
        if divs:
            _groups = []
            _agset = set()
            for g in sorted(g2a):
                if not g:
                    continue
                sgs = g2a[g]
                if g in sgs:
                    # This group is an atomic group
                    if g not in _agset:
                        _agset.add(g)
                        _groups.append(
                            {
                                "Name": f"{klass}.{g}",
                                "Number_of_Students": "0",
                                "Comments": None,
                            }
                        )
                else:
                    _agset.update(sgs)
                    _subgroups = [
                        {
                            "Name": f"{klass}.{sg}",
                            "Number_of_Students": "0",
                            "Comments": None,
                        }
                        for sg in sorted(sgs)
                    ]
                    _groups.append(
                        {
                            "Name": f"{klass}.{g}",
                            "Number_of_Students": "0",
                            "Comments": None,
                            "Subgroup": _subgroups,
                        }
                    )
            year_entry["Category"] = {
                "Number_of_Divisions": f"{len(atoms)}",
                "Division": atoms,
            }
            year_entry["Group"] = _groups

#TODO: Have I got an atoms -> group LIST mappping? Do I still need one?
        fet_classes.append(klass, year_entry, g2a, a2g)
    return fet_classes


def timeoff_fet(available: str) -> list[dict[str, str]]:
    """Build "not available" entries for the given data.
    The period values are from '-' through 1 to 9 and '+'.
    fet, however, only deals with "blocked" "available" values.
    Also collect possible (lunch) break times, sorted by day.
    Return: (
        [{"Day": day, "Hour": period}, ... ]
        {day -> [period, ... ]}
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
                    possible_breaks[d].append(p)
                except KeyError:
                    possible_breaks[d] = [p]
    return blocked_periods, possible_breaks


class TimetableCourses(Courses):
    __slots__ = (
        "TT_CONFIG",
        "timetable_teachers",
        "timetable_subjects",
        "timetable_classes",
        "parallel_tags",
        "locked_aids",
#?
        "fet_classes",
        "group2atoms",
        "activities",
        "__virtual_room_map",
        "__virtual_rooms",
        "time_constraints",
        "space_constraints",
        "class2sid2ag2aids",
        "fancy_rooms",
    )

    def __init__(self, fet_classes):
        self.fet_classes = fet_classes
        self.group2atoms = fet_classes.g2a
        super().__init__(self.group2atoms)
        self.TT_CONFIG = MINION(DATAPATH("CONFIG/TIMETABLE"))

    def read_lessons(self):
        """Produce a list of fet-activity (lesson) items with a
        reference to the id of the source line in the LESSONS table.
        Any blocks with no sublessons are ignored.
        Constraints for time and rooms are added as appropriate.
        """
        # Collect teachers and subjects with timetable entries:
        self.timetable_teachers = set()
        self.timetable_subjects = set()
        # Collect locked placements:
        self.locked_aids: dict[str, Optional[tuple[str,str]]] = {}
#? I think this can be done separately now ...
        # Collect activities with "parallel" tags, {tag: [activity-id, ... ]}
        self.parallel_tags: dict[str, list[str]] = {}
        # Collect more complex room allocations
        self.fancy_rooms = []

        self.time_constraints = {}
        self.space_constraints = {}
        self.activities: list[dict] = []  # fet activities
        # Used for managing "virtual" rooms:
        self.__virtual_room_map: dict[str, str] = {}  # rooms hash -> room id
        self.__virtual_rooms: dict[str, dict] = {}  # room id -> fet room
        # For constraints concerning relative placement of individual
        # lessons in the various subjects, collect the "atomic" pupil
        # groups and their activity ids for each subject, divided by class:
        self.class2sid2ag2aids: dict[str, dict[str, dict[str, list[int]]]] = {}

#        atoms2grouplist = {}
        self.timetable_classes = []
#        for klass, year_entry, g2atoms, a2glist in fet_classes:
        for klass, year_entry in self.fet_classes:
            self.timetable_classes.append(year_entry)
#            self.group2atoms[klass] = g2atoms
#            atoms2grouplist[klass] = a2glist
#? was <atoms2grouplist> (the value was a list, now a single group)
        atoms2group = self.fet_classes.a2g

#NEW:
        # Get activities from database
        cl_lists, t_lists, lg_2_c = read_db()

        '''
        class ActivityItem(NamedTuple):
            course_data: tuple[str, str, str, str] # class, group, subject, teacher
            workload: int
            lesson_group: int
            blocktag: Optional[BlockTag]
            lessons: list[int]
            paytag: Optional[Workload]
            room: str
        '''

        # <cl_lists> is a mapping { class -> [activity, ... ] }
        for klass in sorted(cl_lists):
            ailist = cl_lists[klass]



        return

#???
        # tag2entries: {block-tag -> [BlockInfo, ... ]}
        for tag, blocklist in self.tag2entries.items():
            lessons = sublessons(tag)
            if not lessons:
                continue
            class_set = set()
            group_sets = {}  # {klass -> set of atomic groups}
            teacher_set = set()
            roomlists = []  # list of unique room lists
            for blockinfo in blocklist:
                course = blockinfo.course
                klass = course.klass
                class_set.add(klass)
                g = course.group
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
                if course.tid != "--":
                    teacher_set.add(course.tid)
                # Add rooms, retaining order
                rl = blockinfo.rooms
                if rl and rl not in roomlists:
                    roomlists.append(rl)
            # Get "usable" groups
            groups = []
            for klass, aset in group_sets.items():
                a2glist = atoms2grouplist[klass]
                try:
                    key = tuple(sorted(aset))
                    for g in a2glist[key]:
                        groups.append(f"{klass}.{g}" if g else klass)
                        # print("$$$", klass, g, key, a2glist)
                except KeyError:
                    REPORT(
                        "ERROR",
                        T["INVALID_GROUP_LIST"].format(
                            tag=tag, groups=",".join(key)
                        ),
                    )
            # Get the subject-id from the block-tag, if it has a
            # subject, otherwise from the course (of which there
            # should be only one!)
            sid = blockinfo.block.sid or course.sid
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
            if len(roomlists) > 1:
                self.fancy_rooms.append((classes_str, tag, roomlists))
                for rl in roomlists:
                    if rl[-1] != '+':
                        if len(rl) == 1:
                            singles.append(rl[0])
                        else:
                            roomlists0.append(rl)
            elif len(roomlists) == 1:
                rl = roomlists[0]
                if rl[-1] == '+':
                    self.fancy_rooms.append((classes_str, tag, roomlists))
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

            # Add to "used" teachers and subjects
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
            # Divide lessons up according to duration
            durations = {}
            total_duration = 0
            for sl in lessons:
                l = sl.LENGTH
                total_duration += l
                try:
                    durations[l].append(sl)
                except KeyError:
                    durations[l] = [sl]
            activity0["Total_Duration"] = str(total_duration)
            id0 = self.next_activity_id()
            activity0["Activity_Group_Id"] = str(id0 if len(lessons) > 1 else 0)
            for l in sorted(durations):
                dstr = str(l)
                for sl in durations[l]:
                    id_str = str(id0)
                    activity = activity0.copy()
                    activity["Id"] = id_str
                    activity["Duration"] = dstr
                    activity["Comments"] = str(sl.id)
                    self.add_placement(id_str, sl, rooms)
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

    def add_placement(self, id_str, sublesson, rooms):
        t = sublesson.TIME
        if t:
            try:
                d, p = t.split(".", 1)
            except ValueError:
                # "Parallel" tag
                try:
                    self.parallel_tags[t].append(id_str)
                except KeyError:
                    self.parallel_tags[t] = [id_str]
            else:
                # Fixed starting time
                try:
                    timeslot2index(t)   # This is just a check
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

#TODO --
#            if room != "rSp":
#                return

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

    def constraint_classes_timeoff(self):
        """Constraint: students set not available ...
        Also handle possible (lunch) break periods.
        """
        constraints = []
        classes = get_classes()
        for klass, _ in classes.get_class_list():
            try:
                available, lunchbreak_weight = db_read_unique(
                    "TT_CLASSES",
                    ["AVAILABLE", "LUNCHBREAK"],
                    CLASS=klass
                )
            except NoRecord:
                return
            blocked_periods, possible_breaks = timeoff_fet(available)
            if blocked_periods:
                constraints.append(
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
            if possible_breaks:
                self.class_lunch_breaks(
                    klass,
                    possible_breaks,
                    lunchbreak_weight
                )
        add_constraints(
            self.time_constraints,
            "ConstraintStudentsSetNotAvailableTimes",
            constraints,
        )

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

    def class_lunch_breaks(self, klass, possible_breaks, weight):
        """Add activities and constraints for lunch breaks.
        There needs to be a lunch-break activity for every sub-group of
        a class, to be on the safe side.
        Note that the number of periods offered should be at least two,
        because if only one period is possible it would probably be
        better to set the class as "not available" in that period.
        As the breaks are implemented here by means of a lunch-break
        activity, the weight isn't of much use.
        """
        if (not weight) or (weight == '-'):
            return
        lb_sid = T["LUNCH_BREAK"].split(":", 1)[0]
        constraints = []
        # Get a list of groups (without class). To ensure that also
        # classes with no groups get lunch breaks, add a null string to
        # an empty list.
        atomic_groups = self.group2atoms[klass][""] or [""]
        # print(f"??? {klass}", atomic_groups)
        for day, periods in possible_breaks.items():
# Maybe rather get possible times from config, then compare with
# available slots ... 
            print("??????", day, periods)
            

            nperiods = str(len(periods))
            # Add lunch-break activity
            for g in atomic_groups:
                aid_s = str(self.next_activity_id())
                activity = {
                    # no teacher
                    "Subject": lb_sid,
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

    def teacher_lunch_breaks(self, tid, possible_breaks):
        """Add activities and constraints for lunch breaks.
        Note that the number of periods offered should be at least two,
        because if only one period is possible it would probably be
        better to set the teacher as "not available" in that period.
        """
        lb_sid = T["LUNCH_BREAK"].split(":", 1)[0]
        constraints = []
        for day, periods in possible_breaks.items():
            nperiods = str(len(periods))
            # Add lunch-break activity
            aid_s = str(self.next_activity_id())
            activity = {
                "Teacher": tid,
                "Subject": lb_sid,
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

    ############### FURTHER CONSTRAINTS ###############

    def constraints_MINDAILY(self, default):
        clist: list[dict] = []
        classes = get_classes()
        for klass, _ in classes.get_class_list():
            data = classes[klass]
            try:
                n = data.tt_data["MINDAILY"]
            except KeyError:
                # If the constraint is not present, don't add it for
                # this class
                continue
            if n:
                if n == "*":
                    n = default
                val = self.class_periods_constraint(n, klass, "MAXGAPSWEEKLY")
                if val and val[1] != 0:
                    clist.append(
                        {
                            "Weight_Percentage": "100",  # necessary!
                            "Minimum_Hours_Daily": str(val[0]),
                            "Students": klass,
                            "Allow_Empty_Days": "false",
                            "Active": "true",
                            "Comments": None,
                        }
                    )
                    # print(f"++ ConstraintStudentsSetMinHoursDaily {klass}: {n}")
        return "ConstraintStudentsSetMinHoursDaily", clist

    # Version for all classes:
    #    time_constraints['ConstraintStudentsMinHoursDaily'] = [
    #        {   'Weight_Percentage': '100',
    #            'Minimum_Hours_Daily': str(min_lessons),
    #            'Allow_Empty_Days': 'false',
    #            'Active': 'true',
    #            'Comments': None
    #        }
    #    ]

    def constraints_MAXGAPSWEEKLY(self, default):
        """Maximum gaps per week for the specified classes.
        If the constraint is not specified for a class, that class will
        not have the constraint.
        """
        clist: list[dict] = []
        classes = get_classes()
        for klass, _ in classes.get_class_list():
            data = classes[klass]
            try:
                n = data.tt_data["MAXGAPSWEEKLY"]
            except KeyError:
                # If the constraint is not present, don't add it for
                # this class
                continue
            if n:
                if n == "*":
                    n = default
                val = self.class_periods_constraint(n, klass, "MAXGAPSWEEKLY")
                if val and val[1] != 0:
                    clist.append(
                        {
                            "Weight_Percentage": "100",  # necessary!
                            "Max_Gaps": str(val[0]),
                            "Students": klass,
                            "Active": "true",
                            "Comments": None,
                        }
                    )
                    # print(f"++ ConstraintStudentsSetMaxGapsPerWeek {klass}: {n}")
        return "ConstraintStudentsSetMaxGapsPerWeek", clist

    def pair_constraint(
        self, klass, pairs, t_constraint
    ) -> list[tuple[set[tuple[int, int]], str]]:
        """Find pairs of activity ids of activities which link two
        subjects (subject tags) for a constraint.
        The returned pairs share at least one "atomic" group.
        The subject pairs are supplied as parameter <pairs>. There can
        be multiple pairs (space separated) and each pair can have a
        weighting (0-10) after a "@" separator, e.g. "En+Fr@8 Eu+Sp".
        The result is a list of pairs, (set of activity ids, fet-weighting).
        fet-weighting is a string in the range "0" to "100".
        """
        result: list[tuple[set[tuple[int, int]], str]] = []
        sid2ag2aids = self.class2sid2ag2aids[klass]
        for wpair in pairs.split():
            try:
                pair, w_ = wpair.split("@", 1)
            except ValueError:
                pair, w = wpair, -1
            else:
                try:
                    w = int(w_)
                except ValueError:
                    w = -1
                if w < 0 or w > 10:
                    REPORT(
                        "ERROR",
                        T["INVALID_CLASS_CONSTRAINT"].format(
                            klass=klass, constraint=t_constraint, val=wpair
                        ),
                    )
                    return []
            percent = WEIGHTS[w]
            if not percent:
                continue
            try:
                sid1, sid2 = pair.split("+")
            except ValueError:
                REPORT(
                    "ERROR",
                    T["INVALID_CLASS_CONSTRAINT"].format(
                        klass=klass, constraint=t_constraint, val=wpair
                    ),
                )
                return []
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

    def constraints_NOTAFTER(self, default):
        """Two subjects should NOT be in the given order, if on the same day."""
        aidmap: dict[tuple[str, str], str] = {}
        classes = get_classes()
        for klass, _ in classes.get_class_list():
            data = classes[klass]
            try:
                pairs = data.tt_data["NOTAFTER"]
            except KeyError:
                # If the constraint is not present, don't add it for
                # this class
                continue
            for aidpairs, percent in self.pair_constraint(
                klass, pairs, "NOTAFTER"
            ):
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
                    "First_Activity_Id": str(aidpair[0]),
                    "Second_Activity_Id": str(aidpair[1]),
                    "Active": "true",
                    "Comments": None,
                }
            )
            # a1 = self.activities[aidpair[0] - 1]["Subject"]
            # a2 = self.activities[aidpair[1] - 1]["Subject"]
            # print(f" ++ ConstraintTwoActivitiesOrderedIfSameDay:"
            #    f" {a1}/{aidpair[0]} {a2}/{aidpair[1]}")
        return "ConstraintTwoActivitiesOrderedIfSameDay", clist

    def constraints_PAIRGAP(self, default):
        """Two subjects should have at least one lesson in between."""
        aidmap: dict[tuple[str, str], str] = {}
        classes = get_classes()
        for klass, _ in classes.get_class_list():
            data = classes[klass]
            try:
                pairs = data.tt_data["PAIRGAP"]
            except KeyError:
                # If the constraint is not present, don't add it for
                # this class
                continue
            for aidpairs, percent in self.pair_constraint(
                klass, pairs, "PAIRGAP"
            ):
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
            # a1 = self.activities[aidpair[0] - 1]["Subject"]
            # a2 = self.activities[aidpair[1] - 1]["Subject"]
            # print(f" ++ ConstraintMinGapsBetweenActivities:"
            #    f" {a1}/{aidpair[0]} {a2}/{aidpair[1]}")
        return "ConstraintMinGapsBetweenActivities", clist

    def add_class_constraints(self):
        """Add time constraints according to the "info" entries in the
        timetable data files for each class.
        """
        # Get names and default values of constraints, call handlers
        for name, val in self.TT_CONFIG["CLASS_CONSTRAINTS"].items():
            try:
                func = getattr(self, f"constraints_{name}")
            except AttributeError:
                raise Bug(f"Unknown class constraint: {name}")
            cname, clist = func(val)
            add_constraints(self.time_constraints, cname, clist)

    def add_teacher_constraints(self, used):
        blocked = []  # AVAILABLE
        constraints_m = []  # MINPERDAY
        constraints_gd = []  # MAXGAPSPERDAY
        constraints_gw = []  # MAXGAPSPERWEEK
        constraints_u = []  # MAXBLOCK
        ### Not-available times
        for tid, data in get_teachers().items():
            if tid not in used:
                continue
            ttdata = data.tt_data
            blocked_periods, possible_breaks = timeoff_fet(ttdata)
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
            if possible_breaks:
                self.teacher_lunch_breaks(tid, possible_breaks)
            # The constraint values in the following are <None> or a
            # (number, weight) pair (integers, though the weight may be
            # <None>)
            minl = self.teacher_periods_constraint(tid, ttdata, "MINPERDAY")
            if minl:
                # print("$$$$$ MINPERDAY", tid, minl)
                constraints_m.append(
                    {
                        "Weight_Percentage": "100",  # necessary!
                        "Teacher_Name": tid,
                        "Minimum_Hours_Daily": str(minl[0]),
                        "Allow_Empty_Days": "true",
                        "Active": "true",
                        "Comments": None,
                    }
                )
            gd = self.teacher_periods_constraint(tid, ttdata, "MAXGAPSPERDAY")
            if gd:
                # print("$$$$$ MAXGAPSPERDAY", tid, gd)
                constraints_gd.append(
                    {
                        "Weight_Percentage": "100",  # necessary!
                        "Teacher_Name": tid,
                        "Max_Gaps": str(gd[0]),
                        "Active": "true",
                        "Comments": None,
                    }
                )
            gw = self.teacher_periods_constraint(tid, ttdata, "MAXGAPSPERWEEK")
            if gw:
                # print("$$$$$ MAXGAPSPERWEEK", tid, gw)
                constraints_gw.append(
                    {
                        "Weight_Percentage": "100",  # necessary!
                        "Teacher_Name": tid,
                        "Max_Gaps": str(gw[0]),
                        "Active": "true",
                        "Comments": None,
                    }
                )
            u = self.teacher_periods_constraint(tid, ttdata, "MAXBLOCK")
            if u:
                n, w = u
                # print("$$$$$ MAXBLOCK", tid, u, WEIGHTS[w])
                if w:
                    constraints_u.append(
                        {
                            "Weight_Percentage": WEIGHTS[w],
                            "Teacher_Name": tid,
                            "Maximum_Hours_Continuously": str(n),
                            "Active": "true",
                            "Comments": None,
                        }
                    )
        add_constraints(
            self.time_constraints,
            "ConstraintTeacherNotAvailableTimes",
            blocked,
        )
        add_constraints(
            self.time_constraints,
            "ConstraintTeacherMinHoursDaily",
            constraints_m,
        )
        add_constraints(
            self.time_constraints,
            "ConstraintTeacherMaxGapsPerDay",
            constraints_gd,
        )
        add_constraints(
            self.time_constraints,
            "ConstraintTeacherMaxGapsPerWeek",
            constraints_gw,
        )
        add_constraints(
            self.time_constraints,
            "ConstraintTeacherMaxHoursContinuously",
            constraints_u,
        )

    def teacher_periods_constraint(
        self, tid: str, ttdata: dict[str, str], constraint: str
    ) -> Optional[tuple[int, int]]:
        val = ttdata.get(constraint)
        if not val:
            return None
        if val == "*":
            val = self.TT_CONFIG[f"TEACHER_{constraint}"]
        try:
            v, w = val.split("@", 1)
        except ValueError:
            v = val
            w = -1
        try:
            number = int(v)
            weight = int(w)
            if number >= 0 and number <= 10 and weight >= -1 and weight <= 10:
                return number, weight
        except ValueError:
            pass
        REPORT(
            "ERROR",
            T["INVALID_TEACHER_CONDITION_VALUE"].format(
                tid=tid, val=val, constraint=constraint
            ),
        )
        return None

    def class_periods_constraint(
        self, val: str, klass: str, constraint: str
    ) -> Optional[tuple[int, int]]:
        if not val:
            return None
        try:
            v, w = val.split("@", 1)
        except ValueError:
            v = val
            w = -1
        try:
            number = int(v)
            weight = int(w)
            if number >= 0 and number <= 10 and weight >= -1 and weight <= 10:
                return number, weight
        except ValueError:
            pass
        REPORT(
            "ERROR",
            T["INVALID_CLASS_CONDITION_VALUE"].format(
                klass=klass, val=val, constraint=constraint
            ),
        )
        return None

    def add_parallels(self):
        parallels = []
        for ptag, aidlist in self.parallel_tags.items():
            l = len(aidlist)
            if l > 1:
                w = WEIGHTS[get_simultaneous_weighting(ptag)]
                if w:
                    parallels.append(
                        {
                            "Weight_Percentage": w,
                            "Number_of_Activities": str(l),
                            "Activity_Id": aidlist,
                            "Active": "true",
                            "Comments": None,
                        }
                    )
            else:
                REPORT("WARNING", T["PARALLEL_SINGLE"].format(tag=ptag))
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
            _weight = self.TT_CONFIG["DOUBLE_LESSON_START_WEIGHT"]
            weight = WEIGHTS[int(_weight)]
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

    def placements_extern(self, xmlfile):
        """Get the preset placements from a fet "activities" file (passed
        as a file path) generated by a successful run of fet.
        The "locked" status is obtained from the original data.
        """
        # Get the placement data
        with open(xmlfile, "rb") as fh:
            xml = fh.read()
        pos_data = xmltodict.parse(xml)
        pos_list = pos_data["Activities_Timetable"]["Activity"]
        aid_data = {}
        db_backup()
        for p in pos_list:
            aid = p["Id"]
            try:
                activity = self.activities[int(aid) - 1]
            except:
                # Could indicate a mismatch between input data and result file ...
                print(" BAD INDEX:", aid)
                continue
            lesson_id = activity["Comments"]
            if lesson_id:
                if aid in self.locked_aids:
                    ptime = f"{p['Day']}.{p['Hour']}"
                else:
                    ptime = f"?{p['Day']}.{p['Hour']}"
                field_values = [("TIME", ptime)]
                room = p['Room']
                if room:
                    rlist = p.get('Real_Room')
                    if rlist:
                        field_values.append(("ROOMS", ','.join(rlist)))
                    else:
                        field_values.append(("ROOMS", room))
                # print("§§§", lesson_id, field_values)
                db_update_fields("LESSONS", field_values, id=int(lesson_id))


# TODO --
### Messages ... referred to in class Placements_fet
# _NO_LESSON_WITH_TAG = (
#    "Tabelle der festen Stunden: Kennung {tag} hat keine"
#    " entsprechenden Unterrichtsstunden"
# )
# _TAG_TOO_MANY_TIMES = (
#    "Tabelle der festen Stunden: Kennung {tag} gibt"
#    " mehr Zeiten an, als es dafür Unterrichtsstunden gibt"
# )

# TODO: Do I still need some of this? It might be useful if there are
# lessons-start-at-same-time constraints ... At present, the front end
# provides no interface for such constraints.
class Placements_fet:  # (TT_Placements):
    def placements(self):
        days = self.classes.daytags
        ndays = str(len(days))
        periods = self.classes.periodtags
        nperiods = str(len(periods))
        lid2aids: dict[int, list[str]] = self.classes.lid2aids
        constraints_parallel = []
        constraints_fixed = []
        constraints_multi = []
        constraints_l = []
        # print("\n*** Parallel tags ***")
        for tag, lids in self.classes.parallel_tags.items():
            # for i in lids:
            #    print(f"  {tag}: {i} --> {lid2aids[i]}")
            #    print(f"    ... {self.get_info(tag)}")
            weighting, places_list = self.get_info(tag)
            # What exactly the weighting applies to is not clear.
            # It could be the placement, or the parallel activities ...
            # I assume the placement(s), if there are any, otherwise
            # the parallel activities.
            w = WEIGHTS[weighting]
            # Collect tagged activities where there is no places list,
            # also where there are not enough places:
            excess = []
            for lid in lids:
                try:
                    aids = lid2aids[lid]
                except KeyError:
                    REPORT("WARN", _NO_LESSON_WITH_TAG.format(tag=tag))
                    continue
                i = 0
                for d, p in places_list:
                    try:
                        aid = aids[i]
                    except IndexError:
                        REPORT("ERROR", _TAG_TOO_MANY_TIMES.format(tag=tag))
                        continue
                    i += 1
                    if p == LAST_LESSON:
                        constraints_l.append(
                            {
                                "Weight_Percentage": "100",  # necessary!
                                "Activity_Id": aid,
                                "Active": "true",
                                "Comments": None,
                            }
                        )
                        if d < 0:
                            # Any day, no further constraint is needed
                            continue
                        else:
                            # A constraint to fix the day is needed
                            p = -2
                    if p < 0:
                        # Fix the day (any period)
                        xd = days[d]
                        constraints_multi.append(
                            {
                                "Weight_Percentage": w,
                                "Activity_Id": aid,
                                "Number_of_Preferred_Starting_Times": nperiods,
                                "Preferred_Starting_Time": [
                                    {
                                        "Preferred_Starting_Day": xd,
                                        "Preferred_Starting_Hour": xp,
                                    }
                                    for xp in periods
                                ],
                                "Active": "true",
                                "Comments": None,
                            }
                        )
                    elif d < 0:
                        # Fix the period (any day)
                        xp = periods[p]
                        constraints_multi.append(
                            {
                                "Weight_Percentage": w,
                                "Activity_Id": aid,
                                "Number_of_Preferred_Starting_Times": ndays,
                                "Preferred_Starting_Time": [
                                    {
                                        "Preferred_Starting_Day": xd,
                                        "Preferred_Starting_Hour": xp,
                                    }
                                    for xd in days
                                ],
                                "Active": "true",
                                "Comments": None,
                            }
                        )
                    else:
                        # Fix day and period
                        constraints_fixed.append(
                            {
                                "Weight_Percentage": w,
                                "Activity_Id": aid,
                                "Preferred_Day": days[d],
                                "Preferred_Hour": periods[p],
                                "Permanently_Locked": "true",
                                "Active": "true",
                                "Comments": None,
                            }
                        )
                excess.append(aids[i:])
            # Only those lists containing more than one list are
            # interesting for parallel activities.
            # Others may be used for special placement rules ...
            if len(excess) > 1:
                # Check that all lists are of equal length
                l = len(excess[0])
                for e in excess[1:]:
                    if len(e) != l:
                        raise Bug("Mismatch in parallel tag lists, tag = {tag}")
                excess_n = str(len(excess))
                for i in range(l):
                    parallel = [e[i] for e in excess]
                    constraints_parallel.append(
                        {
                            "Weight_Percentage": w,
                            "Number_of_Activities": excess_n,
                            "Activity_Id": parallel,
                            "Active": "true",
                            "Comments": None,
                        }
                    )
        time_constraints = self.classes.time_constraints
        add_constraints(
            time_constraints,
            "ConstraintActivityPreferredStartingTime",
            constraints_fixed,
        )
        add_constraints(
            time_constraints,
            "ConstraintActivitiesSameStartingTime",
            constraints_parallel,
        )
        add_constraints(
            time_constraints,
            "ConstraintActivityPreferredStartingTimes",
            constraints_multi,
        )
        add_constraints(
            time_constraints, "ConstraintActivityEndsStudentsDay", constraints_l
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


############################################################################

def getActivities(working_folder):
    from qtpy.QtWidgets import QApplication, QFileDialog
    app = QApplication.instance()
    if app is None:
        # if it does not exist then a QApplication is created
        app = QApplication(sys.argv)
#TODO: T ...
    d = QFileDialog(None, "Open fet 'activities' file", "", "'Activities' Files (*_activities.xml)")
    d.setFileMode(QFileDialog.ExistingFile)
    d.setOptions(QFileDialog.DontUseNativeDialog)
    history_file = os.path.join(working_folder, "activities_history")
    if os.path.isfile(history_file):
        with open(history_file, "r", encoding="utf-8") as fh:
            history = fh.read().split()
        d.setHistory(history)
        if history:
            d.setDirectory(history[-1])
    d.exec()
    files = d.selectedFiles()
    if files:
        with open(history_file, "w", encoding="utf-8") as fh:
            fh.write("\n".join(d.history()[-10:]))
        return files[0]
    return None


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database

    open_database()

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

    # Classes' not-available times
    courses.constraint_classes_timeoff()

    # Teacher-specific constraints
    courses.add_teacher_constraints(courses.timetable_teachers)

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

    print("\nClass constraints ...")
    courses.add_class_constraints()

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
#    xmlfile = getActivities(outdir)
#    if xmlfile:
#        courses.placements_extern(xmlfile)
#    else:
    if True:

        xml_fet = xmltodict.unparse(courses.gen_fetdata(), pretty=True)

        outpath = os.path.join(outdir, "tt_out.fet")
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
