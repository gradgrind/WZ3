"""
core/course_data.py

Last updated:  2023-04-04

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
    db_read_fields,
    db_read_unique,
    db_read_unique_field,
    db_values,
    NoRecord,
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
    return courses


def course_activities(course_id:int
) -> tuple[Optional[dict], Optional[dict], list[dict]]:
    """Seek lessons and workload/payment info for the given course
    (<course_id>).
    There can be pay-only entries.
    There can be groups of simple lessons.
    There can be named blocks – with distinct (non-empty)
    BLOCK_SID/BLOCK_TAG values.

    Return: (pay-only elements, simple elements, block elements)

    NOTE how the parameters are set in various tables. The room-wish
    and pay details apply to all lesson components as they are set in
    WORKLOAD. Only the time-wish is set in the lesson component.
    This may be a bit restrictive, but is perhaps reasonable for most
    cases. Normally only single simple or pay-only elements would be
    expected.
    
    There is also the possibility that multiple courses share a WORKLOAD
    entry, which means that room and pay-data values are shared by all
    the courses. The main idea behind this option is to facilitate
    combining groups (especially from different classes – within one
    class it is probably better to have a single group for this). It
    could also be used for joint teaching as long as the room is shared
    and the pay-data identical. Otherwise a block might be better. 
    """
    workload_elements = []
    simple_elements = []
    block_elements = []
    fields, records = db_read_full_table(
        "COURSE_WORKLOAD", course=course_id
    )
    for rec in records:
        # The uniqueness of a COURSES/WORKLOAD connection
        # should be enforced by the UNIQUE constraint on the
        # COURSE_WORKLOAD table ("course" + "workload" fields).
        cwdict = {fields[i]: val for i, val in enumerate(rec)}
        fields_w, record_w = db_read_unique_entry(
            "WORKLOAD", workload=cwdict["workload"]
        )
        ## Combined <dict> for the COURSE_WORKLOAD and WORKLOAD entries.
        ## If there is a LESSON_GROUPS entry, its fields will also be added.
        for i, val in enumerate(record_w):
            cwdict[fields_w[i]] = val
        # <cwdict> contains workload/payment and room-wish fields
        lg = cwdict["lesson_group"]
        if lg:
            lgfields, lgrecord = db_read_unique_entry(
                "LESSON_GROUPS", lesson_group=lg
            )
            for i, val in enumerate(lgrecord):
                cwdict[lgfields[i]] = val
            # This contains the block-name, if any
            block_sid = cwdict["BLOCK_SID"]
            block_tag = cwdict["BLOCK_TAG"]
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
                simple_elements.append(cwdict)
        else:
            # pay-only item
            workload_elements.append(cwdict)
    return (workload_elements, simple_elements, block_elements)

######### for new-course-element dialog #########

def courses_in_block(bsid, btag):
    """Find all courses which are members of the given block.
    Return also the WORKLOAD and LESSON_GROUPS keys.
    """
    try:
        lg = db_read_unique_field(
            "LESSON_GROUPS",
            "lesson_group",
            BLOCK_SID=bsid,
            BLOCK_TAG=btag
        )
    except NoRecord:
        # There is no lesson_group with this block-name
        return []
    wlist = db_values("WORKLOAD", "workload", lesson_group=lg)
    courses = []
    for w in wlist:
        for course in db_values("COURSE_WORKLOAD", "course", workload=w):
            cdata = db_read_unique(
                "COURSES",
                ("CLASS", "GRP", "SUBJECT", "TEACHER"),
                course=course
            )
            courses.append((cdata, w, lg, course))
    return courses


def simple_with_subject(sid):
    """Find all courses with simple lessons in the given subject.
    """
    lgset = {
        lg for lg, s in db_read_fields(
            "LESSON_GROUPS", ("lesson_group", "BLOCK_SID")
        ) if not s
    }
    wmap = {
        w: lg for w, lg in db_read_fields(
            "WORKLOAD", ("workload", "lesson_group")
        ) if lg in lgset
    }
    courses = {
        c: (cl, g, t) for c, cl, g, t in db_read_fields(
            "COURSES",
            ("course", "CLASS", "GRP", "TEACHER"),
            SUBJECT=sid,
        )
    }
    matches = []
    for c, w in db_read_fields(
        "COURSE_WORKLOAD",
        ("course", "workload"),
    ):
        try:
            cl, g, t = courses[c]
        except KeyError:
            continue
        try:
            lg = wmap[w]
        except KeyError:
            continue
        matches.append(((cl, g, sid, t), w, lg, c))
    return matches


def payonly_with_subject(sid):
    """Find all courses with pay-only elements in the given subject.
    """
    wset = {
        w for w, lg in db_read_fields(
            "WORKLOAD", ("workload", "lesson_group")
        ) if not lg
    }
    courses = {
        c: (cl, g, t) for c, cl, g, t in db_read_fields(
            "COURSES",
            ("course", "CLASS", "GRP", "TEACHER"),
            SUBJECT=sid,
        )
    }
    matches = []
    for c, w in db_read_fields(
        "COURSE_WORKLOAD",
        ("course", "workload"),
    ):
        if w in wset:
            try:
                cl, g, t = courses[c]
            except KeyError:
                continue
            matches.append(((cl, g, sid, t), w, 0, c))
    return matches
