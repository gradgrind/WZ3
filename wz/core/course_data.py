"""
core/course_data.py

Last updated:  2023-03-25

Support functions dealing with courses, lessons, etc.


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

#T = TRANSLATIONS("core.course_data")

### +++++

from typing import Optional
from core.db_access import (
    db_read_full_table,
    db_read_unique_entry,
)
from core.basic_data import (
    Workload,
    BlockTag,
)

### -----

def filtered_courses(filter, value):
    fields, records = db_read_full_table(
        "COURSES",
        sort_field="SUBJECT",
        **{filter: value}
    )
    courses = []
    for r, rec in enumerate(records):
        rdict = {fields[i]: val for i, val in enumerate(rec)}
        courses.append(rdict)
        # print("  --", rdict)
    return courses


def course_activities(course_id:int
) -> tuple[Optional[tuple], Optional[tuple], list[dict]]:
    """Seek lessons and workload/pament info for the given course
    (<course_id>).
    There can be a (single) workload/payment entry.
    There can be a (single) group of simple lessons.
    There can be named blocks – with distinct (non-empty)
    BLOCK_SID/BLOCK_TAG values.

    Return: (workload/payment element, simple element, block elements)

    NOTE how the parameters are set in various tables. The room-wish
    and pay details apply to all lesson components as they are set in
    COURSE_LESSONS. Only the time-wish is set in the lesson component.
    This may be a bit restrictive, but is perhaps reasonable for most
    cases. If it is really essential to have a particular room for a
    particular lesson (and another one, or a choice, for another
    lesson), perhaps some additional constraint could be added ...
    """
    workload_element = None
    simple_element = None
    block_elements = []
    fields, records = db_read_full_table(
        "COURSE_LESSONS", course=course_id
    )
    for rec in records:
        cldict = {fields[i]: val for i, val in enumerate(rec)}
        workload_data = Workload(**cldict)
        # <cldict> contains workload/payment and room-wish fields
        lg = cldict["lesson_group"]
        if lg:
            lgfields, lgrecord = db_read_unique_entry(
                "LESSON_GROUP", lesson_group=lg
            )
            lgdata = {
                lgfields[i]: val for i, val in enumerate(lgrecord)
            }
            # This contains the block-name, if any
            block_sid = lgdata["BLOCK_SID"]
            block_tag = lgdata["BLOCK_TAG"]
            # The uniqueness of a block name should be enforced by
            # the UNIQUE constraint on the LESSON_GROUP table
            # ("BLOCK_SID" + "BLOCK_TAG" fields).
            # The uniqueness of a course/lesson_group connection
            # should be enforced by the UNIQUE constraint on the
            # COURSE_LESSONS table ("course" + "lesson_group" fields).
            lfields, lrecords = db_read_full_table(
                "LESSONS", lesson_group=lg
            )
            lessons = [
                {lfields[i]: val for i, val in enumerate(lrec)}
                for lrec in lrecords
            ]
            if block_sid:
                bt = BlockTag.build(block_sid, block_tag)
                block_elements.append(
                    (workload_data, cldict, lgdata, lessons, bt)
                )
            else:
                if simple_element:
                    raise Bug(
                        "Multiple entries in COURSE_LESSONS"
                        f"for simple lesson item, course {course_id}"
                    )
                simple_element = (workload_data, cldict, lgdata, lessons)
        else:
            # payment/workload item
            if workload_element:
                raise Bug("Multiple entries in COURSE_LESSONS"
                    f"for workload item, course {course_id}"
                )
            workload_element = (workload_data, cldict)
    return (workload_element, simple_element, block_elements)


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()

    for course in filtered_courses("TEACHER", "AE"):
        print("\n\n *** COURSE:", course["course"], course)
        w, l, b = course_activities(course["course"])
        if w:
            print("  ***", str(w[0]), w[1:])
        else:
            print("  ***")
        if l:
            print("  ---", str(l[0]), l[1:])
        else:
            print("  ---")
        if b:
            for bi in b:
                print("  +++", str(bi[0]) or "-$-", bi[1:])
        else:
            print("  +++ []")
