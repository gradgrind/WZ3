"""
timetable/activities.py

Last updated:  2023-05-07

Collect information on "activities" – from the BLOCKS and COURSES db tables.

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

###############################################################

#TODO: freshly copied over from WZ

T = TRANSLATIONS("timetable.activities")

### +++++

from typing import NamedTuple

from core.db_access import db_read_fields
from core.basic_data import (
    get_classes,
    get_rooms,
#    check_group,
#    read_payment,
#    read_block_tag,
    BlockTag,
#    PaymentData,
)

### -----


class CourseData(NamedTuple):
    klass: str
    group: str
    sid: str
    tid: str

    def __str__(self):
        return T["CourseData"].format(
            klass=self.klass, group=self.group, sid=self.sid, tid=self.tid
        )

    def class_group(self):
        if self.group:
            return f"{self.klass}.{self.group}"
        else:
            return f"({self.klass})"


class BlockInfo(NamedTuple):
    course: CourseData
#    block: BlockTag
    rooms: list[str]
#    payment_data: PaymentData
    notes: str


def lesson_rooms(room: str, course: CourseData, lesson_id: int) -> list[str]:
    """Read a list of possible rooms for the given lesson.
    Check the validity of the individual rooms, convert '$' to the
    corresponding classroom.
    The lesson-id is only passed for use in error messages.
    """
    if not room:
        return []
    rlist = []
    room_list = get_rooms()
    rooms = room.rstrip("+")
    if rooms:
        for r in rooms.split("/"):
            if r == "$":
                # Get classroom
                classroom = get_classes().get_classroom(course.klass)
                if not classroom:
                    REPORT(
                        "ERROR",
                        T["NO_CLASSROOM"].format(course=course, id=lesson_id),
                    )
                    continue
                rlist.append(classroom)
            else:
                try:
                    room_list.index(r)
                except KeyError:
                    REPORT(
                        "ERROR",
                        T["UNKNOWN_ROOM"].format(
                            rid=r, course=course, id=lesson_id
                        ),
                    )
                else:
                    rlist.append(r)
    if room[-1] == "+":
        rlist.append("+")
    return rlist


class Courses:
    __slots__ = (
        # "paydata",
        "tid2paydata",  # {tid -> [(CourseData, PaymentData), ... ]}
        "tag2entries",  # {block-tag -> [BlockInfo, ... ]}
        "tid2tags",     # {tid -> {block-tag -> [BlockInfo, ... ]}}
        "klass2tags",   # {klass -> {block-tag -> [BlockInfo, ... ]}}
    )

    def __init__(self, group2atoms):
        ### First read the COURSES table.
        course2data = {}
        for course, klass, group, sid, tid in db_read_fields(
            "COURSES", ("course", "CLASS", "GRP", "SUBJECT", "TEACHER")
        ):
            # CLASS, SUBJECT and TEACHER are foreign keys and should be
            # automatically bound to appropriate entries in the database.
            # GRP should be checked here ...
            if klass == "--":
                if group:
                    REPORT(
                        "ERROR",
                        T["NULL_CLASS_GROUP"].format(
                            group=group, sid=sid, tid=tid
                        ),
                    )
                    continue
            elif group == '*':
                group = ''
            elif group not in group2atoms[klass]:
                REPORT(
                    "ERROR",
                    T["UNKNOWN_GROUP"].format(
                        klass=klass, group=group, sid=sid, tid=tid
                    ),
                )
                continue

            course2data[course] = CourseData(
                klass=klass, group=group, sid=sid, tid=tid
            )
            if not tid:
                raise Bug(f"Empty teacher field in {course2data[course]}")

        ### Now read the BLOCKS table.

        # TODO: Is this really needed? At present it is not used.
        # self.paydata = []  # [(CourseData, PaymentData), ... ]

        self.tid2paydata = {}
        tag2entries = {}
        self.tag2entries = tag2entries
        tid2tags = {}
        self.tid2tags = tid2tags
        klass2tags = {}
        self.klass2tags = klass2tags
        # Collect payment-only entries for courses (check for multiple entries):
        paycourses = set()
        # The "id" field is read only for error reports
        for id, course, payment, room, tag, notes in db_read_fields(
            "BLOCKS",
            ("id", "course", "PAYMENT", "ROOM", "LESSON_TAG", "NOTES"),
        ):
            try:
                coursedata = course2data[course]
            except KeyError:
                #TODO: The error should have been reported earlier ...
                REPORT(
                    "ERROR",
                    f"[Courses: repeat error?"
                    f" Unknown course in BLOCKS table: {course}]"
                )
                continue
            try:
                payment_data = read_payment(payment)
            except ValueError as e:
                REPORT(
                    "ERROR",
                    T["LESSON_ERROR"].format(id=id, course=coursedata, e=e),
                )
                continue
            if tag:
                ## Build a mapping {tag -> [BlockInfo, ... ]}.
                try:
                    blocktag = read_block_tag(tag)
                except ValueError as e:
                    REPORT(
                        "ERROR",
                        T["LESSON_ERROR"].format(id=id, course=coursedata, e=e),
                    )
                    continue
                roomlist = lesson_rooms(room, coursedata, id)
                entry = BlockInfo(
                    coursedata, blocktag, roomlist, payment_data, notes
                )
                try:
                    tag2entries[tag].append(entry)
                except KeyError:
                    tag2entries[tag] = [entry]

                # Add to teacher mapping
                tid = coursedata.tid
                try:
                    __tag2entries = tid2tags[tid]
                except KeyError:
                    tid2tags[tid] = {tag: [entry]}
                else:
                    try:
                        __tag2entries[tag].append(entry)
                    except KeyError:
                        __tag2entries[tag] = [entry]

                # Add to class mapping
                klass = coursedata.klass
                try:
                    __tag2entries = klass2tags[klass]
                except KeyError:
                    klass2tags[klass] = {tag: [entry]}
                else:
                    try:
                        __tag2entries[tag].append(entry)
                    except KeyError:
                        __tag2entries[tag] = [entry]

            else:
                ## non-lesson, additional duties (with payment) for teachers
                if room:
                    REPORT(
                        "ERROR",
                        T["ROOM_NON_LESSON"].format(
                            id=id, course=coursedata, room=room
                        ),
                    )
                    continue
                if coursedata.tid == "--":
                    REPORT(
                        "ERROR",
                        T["NON_LESSON_NO_TEACHER"].format(
                            id=id, course=coursedata
                        ),
                    )
                    continue
                if not payment_data[0]:
                    REPORT(
                        "ERROR",
                        T["PAYMENT_NO_NUMBER"].format(
                            id=id, course=coursedata, payment=payment
                        ),
                    )
                pd = (coursedata, payment_data)
                # self.paydata.append(pd)

                # Add to teacher mapping
                tid = coursedata.tid
                try:
                    self.tid2paydata[tid].append(pd)
                except KeyError:
                    self.tid2paydata[tid] = [pd]

                # Check multiple such entries for any one course
                if course in paycourses:
                    REPORT(
                        "WARNING",
                        T["COURSE_MULTIPLE_PAY"].format(course=coursedata),
                    )
                else:
                    paycourses.add(course)


def filter_roomlists(roomlists: list[list[str]]) -> list[list[str]]:
    """Simplify room lists, check for room conflicts. It is possible
    that room allocations which must remain open (containing '+') are
    not resolved during initial placement, but may be done manually later.
    """
    # Collect single room "choices" and remove redundant entries
    singles = set()
    extra = []
    while True:
        singles1 = set()
        roomlists1 = []
        for rl in roomlists:
            rl1 = [r for r in rl if r not in singles]
            if rl1:
                if len(rl1) == 1:
                    if rl1[0] == '+':
                        extra = [['+']]
                    else:
                        singles1.add(rl1[0])
                else:
                    # This could be a duplicate, but as the initial
                    # entry (before simplification) was different, this
                    # is accepted as a separate room request
                    roomlists1.append(rl1)
            else:
                raise ValueError
        if singles1:
            singles.update(singles1)
            roomlists = roomlists1
            continue
        return [[s] for s in sorted(singles)] + extra + roomlists1
