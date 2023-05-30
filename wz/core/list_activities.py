"""
core/list_activities.py

Last updated:  2023-05-30

Present information on activities for teachers and classes/groups.
The information is formatted in pdf documents using the reportlab
library.
Also (unformatted) xlsx spreadsheets can be exported.

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

T = TRANSLATIONS("core.list_activities")

### +++++

from typing import NamedTuple, Optional
from io import BytesIO

from core.base import class_group_join
from core.classes import GROUP_ALL
from core.basic_data import (
    Workload,
    BlockTag,
    get_subjects,
    get_teachers,
    get_classes,
)
from core.db_access import db_read_fields
from core.activities import read_db, ActivityItem
import lib.pylightxl as xl
from tables.pdf_table import TablePages

DECIMAL_SEP = CONFIG["DECIMAL_SEP"]

### -----


def PAY_FORMAT(pay):
    if type(pay) == float:
        return f"{pay:.3f}".replace(".", DECIMAL_SEP)
    else:
        return pay


class TeacherData(NamedTuple):
    klass: str
    block_subject: str
    block_tag: str
    subject: str
    group: str
    room: str
    lessons: str
    nlessons: int
    workgroup: int  # the WORKLOAD index
    lesson_group: int
    paynum: str     # for blocks/"Epochen" *can* be the number
    paystr: str
    pay: float


class ClassData(NamedTuple):
    subject: str
    group: str
    teacher_id: str
    block_subject: str
    block_tag: str
    workgroup: int      # the WORKLOAD index
    lesson_group: int   # the LESSON_GROUPS index
    room: str
    lessons: str
    nlessons: int
    paystr: str         #TODO: not reliable for pay if combined groups!


def pay_data(paytag, nlessons):
    """Process the workload/payment data into a display form.
    """
    t_pay = paytag.PAYMENT
    if paytag.PAY_FACTOR_TAG:
        if paytag.NLESSONS == -1:
            t_paystr = f"[{nlessons}] x {paytag.PAY_FACTOR_TAG}"
            if nlessons > 0:
                t_pay = paytag.PAY_FACTOR * nlessons
        else:
            t_paystr = f"{paytag.NLESSONS} x {paytag.PAY_FACTOR_TAG}"
    else:
        t_paystr = ""
    return (str(paytag.NLESSONS), t_paystr, t_pay)  # str, str, float


def teacher_list(tlist: list[ActivityItem]):
    """Deal with the data for a single teacher. Return the data needed
    for a lesson + pay list sorted according to class and subject.
    """
    courses = []
    subjects = get_subjects()
    for data in tlist:
        lessons = data.lessons
        t_lessons = ','.join(str(l) for l in lessons)
        pdata = pay_data(data.paytag, (nlessons := sum(lessons)))
        if data.blocktag:
            bs = data.blocktag.subject
            bt = data.blocktag.tag
        else:
            bs, bt = "", ""
        tdata = TeacherData(
            data.klass,
            bs,
            bt,
            subjects.map(data.subject),
            data.group,
            data.room,
            t_lessons,
            nlessons,
            data.workload,
            data.lesson_group,
            *pdata
        )
        courses.append(tdata)
    courses.sort()
    return courses


def print_class_group(klass, group):
    """Return a representation of the class and group for the
    teacher-lists.
    If there is no group, return the class in brackets.
    If the group is the whole class, just return the class.
    Otherwise return the standard form for class + cgroup.
    """
    if group:
        if group == GROUP_ALL:
            return klass
        return class_group_join(klass, group)
    return f"({klass})"


def class_list(clist: list[ActivityItem]):
    """Deal with the data for a single class. Return the data needed
    for a lesson + teacher list sorted according to subject.
    """
    subjects = get_subjects()
    courses = []
    for data in clist:
        lessons = data.lessons
        nlessons = sum(lessons)
        t_lessons = ','.join(str(l) for l in lessons)
        if data.blocktag:
            bs = data.blocktag.subject
            bt = data.blocktag.tag
        else:
            bs, bt = "", ""
        cdata = ClassData(
            subjects.map(data.subject),
            data.group,
            data.teacher,
            bs,
            bt,
            data.workload,
            data.lesson_group,
            data.room,  #?
            t_lessons,
            nlessons,
            pay_data(data.paytag, nlessons)[1] # pay string
        )
        courses.append(cdata)
    courses.sort()
    return courses


def write_xlsx(xl_db, filepath):
    """Write a pylightxl "database" to the given path.
    """
    xl.writexl(db=xl_db, fn=filepath)


def make_teacher_table_xlsx(activity_lists):
    headers = [
        "H_class",
        "H_block_subject",
        "H_block_tag",
        "H_subject",
        "H_group",
        "H_room",
        "H_units",
        "H_team",
        "H_npay",
        "H_workload",
        "H_pay",
    ]
    db = xl.Database()
    teachers = get_teachers()
    for t in teachers:
        try:
            datalist = activity_lists[t]
        except KeyError:
            continue    # skip teachers without entries
        tname = teachers.name(t)
        items = teacher_list(datalist)
        # Add "worksheet" to table builder
        db.add_ws(ws=tname)
        sheet = db.ws(ws=tname)
        for col_id, field in enumerate(headers, start=1):
            sheet.update_index(row=1, col=col_id, val=T[field])
        # Add data to spreadsheet table
        row_id = 2
        pay_total = 0.0
        workgroups = set()
        for line in items:
            if line.workgroup in workgroups:
                line = line._replace(paynum="", paystr="*", pay="")
            else:
                workgroups.add(line.workgroup)
                pay_total += line.pay
            for col_id, field in enumerate(line, start=1):
                sheet.update_index(row=row_id, col=col_id, val=field)
            row_id += 1
        # Total
        lastcol = len(headers)
        sheet.update_index(row=row_id, col=lastcol, val=pay_total)
        sheet.update_index(row=row_id, col=lastcol - 1, val="insgesamt")
    return db


def make_class_table_xlsx(activity_lists):
    db = xl.Database()
    headers = [
        "H_subject",
        "H_group",
        "H_teacher",
        "H_block_subject",
        "H_block_tag",
        "H_team",
        "H_room",
        "H_units",
        "H_lessons"
    ]
    # teachers = get_teachers()
    for c in sorted(activity_lists):
        datalist = activity_lists[c]
        items = class_list(datalist)
        # Calculate the total number of lessons for the pupils.
        # The results should cover all (sub-)groups.
        # Each LESSON_GROUPS entry must be counted only once FOR
        # EACH GROUP, so keep track:
        lgsets = {}
        ag2lessons = {}
        class_groups = get_classes()[c].divisions
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
        # Add "worksheet" to table builder
        db.add_ws(ws=c)
        sheet = db.ws(ws=c)
        for col_id, field in enumerate(headers, start=1):
            sheet.update_index(row=1, col=col_id, val=T[field])
        row_id = 2
        for data in items:
            # Allocate the lessons to the minimal subgroups
            if (
                (g := data.group)
                and (lg := data.lesson_group)
                and (lessons := data.nlessons)
            ):
                if no_subgroups:
                    assert g == GROUP_ALL, (
                        f"group ({g}) lessons in class ({klass})"
                        " without subgroups???"
                    )
                    if lg in lgsets[GROUP_ALL]: continue
                    lgsets[GROUP_ALL].add(lg)
                    ag2lessons[GROUP_ALL] += lessons
                else:
                    ags = lgsets.keys() if g == GROUP_ALL else g2ags[g]
                    for ag in ags:
                        if lg in lgsets[ag]: continue
                        lgsets[ag].add(lg)
                        ag2lessons[ag] += lessons
            # Gather the display info for this line
            line = [
                data.subject,
                data.group,
                data.teacher_id,
                data.block_subject,
                data.block_tag,
                data.workgroup,
                data.room,
                data.lessons,
                data.paystr,
            ]
            for col_id, field in enumerate(line, start=1):
                sheet.update_index(row=row_id, col=col_id, val=field)
            row_id += 1
        # Collate the lesson counts
        if no_subgroups:
            results = [("", ag2lessons[GROUP_ALL])]
        else:
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
        # Total
        lastcol = len(headers)
        for g, l in results:
            sheet.update_index(row=row_id, col=lastcol, val=l)
            sheet.update_index(
                row=row_id,
                col=lastcol - 1,
#TODO: T ...
                val=g if g else "insgesamt"
            )
            row_id += 1
    return db


def make_teacher_table_room(activity_lists):
    """Construct a pdf with a table for each teacher, each such table
    starting on a new page.
    The sorting within a teacher table is first class, then block,
    then subject.
    """
    def add_simple_items():
        for item in noblocklist:
            # The "team" tag is shown only when it is referenced later
            pdf.add_line(item)
        noblocklist.clear()

    headers = []
    colwidths = []
    for h, w in (
        ("H_team_tag",          15),
        ("H_group",             20),
        ("H_subject",           60),
        ("H_units",             35),
        ("H_room",              40),
    ):
        headers.append(T[h])
        colwidths.append(w)

    pdf = TablePages(
        title=T["teacher_activities"],
        author=CONFIG["SCHOOL_NAME"],
        headers=headers,
        colwidths=colwidths,
        align=((1, "l"), (2, "p")),
    )

    noblocklist = []
    teachers = get_teachers()
    for t in teachers:
        try:
            datalist = activity_lists[t]
        except KeyError:
            continue    # skip teachers without entries
        tname = teachers.name(t)
        pdf.add_page(tname)
        items = teacher_list(datalist)

        workgroups = {} # for detecting parallel groups
        lesson_groups = set()
        pay_total = 0.0
        lessons_total = 0
        for item in items:
            w = item.workgroup
            if w in workgroups:
                workgroups[w] = 1
            else:
                workgroups[w] = 0
                pay_total += item.pay
            if item.lesson_group not in lesson_groups:
                lesson_groups.add(item.lesson_group)
                lessons_total += item.nlessons
#        pdf.add_text(
##TODO: T ...
#            f"Deputat, insgesamt: {PAY_FORMAT(pay_total)}"
#            f"   &   Stundenplanbelegung: {lessons_total}"
#        )
        pdf.add_text(
#TODO: T ...
            f"Stundenplanbelegung: {lessons_total}"
        )
        pdf.add_vspace(5)

        klass = None
        for item in items:
            # The "team" tag is shown only when it is referenced later
            if workgroups[item.workgroup] > 0:
                ## first time, show workgroup
                w = f"[{item.workgroup}]"
                workgroups[item.workgroup] = -1
                ref = ""
                room = item.room
            elif workgroups[item.workgroup] < 0:
                ## second time, show reference to workgroup
                ref = f"→ [{item.workgroup}]"
                w = ""
                room = ""
            else:
                ref = ""
                w = ""
                room = item.room

            if item.klass != klass:
                add_simple_items()
                # Add space before new class
                pdf.add_line()
                klass = item.klass

            # Combine class and group
            cg = print_class_group(item.klass, item.group)
            if item.block_subject:
                ## Add block item
                if ref:
                    t_lessons = ref
                else:
                    t_lessons = item.lessons
                    try:
                        n = int(item.paynum)
                        if (n > 0) and (n != item.nlessons):
                            t_lessons += f" [{n}]"
                    except ValueError:
                        pass
                pdf.add_line((
                    w,
                    cg,
                    f"{item.block_subject}::{item.subject}",
                    t_lessons,
                    room,
                ))
            else:
                noblocklist.append(
                    (w, cg, item.subject, ref or item.lessons, room)
                )
        if noblocklist:
            add_simple_items()
        # Add space before final underline
        pdf.add_line()
    return pdf.build_pdf()


def make_teacher_table_pay(activity_lists):
    """Construct a pdf with a table for each teacher, each such table
    starting on a new page.
    The sorting within a teacher table is first class, then block,
    then subject.
    """
    def add_simple_items():
        for item in noblocklist:
            # The "team" tag is shown only when it is referenced later
            pdf.add_line(item)
        noblocklist.clear()

    headers = []
    colwidths = []
    for h, w in (
        ("H_team_tag",          15),
        ("H_group",             20),
        ("H_subject",           60),
        ("H_units",             30),
        ("H_workload",          25),
        ("H_pay",               20),
    ):
        headers.append(T[h])
        colwidths.append(w)

    pdf = TablePages(
        title=T["teacher_workload_pay"],
        author=CONFIG["SCHOOL_NAME"],
        headers=headers,
        colwidths=colwidths,
        align=((5, "r"), (1, "l"), (2, "p")),
    )

    noblocklist = []
    teachers = get_teachers()
    for t in teachers:
        try:
            datalist = activity_lists[t]
        except KeyError:
            continue    # skip teachers without entries
        tname = teachers.name(t)
        pdf.add_page(tname)
        items = teacher_list(datalist)

        workgroups = {} # for detecting parallel groups
        lesson_groups = set()
        pay_total = 0.0
        lessons_total = 0
        for item in items:
            w = item.workgroup
            if w in workgroups:
                workgroups[w] = 1
            else:
                workgroups[w] = 0
                pay_total += item.pay
            if item.lesson_group not in lesson_groups:
                lesson_groups.add(item.lesson_group)
                lessons_total += item.nlessons
        pdf.add_text(
#TODO: T ...
            f"Deputat, insgesamt: {PAY_FORMAT(pay_total)}"
            f"   &   Stundenplanbelegung: {lessons_total}"
        )
        pdf.add_vspace(5)

        klass = None
        for item in items:
            # The "team" tag is shown only when it is referenced later
            if workgroups[item.workgroup] > 0:
                # first time, show pay and workgroup
                paystr = item.paystr
                pay = PAY_FORMAT(item.pay)
                w = f"[{item.workgroup}]"
                workgroups[item.workgroup] = -1
            elif workgroups[item.workgroup] < 0:
                # second time, show reference to workgroup
                paystr = f"→ [{item.workgroup}]"
                pay = ""
                w = ""
            else:
                paystr = item.paystr
                pay = PAY_FORMAT(item.pay)
                w = ""

            if item.klass != klass:
                add_simple_items()
                # Add space before new class
                pdf.add_line(("",) * 6)
                klass = item.klass

            # Combine class and group
            cg = print_class_group(item.klass, item.group)
            if item.block_subject:
                ## Add block item
                pdf.add_line((
                    w,
                    cg,
                    f"{item.block_subject}::{item.subject}",
                    item.lessons,
                    paystr,
                    pay,
                ))
            else:
                noblocklist.append(
                    (w, cg, item.subject, item.lessons, paystr, pay)
                )
        if noblocklist:
            add_simple_items()
        # Add space before final underline
        pdf.add_line(("",) * 6)
    return pdf.build_pdf()


def make_class_table_pdf(activity_lists, lg_2_c):
    headers = []
    colwidths = []
    for h, w in (
        ("H_subject",           80),
        ("H_group",             20),
        ("H_teacher",           20),
        ("H_lessons",           20),
        ("H_units",             30),
    ):
        headers.append(T[h])
        colwidths.append(w)

    pdf = TablePages(
        title=T["class_lessons"],
        author=CONFIG["SCHOOL_NAME"],
        headers=headers,
        colwidths=colwidths,
        align=((0, "p"), (4, "r")),
    )

    classes = get_classes()
    for klass in sorted(activity_lists):
        datalist = activity_lists[klass]
        items = class_list(datalist)
        class_data = classes[klass]
        w_set = set()   # to keep track of WORKLOAD indexes
        # Calculate the total number of lessons for the pupils.
        # The results should cover all (sub-)groups.
        # Each LESSON_GROUPS entry must be counted only once FOR
        # EACH GROUP, so keep track:
        lgsets = {}
        ag2lessons = {}
        class_groups = class_data.divisions
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
        # Add page to table builder
        pdf.add_page(f"{klass}: {class_data.name}")
        lessonblocks = {}
        simplelessons = []
        for data in items:
            # Gather the display info for this line
            if data.block_subject:
                line = (
                    f"\u00A0\u00A0– {data.subject}",
                    data.group,
                    data.teacher_id,
                    data.paystr,
                    "",
                )
                try:
                    lbtagmap = lessonblocks[data.block_subject]
                except KeyError:
                    lessonblocks[data.block_subject] = (lbtagmap := {})
                try:
                    lbtagmap[data.block_tag].append(line)
                except KeyError:
                    # find parallel classes
                    clset = {c[0] for c in lg_2_c[data.lesson_group]}
                    clset.remove(klass)
                    s = f"{data.block_subject}#" # substitute '#' later
                    if clset:
                        s = f"{s} // {','.join(sorted(clset))}"
#TODO: should the (total) group be determined and shown?
# If not, could span the columns ...
                    bline = [s, "", "", "", data.lessons]
                    lbtagmap[data.block_tag] = [bline, line]

            else:
                # Manage "teams"
                if data.workgroup in w_set:
                    l = f"({data.lessons})"
                else:
                    w_set.add(data.workgroup)
                    l = data.lessons
                simplelessons.append((
                    data.subject,
                    data.group,
                    data.teacher_id,
                    "",
                    l,
                ))
            # Allocate the lessons to the minimal subgroups
            if (
                (g := data.group)
                and (lg := data.lesson_group)
                and (lessons := data.nlessons)
            ):
                if no_subgroups:
                    assert g == GROUP_ALL, (
                        f"group ({g}) lessons in class ({klass})"
                        " without subgroups???"
                    )
                    if lg in lgsets[GROUP_ALL]: continue
                    lgsets[GROUP_ALL].add(lg)
                    ag2lessons[GROUP_ALL] += lessons
                else:
                    ags = lgsets.keys() if g == GROUP_ALL else g2ags[g]
                    for ag in ags:
                        if lg in lgsets[ag]: continue
                        lgsets[ag].add(lg)
                        ag2lessons[ag] += lessons
        # Collate the lesson counts
        if no_subgroups:
            results = [("", ag2lessons[GROUP_ALL])]
        else:
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
        # Total
        if len(results) == 1:
            gl = [results[0][1]]
        else:
            gl = [f"{g}: {l}" for g, l in results]
        pdf.add_list_table(
            (T["total_lessons"], *gl),
            skip0=True,
            ncols=8,
        )
        pdf.add_vspace(5)   # mm

        ## Add table, first blocks, then simple lessons
        pdf.add_line()
        for bs in sorted(lessonblocks):
            btmap = lessonblocks[bs]
            for bt, lines in btmap.items():
                l = lines[0]
                sx = " #{bt}" if len(btmap) > 1 else ""
                l[0] = l[0].replace('#', sx)
                for line in lines:
                    pdf.add_line(line)
        for line in simplelessons:
            pdf.add_line(line)

        # Add space before final underline
        pdf.add_line()
    return pdf.build_pdf()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    from ui.ui_base import saveDialog

    open_database()
    cl_lists, t_lists, lg_2_c = read_db()

    pdfbytes = make_teacher_table_pay(t_lists)
    filepath = saveDialog("pdf-Datei (*.pdf)", "Deputate")
    if filepath and os.path.isabs(filepath):
        if not filepath.endswith(".pdf"):
            filepath += ".pdf"
        with open(filepath, "wb") as fh:
            fh.write(pdfbytes)
        print("  --->", filepath)

    pdfbytes = make_teacher_table_room(t_lists)
    filepath = saveDialog("pdf-Datei (*.pdf)", "Lehrer-Stunden")
    if filepath and os.path.isabs(filepath):
        if not filepath.endswith(".pdf"):
            filepath += ".pdf"
        with open(filepath, "wb") as fh:
            fh.write(pdfbytes)
        print("  --->", filepath)

    pdfbytes = make_class_table_pdf(cl_lists, lg_2_c)
    filepath = saveDialog("pdf-Datei (*.pdf)", "Klassen-Stunden")
    if filepath and os.path.isabs(filepath):
        if not filepath.endswith(".pdf"):
            filepath += ".pdf"
        with open(filepath, "wb") as fh:
            fh.write(pdfbytes)
        print("  --->", filepath)

    tdb = make_teacher_table_xlsx(t_lists)
    filepath = saveDialog("Excel-Datei (*.xlsx)", "Deputate")
    if filepath and os.path.isabs(filepath):
        if not filepath.endswith(".xlsx"):
            filepath += ".xlsx"
        xl.writexl(db=tdb, fn=filepath)
        print("  --->", filepath)

    cdb = make_class_table_xlsx(cl_lists)
    filepath = saveDialog("Excel-Datei (*.xlsx)", "Klassen-Stunden")
    if filepath and os.path.isabs(filepath):
        if not filepath.endswith(".xlsx"):
            filepath += ".xlsx"
        xl.writexl(db=cdb, fn=filepath)
        print("  --->", filepath)
