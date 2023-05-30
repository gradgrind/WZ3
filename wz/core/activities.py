"""
core/activities.py

Last updated:  2023-05-30

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

from typing import NamedTuple, Optional

from core.basic_data import (
    Workload,
    BlockTag,
)
from core.db_access import db_read_fields, db_read_unique_field

LESSONS_FIELDS = ("id", "LENGTH", "TIME", "PLACEMENT", "ROOMS")

### -----


class ActivityItem(NamedTuple):
    klass: str
    group: str
    subject: str
    teacher: str
    workload: int
    lesson_group: int
    blocktag: Optional[BlockTag]
    lessons: list[int]
    paytag: Optional[Workload]
    room: str


class CourseWithRoom(NamedTuple):
    """This structure contains the info from the COURSES entry
    and the room wish from a WORKLOAD entry which is associated with it.
    """
    klass: str
    group: str
    subject: str
    teacher: str
    room: str


class LessonInfo(NamedTuple):
    id: str
    length: int
    time: str
    placement: str
    rooms: str


class ActivityGroup(NamedTuple):
    course_list: list[CourseWithRoom]
    block_tag:  Optional[BlockTag]
    lessons: list[LessonInfo]


def read_db():
    """Read all the relevant data from the database tables concerning
    the workload of classes and teachers.
    """
    cl_lists = {}
    t_lists = {}

    c_2_cl_g_s_t = {}
    w_2_lg_p_r = {}
    lg_2_ll = {}
    lg_2_bt_ll = {}
    lg_2_c = {}

    for c, cl, g, s, t in db_read_fields(
        "COURSES",
        ("course", "CLASS", "GRP", "SUBJECT", "TEACHER")
    ):
        c_2_cl_g_s_t[c] = (cl, g, s, t)

    for w, lg, paytag, room in db_read_fields(
        "WORKLOAD",
        ("workload", "lesson_group", "PAY_TAG", "ROOM")
    ):
        w_2_lg_p_r[w] = (lg, Workload.build(paytag), room)

    for lg, l in db_read_fields(
        "LESSONS",
        ("lesson_group", "LENGTH")
    ):
        try:
            lg_2_ll[lg].append(l)
        except KeyError:
            lg_2_ll[lg] = [l]

    for lg, bsid, btag in db_read_fields(
        "LESSON_GROUPS",
        ("lesson_group", "BLOCK_SID", "BLOCK_TAG")
    ):
        lg_2_bt_ll[lg] = (
            BlockTag.build(bsid, btag) if bsid else None,
            lg_2_ll[lg]     # assumes each lg has lessons!
        )

    for c, w in db_read_fields(
        "COURSE_WORKLOAD",
        ("course", "workload")
    ):
        cdata = c_2_cl_g_s_t[c]
        lg, p, r = w_2_lg_p_r[w]
        if lg:
            bt, ll = lg_2_bt_ll[lg]
        else:
            bt, ll = None, []
        cl = cdata[0]
        t = cdata[3]
        data = ActivityItem(*cdata, w, lg, bt, ll, p, r)
        try:
            t_lists[t].append(data)
        except KeyError:
            t_lists[t] = [data]
        try:
            cl_lists[cl].append(data)
        except KeyError:
            cl_lists[cl] = [data]
        try:
            lg_2_c[lg].append(cdata)
        except KeyError:
            lg_2_c[lg] = [cdata]
    return (cl_lists, t_lists, lg_2_c)


def collect_activity_groups() -> dict[int, ActivityGroup]:
    """Read all activities with lessons from database. Gather the
    information needed for the timetable for each lesson-group.
    """
    # Get activities from database
    cl_lists, t_lists, lg_2_c = read_db()
    # <cl_lists> is a mapping { class -> [activity, ... ] }
    lg_data = {}    # { lesson-group -> ActivityGroup }
    for klass in sorted(cl_lists):
        classroom = db_read_unique_field("CLASSES", "CLASSROOM", CLASS=klass)
        for ai in cl_lists[klass]:
            if not ai.lessons:
                continue
            try:
                data = lg_data[(lg := ai.lesson_group)]
            except KeyError:
                lessons = [
                    LessonInfo(*row)
                    for row in db_read_fields(
                        "LESSONS", LESSONS_FIELDS, lesson_group=lg
                    )
                ]
                lg_data[lg] = ActivityGroup(
                    [
                        CourseWithRoom(
                            *ai[:4],
                            ai.room.replace('$', classroom)
                        )
                    ],
                    ai.blocktag,
                    lessons,
                )
            else:
                data.course_list.append(
                    CourseWithRoom(*ai[:4], ai.room.replace('$', classroom))
                )
    return lg_data


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    cl_lists, t_lists, lg_2_c = read_db()

    lg_map = collect_activity_groups()
    for lg, ag in lg_map.items():
        print(" ***", ag)
