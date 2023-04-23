"""
core/list_activities.py

Last updated:  2023-04-23

Present information on activities for teachers and classes/groups.
The information is formatted in pdf documents using the reportlab
library.

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
from core.classes import Subgroup
from core.basic_data import (
    Workload,
    BlockTag,
    get_subjects,
    get_teachers,
    get_classes,
)
from core.db_access import db_read_fields
from core.course_data import WHOLE_CLASS, WHOLE_CLASS_SG
import lib.pylightxl as xl
from tables.pdf_table import TablePages

DECIMAL_SEP = CONFIG["DECIMAL_SEP"]
        
### -----


def PAY_FORMAT(pay):
    if type(pay) == float:
        return f"{pay:.3f}".replace(".", DECIMAL_SEP)
    else:
        return pay


class ActivityItem(NamedTuple):
    course_data: tuple[str, str, str, str] # class, group, subject, teacher
    workload: int
    lesson_group: int
    blocktag: Optional[BlockTag]
    lessons: list[int]
    paytag: Optional[Workload]
    room: str


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
        data = ActivityItem(cdata, w, lg, bt, ll, p, r)
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
        klass, group, sid, tid = data.course_data
        lessons = data.lessons
        t_lessons = ','.join(str(l) for l in lessons)
        pdata = pay_data(data.paytag, (nlessons := sum(lessons)))
        if data.blocktag:
            bs = data.blocktag.subject
            bt = data.blocktag.tag
        else:
            bs, bt = "", ""
        tdata = TeacherData(
            klass,
            bs,
            bt,
            subjects.map(sid),
            group,
            data.room,
            t_lessons,
            nlessons,
            data.workload,
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
        if group == WHOLE_CLASS:
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
        klass, group, sid, tid = data.course_data
        lessons = data.lessons
        nlessons = sum(lessons)
        t_lessons = ','.join(str(l) for l in lessons)
        if data.blocktag:
            bs = data.blocktag.subject
            bt = data.blocktag.tag
        else:
            bs, bt = "", ""
        cdata = ClassData(
            subjects.map(sid),
            group,
            tid,
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
        fag2lessons = {}
        class_groups = get_classes()[c].divisions
        g2fags = class_groups.group2atoms
        no_subgroups = not class_groups.filtered_atomic_groups
        if no_subgroups:
            # Add whole-class target
            fag2lessons[WHOLE_CLASS_SG] = 0
            lgsets[WHOLE_CLASS_SG] = set()
        else:
            for fag in class_groups.filtered_atomic_groups:
                fag2lessons[fag] = 0
                lgsets[fag] = set()
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
                if g == WHOLE_CLASS and no_subgroups:
                    if lg not in lgsets[WHOLE_CLASS_SG]:
                        lgsets[WHOLE_CLASS_SG].add(lg)
                        fag2lessons[WHOLE_CLASS_SG] += lessons
                else:
                    for fag in g2fags[Subgroup(g.split('.'))]:
                        if lg not in lgsets[fag]:
                            lgsets[fag].add(lg)
                            fag2lessons[fag] += lessons
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
            ln = fag2lessons.pop(WHOLE_CLASS_SG)
            assert not fag2lessons, "group lessons in class without subgroups???"
            group_data = [("", ln)]
        else:
            # Simplify groups
            ln_lists = {}
            for fag, l in fag2lessons.items():
                try:
                    ln_lists[l].append(fag)
                except KeyError:
                    ln_lists[l] = [fag]
            fags2g = class_groups.atoms2group
            group_data = []
            for l, fags in ln_lists.items():
                g = str(fags2g[frozenset(fags)])
                if g == WHOLE_CLASS:
                    assert len(ln_lists) == 1, "WHOLE_CLASS *and* group lessons???"
                    group_data = [("", l)]
                    break
                group_data.append((str(fags2g[frozenset(fags)]), l))
            else:
                group_data.sort()
        # Total
        lastcol = len(headers)
        for g, l in group_data:
            sheet.update_index(row=row_id, col=lastcol, val=l)
            sheet.update_index(
                row=row_id,
                col=lastcol - 1,
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
        pay_total = 0.0
        for item in items:
            w = item.workgroup
            if w in workgroups:
                workgroups[w] = 1
            else:
                workgroups[w] = 0
                pay_total += item.pay
        # pdf.add_paragraph(f"Deputat, insgesamt: {PAY_FORMAT(pay_total)}")
        # pdf.add_vspace(5)

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
        pay_total = 0.0
        for item in items:
            w = item.workgroup
            if w in workgroups:
                workgroups[w] = 1
            else:
                workgroups[w] = 0
                pay_total += item.pay
        pdf.add_paragraph(f"Deputat, insgesamt: {PAY_FORMAT(pay_total)}")
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
        # Calculate the total number of lessons for the pupils.
        # The results should cover all (sub-)groups.
        # Each LESSON_GROUPS entry must be counted only once FOR
        # EACH GROUP, so keep track:
        lgsets = {}
        fag2lessons = {}
        class_groups = class_data.divisions
        g2fags = class_groups.group2atoms
        no_subgroups = not class_groups.filtered_atomic_groups
        if no_subgroups:
            # Add whole-class target
            fag2lessons[WHOLE_CLASS_SG] = 0
            lgsets[WHOLE_CLASS_SG] = set()
        else:
            for fag in class_groups.filtered_atomic_groups:
                fag2lessons[fag] = 0
                lgsets[fag] = set()
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
                simplelessons.append((
                    data.subject,
                    data.group,
                    data.teacher_id,
                    "",
                    data.lessons,
                ))

            # Allocate the lessons to the minimal subgroups
            if (
                (g := data.group)
                and (lg := data.lesson_group)
                and (lessons := data.nlessons)
            ):
                if g == WHOLE_CLASS and no_subgroups:
                    if lg not in lgsets[WHOLE_CLASS_SG]:
                        lgsets[WHOLE_CLASS_SG].add(lg)
                        fag2lessons[WHOLE_CLASS_SG] += lessons
                else:
                    for fag in g2fags[Subgroup(g.split('.'))]:
                        if lg not in lgsets[fag]:
                            lgsets[fag].add(lg)
                            fag2lessons[fag] += lessons

        # Collate the lesson counts
        if no_subgroups:
            ln = fag2lessons.pop(WHOLE_CLASS_SG)
            assert not fag2lessons, "group lessons in class without subgroups???"
            group_data = [("", ln)]
        else:
            # Simplify groups
            ln_lists = {}
            for fag, l in fag2lessons.items():
                try:
                    ln_lists[l].append(fag)
                except KeyError:
                    ln_lists[l] = [fag]
            fags2g = class_groups.atoms2group
            group_data = []
            for l, fags in ln_lists.items():
                g = str(fags2g[frozenset(fags)])
                if g == WHOLE_CLASS:
                    assert len(ln_lists) == 1, "WHOLE_CLASS *and* group lessons???"
                    group_data = [("", l)]
                    break
                group_data.append((str(fags2g[frozenset(fags)]), l))
            else:
                group_data.sort()

        # Total
        if len(group_data) == 1:
            gl = [group_data[0][1]]
        else:
            gl = [f"{g}: {l}" for g, l in group_data]
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
    filepath = saveDialog("pdf-Datei (*.pdf)", T["teacher_workload_pay"])
    if filepath and os.path.isabs(filepath):
        if not filepath.endswith(".pdf"):
            filepath += ".pdf"
        with open(filepath, "wb") as fh:
            fh.write(pdfbytes)
        print("  --->", filepath)

    pdfbytes = make_teacher_table_room(t_lists)
    filepath = saveDialog("pdf-Datei (*.pdf)", T["teacher_activities"])
    if filepath and os.path.isabs(filepath):
        if not filepath.endswith(".pdf"):
            filepath += ".pdf"
        with open(filepath, "wb") as fh:
            fh.write(pdfbytes)
        print("  --->", filepath)

    pdfbytes = make_class_table_pdf(cl_lists, lg_2_c)
    filepath = saveDialog("pdf-Datei (*.pdf)", T["class_lessons"])
    if filepath and os.path.isabs(filepath):
        if not filepath.endswith(".pdf"):
            filepath += ".pdf"
        with open(filepath, "wb") as fh:
            fh.write(pdfbytes)
        print("  --->", filepath)

#    quit(0)

    tdb = make_teacher_table_xlsx(t_lists)

    filepath = saveDialog("Excel-Datei (*.xlsx)", "Deputate")
    if filepath and os.path.isabs(filepath):
        if not filepath.endswith(".xlsx"):
            filepath += ".xlsx"
        xl.writexl(db=tdb, fn=filepath)
        print("  --->", filepath)

    cdb = make_class_table_xlsx(cl_lists)

    filepath = saveDialog("Excel-Datei (*.xlsx)", "Klassenstunden")
    if filepath and os.path.isabs(filepath):
        if not filepath.endswith(".xlsx"):
            filepath += ".xlsx"
        xl.writexl(db=cdb, fn=filepath)
        print("  --->", filepath)
