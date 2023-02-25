"""
core/base.py

Last updated:  2023-01-07

Basic configuration and structural stuff.

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

NO_DATE = "*"  # an unspecified date

########################################################################

import sys, os, re, builtins, datetime
from typing import Optional, Tuple

if __name__ == "__main__":
    # Enable package import if running module directly
    this = sys.path[0]
    appdir = os.path.dirname(this)
    sys.path[0] = appdir
else:
    appdir = sys.path[0]
basedir = os.path.dirname(appdir)

def __programdata(path):
    """Return a path within the school-data folder.
    <path> is a '/'-separated path relative to this folder.
    """
    return os.path.join(basedir, "wz-data", *path.split("/"))
builtins.APPDATAPATH = __programdata

### +++++

class Bug(Exception):
    pass
builtins.Bug = Bug

class DataError(Exception):
    pass

from minion2 import Minion

_Minion = Minion()
builtins.MINION = _Minion.parse_file

__TRANSLATIONS = MINION(APPDATAPATH("Translations.minion"))
def __translations(module):
    return __TRANSLATIONS[module]
builtins.TRANSLATIONS = __translations

T = TRANSLATIONS("core.base")

### -----

def report(mtype, text):
    """The default reporting function prints to stdout.
    It can be overridden later.
    """
    print("%s: %s" % (mtype, text), flush=True)

builtins.REPORT = report


# TODO: configuration/settings file?
# posix: os.path.expanduser('~/.config/WZ')
# win: os.path.expanduser('~\\AppData\\Local\\Programs\\WZ\\config')
# Could use the "winpath" package, but it seems unnecessary!
# Can perhaps also install to the WZ folder on windows?
# Perhaps there can also be a launcher there (see python)?
# On Linux install to .local/(bin, lib, share)? or to ~/bin/WZ?


class start:
    """Initialize data paths, etc."""

    __DATA = None  # Base folder for school data

    @classmethod
    def setup(cls, datadir):
        """<datadir> is the full path to the folder containing the
        application data (i.e. the school data).
        """
        cls.__DATA = datadir
        builtins.DATAPATH = cls.__datadir
        builtins.RESOURCEPATH = cls.__resourcedir
        builtins.CONFIG = MINION(DATAPATH("CONFIG/BASE"))
        builtins.CALENDAR = Dates.get_calendar(DATAPATH("CONFIG/Calendar"))
        builtins.SCHOOLYEAR = Dates.calendar_year(CALENDAR)

    @classmethod
    def __datadir(cls, path, base=""):
        """Return a path within the school-data folder.
        <path> is a '/'-separated path relative to this folder.
        <base> is an optional alternative, '/'-separated base folder
        within the data folder.
        """
        return os.path.join(cls.__DATA, *base.split("/"), *path.split("/"))

    @classmethod
    def __resourcedir(cls, path):
        """Return a path within the resources folder.
        <path> is a '/'-separated path relative to this folder.
        """
        return os.path.join(cls.__DATA, "RESOURCES", *path.split("/"))

    @staticmethod
    def year_data_path(year, path=""):
        """Return the directory (full path) containing the data for the
        given year.
        """
        return os.path.join(basedir, f"DATA-{year}", *path.split("/"))

class Dates:
    @staticmethod
    def print_date(date, date_format, trap=True):
        """Convert a date string from the program format (e.g. "2016-12-06")
        to the format used for output (e.g. "06.12.2016").
        If an invalid date is passed, a <DataError> is raised, unless
        <trap> is false. In that case <None> – an invalid date – is returned.
        """
        try:
            d = datetime.datetime.strptime(date, "%Y-%m-%d")
            return d.strftime(date_format)
        except:
            if trap:
                raise DataError(T["BAD_DATE"].format(date=date))
        return None

    @classmethod
    def today(cls, iso=True):
        """Get the current date, normally in YYYY-MM-DD format.
        If <iso> is false it will used the format produced by <dateConv>.
        """
        today = None
        # Allow "faking" the current date (at least in some respects ...).
        fakepath = DATAPATH("__TODAY__")
        if os.path.isfile(fakepath):
            with open(fakepath, encoding="utf-8") as fh:
                while True:
                    l = fh.readline().strip()
                    if l and l[0] != "#":
                        today = l
                        break
        if not today:
            today = datetime.date.today().isoformat()
        return today if iso else cls.dateConv(today)

    @staticmethod
    def timestamp():
        """Return a "timestamp", accurate to the minute.
        It can be used for dating files, etc.
        """
        return datetime.datetime.now().isoformat(sep="_", timespec="minutes")

    @staticmethod
    def next_year() -> str:
        return str(int(SCHOOLYEAR) + 1)

    @staticmethod
    def day1(schoolyear):
        """Return the date of the first day of the school year."""
        m1 = int(CONFIG["SCHOOLYEAR_MONTH_1"])
        y = schoolyear if m1 == 1 else str(int(schoolyear) - 1)
        return f"{y}-{m1:02}-01"

    @classmethod
    def lastday(cls, schoolyear):
        d = datetime.date.fromisoformat(cls.day1(str(int(schoolyear) + 1)))
        return (d - datetime.timedelta(days=1)).isoformat()

    @classmethod
    def check_schoolyear(cls, schoolyear, d):
        """Test whether the given date <d> lies within the schoolyear.
        <d> must be in isoformat.
        Return true/false.
        """
        d1 = cls.day1(schoolyear)
        oneday = datetime.timedelta(days=1)
        d2 = cls.lastday(schoolyear)
        try:
            datetime.date.fromisoformat(d)
        except ValueError:
            raise DataError(T["BAD_DATE"].format(date=d))
        if d < d1:
            return False
        return d <= d2

    @classmethod
    def get_schoolyear(cls, d=None):
        """Return the school-year containing the given date <d>.
        If no date is given, use "today".
        """
        if not d:
            d = cls.today()
        y = int(d.split("-", 1)[0])
        if d >= cls.day1(y + 1):
            return str(y + 1)
        return str(y)

    @classmethod
    def save_calendar(cls, text, fpath=None):
        """Save the given text as a calendar file to the given path.
        If no path is supplied, don't save.
        If the path is '*', save as the current calendar file.
        Some very minimal checks are made.
        Return the (modified) text.
        """
        print("SAVE CALENDAR", fpath)
        cls.check_calendar(_Minion.parse(text))  # check the school year
        header = CONFIG["CALENDAR_HEADER"].format(date=cls.today())
        try:
            text = text.split("#---", 1)[1]
            text = text.lstrip("-")
            text = text.lstrip()
        except:
            pass
        text = header + text
        if fpath:
            if fpath == '*':
                fpath = DATAPATH("CONFIG/Calendar")
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            with open(fpath, "w", encoding="utf-8") as fh:
                fh.write(text)
        return text

    @classmethod
    def get_calendar(cls, fpath):
        """Parse the given calendar file (full path):"""
        cal = MINION(fpath)
        cls.check_calendar(cal)
        return cal

    @classmethod
    def check_calendar(cls, calendar):
        """Check the given calendar object."""
        schoolyear = cls.calendar_year(calendar)
        # Check that the year is reasonable
        y0 = cls.today().split("-", 1)[0]
        try:
            y1 = int(schoolyear)
        except ValueError:
            raise DataError(T["INVALID_SCHOOLYEAR"].format(year=schoolyear))
        if y1 < int(y0) or y1 > int(y0) + 2:
            raise DataError(T["DODGY_SCHOOLYEAR"].format(year=schoolyear))
        for k, v in calendar.items():
            if isinstance(v, list):
                # range of days, check validity
                if k[0] == "~" or (
                    cls.check_schoolyear(schoolyear, v[0])
                    and cls.check_schoolyear(schoolyear, v[1])
                ):
                    continue
            else:
                # single day or year field, check validity
                if "SCHOOLYEAR" in k:
                    continue
                if k[0] == "~" or cls.check_schoolyear(schoolyear, v):
                    continue
            raise DataError(T["BAD_DATE_CAL"].format(line="%s: %s" % (k, v)))
        return calendar

    @staticmethod
    def calendar_year(calendar):
        """Return the school-year of the given calendar."""
        try:
            return calendar["LAST_DAY"].split("-", 1)[0]
        except KeyError:
            raise DataError(T["MISSING_LAST_DAY"])

    @classmethod
    def migrate_calendar(cls, new_year=None, calendar_path=None, save=True):
        """Generate a "starter" calendar for the given school-year.
        It simply takes the given calendar and changes anything that
        looks like a year to fit the new year. It of course still needs
        extensive editing, but it should allow the new year to be opened.
        If no calendar file is supplied, use the currently active one.
        If no <new_year> is supplied, use the one following the currently
        active one.
        """

        def fn_sub(m):
            y = m.group(1)
            if y == old_lastyear:
                y = new_lastyear
            elif y == old_year:
                y = new_year
            return y

        calfile = calendar_path or DATAPATH("CONFIG/Calendar")
        with open(calfile, "r", encoding="utf-8") as fh:
            caltext = fh.read()
        if not new_year:
            new_year = cls.next_year()
        old_year = cls.calendar_year(_Minion.parse(caltext))
        old_lastyear = str(int(old_year) - 1)
        new_lastyear = str(int(new_year) - 1)
        rematch = r"([0-9]{4})"
        text = re.sub(rematch, fn_sub, caltext)
        if save:
            path = start.year_data_path(new_year, "CONFIG/Calendar")
            return cls.save_calendar(text, fpath=path)
        return cls.save_calendar(text)


def class_group_split(class_group: str) -> Tuple[str,str]:
    """Split a full group descriptor (class.group) into class and group.
    """
    try:
        class_group, g = class_group.split(".", 1)
    except ValueError:
        g = ""
    return class_group, g


def class_group_join(klass:str, group: Optional[str] = None) -> str:
    """Make a full group descriptor (class or class.group) from the
    given class and optional group.
    """
    if group:
        return f"{klass}.{group}"
    return klass


# TODO:
import tarfile

# tarfile doesn't have the encoding problems some
# filenames have with zipfile.
def archive_testdata():
    # The filter is perhaps a nice idea, but I suspect it is not really of
    # much practical use. If an archive is unpacked by a normal user, its
    # contents will be owned by that user anyway.
    def owner(tf0):
        tf0.uid = 0
        tf0.gid = 0
        tf0.uname = "root"
        tf0.gname = "root"
        return tf0

    with tarfile.open("testdata.tar.gz", "w:gz") as tf:
        for root, directories, files in os.walk("TESTDATA"):
            if os.path.basename(root) == "tmp":
                continue
            for filename in files:
                #                tf.add(os.path.join(root, filename), filter = owner)
                tf.add(os.path.join(root, filename))


# To read just one file
# tx = tf.extractfile('TESTDATA/CONFIG')
# tx.read() -> <bytes>


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":

# TODO: use TESTDATA?
    #start.setup(os.path.join(basedir, 'TESTDATA'))
    #start.setup(os.path.join(basedir, "DATA"))
    start.setup(os.path.join(basedir, "DATA-2023"))
    print("Today (possibly faked):", Dates.today())
    print("Current school year:", Dates.get_schoolyear())
    print("School year of data:", SCHOOLYEAR)
    print("A date:", Dates.print_date("2016-04-25", "%d.%m.%Y"))
    try:
        print("BAD Date:", Dates.print_date("2016-02-30", "%d.%m.%Y"))
    except DataError as e:
        print(" ... trapped:", e)
    new_year = Dates.next_year()
    print(f"\n\nCalendar for {new_year}:\n" + Dates.migrate_calendar(save=False))
