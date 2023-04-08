"""
core/classes.py - last updated 2023-04-07

Manage class data.

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

if __name__ == "__main__":
    import sys, os

    this = sys.path[0]
    appdir = os.path.dirname(this)
    sys.path[0] = appdir
    basedir = os.path.dirname(appdir)
    from core.base import start

    start.setup(os.path.join(basedir, 'TESTDATA'))

T = TRANSLATIONS("core.classes")

### +++++

from typing import NamedTuple
from itertools import combinations, product

from core.db_access import open_database, db_read_fields

class Subgroup(frozenset):
    """This <frozenset> wrapper is used for groups and subgroups within
    a class.
    """
    def __str__(self):
        return '.'.join(sorted(self))

### -----

class Classes(dict):
    def __init__(self):
        super().__init__()
        self.__group_info = {}
        # ?    open_database()
        for klass, name, classroom, divisions in db_read_fields(
            "CLASSES",
            ("CLASS", "NAME", "CLASSROOM", "DIVISIONS"),
            sort_field="CLASS",
        ):
            self[klass] = ClassData(
                klass=klass,
                name=name,
                divisions=ClassGroups(divisions),
                classroom=classroom,
            )

    def get_class_list(self, skip_null=True):
        classes = []
        for k, data in self.items():
            if k == "--" and skip_null:
                continue
            classes.append((k, data.name))
        return classes

    def get_classroom(self, klass, null_ok=False):
        if (not null_ok) and klass == "--":
            raise Bug("Empty class has no classroom")
        return self[klass].classroom


class ClassGroups:
    """Manage the groups of pupils within a class.
    A primary group is designated by an alphanumeric string.
    A class may be divided in several ways, each division being a list
    of primary groups. Each group may only occur in a single division.
    Also subgroups are possible, combining groups from various divisions.
    To avoid confusion, subgroup names order the primary group names
    according to their divisions. If there are two divisions, "A+Z"
    and "P+Q", the subgroup "Z.P" will be chosen rather than "P.Z".
    The cartesian product of all the divisions gives the smallest
    independent subgroups. Some of these may be empty (no pupils). It
    is possible to specify which of these minimal subgroups ("atomic"
    groups) are empty, which can simplify (well, shorten ...) group naming.
    """
    def __init__(self, source:str):
        self.source = source
        divs = source.replace(' ', '')
        # Split off empty subgroups
        empty_subgroups = divs.split('-')
        divs = empty_subgroups[0]
        self.subgroup_empties = {
            self.group2set(s): s for s in empty_subgroups[1:]
        }
        if divs:
            self.init_divisions(divs.split(';'))
        else:
            self.init_divisions([])
        elist = self.filter_atomic_groups()
        if elist:
            prefix = "\n - "
            REPORT(
                "ERROR",
                T["GROUP_ERRORS"].format(
                    source=source, prefix=prefix, errors=prefix.join(elist)
                )
            )
 
    def init_divisions(
        self,
        divlist:list[str],
        report_errors:bool=True
    ) -> str:
        self.primary_groups = set()
        self.divisions = []
        if divlist:
            for div in divlist:
                gset, e = self.check_division(div, self.primary_groups)
                if e:
                    if report_errors:
                        REPORT(
                            "ERROR",
                            T["CLASS_GROUPS_ERROR"].format(
                                text=self.source, e=e
                            )
                        )
                    else:
                        return e
                else:
                    self.divisions.append(gset)
            self.atomic_groups = frozenset(
                Subgroup(ag) for ag in product(*self.divisions)
            )
        else:
            self.atomic_groups = frozenset()
        return ""

    def check_division(
        self,
        div:str,
        all_groups:set[str]
    ) -> tuple[set[str],str]:
        divset = set()
        for g in div.split('+'):
            if not g.isalnum():
                return (
                    divset,
                    T["INVALID_GROUP_TAG"].format(
                        div=div,
                        g=g
                    )
                )
            if g in all_groups:
                return (
                    divset,
                    T["REPEATED_GROUP"].format(
                        div=div,
                        g=g
                    )
                )
            divset.add(g)
            all_groups.add(g)
        if len(divset) > 1:
            return (divset, "")
        return (divset, T["TOO_FEW_GROUPS"].format(div=div))

    def division_lines(self) -> list[str]:
        """Return a list of the divisions as text lines.
        """
        return [
            "+".join(sorted(d))
            for d in self.divisions
        ]

    def text_value(self) -> str:
        """Return a text representation of the data:
            - divisions as '+'-separated primary groups
            - divisions seprated by ';'
            - after the divisions a '-'-separated empty subgroup list
              (there is a '-' before the first such subgroup, too)
            - the empty subgroups must be valid "atomic" groups
        """
        divs = ';'.join(self.division_lines())
        if self.subgroup_empties:
            empties = [self.set2group(fs) for fs in self.subgroup_empties]
            empties.sort()
            return f"{divs}-{'-'.join(empties)}"
        return divs

    def group2set(self, g:str) -> Subgroup[str]:
        return Subgroup(g.split('.'))

    def set2group(self, s:set) -> str:
        glist = []
        for d in self.divisions:
            isct = s & d
            if len(isct) == 1:
                for g in isct: break
                glist.append(g)
            elif len(isct) != 0:
                raise Bug(f"Invalid class-group: '{s}'")
        if len(glist) != len(s):
            raise Bug(f"Invalid class-group: '{s}'")
        return ".".join(glist)

    def filter_atomic_groups(self) -> list[str]:
        self.filtered_atomic_groups = {
            Subgroup(ag) for ag in self.atomic_groups
        }
        elist = []
        if self.subgroup_empties:
            # Remove the specified empty atomic groups
            duds = set()
            for fs, sub in self.subgroup_empties.items():
                try:
                    self.filtered_atomic_groups.remove(fs)
                except KeyError:
                    duds.add(fs)
                    elist.append(T["FILTER_NOT_ATOM"].format(sub=sub))
            for fs in duds:
                del(self.subgroup_empties[fs])
        # Get the (filtered) atomic groups for the primary groups
        gdict = {}
        for bg in self.primary_groups:
            faglist = []
            for fag in self.filtered_atomic_groups:
                if bg in fag:
                    faglist.append(fag)
            if faglist:
                gdict[frozenset(faglist)] = Subgroup([bg])
            else:
                elist.append(T["EMPTY_GROUP"].format(g=bg))
        # Add the atomic groups for all possible subgroups, starting
        # with the shortest
        for l in range(2, len(self.divisions)):
            c_set = set()
            for fag in self.filtered_atomic_groups:
                for c in combinations(fag, l):
                    c_set.add(Subgroup(c))
            for c in c_set:
                faglist = []
                for fag in self.filtered_atomic_groups:
                    if c < fag:
                        faglist.append(fag)
                if faglist:
                    fs = frozenset(faglist)
                    if fs not in gdict:
                        gdict[fs] = c
        # Add atomic groups, if they are not already represented by
        # shorter group tags
        for fag in self.filtered_atomic_groups:
            fs = Subgroup([fag])
            if fs not in gdict:
                gdict[fs] = fag
        # Reverse the mapping to get the group -> atoms mapping
        self.group2atoms = {v: k for k, v in gdict.items()}
        return elist


class ClassData(NamedTuple):
    klass: str
    name: str
    divisions: ClassGroups
    classroom: str


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":

    for cglist in (
        "G+R;A+B;I+II+III-A.R.I-A.R.II-A.R.III-B.G.I-B.G.II",
        "",
        "A+B;G+R;B+A-A.R",
        "A+B;G+r:I+II+III",
    ):
        cg = ClassGroups(cglist)
        print(f"\n{cglist} ->", cg.filtered_atomic_groups)
        print("divisions:", cg.divisions)
        for g, alist in cg.group2atoms.items():
            print(
                cg.set2group(g),
                "::",
                [cg.set2group(a) for a in alist]
            )
        print("%TEXT%", cg.text_value())
