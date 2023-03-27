"""
core/course_data.py

Last updated:  2023-03-27

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
from core.basic_data import BlockTag

### -----

def filtered_courses(filter:str, value:str) -> list[dict]:
    """Return a list of COURSES (as <dict>s) where the value of
    field <filter> is equal to <value>.
    Filter can be "CLASS", "TEACHER" or "SUBJECT".
    """
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
) -> tuple[Optional[dict], Optional[dict], list[dict], dict]:
    """Seek lessons and workload/pament info for the given course
    (<course_id>).
    There can be a (single) workload/payment entry.
    There can be a (single) group of simple lessons.
    There can be named blocks – with distinct (non-empty)
    BLOCK_SID/BLOCK_TAG values.

    Return: (workload/payment element, simple element, block elements)

    NOTE how the parameters are set in various tables. The room-wish
    and pay details apply to all lesson components as they are set in
    WORKLOAD. Only the time-wish is set in the lesson component.
    This may be a bit restrictive, but is perhaps reasonable for most
    cases. If it is really essential to have a particular room for a
    particular lesson (and another one, or a choice, for another
    lesson), perhaps some additional constraint could be added ...
    
    There is also the possibility that multiple courses share a WORKLOAD
    entry, which means that room and pay-data values are shared by all
    the courses. The main idea behind this option is to facilitate
    combining groups (especially from different classes – within one
    class it is probably better to have a single group for this). It
    could also be used for joint teaching as long as the room is shared
    and the pay-data identical. Otherwise a block might be better. 
    """
    workload_element = None
    simple_element = None
    block_elements = []
    workload_map = {}   # record usage of WORKLOAD entries
    fields, records = db_read_full_table(
        "COURSE_WORKLOAD", course=course_id
    )
    for rec in records:
        # The uniqueness of a COURSES/WORKLOAD connection
        # should be enforced by the UNIQUE constraint on the
        # COURSE_WORKLOAD table ("course" + "workload" fields).
        cwdict = {fields[i]: val for i, val in enumerate(rec)}
        w = cwdict["workload"]
        workload_map[w] = cwdict
        fields_w, record_w = db_read_unique_entry(
            "WORKLOAD", workload=w
        )
        ## Combined <dict> for the COURSE_WORKLOAD and WORKLOAD entries
        for i, val in enumerate(record_w):
            cwdict[fields_w[i]] = val
        # <cwdict> contains workload/payment and room-wish fields
        lg = cwdict["lesson_group"]
        if lg:
            lgfields, lgrecord = db_read_unique_entry(
                "LESSON_GROUPS", lesson_group=lg
            )
            lgdata = {
                lgfields[i]: val for i, val in enumerate(lgrecord)
            }
            ## Add data from LESSON_GROUPS entry
            cwdict["lesson_group_data"] = lgdata
            # This contains the block-name, if any
            block_sid = lgdata["BLOCK_SID"]
            block_tag = lgdata["BLOCK_TAG"]
            # The uniqueness of a block name should be enforced by
            # the UNIQUE constraint on the LESSON_GROUPS table
            # ("BLOCK_SID" + "BLOCK_TAG" fields).
            lfields, lrecords = db_read_full_table(
                "LESSONS", lesson_group=lg
            )
            lessons = [
                {lfields[i]: val for i, val in enumerate(lrec)}
                for lrec in lrecords
            ]
            ## Add LESSONS data (list)
            cwdict["lessons"] = lessons
            if block_sid:
                cwdict["blocktag"] = BlockTag.build(block_sid, block_tag)
                block_elements.append(cwdict)
            else:
                if simple_element:
                    raise Bug(
                        "Multiple entries in COURSE_LESSONS"
                        f"for simple lesson item, course {course_id}"
                    )
                simple_element = cwdict
        else:
            # payment/workload item
            if workload_element:
                raise Bug("Multiple entries in COURSE_LESSONS"
                    f"for workload item, course {course_id}"
                )
            workload_element = cwdict
    return (workload_element, simple_element, block_elements, workload_map)


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()

    for course in filtered_courses("TEACHER", "AE"):
        print("\n\n *** COURSE:", course["course"], course)
        w, l, b, wm = course_activities(course["course"])
        if w:
            print("  ***", w)
        else:
            print("  ***")
        if l:
            print("  ---", l)
        else:
            print("  ---")
        if b:
            for bi in b:
                print("  +++", bi)
        else:
            print("  +++ []")
        print("  ###", list(wm))
