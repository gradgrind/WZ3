"""
core/activities.py

Last updated:  2023-07-23

Collect basic information on "activities".


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

#TODO ... adapt to new db structure ... can it be combined with the code
# in course_data_3a? I will try that first – so this module may be
# redundant!

if __name__ == "__main__":
    # Enable package import if running as module
    import sys, os

    this = sys.path[0]
    appdir = os.path.dirname(this)
    sys.path[0] = appdir
    basedir = os.path.dirname(appdir)
    from core.base import start
    start.setup(os.path.join(basedir, "TESTDATA"))

#T = TRANSLATIONS("core.activities")

### +++++

from typing import NamedTuple

from core.db_access import (
    db_read_fields,
    db_select,
    db_read_unique_field,
    Record
)

### -----


class CourseWithRoom(NamedTuple):
    """This structure contains the info from the COURSES entry
    and the room wish from the associated LESSON_DATA entry.
    """
    klass: str
    group: str
    subject: str
    teacher: str
    room: str


class ActivityGroup(NamedTuple):
    course_list: list[CourseWithRoom]
    block_sid: str
    block_tag: str
    lessons: list[Record]


def read_from_db():
    """Read all the relevant data from the database tables concerning
    the workload of classes and teachers.
    """
    q = """select
        Course,
        CLASS,
        GRP,
        SUBJECT,
        TEACHER,
        coalesce(Cl_id, -1) Cl_id,
        coalesce(Lesson_group, -1) Lesson_group,
        coalesce(Lesson_data, 0) Lesson_data,
        coalesce(ROOM, '') ROOM,
        coalesce(PAY_NLESSONS, '0') PAY_NLESSONS,
        coalesce(PAY_TAG, '') PAY_TAG,
        coalesce(PAY_WEIGHT, '') PAY_WEIGHT,
        coalesce(BLOCK_SID, '') BLOCK_SID,
        coalesce(BLOCK_TAG, '') BLOCK_TAG

        from COURSES
        inner join COURSE_LESSONS using (Course) -- excludes "unused" courses
        left join LESSON_GROUPS using(Lesson_group)
        left join LESSON_DATA using(Lesson_data)
        left join PAY_FACTORS using (Pay_factor_id)

        order by CLASS, SUBJECT, GRP, TEACHER
    """
    records = db_select(q)
    lg_ll = {}
    for lg, l in db_read_fields("LESSONS", ("Lesson_group", "LENGTH")):
        try:
            lg_ll[lg].append(l)
        except KeyError:
            lg_ll[lg] = [l]
    t_rec = {}
    c_rec = {}
    lg_rec = {}
    for rec in records:
        tid = rec["TEACHER"]
        k = rec["CLASS"]
        lg = rec["Lesson_group"]
        try:
            t_rec[tid].append(rec)
        except KeyError:
            t_rec[tid] = [rec]
        try:
            c_rec[k].append(rec)
        except KeyError:
            c_rec[k] = [rec]
        try:
            lg_rec[lg].append(rec)
        except KeyError:
            lg_rec[lg] = [rec]
    return {
        "T_ACTIVITIES": t_rec,
        "C_ACTIVITIES": c_rec,
        "Lg_ACTIVITIES": lg_rec,
        "Lg_LESSONS": lg_ll
    }


def collect_activity_groups() -> dict[int, ActivityGroup]:
    """Read all activities with lessons from database. Gather the
    information needed for the timetable for each lesson-group.
    """
    # Get activities from database
    activities = read_from_db()
    c_activities = activities["C_ACTIVITIES"]
    lg_data = {}    # { lesson-group -> ActivityGroup }
    for klass in sorted(c_activities):
        classroom = db_read_unique_field("CLASSES", "CLASSROOM", CLASS=klass)
        for ai in c_activities[klass]:
            if (lg := ai["Lesson_group"]) == 0:
                continue        # not relevant for timetable (no lessons)
            try:
                data = lg_data[lg]
            except KeyError:
                lessons = db_select(
                    f"select * from LESSONS where Lesson_group = {lg}"
                )
                assert lessons
                lg_data[lg] = ActivityGroup(
                    [
                        CourseWithRoom(
                            ai["CLASS"],
                            ai["GRP"],
                            ai["SUBJECT"],
                            ai["TEACHER"],
                            ai["ROOM"].replace('$', classroom)
                        )
                    ],
                    ai["BLOCK_SID"],
                    ai["BLOCK_TAG"],
                    lessons,
                )
            else:
                data.course_list.append(
                    CourseWithRoom(
                        ai["CLASS"],
                        ai["GRP"],
                        ai["SUBJECT"],
                        ai["TEACHER"],
                        ai["ROOM"].replace('$', classroom)
                    )
                )
    return lg_data


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database("wz_db.sqlite")
    activities = read_from_db()
    for r in activities["T_ACTIVITIES"]["MT"]:
        print(" --", r)

    lg_map = collect_activity_groups()
    for lg, ag in lg_map.items():
        print(" *****************************************")
        for c in ag.course_list: print(" --", c)
        print(f"   BLOCK: {ag.block_sid}#{ag.block_tag}")
        for l in ag.lessons: print("     ++", l)

