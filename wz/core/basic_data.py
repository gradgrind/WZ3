"""
core/basic_data.py - last updated 2022-11-05

Handle caching of the basic data sources

==============================
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
        "XDPT_WEIGHTINGS", "TAG", "WEIGHT", check=check
    )
    SHARED_DATA["PAYMENT"] = payment_weights
    return payment_weights


class BlockTag(NamedTuple):
    sid: str
    tag: str
    subject: str

    def isNone(self):
        return (not self.sid) and (not self.tag)

    def __str__(self):
        return f"{self.sid}#{self.tag}" if self.sid else self.tag


def read_block_tag(block_tag: str) -> BlockTag:
    """Decode the given block tag. Return a triple:
    (subject-id, identifier-tag, subject name).
    """
    if not block_tag:
        return BlockTag("", "", NO_SUBJECT)
    try:
        sid, tag = block_tag.split("#", 1)
    except ValueError:
        return BlockTag("", block_tag, NO_SUBJECT)
    try:
        subject = get_subjects().map(sid)
    except KeyError:
        raise ValueError(
            T["BLOCKTAG_UNKNOWN_SUBJECT"].format(tag=block_tag, sid=sid)
        )
    if not tag:
        return BlockTag(sid, "", subject)
    if TAG_FORMAT.match(tag).hasMatch():
        return BlockTag(sid, tag, subject)
    raise ValueError(T["BLOCKTAG_INVALID"].format(tag=block_tag))


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


class PaymentData(NamedTuple):
    number: str
    factor: str
    tag: str
#    divisor: str
    number_val: float
    factor_val: float

    def isNone(self):
        return not self.factor

    def __str__(self):
        if self.factor:
            t = f"/{self.tag}" if self.tag else ""
#            if self.divisor:
#                t += f"/{self.divisor}"
            return f"{self.number}*{self.factor}{t}"
        return ""


def read_payment(payment: str) -> Optional[PaymentData]:
    """Read the individual parts of a payment entry.
    If the input is invalid a <ValueError> exception wil be raised.
    """
    if not payment:
#        return PaymentData("", "", "", "", 0.0, 0.0)
        return PaymentData("", "", "", 0.0, 0.0)
    try:
        n, f = payment.split("*", 1)  # can raise ValueError
    except ValueError:
        raise ValueError(T["INVALID_PAYMENT"].format(text=payment))
    try:
        f, t = f.split("/", 1)
    except ValueError:
#        t, d = "", ""
        t = ""
    else:
        if not PAYMENT_TAG_FORMAT.match(t).hasMatch():
            raise ValueError(T["INVALID_PAYMENT_TAG"].format(text=t))
#        try:
#            t, d = t.split("/", 1)
#        except ValueError:
#            t, d = t, ""
    if n:
        try:
            if PAYMENT_FORMAT.match(n).hasMatch():
                nd = float(n.replace(",", "."))
                if nd < 0.0 or nd > PAYMENT_MAX:
                    raise ValueError
            else:
                raise ValueError
        except ValueError:
            raise ValueError(T["BAD_NUMBER"].format(val=n))
    else:
        nd = 0.0
    try:
        fd = float(get_payment_weights().map(f).replace(",", "."))
    except KeyError:
        raise ValueError(T["UNKNOWN_PAYMENT_WEIGHT"].format(key=f))
#    return PaymentData(n, f, t, d, nd, fd)
    return PaymentData(n, f, t, nd, fd)


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
