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

from typing import NamedTuple
from core.db_access import (
    db_read_unique,
    db_read_full_table,
    db_update_field,
    db_update_fields,
    db_new_row,
    db_delete_rows,
    db_values,
    db_read_unique_entry,
    NoRecord,
)
from core.teachers import Teachers
from core.classes import Classes
from core.basic_data import (
    Workload,
    clear_cache,
    get_subjects,
    BlockTag,
    ParallelTag,
)

#TODO ...???

# SUBJECT, CLASS and TEACHER are foreign keys with:
#  on delete cascade + on update cascade
FOREIGN_FIELDS = ("CLASS", "TEACHER", "SUBJECT")

COURSE_TABLE_FIELDS = ( # the fields shown in the course table
# (db-field name, column-type, horizontal text alignment)
# column-type:
#   -1: checkbox
#    0: db-value
#    1: display-value (from column-dependent map)
# alignment:
#   -1: left
#    0: centre
#    1: right
    ("CLASS", 0, 0),
    ("GRP", 0, 0),
    ("SUBJECT", 1, -1),
    ("TEACHER", 1, -1),
    ("REPORT", -1, 0),
    ("GRADES", -1, 0),
    ("INFO", 0, -1),
)

class LessonRowData(NamedTuple):
    """ROW_TYPE:
        -2 – no item (all other fields <None>)
        -1 – workload/payment item (only COURSE_LESSON_INFO not <None>)
         0 – "normal" lesson group (not a block)
         1 – block lesson group
    """
    ROW_TYPE: int
    COURSE_LESSON_INFO: dict
    LESSON_GROUP_INFO: dict
    LESSON_INFO: dict

### -----

def load_course_table(filter, value):
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


def course_activities(course_id):
    """Seek lessons and workload/pament info for the given course
    (<course_id>).
    """
    fields, records = db_read_full_table(
        "COURSE_LESSONS", course=course_id
    )
    ## Build a list of entries, loop through entries in COURSE_LESSONS.
    ## There can be a (single) workload/pament entry.
    ## There can be a (single) group of simple lessons.
    ## There can be named blocks.
    course_lessons = []

# DETAILS:
# There should be only one COURSE_LESSONS entry for "simple lesson"
# types and "workload/payment" types. For "block lesson" types there
# can be more than one entry, but they should be connected with
# LESSON_GROUP entries with distinct (non-empty) BLOCK_x values.
# If violations are discovered, there should be an error report. It
# might be helpful to delete the offending entries, but as they are
# really not expected – and should not be possible – it is perhaps
# better to report the offending entries and not to delete them, so
# that they are available for debugging purposes – the report could
# be via a bug exception?

# Also note how the parameters are set in various tables. The room
# wish and pay details apply to all lesson components as they are set in
# COURSE_LESSONS. Only the time wish is set in the lesson component.
# This may be a bit restrictive, but is perhaps reasonable for most
# cases. If it is really essential to have a particular room for a
# particular lesson (and another one, or a choice, for another lesson),
# perhaps some additional constraint could be added ...

    workload_element = False
    simple_element = False
    for rec in records:
        cldict = {fields[i]: val for i, val in enumerate(rec)}
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
            if block_sid:
                etype = 1
                bt = BlockTag.build(block_sid, block_tag)
                lgdata["BlockTag"] = bt
            else:
                if simple_element:
                    raise Bug(
                        "Multiple entries in COURSE_LESSONS"
                        f"for simple lesson item, course {course_id}"
                    )
                simple_element = True
                etype = 0
            lfields, lrecords = db_read_full_table(
                "LESSONS", lesson_group=lg
            )
            lgdata["nLessons"] = len(lrecords)
            for lrec in lrecords:
                ldata = {lfields[i]: val for i, val in enumerate(lrec)}
                ln = ldata["LENGTH"]
                course_lessons.append(
                    LessonRowData(etype, cldict, lgdata, ldata)
                )
        else:
            # payment/workload item
            if workload_element:
                raise Bug("Multiple entries in COURSE_LESSONS"
                    f"for workload item, course {self.course_id}"
                )
            workload_element = True
            course_lessons.append(
                LessonRowData(-1, cldict, None, None)
            )
    return course_lessons


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()

    for course in load_course_table("TEACHER", "AE"):
        print("\n\n *** COURSE:", course)
        for l in course_activities(course["course"]):
            print("\n  ---", l)
