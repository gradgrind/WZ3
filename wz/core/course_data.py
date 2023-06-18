"""
core/course_data.py

Last updated:  2023-06-18

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
    db_select,
    db_read_full_table,
    db_read_unique_entry,
    db_read_fields,
    db_read_unique,
    db_read_unique_field,
    db_values,
    Record,
    NoRecord,
)
from core.basic_data import BlockTag, Workload, get_classes, get_subjects
from core.classes import GROUP_ALL

### -----

def filtered_courses(filter:str, value:str) -> list[dict]:
    """Return a list of COURSES (as <dict>s) where the value of
    field <filter> is equal to <value>.
    Filter can be "CLASS", "TEACHER" or "SUBJECT".
    """
    fields, records = db_read_full_table(
        "COURSES",
        sort_field="CLASS,SUBJECT,GRP,TEACHER",
        **{filter: value}
    )
    courses = []
    for r, rec in enumerate(records):
        rdict = {fields[i]: val for i, val in enumerate(rec)}
        courses.append(rdict)
    return courses


#TODO: experimental
def filter_activities(filter:str, value:str) -> dict[str, list[Record]]:
    """Seek COURSES and lessons/workload/payment info for the given
    course filter (CLASS, TEACHER or SUBJECT).
    
    Return: {course-id: [records]}

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
    q = f"""select
        Course,
        CLASS,
        GRP,
        SUBJECT,
        -- NAME as SUBJECT_NAME,
        TEACHER,
        coalesce(REPORT, '') REPORT,
        coalesce(GRADES, '') GRADES,
        coalesce(REPORT_SUBJECT, '') REPORT_SUBJECT,
        coalesce(AUTHORS, '') AUTHORS,
        coalesce(INFO, '') INFO,
        coalesce(Cw, 0) Cw,
        coalesce(Workload, 0) Workload,
        coalesce(Lesson_group, 0) Lesson_group,
        coalesce(ROOM, '') ROOM,
        coalesce(PAY_TAG, '') PAY_TAG,
        coalesce(BLOCK_SID, '') BLOCK_SID,
        coalesce(BLOCK_TAG, '') BLOCK_TAG,
        coalesce(NOTES, '') NOTES,
        coalesce(Lid, 0) Lid,
        coalesce(LENGTH, 0) LENGTH,
        coalesce(TIME, '') TIME,
        coalesce(PLACEMENT, '') PLACEMENT,
        coalesce(ROOMS, '') ROOMS
        from COURSES
        
        -- left join SUBJECTS on COURSES.SUBJECT = SUBJECTS.SID

        left join COURSE_WORKLOAD using (course)
        
        left join WORKLOAD using (workload)
        
        left join LESSON_GROUPS -- includes null lesson_groups in WORKLOAD
        -- inner join LESSON_GROUPS -- excludes null lesson_groups in WORKLOAD
        using (lesson_group)
        
        left join LESSONS using (lesson_group)
        
        where {filter} = '{value}'
        order by CLASS, SUBJECT, GRP, TEACHER
    """
    # The uniqueness of a COURSES/WORKLOAD connection
    # should be enforced by the UNIQUE constraint on the
    # COURSE_WORKLOAD table ("course" + "workload" fields).
    records = db_select(q)
    # Sort according to type
    subjects = get_subjects()
    course_map = {}
    for rec in records:
        c = rec["Course"]
        try:
            cml = course_map[c].append(rec)
        except KeyError:
            course_map[c] = [rec]
        #TODO: Something like this would separate the three types:
        #lg = rec["Lesson_group"]
        #if lg:
        #    if (sid := rec["BLOCK_SID"]): # block
        #        rec["block_subject"] = subjects.map(sid)
        #        cml[2].append(rec)
        #    else: # simple
        #        cml[1].append(rec)
        #else: # pay-only
        #    cml[0].append(rec)
    return course_map


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
    print("! TODO: core.course_data.course_activities is deprecated."
        "Callers should be adapted to use activities_for_course instead."
    )

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


#TODO:
#!!! Maybe the deprecations aren't that clever. The new code seems to
# be rather slow! But the new code might be useful as a basis for an
# implementation in another language? Perhaps the use of QSqlRecord
# objects in python is a problem? I could try using dicts instead ...
# No, it is also slow with dicts.
# Profiling suggests I might be calling db_select too often!

