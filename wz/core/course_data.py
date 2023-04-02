"""
core/course_data.py

Last updated:  2023-04-02

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
) -> tuple[Optional[dict], Optional[dict], list[dict]]:
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
    return (workload_element, simple_element, block_elements)

######### for new-course dialog #########

class CourseLessonData:
    def __init__(self, this_course:dict):
        """Read and link entries in COURSES, COURSE_WORKLOAD,
        WORKLOAD and LESSON_GROUPS db tables.
        <this_course> contains the field values for a "reference" course.
        This supports the creation of new entries for this course.
        """
        self.this_course = this_course
        self.get_courses(this_course["SUBJECT"])
        self.get_lesson_groups()
        self.get_workloads()
        self.get_course_workloads(this_course["course"])

    def can_add_nonblock(self) -> tuple[bool, bool]:
        simple, payonly = True, True
        for w in self.course_workloads:
            lg = self.workloads[w][0]
            if not lg:
                payonly = False
            if lg in self.noblock_lesson_groups:
                simple = False
        return (simple, payonly)

    def get_courses(self, course_sid:str):
        """Read all COURSES entries to the mapping <self.course_map>:
            {course: (CLASS, GRP, SUBJECT, TEACHER), ...}.
        The <course> values of all entries with SUBJECT==course_sid are
        collected in the list <self.same_sid_courses>.
        """
        self.same_sid_courses = []
        self.course_map = {}
        for course, CLASS, GRP, sid, tid in db_read_fields(
            "COURSES", ("course", "CLASS", "GRP", "SUBJECT", "TEACHER")
        ):
            # print("$Cs$$", course, CLASS, GRP, sid, tid)
            if sid == course_sid:
                self.same_sid_courses.append(course)
            self.course_map[course] = (CLASS, GRP, sid, tid)
        # print("§same_sid_courses:", self.same_sid_courses)

    def get_lesson_groups(self):
        """Read the block name from all LESSON_GROUPS entries.
        Build derived data structures:
        1) set of lesson_group keys for simple lessons
            <self.noblock_lesson_groups>:
                {lesson_group, ...}
        2) map lesson_group key to block name
            <self.lesson_group2blockname>:
                 {lesson_group: (BLOCK_SID, BLOCK_TAG), ... }
        3) map block-name (string form) to lesson_group key
            <self.block2lesson_group>:
                {nloack-name: lesson_group, ... } 
        4) map block-sid to block-tag and lesson_group (list)
            <self.blocksid2tags>:
                {BLOCK_SID: [(BLOCK_TAG, lesson_group), ...], ... }
        """
        self.noblock_lesson_groups = set()
        self.lesson_group2blockname = {}
        self.block2lesson_group = {}
        self.blocksid2tags = {}
        for lg, BLOCK_SID, BLOCK_TAG in db_read_fields(
            "LESSON_GROUPS", ("lesson_group", "BLOCK_SID", "BLOCK_TAG")
        ):
            if BLOCK_SID:
                self.lesson_group2blockname[lg] = (BLOCK_SID, BLOCK_TAG)
                key = f"{BLOCK_SID}#{BLOCK_TAG}"
                self.block2lesson_group[key] = lg
                # print(f"$LG$$ {key}:", lg)
                tag_lg = (BLOCK_TAG, lg)
                try:
                    self.blocksid2tags[BLOCK_SID].append(tag_lg)
                except KeyError:
                    self.blocksid2tags[BLOCK_SID] = [tag_lg]
            else:
                self.noblock_lesson_groups.add(lg)
        # print("$LG$$ {}:", self.noblock_lesson_groups)

    def get_workloads(self):
        self.lesson_group2workloads = {}
        self.workloads = {}
        for workload, lg, PAY_TAG, ROOM in db_read_fields(
            "WORKLOAD", ("workload", "lesson_group", "PAY_TAG", "ROOM")
        ):
            lg = lg or 0
            print("$Wl$$", workload, lg, PAY_TAG, ROOM)
            self.workloads[workload] = (lg, PAY_TAG, ROOM)
            try:
                self.lesson_group2workloads[lg].append(workload)
            except KeyError:
                self.lesson_group2workloads[lg] = [workload]

    def get_course_workloads(self, course_course):
        self.workload2courses = {}
        self.course_workloads = []
#TODO: id not really necessary in this module?
        for _id, course, workload in db_read_fields(
            "COURSE_WORKLOAD", ("id", "course", "workload")
        ):
            # print("$CW$$", _id, course, workload)
            try:
                self.workload2courses[workload].append(course)
            except KeyError:
                self.workload2courses[workload] = [course]
            if course == course_course:
                self.course_workloads.append(workload)


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()

    for course in filtered_courses("TEACHER", "AE"):
        print("\n\n *** COURSE:", course["course"], course)
        w, l, b = course_activities(course["course"])
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
