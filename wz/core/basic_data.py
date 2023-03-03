"""
core/basic_data.py - last updated 2023-03-03

Handle caching of the basic data sources

==============================
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
"""

T = TRANSLATIONS("core.basic_data")

### +++++

from typing import Optional, NamedTuple

from core.db_access import (
    db_read_fields,
    db_key_value_list,
    db_read_unique_field,
    NoRecord,
    KeyValueList,
)
from core.classes import Classes
from core.teachers import Teachers
from ui.ui_base import QRegularExpression  ### QtCore

SHARED_DATA = {}

DECIMAL_SEP = CONFIG["DECIMAL_SEP"]
__FLOAT = f"[1-9]?[0-9](?:{DECIMAL_SEP}[0-9]{{1,3}})?"
PAYMENT_FORMAT = QRegularExpression(f"^{__FLOAT}$")
PAYMENT_MAX = 30.0
__TAG_CHAR = "[A-Za-z0-9_.]"
TAG_FORMAT = QRegularExpression(f"^{__TAG_CHAR}+$")
BLOCK_TAG_FORMAT = QRegularExpression(f"^[#]{__TAG_CHAR}*$")
PAYMENT_TAG_FORMAT = QRegularExpression(f"^{__TAG_CHAR}*(?:/{__FLOAT})?$")
NO_SUBJECT = "-----"

### -----


def clear_cache():
    # IMPORTANT: This must be called after any data change.
    SHARED_DATA.clear()


def get_days() -> KeyValueList:
    """Return the timetable days as a KeyValueList of (tag, name) pairs.
    This data is cached, so subsequent calls get the same instance.
    """
    try:
        return SHARED_DATA["DAYS"]
    except KeyError:
        pass
    days = db_key_value_list("TT_DAYS", "TAG", "NAME", "N")
    SHARED_DATA["DAYS"] = days
    return days


def get_periods() -> KeyValueList:
    """Return the timetable "periods" as a KeyValueList of (tag, name) pairs.
    This data is cached, so subsequent calls get the same instance.
    """
    try:
        return SHARED_DATA["PERIODS"]
    except KeyError:
        pass
    periods = db_key_value_list("TT_PERIODS", "TAG", "NAME", "N")
    SHARED_DATA["PERIODS"] = periods
    return periods


def get_classes() -> Classes:
    """Return the data for all classes as a <Classes> instance (dict).
    This data is cached, so subsequent calls get the same instance.
    """
    try:
        return SHARED_DATA["CLASSES"]
    except KeyError:
        pass
    classes = Classes()
    SHARED_DATA["CLASSES"] = classes
    return classes


def get_teachers() -> Teachers:
    """Return the data for all teachers as a <Teachers> instance (dict).
    This data is cached, so subsequent calls get the same instance.
    """
    try:
        return SHARED_DATA["TEACHERS"]
    except KeyError:
        pass
    teachers = Teachers()
    SHARED_DATA["TEACHERS"] = teachers
    return teachers


def get_subjects() -> KeyValueList:
    """Return the subjects as a KeyValueList of (sid, name) pairs.
    This data is cached, so subsequent calls get the same instance.
    """
    try:
        return SHARED_DATA["SUBJECTS"]
    except KeyError:
        pass
    subjects = db_key_value_list("SUBJECTS", "SID", "NAME", sort_field="NAME")
    SHARED_DATA["SUBJECTS"] = subjects
    return subjects


def get_subjects_with_sorting() -> dict:
    try:
        return SHARED_DATA["SUBJECTS_SORTED"]
    except KeyError:
        pass
    sid2data = {}
    i = 0
    for row in db_read_fields(
        "SUBJECTS",
        ("SID", "NAME", "SORTING"),
        "SORTING,NAME"
    ):
        row.insert(0, i)
        sid2data[row[1]] = row
        i += 1
    SHARED_DATA["SUBJECTS_SORTED"] = sid2data
    return sid2data


def get_rooms() -> KeyValueList:
    """Return the rooms as a KeyValueList of (rid, name) pairs.
    This data is cached, so subsequent calls get the same instance.
    """
    try:
        return SHARED_DATA["ROOMS"]
    except KeyError:
        pass
    rooms = db_key_value_list("TT_ROOMS", "RID", "NAME", sort_field="RID")
    SHARED_DATA["ROOMS"] = rooms
    return rooms


class Sublesson(NamedTuple):
    id: int
    TAG: str
    LENGTH: int
    TIME: str
    PLACEMENT: str
    ROOMS: str