# 1) The field names are somewhat changed.
# 2) The "lessons" entry is now all LESSONS fields, so multiple entries!
# 3) This doesn't build BlockTag items.
# 4) Try to eliminate the "coalesce" functions by eliminating NULL fields.
def activities_for_course(course_id:int
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
    q = f"""select
            -- coalesce(Course, 0) Course,
            Cw,
            coalesce(Workload, 0) Workload,
            coalesce(Lesson_group, 0) Lesson_group,
            coalesce(ROOM, '') ROOM,
            coalesce(PAY_TAG, '') PAY_TAG,
            coalesce(BLOCK_SID, '') BLOCK_SID,
            coalesce(BLOCK_TAG, '') BLOCK_TAG,
            coalesce(NOTES, '') NOTES,
            -- coalesce(CLASS, '') CLASS,
            -- coalesce(GRP, '') GRP,
            -- coalesce(SUBJECT, '') SUBJECT,
            -- coalesce(TEACHER, '') TEACHER,
            coalesce(Lid, 0) Lid,
            coalesce(LENGTH, 0) LENGTH,
            coalesce(TIME, '') TIME,
            coalesce(PLACEMENT, '') PLACEMENT,
            coalesce(ROOMS, '') ROOMS
            from COURSE_WORKLOAD
            full join WORKLOAD -- inner join avoids spurious entries in WORKLOAD/LESSON_GROUPS!
            using (workload)
            
            full join LESSON_GROUPS -- includes null lesson_groups in WORKLOAD
            -- inner join LESSON_GROUPS -- excludes null lesson_groups in WORKLOAD
            using (lesson_group)
            
            full join LESSONS using (lesson_group)
            --where lesson_group NOT NULL -- alternative way to filter out null lesson_groups
            where Course = {course_id}
    """
    # The uniqueness of a COURSES/WORKLOAD connection
    # should be enforced by the UNIQUE constraint on the
    # COURSE_WORKLOAD table ("course" + "workload" fields).
    records = db_select(q)
    # Sort according to type
    subjects = get_subjects()
    for rec in records:
        lg = rec["Lesson_group"]
        if lg:
            if (sid := rec["BLOCK_SID"]):
                rec["block_subject"] = subjects.map(sid)
                block_elements.append(rec)
            else:
                simple_elements.append(rec)
        else:
            workload_elements.append(rec)
    return (workload_elements, simple_elements, block_elements)


def workload_teacher(activity_list: list[Record]
) -> tuple[int, float]:
    """Calculate the total number of lessons and the pay-relevant
    workload.
    """
    # Each WORKLOAD entry must be counted only once, for all lessons,
    # so keep track:
    w2pay_lid2len = {}  # {workload: (pay-tag, {lid: length})}
    # Keep track of lessons: don't count blocks twice for plan time
    lidset = set()
    total = 0.0
    nlessons = 0
    for data in activity_list:
        w = data["Workload"]
        try:
            ptag, lid2len = w2pay_lid2len[w]
        except KeyError:
            ptag, lid2len = data["PAY_TAG"], {}
            w2pay_lid2len[w] = (ptag, lid2len)
        lid = data["Lid"]
        lessons = data["LENGTH"]
        lid2len[lid] = lessons
        if (lid) not in lidset:
            lidset.add(lid)
            nlessons += lessons
    for ptag, lid2len in w2pay_lid2len.values():
        lessons = sum(lid2len.values())
        pay = Workload.build(ptag).payment(lessons)
        total += pay
    return (nlessons, total)
 

def teacher_workload(activity_list: list[dict]) -> tuple[int, float]:
    """Calculate the total number of lessons and the pay-relevant
    workload.
    """
    print("! TODO: core.course_data.teacher_workload is deprecated."
        "Callers should be adapted to use workload_teacher instead."
    )

    # Each WORKLOAD entry must be counted only once, so keep track:
    wset = set()
    # Keep track of lesson-groups: don't count blocks twice for plan time
    lgset = set()
    total = 0.0
    nlessons = 0
    for data in activity_list:
        w = data["workload"]
        if w in wset: continue
        wset.add(w)
        lessons = 0
        for l in (data.get("lessons") or []):
            lessons += l["LENGTH"]
        if (lg := data["lesson_group"]) not in lgset:
            lgset.add(lg)
            nlessons += lessons
        pay = Workload.build(data["PAY_TAG"]).payment(lessons)
        total += pay
    return (nlessons, total)


def workload_class(klass:str, activity_list: list[tuple[str, Record]]
) -> list[tuple[str, int]]:
    """Calculate the total number of lessons for the pupils.
    The results should cover all (sub-)groups.
    """
    # Each LESSON in a LESSON_GROUP must be counted only once FOR EACH
    # GROUP, so keep track:
    lgsets = {}
    ag2lessons = {}
    class_groups = get_classes()[klass].divisions
    g2ags = class_groups.group_atoms()
    no_subgroups = not g2ags
    if no_subgroups:
        # Add whole-class target
        ag2lessons[GROUP_ALL] = 0
        lgsets[GROUP_ALL] = set()
    else:
        for ag in class_groups.atomic_groups:
            ag2lessons[ag] = 0
            lgsets[ag] = set()
    # Collect lessons per group
    for g, a in activity_list:
        assert g, "This function shouldn't receive activities with no group"
        lg = a["Lesson_group"]
        if not lg: continue # no lessons (payment-only entry)
        lid = a["Lid"]
        lg_l = (lg, lid)
        lessons = a["LENGTH"]
        if lessons:
            if no_subgroups:
                assert g == GROUP_ALL, "group in class without subgroups???"
                if lg_l in lgsets[GROUP_ALL]: continue
                lgsets[GROUP_ALL].add(lg_l)
                ag2lessons[GROUP_ALL] += lessons
            else:
                ags = lgsets.keys() if g == GROUP_ALL else g2ags[g]
                for ag in ags:
                    if lg_l in lgsets[ag]: continue
                    lgsets[ag].add(lg_l)
                    ag2lessons[ag] += lessons
    if no_subgroups:
        return [("", ag2lessons[GROUP_ALL])]
    # Simplify groups: seek primary groups which cover the various
    # numeric results
    # print("§ag2lessons:", ag2lessons)
    ln_lists = {}
    for ag, l in ag2lessons.items():
        try:
            ln_lists[l].add(ag)
        except KeyError:
            ln_lists[l] = {ag}
    results = []
    for l, agset in ln_lists.items():
        for g, ags in g2ags.items():
            if set(ags) == agset:
                results.append((g, l))
                break
        else:
            if set(class_groups.atomic_groups) == agset:
                g = ""
            else:
                g = f"<{','.join(sorted(agset))}>"
            results.append((g, l))
    results.sort()
    return results


def class_workload(klass:str, activity_list: list[tuple[str, dict]]
) -> list[tuple[str, int]]:
    """Calculate the total number of lessons for the pupils.
    The results should cover all (sub-)groups.
    """
    print("! TODO: core.course_data.class_workload is deprecated."
        "Callers should be adapted to use workload_class instead."
    )
    
    # Each LESSON_GROUPS entry must be counted only once FOR EACH GROUP,
    # so keep track:
    lgsets = {}
    ag2lessons = {}
    class_groups = get_classes()[klass].divisions
    g2ags = class_groups.group_atoms()
    no_subgroups = not g2ags
    if no_subgroups:
        # Add whole-class target
        ag2lessons[GROUP_ALL] = 0
        lgsets[GROUP_ALL] = set()
    else:
        for ag in class_groups.atomic_groups:
            ag2lessons[ag] = 0
            lgsets[ag] = set()
    # Collect lessons per group
    for g, data in activity_list:
        assert g, "This function shouldn't receive activities with no group"
        lg = data["lesson_group"]
        if not lg:  # no lessons (payment-only entry)
            continue
        lessons = 0
        for l in (data.get("lessons") or []):
            lessons += l["LENGTH"]
        if lessons:
            if no_subgroups:
                assert g == GROUP_ALL, "group in class without subgroups???"
                if lg in lgsets[GROUP_ALL]: continue
                lgsets[GROUP_ALL].add(lg)
                ag2lessons[GROUP_ALL] += lessons
            else:
                ags = lgsets.keys() if g == GROUP_ALL else g2ags[g]
                for ag in ags:
                    if lg in lgsets[ag]: continue
                    lgsets[ag].add(lg)
                    ag2lessons[ag] += lessons
    if no_subgroups:
        return [("", ag2lessons[GROUP_ALL])]
    # Simplify groups: seek primary groups which cover the various
    # numeric results
    # print("§ag2lessons:", ag2lessons)
    ln_lists = {}
    for ag, l in ag2lessons.items():
        try:
            ln_lists[l].add(ag)
        except KeyError:
            ln_lists[l] = {ag}
    results = []
    for l, agset in ln_lists.items():
        for g, ags in g2ags.items():
            if set(ags) == agset:
                results.append((g, l))
                break
        else:
            if set(class_groups.atomic_groups) == agset:
                g = ""
            else:
                g = f"<{','.join(sorted(agset))}>"
            results.append((g, l))
    results.sort()
    return results


######### for dialog_block_name #########

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


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    import time
    from core.db_access import open_database
    open_database()
    
    t0 = time.time()
    cmap = filter_activities("CLASS", "01G")
    t1 = time.time()
    total = 0
    for c in sorted(cmap):
        for r in cmap[c]:
            print(":::", r)
            total += 1

    print("\nNCOURSES:", len(cmap))
    print(f"Activities: {total} in {t1-t0} ms")
