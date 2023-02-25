"""
core/teachers.py - last updated 2022-07-10

Manage teacher data.

=+LICENCE=================================
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
=-LICENCE=================================
"""

###############################################################

import sys, os

if __name__ == "__main__":
    # Enable package import if running as module
    this = sys.path[0]
    appdir = os.path.dirname(this)
    sys.path[0] = appdir
    basedir = os.path.dirname(appdir)
    from core.base import start

    #    start.setup(os.path.join(basedir, 'TESTDATA'))
    # start.setup(os.path.join(basedir, "DATA"))
    # start.setup(os.path.join(basedir, "NEXT"))
    start.setup(os.path.join(basedir, "DATA-2023"))

# T = TRANSLATIONS("core.teachers")

### +++++

from typing import NamedTuple

from core.db_access import open_database, db_read_fields, read_pairs

### -----


class TeacherData(NamedTuple):
    tid: str
    firstname: str
    lastname: str
    signed: str
    sortname: str
    tt_data: str


class Teachers(dict):
    """Reader for teacher data.
    An instance of this class is a <dict> holding the teacher data as a
    mapping: {tid -> <TeacherData> instance}.
    The dictionary is ordered by SORTNAME.
    """

    def __init__(self):
        super().__init__()
        # ?        open_database()
        for (
            tid,
            firstname,
            lastname,
            signed,
            sortname,
            tt_data,
        ) in db_read_fields(
            "TEACHERS",
            ("TID", "FIRSTNAMES", "LASTNAMES", "SIGNED", "SORTNAME", "TT_DATA"),
            sort_field="SORTNAME",
        ):
            self[tid] = TeacherData(
                tid=tid,
                firstname=firstname,
                lastname=lastname,
                signed=signed,
                sortname=sortname,
                tt_data=dict(read_pairs(tt_data)),
            )

    def name(self, tid):
        data = self[tid]
        return f"{data.firstname} {data.lastname}"

    # deprecated?
    def list_teachers(self):
        return list(self)


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    open_database()

    teachers = Teachers()
    for tid, tiddata in teachers.items():
        print(f"\n  {tid}: {teachers.name(tid)} // {tiddata}")
