"""
core/list_activities.py

Last updated:  2023-03-25

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

from core.basic_data import (
    get_group_info,
    get_classes,
    get_teachers,
    get_subjects,
    sublessons,
    Workload,
    BlockTag,
#    PaymentData,
)
from core.course_data import filtered_courses, course_activities

DECIMAL_SEP = CONFIG["DECIMAL_SEP"]

### -----

#TODO ...

class ClassBlockInfo(NamedTuple):
#    course: CourseData
    block: BlockTag
    lessons: list[int]
    periods: float  # (per week, averaged over the year)
    notes: str


class TeacherClassCourses:#(Courses):
    def teacher_class_subjects(self):
        """Organize the data according to teachers and classes, keeping
        data for real lessons and payment-only entries separate.
        Return an ordered list of the teachers, each with his/her own data.
        The entries in this list are tuples:
            teacher-id: str
            teacher-name: str
            lesson-data: {class -> {tag -> [BlockInfo, ... ]}}
            payment-only-data: {class -> [(CourseData, PaymentData), ... ]}
            partner-courses: {partner-tag -> [CourseData, ... ]}
        For "continuous" items, a partner-tag is just the block-tag; if
        there is a pay-tag, the partner-tag is "block-tag+sid%pay-tag".
        """
        teachers = get_teachers()
        tlist = []
        already_warned = set()  # for limiting warnings
        for tid in teachers:
            tname = teachers.name(tid)
            ### Divide the data into classes
            ## lesson data
            c2tags = {}
            tag2courses = {}  # {partner-tag -> [course, ... ]}
            for tag, blockinfolist in (self.tid2tags.get(tid) or {}).items():
                continuous = None
                total_length = 0
                tagged = {}
                for blockinfo in blockinfolist:
                    payinfo = blockinfo.payment_data
                    course = blockinfo.course

                    if not blockinfo.block.sid:
                        ## A "plain" lesson
                        # No block-sid, nothing parallel
                        if len(blockinfolist) > 1:
                            REPORT(
                                "ERROR",
                                T["BAD_PLAIN_BLOCK"].format(
                                    course=course, tag=tag
                                ),
                            )
                            continue

                    elif payinfo.number:
                        if payinfo.tag:
                            stkey = f"{course.sid}%{payinfo.tag}"
                            try:
                                clist, pay, rooms = tagged[stkey]
                            except KeyError:
                                __courses = [course]
                                tagged[stkey] = (
                                    __courses,
                                    (payinfo.number, payinfo.factor),
                                    blockinfo.rooms,
                                )
                                tag2courses[f"{tag}+{stkey}"] = __courses
                            else:
                                if pay != (payinfo.number, payinfo.factor):
                                    REPORT(
                                        "ERROR",
                                        T["PARTNER_PAY_MISMATCH"].format(
                                            course1=clist[0],
                                            course2=course,
                                            tag=tag,
                                        ),
                                    )
                                    continue
                                if (
                                    rooms
                                    and blockinfo.rooms
                                    and blockinfo.rooms != rooms
                                ):
                                    REPORT(
                                        "ERROR",
                                        T["PARTNER_ROOM_MISMATCH"].format(
                                            course1=clist[0],
                                            course2=course,
                                            tag=tag,
                                        ),
                                    )
                                    continue
                                clist.append(course)

                        # else: A normal block member

                        total_length += payinfo.number_val

                    else:
                        # All parallel items must have the same subject
                        # and payment, and same (or null) rooms
                        if payinfo.tag:
                            # A pay-tag would be superfluous as only one
                            # "continuous" item is allowed anyway.
                            REPORT(
                                "ERROR",
                                T["CONTINUOUS_BLOCK_TAG"].format(
                                    course=course, tag=tag
                                ),
                            )
                            continue
                        if continuous:
                            if continuous[1] != (
                                payinfo.number,
                                payinfo.factor,
                            ):
                                REPORT(
                                    "ERROR",
                                    T["PARTNER_PAY_MISMATCH"].format(
                                        course1=continuous[0][0],
                                        course2=course,
                                        tag=tag,
                                    ),
                                )
                                continue
                            if continuous[0][0].sid != course.sid:
                                REPORT(
                                    "ERROR",
                                    T["PARTNER_SID_MISMATCH"].format(
                                        course1=continuous[0][0],
                                        course2=course,
                                        tag=tag,
                                    ),
                                )
                                continue
                            if (
                                continuous[2]
                                and blockinfo.rooms
                                and blockinfo.rooms != continuous[2]
                            ):
                                REPORT(
                                    "ERROR",
                                    T["PARTNER_ROOM_MISMATCH"].format(
                                        course1=continuous[0][0],
                                        course2=course,
                                        tag=tag,
                                    ),
                                )
                                continue
                            continuous[0].append(course)
                        else:
                            continuous = (
                                [course],
                                (payinfo.number, payinfo.factor),
                                blockinfo.rooms,
                            )
                            tag2courses[tag] = continuous[0]

                    klass = blockinfo.course.klass
                    try:
                        tag2blockinfo = c2tags[klass]
                    except KeyError:
                        c2tags[klass] = {tag: [blockinfo]}
                    else:
                        try:
                            tag2blockinfo[tag].append(blockinfo)
                        except KeyError:
                            tag2blockinfo[tag] = [blockinfo]

                if continuous:
                    if total_length:
                        REPORT(
                            "ERROR",
                            T["CONTINUOUS_PLUS_OTHERS"].format(
                                course=continuous[0][0], tag=tag
                            ),
                        )
                else:
                    lessons = [sl.LENGTH for sl in sublessons(tag)]
                    suml = sum(lessons)
                    if suml:
                        if total_length > suml:
                            REPORT(
                                "ERROR",
                                T["BLOCK_TOO_FULL"].format(
                                    teacher=tname, tag=tag
                                ),
                            )
                    elif tag not in already_warned:
                        REPORT("WARNING", T["BLOCK_NO_LESSONS"].format(tag=tag))
                        already_warned.add(tag)

            ## Payment-only data
            c2paydata = {}
            for course_pay_data in self.tid2paydata.get(tid) or []:
                klass = course_pay_data[0].klass
                try:
                    c2paydata[klass].append(course_pay_data)
                except KeyError:
                    c2paydata[klass] = [course_pay_data]
            ### Add teacher data to list of all teachers
            tlist.append((tid, tname, c2tags, c2paydata, tag2courses))
        return tlist

    def read_class_blocks(self):
        """Organize the data according to classes.
        This method isolates the actual lessons taught in the various
        classes – as far as the available information allows.
        Payment-only entries are ignored.
        Return an ordered list of the classes, each with its own data.
        The entries in this list are tuples:
            class: str
            name: str
            lesson-data: {tag -> [ClassBlockInfo, ... ]}
            period-counts: {basic-group -> average number of periods per week}
        """
        classes = get_classes()
        clist = []
        tag2classes = {}  # {tag -> {klass}}
        self.tag2classes = tag2classes
        for klass, kname in classes.get_class_list():
            tag2blocks = {}  # {tag -> [ClassBlockInfo, ... ]}
            # Prepare group data – the null class is excluded
            group_info = get_group_info(klass)
            basic_groups = group_info["BASIC"]
            if basic_groups:
                group2basic = group_info["GROUP_MAP"]
            else:
                # If no class divisions, add an entry for the whole class
                basic_groups = {"*"}
                group2basic = {"*": ["*"]}
            # Counters for number of periods per basic-group:
            group_counts = {g: 0.0 for g in basic_groups}
            # Read blocklist for each tag
            try:
                tag2blocklist = self.klass2tags[klass]
            except KeyError:
                clist.append((klass, kname, tag2blocks, group_counts))
                continue
            for tag, blockinfolist in tag2blocklist.items():
                try:
                    tag2classes[tag].add(klass)
                except KeyError:
                    tag2classes[tag] = {klass}
                lessons = [sl.LENGTH for sl in sublessons(tag)]
                lesson_sum = sum(lessons)
                groups = set()
                blocks = []
                tag2blocks[tag] = blocks
                for blockinfo in blockinfolist:
                    course = blockinfo.course
                    if not blockinfo.block.sid:
                        ## A "plain" lesson
                        # No block-sid, nothing parallel
                        if len(blockinfolist) > 1:
                            REPORT(
                                "ERROR",
                                T["BAD_PLAIN_BLOCK"].format(
                                    course=course, tag=tag
                                ),
                            )
                            continue

                    # Only include info if there are real pupils
                    if course.group:
                        # Add number of periods to totals for basic groups
                        if course.group == "*":
                            groups.update(basic_groups)
                        else:
                            groups.update(group2basic[course.group])
                        payinfo = blockinfo.payment_data
                        if payinfo.number and blockinfo.block.sid:
                            n = payinfo.number_val
                        else:
                            n = lesson_sum
                        # Collect the necessary information about the block
                        blocks.append(
                            ClassBlockInfo(
                                course,
                                blockinfo.block,
                                lessons,
                                n,
                                blockinfo.notes,
                            )
                        )
                if lesson_sum:
                    for g in groups:
                        group_counts[g] += lesson_sum

            ## Payment-only data is not collected for classes

            ### Add class data to list of all classes
            clist.append((klass, kname, tag2blocks, group_counts))
            # if klass == '07G':
            #     print(f"$$$ {klass}:", group_counts)
            #     for k, v in tag2blocks.items():
            #         print(f"\n  +++ {k}:", v)
        return clist


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
                    lessonlist = [sl.LENGTH for sl in sublessons(tag)]
                    lessons = ",".join(map(str, lessonlist))
                    lesson_sum = sum(lessonlist)
                    # print("???TAG", tag)
                    block = blockinfolist[0].block
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


PAGESIZE = A4
PAGESIZE_L = landscape(PAGESIZE)
BASE_MARGIN = 20 * mm


class MyDocTemplate(SimpleDocTemplate):
    """This is adapted to emit an "outline" for the teacher pages."""

    def __init__(self, *args, **kargs):
        self.key = 0
        super().__init__(*args, **kargs)

    def handle_flowable(self, flowables):
        if flowables:
            flowable = flowables[0]
            try:
                flowable.toc(self.canv)
            except AttributeError:
                pass
        super().handle_flowable(flowables)


tablestyle0 = [
    ("FONT", (0, 0), (-1, -1), "Helvetica"),
    ("FONTSIZE", (0, 0), (-1, -1), 12),
    ("LINEABOVE", (0, -1), (-1, -1), 1, colors.lightgrey),
]

tablestyle = [
    #         ('ALIGN', (0, 1), (-1, -1), 'RIGHT'),
    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
    ("LINEBELOW", (0, -1), (-1, -1), 1, colors.black),
    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
    #         ('LINEABOVE', (0,-1), (-1,-1), 1, colors.black),
    ("FONT", (0, 1), (-1, -1), "Helvetica"),
    #         ('BACKGROUND', (1, 1), (-2, -2), colors.white),
    ("TEXTCOLOR", (0, 0), (1, -1), colors.black),
    ("FONTSIZE", (0, 0), (-1, -1), 11),
]


class PdfCreator:
    def add_page_number(self, canvas, doc):
        canvas.saveState()
        font_name = "Helvetica"
        font_size = 11
        canvas.setFont(font_name, font_size)
        page_number_text = str(doc.page)
        w = stringWidth(page_number_text, font_name, font_size)
        x = (self.pagesize[0] - w) / 2
        canvas.drawCentredString(x, 10 * mm, page_number_text)
        canvas.restoreState()

    def build_pdf(
        self,
        pagelist,
        title,
        author,
        headers,
        colwidths=None,
        do_landscape=False,
    ):
        all_refs = set()

        class PageHeader(Paragraph):
            # class PageHeader(Preformatted):
            def __init__(self, text, ref):
                if ref in all_refs:
                    REPORT("ERROR", T["Repeated_page_title"].format(ref=ref))
                    self.ref = None
                else:
                    self.ref = ref
                    all_refs.add(ref)
                super().__init__(text, heading_style)

            def toc(self, canvas):
                if self.ref:
                    canvas.bookmarkPage(self.ref)
                    canvas.addOutlineEntry(self.ref, self.ref, 0, 0)

        pdf_buffer = BytesIO()
        self.pagesize = PAGESIZE_L if do_landscape else PAGESIZE
        my_doc = MyDocTemplate(
            pdf_buffer,
            title=title,
            author=author,
            pagesize=self.pagesize,
            topMargin=BASE_MARGIN,
            leftMargin=BASE_MARGIN,
            rightMargin=BASE_MARGIN,
            bottomMargin=BASE_MARGIN,
        )
        sample_style_sheet = getSampleStyleSheet()
        body_style = sample_style_sheet["BodyText"]
        # body_style = sample_style_sheet["Code"]
        body_style.fontSize = 11
        # body_style.leading = 14
        # body_style.leftIndent = 0

        # body_style_2 = copy.deepcopy(body_style)
        # body_style.spaceBefore = 10
        # body_style_2.alignment = TA_RIGHT

        heading_style = sample_style_sheet["Heading1"]
        # print("????????????", heading_style.fontName)
        # heading_style = copy.deepcopy(body_style)
        heading_style.fontName = "Helvetica-Bold"
        heading_style.fontSize = 14
        heading_style.spaceAfter = 24

        # sect_style = sample_style_sheet["Heading2"]
        # sect_style.fontSize = 13
        # sect_style.spaceBefore = 20
        # print("\n STYLES:", sample_style_sheet.list())

        flowables = []
        for pagehead, plist in pagelist:
            # print("§§§", repr(pagehead))
            tstyle = tablestyle.copy()
            # h = Paragraph(pagehead, heading_style)
            h = PageHeader(pagehead, pagehead)  # .split("(", 1)[0].rstrip())
            flowables.append(h)
            lines = [headers]
            nh = len(headers)
            for secthead, slist in plist:
                if secthead == "#":
                    table = Table(slist)
                    table_style = TableStyle(tablestyle0)
                    table.setStyle(table_style)
                    flowables.append(table)
                    continue
                lines.append("")
                for sline in slist:
                    r = len(lines)
                    if sline:
                        if sline[0].startswith("[["):
                            tstyle.append(("SPAN", (0, r), (2, r)))
                        elif sline[0] == "-----":
                            tstyle.append(
                                ("LINEABOVE", (0, r), (-1, r), 1, colors.black),
                            )
                            sline = sline[1:]
                        lines.append(sline[:nh])
                    else:
                        lines.append("")

            kargs = {"repeatRows": 1}
            if colwidths:
                kargs["colWidths"] = [w * mm for w in colwidths]
            table = Table(lines, **kargs)
            table_style = TableStyle(tstyle)
            table.setStyle(table_style)
            flowables.append(table)

            flowables.append(PageBreak())
        my_doc.build(
            flowables,
            onFirstPage=self.add_page_number,
            onLaterPages=self.add_page_number,
        )
        pdf_value = pdf_buffer.getvalue()
        pdf_buffer.close()
        return pdf_value



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


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    from ui.ui_base import saveDialog

    open_database()
    list_one_teacher("AE")
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
