"""
core/pupils.py - last updated 2023-04-28

Manage pupil data.

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

#TODO: freshly copied over from WZ ...

import sys, os

if __name__ == "__main__":
    # Enable package import if running as module
    this = sys.path[0]
    appdir = os.path.dirname(this)
    sys.path[0] = appdir
    basedir = os.path.dirname(appdir)
    from core.base import start

    #    start.setup(os.path.join(basedir, 'TESTDATA'))
    start.setup(os.path.join(basedir, "DATA-2023"))

T = TRANSLATIONS("core.pupils")

### +++++

from core.db_access import (
    db_read_table,
    db_read_unique_entry,
    NoRecord,
    db_new_row,
    db_delete_rows,
    db_update_fields,
)
from core.base import class_group_split
from core.basic_data import SHARED_DATA, get_classes, clear_cache
from local.local_pupils import (
    next_class,
    migrate_special,
    read_pupils_source,
)

### -----


def pupil_data(pid, allow_none=False):
    """Return a mapping of the pupil-data for the given pupil-id.
    IMPORTANT: This data is not cached.
    """
    try:
        flist, row = db_read_unique_entry("PUPILS", PID=pid)
    except NoRecord:
        if allow_none:
            return None
        raise Bug(T["UNKNOWN_PID"].format(pid=pid))
    return dict(zip(flist, row))


def get_pupil_fields():
    return {f[0]: f[1:] for f in CONFIG["PUPILS_FIELDS"]}


def get_pupils(klass, use_cache=True):
    """Return a list of data mappings, one for each member of the given class.
    This data is cached by default, so subsequent calls get the same instance.
    """
    key = f"PUPILS_{klass}"
    if use_cache:
        try:
            return SHARED_DATA[key]
        except KeyError:
            pass
    field_list = get_pupil_fields()
    pupils = []
    for row in db_read_table(
        "PUPILS",
        field_list,
        sort_field="SORT_NAME",
        CLASS=klass,
    )[1]:
        pupils.append(dict(zip(field_list, row)))
    SHARED_DATA[key] = pupils
    return pupils


def pupils_in_group(class_group, date=None):
    """Read the pupil data for the given school-class (possibly with
    group specifier, e.g. "12G.A").
    Return a list of mappings {field -> value} (the table rows), the
    pupils being ordered alphabetically.
    If <date> is supplied, pupils who left the school before that
    date will not be included.
    """
    k, g = class_group_split(class_group)
    plist = []
    for pdata in get_pupils(k):
        if (not g) or g in pdata["GROUPS"].split():
            if date:
                # Check exit date
                if exd := pdata.get("EXIT_D"):
                    if exd < date:
                        continue
            plist.append(pdata)
    return plist


def pupil_name(pupil_data):
    """Return the short-name of the pupil."""
    return f"{pupil_data['FIRSTNAME']} {pupil_data['LASTNAME']}"


def final_year_pupils():
    """Return lists of pupils in their final year:
    {class: [(pid, name), ... ], ...}
    """
    collect = {}
    for k_g in CONFIG["LEAVING_GROUPS"]:
        for pdata in pupils_in_group(k_g):
            k = pdata["CLASS"]
            item = (pdata["PID"], pupil_name(pdata))
            try:
                collect[k].append(item)
            except KeyError:
                collect[k] = [item]
    return collect


def migrate_pupils():
    """Migrate all pupils to the next class.
    This is a preparation for the next school year.
    Return a mapping {new-class: pupil-data-list}.
    A second result returns a mapping containing pupils who would
    normally leave the school at the end of the year. In this mapping
    the classes are not changed.
    Pupils with explicit leaving dates before the start of the next year
    will be dropped.
    """
    date1 = CALENDAR["~NEXT_FIRST_DAY"]
    leavers = {}
    for cg in CONFIG.get("LEAVING_GROUPS") or []:
        for pdata in pupils_in_group(cg, date=date1):
            leavers[pdata["PID"]] = pdata.copy()
    migrated = {}
    classes = get_classes()
    for klass, name in classes.get_class_list():
        try:
            new_class = CONFIG["MIGRATE_CLASS"][klass]
        except KeyError:
            new_class = next_class(klass)
        class_list = []
        for pdata in pupils_in_group(klass, date=date1):
            pid = pdata["PID"]
            if pid not in leavers:
                new_pdata = pdata.copy()
                new_pdata["CLASS"] = new_class
                migrate_special(new_pdata)
                class_list.append(new_pdata)
        if class_list:
            migrated[new_class] = class_list
    return migrated, leavers


def compare_update(newdata):
    """Compare the new data with the existing data and compile a list
    of changes. There are three types:
        - new pupil
        - pupil to remove (pupils shouldn't be removed within a
          school-year, just marked in DATE_EXIT, but this could be
          needed for patching or migrating to a new year)
        - field(s) changed.
    """
    pupils_delta = []
    # Get a mapping of all current pupils: {pid: pupil-data}
    current_pupils = {}
    classes = get_classes()
    for klass, kname in classes.get_class_list():
        for pdata in get_pupils(klass):
            current_pupils[pdata["PID"]] = pdata
    first_day = CALENDAR["FIRST_DAY"]
    for pdata in newdata:
        date_exit = pdata["DATE_EXIT"]
        if date_exit and date_exit < first_day:
            continue
        try:
            olddata = current_pupils.pop(pdata["PID"])
        except KeyError:
            # New pupil
            pupils_delta.append(("NEW", pdata))
            continue
        # Compare the fields of the old pupil-data with the new ones.
        # Build a list of pairs detailing the deviating fields:
        #       [(field, new-value), ...]
        # Only the fields of the new data are taken into consideration.
        delta = [(k, v) for k, v in pdata.items() if v != olddata[k]]
        if delta:
            pupils_delta.append(("DELTA", olddata, delta))
    # Add removed pupils to list
    for pid, pdata in current_pupils.items():
        pupils_delta.append(("REMOVE", pdata))
    return pupils_delta


def update_classes(changes):
    """Apply the changes in the <changes> lists to the pupil data.
    The entries are basically those generated by <compare_update>,
    but it would be possible to insert a filtering step before
    calling this function, e.g in the GUI.
    """
    print("\n???????????????????\n", changes)
    for d in changes:
        pdata = d[1]
        if d[0] == "NEW":
            #print("\n§§§§§ ADD", pdata)
            # Add to pupils
            db_new_row("PUPILS", **pdata)
        elif d[0] == "REMOVE":
            #print("\n§§§§§ REMOVE", pdata)
            # Remove from pupils
            db_delete_rows("PUPILS", PID=pdata["PID"])
        elif d[0] == "DELTA":
            #print("\n§§§§§ UPDATE", pdata, "\n  :::", d[2])
            # Changes field values
            db_update_fields("PUPILS", d[2], PID=pdata["PID"])
        else:
            raise Bug("Bad delta key: %s" % d[0])
    clear_cache()


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database

    open_database()

    # TODO: switch to test data ...

    # get_pupils("11G")

    __k = "11G.R"
    print(f"\nPupils in {__k}:")
    for pdata in pupils_in_group(__k):
        print("  +++", pdata)
        pid = pdata["PID"]

    print(f"\nDATA FOR PID={pid}:")
    print(pupil_data(pid))

    migrated, leavers = migrate_pupils()
    print(f"\nMIGRATE TO {int(SCHOOLYEAR) + 1}")

    print("\nFinal-year pupils:")
    for pdata in leavers.values():
        print("  +++", pdata)

    print("\nImported pupils:")
    plist = read_pupils_source(RESOURCEPATH("import_pupils"))
    for pdata in plist[:20]:
        print(" ::: ", pdata)
    print("\n     ...\n")
    for pdata in plist[-20:]:
        print(" ::: ", pdata)

    print("\nDELTA")
    delta = compare_update(plist)
    for line in delta:
        print("    ...", line)

    ### CAREFUL with this!
    #print("\n UPDATING PUPILS IN DB!")
    #update_classes(delta)

    quit(0)

    # ?????????
    _ptables = Pupil_File(
        DATAPATH("testing/delta_test_pupils_2016.ods"), extend=False
    )

    _delta = pupils.compare_update(_ptables)
    for k, dlist in _delta.items():
        print("\n --- KLASSE:", k)
        for d in dlist:
            print("  ", d)
    pupils.update_classes(_delta)

    ### Show the information for all pupils in a class
    _klass = "12"
    print("\n $$$", _klass)
    plist = pupils.class_pupils(_klass)
    for pdata in plist:
        print("\n :::", pdata)

    ### Show the information for a single pupil, keyed by pid
    _pid = "200502"
    _pdata = pupils[_pid]
    print("\n PUPIL %s (class %s)" % (_pdata["PID"], _pdata["CLASS"]))
    print("  ", _pdata)

    ### Update the pupil data with some changes from a new "master" table
    print("\n§§§ CHECK PUPILS UPDATE §§§")
    _ptables = Pupil_File(
        DATAPATH("testing/delta_test_pupils_2016.ods"), extend=False
    )
    _delta = pupils.compare_update(_ptables)
    for klass, changes in _delta.items():
        print("CLASS %s:" % klass)
        for c in changes:
            print("  $  ", c)
    pupils.update_classes(_delta)

    ### Revert the changes by "updating" from a saved table
    _ptables = Pupil_File(DATAPATH("testing/PUPILS_2016.tsv"))
    _delta = pupils.compare_update(_ptables)
    for k, dlist in _delta.items():
        print("\n --- KLASSE:", k)
        for d in dlist:
            print("  ", d)
    pupils.update_classes(_delta)
