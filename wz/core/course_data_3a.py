"""
core/course_data.py

Last updated:  2023-07-19

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

T = TRANSLATIONS("core.course_data")

### +++++

from core.db_access import (
    db_select,
    db_read_fields,
    db_query,
    Record,
)
from core.basic_data_3 import (
    get_classes,
    DECIMAL_SEP,
)
from core.classes import GROUP_ALL

### -----

def filter_activities(filter:str, value:str) -> dict[str, list[Record]]:
    """Seek COURSES and lessons/workload/payment info for the given
    course filter (CLASS, TEACHER or SUBJECT).

    Return: {course-id: [records]}

    NOTE how the parameters are set in various tables. The room-wish
    and pay details apply to all lesson components as they are set in
    COURSE_LESSONS. Only the time-wish is set in the lesson component.
    This may be a bit restrictive, but is perhaps reasonable for most
    cases. Normally only single simple or pay-only elements would be
    expected.

    A pay_tag_id may be shared by several "courses". The main idea
    behind this option is to facilitate combining groups (especially
    from different classes – within one class it is probably better to
    have a single group for this).
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
        coalesce(Cl_id, -1) Cl_id,
        coalesce(Lesson_group, -1) Lesson_group,
        coalesce(Lesson_data, 0) Lesson_data,
        coalesce(ROOM, '') ROOM,
        coalesce(PAY_NLESSONS, '0') PAY_NLESSONS,
        coalesce(PAY_TAG, '') PAY_TAG,
        coalesce(PAY_WEIGHT, '') PAY_WEIGHT,
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

        left join COURSE_LESSONS using (Course) -- includes "unused" courses
        left join LESSON_GROUPS using(Lesson_group)
        left join LESSON_DATA using(Lesson_data)
        left join PAY_FACTORS using (Pay_factor_id)

        -- do I really want to include the lessons here?
        left join LESSONS using (Lesson_group)  -- includes pay-only items

        where {filter} = '{value}'
        order by CLASS, SUBJECT, GRP, TEACHER
    """
    # Where a course has no associated "activities",field  Lesson_group
    # will be NULL (-> -1).
    records = db_select(q)
    course_map = {}
    for rec in records:
        c = rec["Course"]
        try:
            course_map[c].append(rec)
        except KeyError:
            course_map[c] = [rec]
    return course_map


def get_pay_value(adata: Record, nlessons: int) -> float:
    n = adata["PAY_NLESSONS"]
    ptag = adata["PAY_TAG"]
    pweight = adata.get("PAY_WEIGHT", "1")
    #print("$$$", nlessons, n, repr(ptag), pweight)
    try:
        if ptag:
            w = float(pweight.replace(',', '.'))
            ni = int(n)
            if ni < 0:
                return nlessons * w
            if ni > 50:
                raise ValueError
            return ni * w
        f = float(n.replace(',', '.'))
        if f < 0.0 or f > 50.0:
            raise ValueError
        return f
    except ValueError:
        REPORT(
            "ERROR",
            T["INVALID_PAY_TAG"].format(n=n, t=ptag, w=pweight)
        )
    return 0.0


def lesson_pay_display(data: Record, with_value=False) -> str:
    payval = get_pay_value(data, data.get('LENGTH', 1))
    if payval < 0.001:
        return ""
    t = data["PAY_TAG"]
    n = data["PAY_NLESSONS"]
    if not t:
        return n
    if with_value:
        val = f" ({payval:.3f})".replace('.', DECIMAL_SEP)
    else:
        val = ""
    if n[0] == '-':
        return f".*{t}{val}"
    return f"{int(n)}*{t}{val}"


def workload_teacher(activity_list: list[Record]) -> tuple[int, float]:
    """Calculate the total number of lessons and the pay-relevant
    workload.
    """
    # For counting lessons within a lesson-group:
    lg_map = {}
    # Keep track of lessons: each one should only be counted once
    lid_set = set()
    # Each LESSON_DATA entry must be counted only once, so keep track:
    ld_map = {}
    # Count lessons and pay units
    total = 0.0
    nlessons = 0
    for data in activity_list:
        lg = data["Lesson_group"]
        if lg < 0:
            continue
        ld_map[data["Lesson_data"]] = data
        if lg > 0:
            lid = data["Lid"]
            l = data["LENGTH"]
            # Only count this lid for <nlessons> once
            if lid not in lid_set:
                lid_set.add(lid)
                nlessons += l
                try:
                    lg_map[lg] += l
                except KeyError:
                    lg_map[lg] = l
    # Now go through the pay-tags
    for data in ld_map.values():
        lg = data["Lesson_group"]
        total += get_pay_value(data, lg_map[lg] if lg > 0 else 0.0)
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
        if lg <= 0: continue # no lessons (no activities or payment-only entry)
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
    #print("§ag2lessons:", ag2lessons)
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


######### for dialog_block_name and dialog_new_course_lesson #########

def courses_with_lesson_group(lesson_group):
    """Find all courses which have an entry for the given lesson-group.
    Return a list of <Record>s.
    """
    q = f"""select
            CLASS,
            GRP,
            SUBJECT,
            TEACHER,
            Lesson_data,
            coalesce(ROOM, '') ROOM,
            Course
        from COURSE_LESSONS
        inner join COURSES using(Course)
        inner join LESSON_DATA using(Lesson_data)
        where Lesson_group = {lesson_group}
    """
    return sorted(
        db_select(q),
        key=lambda x: (x["CLASS"], x["SUBJECT"], x["GRP"], x["TEACHER"])
    )


def courses_with_no_lessons(lesson_data):
    """Find all courses which have an entry for the given lesson-data.
    Return a list of <Record>s.
    """
    q = f"""select
            CLASS,
            GRP,
            SUBJECT,
            TEACHER,
            Lesson_data,
            Course
        from COURSE_LESSONS
        inner join COURSES using(Course)
        where Lesson_data = {lesson_data}
    """
    return sorted(
        db_select(q),
        key=lambda x: (x["CLASS"], x["SUBJECT"], x["GRP"], x["TEACHER"])
    )


def block_sids_in_class(klass):
    """Return a list of block subject ids already used in the given class.
    """
    q = f"""select distinct
        BLOCK_SID
        from COURSE_LESSONS
        inner join LESSON_GROUPS using(Lesson_group)
        inner join COURSES using(Course)
        where BLOCK_SID != '' and CLASS = '{klass}'
    """
    return [r[0] for r in db_query(q)]


def courses_in_block(bsid, btag, sid=None):
    """Find all courses which are members of the given block.
    If <sid> is passed, only consider the courses with this subject.
    Return a list of <Record>s.
    """
    x = "" if sid is None else f"and SUBJECT = '{sid}'"
    q = f"""select
            CLASS,
            GRP,
            SUBJECT,
            TEACHER,
            Lesson_data,
            coalesce(ROOM, '') ROOM,
            Course,
            Lesson_group,
            PAY_NLESSONS,
            Pay_factor_id
        from COURSE_LESSONS
        inner join COURSES using(Course)
        inner join LESSON_GROUPS using(Lesson_group)
        inner join LESSON_DATA using(Lesson_data)
        where BLOCK_SID = '{bsid}' and BLOCK_TAG = '{btag}' {x}
    """
    return sorted(
        db_select(q),
        key=lambda x: (x["CLASS"], x["SUBJECT"], x["GRP"], x["TEACHER"])
    )


def simple_with_subject(sid):
    """Find all courses with simple lessons in the given subject.
    Return a list of <Record>s.
    """
    q = f"""select
            CLASS,
            GRP,
            SUBJECT,
            TEACHER,
            Lesson_data,
            coalesce(ROOM, '') ROOM,
            Course,
            Lesson_group,
            PAY_NLESSONS,
            Pay_factor_id
        from COURSE_LESSONS
        inner join COURSES using(Course)
        inner join LESSON_GROUPS using(Lesson_group)
        inner join LESSON_DATA using(Lesson_data)
        where Lesson_group != 0 and BLOCK_SID = '' and SUBJECT = '{sid}'
    """
    return sorted(
        db_select(q),
        key=lambda x: (x["CLASS"], x["SUBJECT"], x["GRP"], x["TEACHER"])
    )


def payonly_with_subject(sid):
    """Find all courses with pay-only elements in the given subject.
    Return a list of <Record>s.
    """
    q = f"""select
            CLASS,
            GRP,
            SUBJECT,
            TEACHER,
            Lesson_data,
            coalesce(ROOM, '') ROOM,
            Course,
            Lesson_group,
            PAY_NLESSONS,
            Pay_factor_id
        from COURSE_LESSONS
        inner join COURSES using(Course)
        inner join LESSON_DATA using(Lesson_data)
        where Lesson_group = 0 and Lesson_data != 0 and SUBJECT = '{sid}'
    """
    return sorted(
        db_select(q),
        key=lambda x: (x["CLASS"], x["SUBJECT"], x["GRP"], x["TEACHER"])
    )


def read_block_sid_tags():
    """Get mapping from BLOCK_SID to the list of defined BLOCK_TAGs
    for that subject. Also the lesson_group is included:
        {BLOCK_SID: (BLOCK_TAG, lesson_group), ... }
    """
    bst = {}
    for lg, BLOCK_SID, BLOCK_TAG in db_read_fields(
        "LESSON_GROUPS", ("Lesson_group", "BLOCK_SID", "BLOCK_TAG")
    ):
        if BLOCK_SID:
            tag_lg = (BLOCK_TAG, lg)
            try:
                bst[BLOCK_SID].add(tag_lg)
            except KeyError:
                bst[BLOCK_SID] = {tag_lg}
    # Sort the resulting list
    return {k: sorted(v) for k, v in bst.items()}


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    import time
    from core.db_access import open_database
    open_database("wz_db.sqlite")

    t0 = time.time()
    cmap = filter_activities("CLASS", "01G")
    t1 = time.time()
    total = 0
    for c in sorted(cmap):
        for r in cmap[c]:
            print(":::", r)
            total += 1

    print("\nNCOURSES:", len(cmap))
    print(f"Activities: {total} in {t1-t0} s")

    print("\n  *** courses_in_block ***")
    t0 = time.time()
    for r in courses_in_block("Hu", "OS"):
        print("    --", r)
    t1 = time.time()
    print(f"\n  in: {t1-t0} s")

    print("\n  *** simple_with_subject ***")
    t0 = time.time()
    for r in simple_with_subject("Ma"):
        print("    --", r)
    t1 = time.time()
    print(f"\n  in: {t1-t0} s")

    print("\n  *** payonly_with_subject ***")
    t0 = time.time()
    for r in payonly_with_subject("Kl"):
        print("    --", r)
    t1 = time.time()
    print(f"\n  in: {t1-t0} s")
