"""
core/list_activities.py

Last updated:  2023-04-16

Present information on activities for teachers and classes/groups.
The information is formatted in pdf documents using the reportlab
library.

=+LICENCE=============================
Copyright 2022 Michael Towers

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
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    PageBreak,
    Table,
    TableStyle,
)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth

from core.base import class_group_join
from core.basic_data import (
    Workload,
    BlockTag,
    get_subjects,
    get_teachers,

#? ...
    get_group_info,
    get_classes,
    sublessons,
)
from core.db_access import db_read_fields
from core.course_data import WHOLE_CLASS
import lib.pylightxl as xl

DECIMAL_SEP = CONFIG["DECIMAL_SEP"]

### -----

class ActivityItem(NamedTuple):
    course_data: tuple[str, str, str, str]
    workload: int
    lesson_group: int
    blocktag: Optional[BlockTag]
    lessons: list[int]
    paytag: Optional[str] # ??? Object?
    room: str


class TeacherData(NamedTuple):
    klass: str
    subject: str
    group: str
    blocktag: Optional[BlockTag]
    workgroup: int  # the WORKLOAD index
    room: str
    lessons: str
    paynum: int     # for blocks/"Epochen" *can* be the number
    paystr: str
    pay: float


class ClassData(NamedTuple):
    subject: str
    group: str
    teacher_id: str
    blocktag: Optional[BlockTag]
    workgroup: int  # the WORKLOAD index
    room: str
    lessons: str
    nlessons: int


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
    return (cl_lists, t_lists)


def teacher_list(tlist: list[ActivityItem]):
    """Deal with the data for a single teacher. Return the data needed
    for a lesson + pay list sorted according to class and subject.
    """
    subjects = get_subjects()
    courses = []
    for data in tlist:
        klass, group, sid, tid = data.course_data
        lessons = data.lessons
        nlessons = sum(lessons)
        t_lessons = ','.join(str(l) for l in lessons)
        paytag = data.paytag
        t_pay = paytag.PAYMENT
        if paytag.PAY_FACTOR_TAG:
            if paytag.NLESSONS == -1:
                t_paystr = f"{nlessons} x {paytag.PAY_FACTOR_TAG}"
                if nlessons > 0:
                    t_pay = paytag.PAY_FACTOR * nlessons
            else:
                t_paystr = f"{paytag.NLESSONS} x {paytag.PAY_FACTOR_TAG}"
        else:
            t_paystr = ""
        tdata = TeacherData(
            klass,
            subjects.map(sid),
            group,
            data.blocktag,
            data.workload,
            data.room,
            t_lessons,
            paytag.NLESSONS,    # for blocks/"Epochen" *can* be the number
            t_paystr,
            t_pay
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
        cdata = ClassData(
            subjects.map(sid),
            group,
            tid,
            data.blocktag,
            data.workload,
            data.room,  #?
            t_lessons,
            nlessons,
        )
        courses.append(cdata)
    courses.sort()
    return courses


#TODO ...



def print_rooms(rooms):
    r = "|".join(rooms)
    if len(r) > 14:
        return r[:11] + " ..."
    return r


def print_subject(subject):
    if len(subject) > 18:
        return subject[:15] + " ..."
    return subject


def print_xsubject(subject):
    if len(subject) > 28:
        return subject[:25] + " ..."
    return subject


def ljtrim(text, n):
    if len(text) > n:
        m = n - 4
        return f"{text[:m]:<{m}} ..."
    return f"{text:<{n}}"


def print_teachers(teacher_data, block_tids=None, show_workload=False):
    def partners(tag, course) -> tuple[int, str]:
        try:
            courses = tag2courses[tag]
        except KeyError:
            return ""
        glist = [
            c.klass if c.group == "*" else f"{c.klass}.{c.group}"
            for c in courses
            if c != course
        ]
        return (len(glist), f' //{",".join(glist)}' if glist else "")

    def workload(
        paymentdata: PaymentData,
        lessons: Optional[list[int]] = None,
        ngroups: int = 0,  # number of other groups
    ) -> tuple[float, str]:
        if paymentdata.number:
            n = paymentdata.number
            nd = paymentdata.number_val
        else:
            if lessons is None:
                n = "?"
                nd = 0.0
            else:
                n = sum(lessons)
                nd = float(n)
        val = nd * paymentdata.factor_val
        if ngroups:
            shared = f" /{ngroups+1}"
            val /= float(ngroups + 1)
        else:
            shared = ""
        if show_workload:
            val_str = f"{val:.3f}".replace(".", DECIMAL_SEP)
            text = f"{n} × {paymentdata.factor or '--'}{shared} = {val_str}"
        else:
            text = ""
        return (val, text)

    blocked_tids = set() if block_tids is None else set(block_tids)
    classes = get_classes().get_class_list(skip_null=False)
    teacherlists = []
    for tid, tname, c2tags, c2paydata, tag2courses in teacher_data:
        if tid in blocked_tids:
            REPORT("INFO", T["TEACHER_SUPPRESSED"].format(tname=tname))
            continue
#?
        if not (c2tags or c2paydata):
            REPORT("INFO", T["TEACHER_NO_ACTIVITIES"].format(tname=tname))
            continue
        # print("\n $$$$$$", tname)
        classlists = []
        pay_total = 0.0
        for klass, kname in classes:
            class_list, class_blocks, class_payonly = [], {}, []
            try:
                tags = c2tags[klass]
            except KeyError:
                pass
            else:
                for tag, blockinfolist in tags.items():
#++ lesson lengths
                    lessonlist = [sl.LENGTH for sl in sublessons(tag)]
                    lessons = ",".join(map(str, lessonlist))
                    lesson_sum = sum(lessonlist)
                  
                    # print("???TAG", tag)
                    block = blockinfolist[0].block
#++ block tag
                    if block.sid:
                        bname = block.subject
                        for blockinfo in blockinfolist:
                            course = blockinfo.course
                            sname = print_subject(
                                get_subjects().map(course.sid)
                            )
                            rooms = print_rooms(blockinfo.rooms)
                            payment = blockinfo.payment_data
                            if payment.number:
                                # With number of units taught
                                if payment.tag:
                                    n, plist = partners(
                                        f"{tag}+{course.sid}%{payment.tag}",
                                        course,
                                    )
                                else:
                                    n, plist = 0, ""
                                pay, paytext = workload(payment, lessonlist, n)
                                pay_total += pay
                                if payment.number_val >= lesson_sum:
                                    if course.sid == block.sid:
                                        class_list.append(
#++ what is collected?
                                            (
                                                sname,
                                                course.class_group(),
                                                print_xsubject(sname + plist),
                                                rooms,
                                                lessons,
                                                paytext,
                                            )
                                        )
                                        continue
                                line = (
                                    sname,
                                    f" – {course.class_group()}",
                                    print_xsubject(sname + plist),
                                    rooms,
                                    f"[{payment.number}]",
                                    paytext,
                                )
                                try:
                                    class_blocks[bname][1].append(line)
                                except KeyError:
                                    class_blocks[bname] = (lessons, [line])
                                # print(f"%%% ({bname} {lessons}) {line}")

                            else:
                                # Continuous teaching
                                n, plist = partners(tag, course)
                                pay, paytext = workload(payment, lessonlist, n)
                                pay_total += pay
                                if course.sid == block.sid:
                                    class_list.append(
                                        (
                                            sname,
                                            course.class_group(),
                                            print_xsubject(sname + plist),
                                            rooms,
                                            lessons,
                                            paytext,
                                        )
                                    )
                                    # print("§§§", class_list[-1])

                                else:
                                    line = (
                                        sname,
                                        f" – {course.class_group()}",
                                        sname,
                                        rooms,
                                        f'[{T["continuous"]}]',
                                        paytext,
                                    )
                                    try:
                                        class_blocks[bname][1].append(line)
                                    except KeyError:
                                        class_blocks[bname] = (lessons, [line])
                                    # print(f"&&& ({bname} {lessons}) {line}")

                    else:
                        ## Simple, plain lesson block
                        blockinfo = blockinfolist[0]
                        course = blockinfo.course
                        sname = print_subject(get_subjects().map(course.sid))
                        rooms = print_rooms(blockinfo.rooms)
                        lessons = ",".join(map(str, lessonlist))
                        pay, paytext = workload(
                            blockinfo.payment_data, lessonlist
                        )
                        pay_total += pay
                        class_list.append(
                            (
                                sname,
                                course.class_group(),
                                sname,
                                rooms,
                                lessons,
                                paytext,
                            )
                        )
                        # print("§§§", class_list[-1])

            try:
                paydata = c2paydata[klass]
            except KeyError:
                pass
            else:
                for course, pd in paydata:
                    pay, paytext = workload(pd)
                    pay_total += pay
                    sname = get_subjects().map(course.sid)
                    class_payonly.append(
                        (
                            sname,
                            f"[{course.class_group()}]",
                            sname,
                            "",
                            "",
                            paytext,
                        )
                    )

            # Collate the various activities
            all_items = []
            for bname, data in class_blocks.items():
                all_items.append((f"[[{bname}]]", "", "", data[0], ""))
                for line in sorted(data[1]):
                    all_items.append(line[1:])
            # if all_items:
            #     all_items.append(None)
            all_items += [item[1:] for item in sorted(class_list)]
            if show_workload:
                # if all_items:
                #     all_items.append(None)
                all_items += [item[1:] for item in sorted(class_payonly)]
            if all_items:
                classlists.append((klass, all_items))

        teacherline = f"{tname} ({tid})"
        xclass = ("", [])
        classlists.append(xclass)
        if show_workload:
            pay_str = f"{pay_total:.2f}".replace(".", DECIMAL_SEP)
            xclass[1].append(("-----", "", "", "", "", pay_str))
            # teacherline = f"{teacherline:<30} – {T['WORKLOAD']}: {pay_str}"

        # print("\n  +++++++++++++++++++++", teacherline)
        # print(classlists)
        teacherlists.append((teacherline, classlists))

    pdf = PdfCreator()
    headers = [
        T[h] for h in ("H_group", "H_subject", "H_room", "H_lessons_blocks")
    ]
    if show_workload:
        headers.append(T["H_workload"])
        colwidths = (20, 50, 30, 30, 40)
    else:
        colwidths = (20, 60, 40, 40)
    return pdf.build_pdf(
        teacherlists,
        title=T["teachers-subjects"],
        author=CONFIG["SCHOOL_NAME"],
        headers=headers,
        colwidths=colwidths,
        #        do_landscape=True
    )


def print_classes(class_data, tag2classes):
    classlists = []
    for klass, kname, tag2blocks, counts in class_data:
        if not tag2blocks:
            REPORT("INFO", T["CLASS_NO_ACTIVITIES"].format(klass=klass))
            continue
        class_list, class_blocks = [], {}
        for tag in tag2blocks:
            blockinfolist = tag2blocks[tag]
            # print("???TAG", tag)
            try:
                __blockinfo = blockinfolist[0]
            except IndexError:
                REPORT(
                    "ERROR", T["TAG_NO_ACTIVITIES"].format(klass=klass, tag=tag)
                )
                continue
            block = __blockinfo.block
            if block.sid:
                ## All block types with block name
                blocklist = []
                # Include parallel classes
                try:
                    tag_classes = tag2classes[tag] - {klass}
                except KeyError:
                    raise Bug(f"Tag {tag} not in 'tag2classes'")
                if tag_classes:
                    parallel = f' //{",".join(sorted(tag_classes))}'
                else:
                    parallel = ""
                # Add block entry
                class_blocks[block] = (__blockinfo.lessons, blocklist, parallel)
                # Add members
                for blockinfo in blockinfolist:
                    course = blockinfo.course
                    sname = get_subjects().map(course.sid)
                    group_periods = f"{blockinfo.periods:.1f}".replace(
                        ".", DECIMAL_SEP
                    )
                    blocklist.append(
                        (
                            f" – {sname}",
                            course.group,
                            course.tid,
                            "",
                            f"({group_periods})",
                        )
                    )
                blocklist.sort()
            else:
                ## Simple, plain lesson block
                course = __blockinfo.course
                sname = get_subjects().map(course.sid)
                group_periods = f"{__blockinfo.periods}".replace(
                    ".", DECIMAL_SEP
                )
                class_list.append(
                    (
                        sname,
                        course.group,
                        course.tid,
                        ",".join(map(str, __blockinfo.lessons)),
                        group_periods,
                    )
                )

        # Collate the various activities
        all_items = []
        for block in sorted(class_blocks):
            data = class_blocks[block]
            sbj, tag = block.subject, block.tag
            if tag:
                blockname = f"[[{sbj} #{tag}]]"
            else:
                blockname = f"[[{sbj}]]"
            lessons = data[0]
            all_items.append(
                (
                    blockname + data[2],
                    "",
                    "",
                    ",".join(map(str, lessons)),
                    str(sum(lessons)),
                )
            )
            for line in data[1]:
                all_items.append(line)
        if all_items:
            all_items.append(None)
        all_items += sorted(class_list)
        all_items.append(None)

        classline = f"{kname} ({klass})"
        line = []
        countlines = [line]
        for g in sorted(counts):
            n = counts[g]
            if len(line) >= 6:
                line = []
                countlines.append(line)
            item = f"   {g}: " + f"{n:.1f}".replace(".", DECIMAL_SEP)
            line.append(f"{item:<16}")
        while len(line) < 6:
            line.append(" " * 16)
        countlines.append([""])
        classlists.append((classline, [("#", countlines), ("", all_items)]))

    pdf = PdfCreator()
    headers = [
        T[h]
        for h in ("H_subject", "H_group", "H_teacher", "H_lessons", "H_total")
    ]
    colwidths = (75, 20, 20, 30, 25)
    return pdf.build_pdf(
        classlists,
        title=T["classes-subjects"],
        author=CONFIG["SCHOOL_NAME"],
        headers=headers,
        colwidths=colwidths,
        #        do_landscape=True
    )


class TPrTuple(NamedTuple):
    CLASS: str          # short name
    BLOCKTAG: BlockTag  # invalid for "pay-only" ("#$") and "simple" ("~#")
    SUBJECT: str    # full name
    GROUP: str      # '*' for whole class, empty for "none"
    RIDS: str       # room-ids
    LENGTHS: tuple  # integer values, or empty
    WORKLOAD: Workload

#?
    def pay(self, nlessons:int):
        w = self.WORKLOAD
        if w.WORKLOAD:
            n = w.nd
        else:
            assert (nlessons >= 0)
            n = nlessons
        return (n, w.fd, n*w.fd)

    def __str__(self):
        if self.BLOCKTAG.sid and self.BLOCKTAG.tag:
            # valid block-tag
            prefix = f"[{str(self.BLOCKTAG)}] "
        else:
            prefix = ""
        g = f".{self.GROUP}" if self.GROUP else ""
        ll = ",".join(str(l) for l in self.LENGTHS)
        if self.WORKLOAD.WORKLOAD:
            nw = self.WORKLOAD.nd
#TODO: This is declared as a <float> ... but shouldn't it be an <int>?
# Also look at the setting-dialog ...
        else:
            nw = sum(self.LENGTHS)
        f = self.WORKLOAD.fd
        pay = f"{nw}x{self.WORKLOAD.PAY_FACTOR} = {nw*f}"
        return f"{self.CLASS}{g}|{prefix}{self.SUBJECT}|{self.RIDS}|{ll}|{pay}"

def list_one_teacher(tid):
    tname = get_teachers().name(tid)
    subjects = get_subjects()
    classes = get_classes()
    collect = []
    for course in filtered_courses("TEACHER", tid):
        w, l, b = course_activities(course["course"])
        cl = course["CLASS"]
        cr = classes.get_classroom(cl)
        if w:
            prtuple = TPrTuple(
                cl,                 # CLASS (short name)
                BlockTag("", "$", ""), # invalid block-type
                subjects.map(course["SUBJECT"]), # SUBJECT (full name)
                course["GRP"],      # GROUP
                "",                 # RIDS: room-ids
                (),                 # LENGTHS
                w[0],               # WORKLOAD                 
            )
            collect.append(prtuple)
        if l:
            prtuple = TPrTuple(
                course["CLASS"],    # CLASS (short name)
                BlockTag("~", "", ""), # invalid blocktag
                subjects.map(course["SUBJECT"]), # SUBJECT (full name)
                course["GRP"],      # GROUP
                l[1]["ROOM"].replace('$', cr), # RIDS: room-ids
                tuple(l["LENGTH"] for l in l[3]), # LENGTHS
                l[0],               # WORKLOAD                 
            )
            collect.append(prtuple)
        for bi in b:
            prtuple = TPrTuple(
                course["CLASS"],    # CLASS (short name)
                bi[4],              # blocktag
                subjects.map(course["SUBJECT"]), # SUBJECT (full name)
                course["GRP"],      # GROUP
                bi[1]["ROOM"].replace('$', cr), # RIDS: room-ids
                tuple(l["LENGTH"] for l in bi[3]), # LENGTHS
                bi[0],               # WORKLOAD                 
            )
            print("  +++", prtuple)
            collect.append(prtuple)



def make_teacher_table(activity_lists):
    db = xl.Database()
    teachers = get_teachers()
    for t, datalist in activity_lists.items():
        tname = teachers.name(t)
        # print("\n******", tname)
        # for data in datalist:
        #     print(" --", data)
        items = teacher_list(datalist)
        # for data in items:
        #     print(" ++", data)
        
        db.add_ws(ws=tname)
        sheet = db.ws(ws=tname)
        headers = [
            "Gruppe",
            "Fach",
            "Blockfach",
            "Blockkennung",
            "„Team“",
            "Raum",
            "Stunden",
            "Anzahl",
            "Deputat0",
            "Deputat",
        ]
        for col_id, field in enumerate(headers, start=1):
            sheet.update_index(row=1, col=col_id, val=field)
        workgroups = set()
        row_id = 2
        payments = 0.0
        for data in items:
            if data.blocktag:
                bs = data.blocktag.subject
                bt = data.blocktag.tag
            else:
                bs, bt = "", ""
            cg = print_class_group(data.klass, data.group)
            # Take "teams" into account.
            # A minimum would be to suppress the pay columns for all items
            # belonging to a team except the first:
            w = data.workgroup
            if w in workgroups:
                pay0 = ""
                pay1 = f"[{w}]"
                pay2 = 0.0
            else:
                workgroups.add(w)
                pay0 = data.paynum
                pay1 = data.paystr
                pay2 = data.pay
            payments += pay2
            line = [
                cg, 
                data.subject, 
                bs, 
                bt, 
                data.workgroup, 
                data.room, 
                data.lessons,
                pay0,
                pay1,
                pay2,
            ]
            for col_id, field in enumerate(line, start=1):
                sheet.update_index(row=row_id, col=col_id, val=field)
            row_id += 1
        # Total
        lastcol = len(headers)
        sheet.update_index(row=row_id, col=lastcol, val=payments)
        sheet.update_index(row=row_id, col=lastcol - 1, val="insgesamt")
    return db


#TODO
def make_class_table(activity_lists):
    db = xl.Database()
    # teachers = get_teachers()
    for c, datalist in activity_lists.items():
        # for data in datalist:
        #     print(" --", data)
        items = class_list(datalist)
        # for data in items:
        #     print(" ++", data)
#TODO--  
        continue
        
        db.add_ws(ws=c)
        sheet = db.ws(ws=c)

#    subject: str
#    group: str
#    teacher_id: str
#    blocktag: Optional[BlockTag]
#    workgroup: int  # the WORKLOAD index
#    room: str
#    lessons: str
#    nlessons: int

        headers = [
            "Fach",
            "Gruppe",
            "Lehrer",
            "Blockfach",
            "Blockkennung",
            "„Team“",
            "Raum",
            "Stunden",
        ]
        for col_id, field in enumerate(headers, start=1):
            sheet.update_index(row=1, col=col_id, val=field)
        workgroups = set()
        row_id = 2
        for data in items:
            if data.blocktag:
                bs = data.blocktag.subject
                bt = data.blocktag.tag
            else:
                bs, bt = "", ""
#TODO
            # Take atomic groups and "teams" into account.
# See how it's done in the course editor.

            w = data.workgroup
            if w in workgroups:
                pass

            else:
                workgroups.add(w)
                pass
            

#TODO
            line = [
                cg, 
                data.subject, 
                bs, 
                bt, 
                data.workgroup, 
                data.room, 
                data.lessons,
                pay0,
                pay1,
                pay2,
            ]
            for col_id, field in enumerate(line, start=1):
                sheet.update_index(row=row_id, col=col_id, val=field)
            row_id += 1
        # Total
        lastcol = len(headers)

#TODO: for the individual groups, where they differ ...
        sheet.update_index(row=row_id, col=lastcol, val=payments)
        sheet.update_index(row=row_id, col=lastcol - 1, val="insgesamt")
    return db


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    from ui.ui_base import saveDialog

    open_database()
    cl_lists, t_lists = read_db()
    tdb = make_teacher_table(t_lists)

    filepath = saveDialog("Excel-Datei (*.xlsx)", "Deputate")
    if filepath and os.path.isabs(filepath):
        if not filepath.endswith(".xlsx"):
            filepath += ".xlsx"
        xl.writexl(db=tdb, fn=filepath)
        print("  --->", filepath)

    cdb = make_class_table(cl_lists)


    quit(0)


    def run_me():
        courses = TeacherClassCourses()

        tlist = courses.teacher_class_subjects()
        pdfbytes = print_teachers(tlist)
#TODO: T ...
        filepath = saveDialog("pdf-Datei (*.pdf)", "teachers_subjects")
        if filepath and os.path.isabs(filepath):
            if filepath.endswith(".pdf"):
                filepath = filepath[:-4]
            fullpath = filepath + ".pdf"
            with open(fullpath, "wb") as fh:
                fh.write(pdfbytes)
            print("  --->", fullpath)
            pdfbytes = print_teachers(tlist, show_workload=True)
            fullpath = filepath + "_X.pdf"
            with open(fullpath, "wb") as fh:
                fh.write(pdfbytes)
            print("  --->", fullpath)


        clist = courses.read_class_blocks()
        pdfbytes = print_classes(clist, courses.tag2classes)
#TODO: T ...
        filepath = saveDialog("pdf-Datei (*.pdf)", "class_subjects")
        if filepath and os.path.isabs(filepath):
            if not filepath.endswith(".pdf"):
                filepath += ".pdf"
            with open(filepath, "wb") as fh:
                fh.write(pdfbytes)
            print("  --->", filepath)

    PROCESS(
        run_me, "TeacherClassCourses() ... print teacher and class workload"
    )
