"""
core/basic_data.py - last updated 2023-06-11

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

from typing import NamedTuple

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
__TAG_CHAR = "[A-Za-z0-9_.]"
TAG_FORMAT = QRegularExpression(f"^{__TAG_CHAR}+$")
BLOCK_TAG_FORMAT = QRegularExpression(f"^{__TAG_CHAR}*$")
WEIGHTS = {c for c in '-123456789+'}

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
    rooms = db_key_value_list("ROOMS", "RID", "NAME", sort_field="RID")
    SHARED_DATA["ROOMS"] = rooms
    return rooms


class ParallelTag(NamedTuple):
    TAG: str
    WEIGHTING: str

    @classmethod
    def build(cls, tag: str, weighting: str):
        if tag:
            if not TAG_FORMAT.match(tag).hasMatch():
                REPORT("ERROR", T["TAG_INVALID"].format(tag=tag))
                tag = ""
                weighting = '-'
            elif weighting not in WEIGHTS:
                REPORT(
                    "ERROR",
                    T["WEIGHT_OUT_OF_RANGE"].format(weight=weighting)
                )
                weighting = '-'
        elif weighting:
            REPORT("ERROR", T["WEIGHT_NO_TAG"].format(weight=weighting))
            weighting = ''
        return cls(tag, weighting)

    def __str__(self):
        if self.TAG:
            return f"{self.TAG}%{self.WEIGHTING}"
        return ""


class BlockTag(NamedTuple):
    sid: str        # must be a valid, known, subject-id
    tag: str        # see reg-exp BLOCK_TAG_FORMAT
    subject: str    # the subject-name

    @classmethod
    def read(cls, tag:str):
        """Decode the given block tag. Return a <BlockTag> instance.
        """
        try:
            s, t = tag.split("#", 1)
        except ValueError:
            raise ValueError(T["BLOCKTAG_INVALID"].format(tag=tag))
        return cls.build(s, t)

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
        if BLOCK_TAG_FORMAT.match(tag).hasMatch():
            return cls(sid, tag, subject)
        raise ValueError(T["BLOCKTAG_INVALID_TAG"].format(tag=tag))

    def __str__(self):
        return self. to_string(self.sid, self.tag)

    @staticmethod
    def to_string(sid, tag):
        return f"{sid}#{tag}"


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


'''
deprecated ...

def get_group_info(klass):
    tag = f"group_info_{klass}"
    try:
        return SHARED_DATA[tag]
    except KeyError:
        pass
    gi = get_classes()[klass].divisions
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
'''

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
            REPORT("ERROR", T["BAD_WEIGHT"].format(key=item[0], val=i2))
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


class Workload(NamedTuple):
    PAY_TAG: str
    NLESSONS: int
    PAY_FACTOR_TAG: str
    PAY_FACTOR: float
    PAYMENT: float

    @classmethod
    def build(cls, pay_tag:str):
        """Check the validity of the argument and extract the component
        parts. The results are saved as attributes.
        If any errors are detected, return a special "error" result:
            attribute PAY_TAG is then "!".
        """
        NL = 0
        PY = 0.0
        PFT = ""
        PF = 0.0
        if pay_tag:
            try:
                n, f = pay_tag.split("*", 1)
            except ValueError:
                try:
                    d = float(pay_tag.replace(",", "."))
                    if d < 0.1 or d > 50.0:
                        raise ValueError
                except ValueError:
                    pay_tag = "!"
                    REPORT(
                        "ERROR",
                        T["INVALID_PAY_TAG"].format(tag=pay_tag)
                    )
                else:
                    PY = d
            else:
                if n == ".":
                    # use actual number of lessons
                    NL = -1
                else:
                    try:
                        NL = int(n)
                        if NL < 1:
                            raise ValueError
                    except ValueError:
                        pay_tag = "!"
                        REPORT(
                            "ERROR",
                            T["INVALID_PAY_TAG"].format(tag=pay_tag)
                        )
                try:
                    v = get_payment_weights().map(f)
                    fd = float(v.replace(",", "."))
                    if fd < 0.1 or fd > 50.0:
                        raise ValueError
                except KeyError:
                    REPORT(
                        "ERROR",
                        T["UNKNOWN_PAYMENT_WEIGHT"].format(key=f)
                    )
                    pay_tag = "!"
                except ValueError:
                    REPORT(
                        "ERROR",
                        T["INVALID_PAYMENT_WEIGHT"].format(key=f, val=v)
                    )
                    pay_tag = "!"
                else:
                    PFT = f
                    PF = fd
                    if NL > 0:
                        PY = fd * NL
        return cls(pay_tag, NL, PFT, PF, PY)

    def payment(self, nlessons:int=None):
        # print("§Workload:", self)
        if self.NLESSONS == -1 and nlessons > 0:
            return self.PAY_FACTOR * nlessons
        return self.PAYMENT

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