def get_sublessons(reset:bool=False) -> dict[str,list[Sublesson]]:
    if not reset:
        try:
            return SHARED_DATA["SUBLESSONS"]
        except KeyError:
            pass
    slmap = {}
    for row in db_read_fields("LESSONS", Sublesson._fields):
        sl = Sublesson(*row)
        try:
            slmap[sl.TAG].append(sl)
        except KeyError:
            slmap[sl.TAG] = [sl]
    SHARED_DATA["SUBLESSONS"] = slmap
    return slmap


def get_simultaneous_weighting(tag, with_default=True):
    try:
        return db_read_unique_field("PARALLEL_LESSONS", "WEIGHTING", TAG=tag)
    except NoRecord:
        if with_default:
            return 10
        else:
            raise


def sublessons(tag:str, reset:bool=False) -> list[Sublesson]:
    """Return a list of <Sublesson>s for the given block-tag.
    The <reset> parameter is needed by the course-editor, which can
    change the db contents.
    Also tags are accepted which have no entry in the mapping (i.e. no
    entries in the db table) – because there can be blocks with no
    sublessons. These are added to the mapping as empty lists.
    """
    if tag.replace(" ", "") != tag:
        SHOW_ERROR(f"Bug: Spaces in partner tag: '{tag}'")
        return []
    if not tag:
        return []
    slmap = get_sublessons(reset)
    try:
        return slmap[tag]
    except KeyError:
        l = []
        slmap[tag] = l
    return l


class BlockTag(NamedTuple):
    sid: str
    tag: str
    subject: str

    @classmethod
    def read(cls, tag:str):
        """Decode the given block tag. Return a <BlockTag> instance.
        """
        if not tag:
            return cls("", "", NO_SUBJECT)
        try:
            sid, btag = tag.split("#", 1)
        except ValueError:
            raise ValueError(T["BLOCKTAG_INVALID"].format(tag=tag))
        return cls.build(sid, btag)

    @classmethod
    def build(cls, sid, tag):
        if not sid:
            raise ValueError(T["BLOCK_TAG_WITHOUT_SUBJECT"])
        try:
            subject = get_subjects().map(sid)
        except KeyError:
            raise ValueError(
                T["BLOCKTAG_UNKNOWN_SUBJECT"].format(sid=sid)
            )
        if not tag:
            return cls(sid, "", subject)
        if TAG_FORMAT.match(tag).hasMatch():
            return cls(sid, tag, subject)
        raise ValueError(T["BLOCKTAG_INVALID_TAG"].format(tag=tag))

    def __str__(self):
        return f"{self.sid}#{self.tag}" if self.sid else ""


'''
def blocknotes_info(text:str) -> dict[str,str]:
    """Read an info mapping from the "NOTES" field of a "BLOCKS" entry.
    This ends with "#", the individual entries are separated by spaces
    and are ":"-separated key/value pairs.
    """
    items = {}
    info = text.split("#", 1)
    if len(info) == 2:
        for item in info[0].split():
            try:
                _k, v = item.split(":", 1)
            except:
                raise ValueError(
                    T["BAD_NOTES_INFO"].format(info=info[0], item=item)
                )
            items[k] = v
    return items
'''


def get_group_info(klass):
    tag = f"group_info_{klass}"
    try:
        return SHARED_DATA[tag]
    except KeyError:
        pass
    gi = get_classes().group_info(klass)
    SHARED_DATA[tag] = gi
    return gi


def check_group(klass, group=None):
    try:
        groups = get_classes().group_info(klass)["GROUP_MAP"]
    except KeyError:
        return False
    if group and group != "*":
        # print("§§§", groups)
        if group not in groups:
            return False
    return True


# def check_lesson_length(length: str) -> int:
#    """Return the length of a valid lesson duration as an <int>.
#    Otherwise raise a <ValueError> exception.
#    """
#    try:
#        i = int(length)
#    except ValueError:
#        raise ValueError(T["LENGTH_NOT_NUMBER"].format(val=length))
#    if i < 1 or i > len(get_periods()):
#        raise ValueError(T["LENGTH_NOT_VALID"].format(val=length))
#    return i
#
#    LENGTH_NOT_NUMBER: "Stundendauer ({val}) ist keine Zahl"
#    LENGTH_NOT_VALID: "Stundendauer ({val}) ist nicht möglich"

### FUNCTIONS FOR WORKLOAD/PAYMENT DETAILS ###

