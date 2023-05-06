"""
local/pupil_support.py - last updated 2023-05-06

Manage pupil data – school/location specific code.

=+LICENCE=================================
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
=-LICENCE=================================
"""

T = TRANSLATIONS("core.pupils")

### +++++

#import re

from core.base import Dates
from core.db_access import db_read_unique_field, NoRecord
#from tables.spreadsheet import Spreadsheet, read_DataTable

### -----

def pupil_name(pupil_data):
    """Return the short-name of the pupil."""
    return f"{pupil_data['FIRSTNAME']} {pupil_data['LASTNAME']}"


def check_pid_valid(pid):
    """Check that the pid is of the correct form and not already
    in use.
    Return "" if acceptable, otherwise an error message.
    """
    # Accept any integer that isn't already in use.
    try:
        int(pid)
    except:
        return T["INVALID_PID"].format(pid=pid)
    try:
        db_read_unique_field("PUPILS", "PID", PID=pid)
    except NoRecord:
        return ""
    return T["PID_EXISTS"].format(pid=pid)
    

#TODO
def new_pid(pupils):
    """Generate a new pid conforming to the requirements of
    function <check_pid_valid>.
    """
    # Base the new pid on today's date, adding a number to the end.
    today = Dates.today().replace("-", "")  # it must be an integer
    collect = []
    for pid in pupils:
        if pid.startswith(today):
            try:
                i = int(pid[8:])
            except ValueError:
                continue
            collect.append(i)
    if collect:
        collect.sort()
        i = str(collect[-1] + 1)
    else:
        i = "1"
    return today + i


################### TO ADAPT FOR WZ3 ###################

def next_class(klass):
    """Find the class after the given one (for the following year)."""
    k_year = class_year(klass)
    k_new = int(k_year) + 1
    k_suffix = klass[2:]
    return f"{k_new:02}{k_suffix}"


def migrate_special(pdata):
    """Special migration changes for the locality."""
    # Handle entry into "Qualifikationsphase"
    if pdata["CLASS"] == "12G" and "G" in pdata["GROUPS"].split():
        try:
            pdata["DATE_QPHASE"] = CALENDAR["~NEXT_FIRST_DAY"]
        except KeyError:
            pass


def class_year(klass):
    """Get just the year part of a class name, as <str>, padded to
    2 digits.
    """
    try:
        k = int(klass[:2])
    except:
        k = int(klass[0])
    return f"{k:02}"


def get_remote_data():
    """Fetch the latest school pupil data – from an external source.
    At present this allows choosing and opening a table file containing
    the pupils' data and covering the whole school.
    """
    filetypes = " ".join(["*." + fte for fte in Spreadsheet.filetype_endings()])
    fpath = OPEN_FILE(f'{T["OPEN_TABLETYPE"]} ({filetypes})')
    if fpath:
        return read_pupils_source(fpath)
    else:
        return None


def read_pupils_source(filepath):
    """Read a spreadsheet file containing pupil data from an external
    "master" database.
    """
    try:
        xdb_fields = CONFIG["MASTER_DB"]
    except KeyError:
        return None
    necessary = {line[0] for line in CONFIG["PUPILS_FIELDS"] if line[4]}
    # Change class names, adjust pupil names ("tussenvoegsel")
    day1 = CALENDAR["FIRST_DAY"]
    pupils = []
    data = read_DataTable(filepath)
    for row in data["__ROWS__"]:
        irow = {}
        for f, t in xdb_fields:
            v = row[t]
            if (f in necessary) and (not v):
                REPORT(
                    "ERROR",
                    T["NECESSARY_FIELD_EMPTY"].format(field=t, row=repr(row)),
                )
            irow[f] = v
        if x := irow.get("DATE_EXIT"):
            if x < day1:
                continue
        klass = irow["CLASS"]
        try:
            if klass[-1] == "K":
                klass = f"{int(klass[:-1]):02}K"
                irow["CLASS"] = klass
            elif klass != "13":
                klass = f"{int(klass):02}G"
                irow["CLASS"] = klass
        except ValueError:
            raise ValueError(
                T["INVALID_CLASS"].format(
                    klass=klass, row=repr(row), path=filepath
                )
            )
        (
            irow["FIRSTNAMES"],
            irow["LASTNAME"],
            irow["FIRSTNAME"],
            sort_name,
        ) = tussenvoegsel_filter(
            irow["FIRSTNAMES"], irow["LASTNAME"], irow["FIRSTNAME"]
        )
        s_name = irow.get("SORT_NAME")
        if not s_name:
            s_name = sort_name
            irow["SORT_NAME"] = sort_name
        pupils.append((klass, s_name, irow))
        pupils.sort()
    return [p[-1] for p in pupils]


def get_sortname(pdata):
    """Construct a string to use in sorting pupil names and for
    pupil-related file names. The result should preferably be ASCII-only
    and without spaces, but that is not compulsory.
    """
    return tussenvoegsel_filter(
        pdata["FIRSTNAMES"], pdata["LASTNAME"], pdata["FIRSTNAME"]
    )[-1]