def get_payment_weights() -> KeyValueList:
    """Return the "payment lesson weightings" as a KeyValueList of
    (tag, weight) pairs.
    This data is cached, so subsequent calls get the same instance.
    """

    def check(item):
        i2 = item[1]
        if PAYMENT_FORMAT.match(i2).hasMatch():
            return i2
        else:
            # TODO: rather raise ValueError?
            SHOW_ERROR(T["BAD_WEIGHT"].format(key=item[0], val=i2))
            return None

    try:
        return SHARED_DATA["PAYMENT"]
    except KeyError:
        pass
    payment_weights = db_key_value_list(
        "PAY_FACTORS", "TAG", "WEIGHT", check=check
    )
    SHARED_DATA["PAYMENT"] = payment_weights
    return payment_weights


class WorkloadData(NamedTuple):
    WORKLOAD: str
    PAY_FACTOR: str
    WORK_GROUP: str
    number_val: float
    factor_val: float
    
    def isNone(self):
        return not self.PAY_FACTOR

    def isValid(self):
        return self.PAY_FACTOR != "!"

    def __str__(self):
        if self.PAY_FACTOR:
            t = f"/{self.WORK_GROUP}" if self.WORK_GROUP else ""
            return f"{self.WORKLOAD}*{self.PAY_FACTOR}{t}"
        return ""


def course_lesson2workload(
    WORKLOAD, PAY_FACTOR, WORK_GROUP, **xargs
) -> WorkloadData:
    """Check the validity of the arguments and return a <WorkloadData>
    instance. If any errors are reported, return an empty result.
    """
    ok = True
    if PAY_FACTOR:
        if WORKLOAD:
            try:
                if PAYMENT_FORMAT.match(WORKLOAD).hasMatch():
                    nd = float(WORKLOAD.replace(",", "."))
                    if nd < 0.0 or nd > PAYMENT_MAX:
                        raise ValueError
                else:
                    raise ValueError
            except ValueError:
                REPORT("ERROR", T["BAD_NUMBER"].format(val=WORKLOAD))
                ok = False
        else:
            # Use the number & length of the actual lessons
            nd = -1.0
        try:
            fd = float(
                get_payment_weights().map(PAY_FACTOR).replace(",", ".")
            )
        except KeyError:
                REPORT("ERROR", T["UNKNOWN_PAYMENT_WEIGHT"].format(key=f))
                ok = False
        except ValueError:
            REPORT(
                "ERROR", 
                f"BUG: Invalid db entry in PAY_FACTORS: key {PAY_FACTOR}"
            )
            ok = False
        if WORK_GROUP:
            if not WORKLOAD:
                REPORT(
                    "ERROR", 
                    T["PAYMENT_TAG_WITHOUT_NUMBER"].format(tag=WORK_GROUP)
                )
                ok = False
            elif not PAYMENT_TAG_FORMAT.match(WORK_GROUP).hasMatch():
                REPORT(
                    "ERROR", 
                    T["INVALID_PAYMENT_TAG"].format(tag=WORK_GROUP)
                )
                ok = False
        if ok: 
            return WorkloadData(WORKLOAD, PAY_FACTOR, WORK_GROUP, nd, fd)
    elif WORKLOAD:
        REPORT(
            "ERROR", 
            T["PAYMENT_NUMBER_WITHOUT_WEIGHT"]
        )
    elif WORK_GROUP:
        REPORT(
            "ERROR", 
            T["PAYMENT_TAG_WITHOUT_NUMBER"].format(tag=WORK_GROUP)
        )
    else:
        # "Empty" result
        return WorkloadData("", "", "", 0.0, 0.0)
    # Error result
    return WorkloadData("", "!", "", 0.0, 0.0)

### END: FUNCTIONS FOR WORKLOAD/PAYMENT DETAILS ###

def timeslot2index(timeslot):
    """Convert a "timeslot" in the tag-form (e.g. "Mo.3") to a pair
    of 0-based indexes, (day, period).
    A null value means "unspecified time", returning (-1, -1).
    Invalid values cause a <ValueError> exception.
    """
    if timeslot:
        try:
            d, p = timeslot.split(".")  # Can raise <ValueError>
            return (get_days().index(d), get_periods().index(p))
        except (KeyError, ValueError):
            raise ValueError(T["INVALID_TIMESLOT"].format(val=timeslot))
    return -1, -1


def index2timeslot(index):
    """Convert a pair of 0-based indexes to a "timeslot" in the
    tag-form (e.g. "Mo.3").
    """
    d = get_days()[index[0]][0]
    p = get_periods()[index[1]][0]
    return f"{d}.{p}"
