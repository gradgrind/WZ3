"""
core/classes.py - last updated 2023-05-18

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

from typing import NamedTuple, Optional
from itertools import product

from core.db_access import open_database, db_read_fields

GROUP_ALL = "*"

### -----

class Classes(dict):
    def __init__(self):
        super().__init__()
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

    It is also possible to specify a short form for a set of primary
    groups within a division. For example, a division may contain groups
    A, BG and R. For convenience, the additional groups G=A+BG and B=BG+R
    may be defined.
    """
    def __init__(self, source:str):
        self.source = source
        if (divs := source.replace(' ', '')):
            self.init_divisions(divs.split(';'))
        else:
            self.init_divisions([])
 
    def init_divisions(
        self,
        divlist:list[str],
        report_errors:bool=True
    ) -> str:
        self.primary_groups = set()
        self.divisions = []
        div0 = []
        if divlist:
            for div in divlist:
                gmap, e = self.check_division(div, self.primary_groups)
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
                    self.divisions.append(gmap)
                div0.append(tuple(g for g, v in gmap if v is None))
            self.atomic_groups = ['.'.join(ag) for ag in product(*div0)]
        else:
            self.atomic_groups = []
        return ""

    def check_division(
        self,
        div:str,
        all_groups:set[str]
    ) -> list[ list[ str, Optional[list[str]] ] ]:
        divmap = []
        d_shortcuts = div.split('/')
        pgroups = []    # primary groups
        for g in d_shortcuts[0].split('+'):
            if not (g.isalnum() and g.isascii()):
                return (
                    divmap,
                    T["INVALID_GROUP_TAG"].format(div=div, g=g)
                )
            if g in all_groups:
                return (
                    divmap,
                    T["REPEATED_GROUP"].format(div=div, g=g)
                )
            pgroups.append(g)
            divmap.append([g, None])
            all_groups.add(g)
        # Manage group "shortcuts"
        for sc in d_shortcuts[1:]:
            try:
                g, gs = sc.split('=', 1)
            except ValueError:
                return (
                    divmap,
                    T["INVALID_GROUP_SHORTCUT"].format(text=sc)
                )
            if g in all_groups:
                return (
                    divmap,
                    T["REPEATED_GROUP"].format(div=div, g=g)
                )
            glist = sorted(gs.split('+'))
            if len(glist) < 2:
                return (
                    divmap,
                    T["TOO_FEW_PRIMARIES"].format(div=div, g=sc)
                )
            for gg in glist:
                if gg not in pgroups:
                    return(
                        divmap,
                        T["NOT_PRIMARY_GROUP"].format(div=div, g=gg)
                    )
            if len(glist) >= len(pgroups):
                return (
                    divmap,
                    T["TOO_MANY_PRIMARIES"].format(div=div, g=sc)
                )
            for gx, scx in divmap:
                if scx == glist:
                    return (
                        divmap,
                        T["REPEATED EXTRA"].format(div=div, g=gx, x=sc)
                    )
            all_groups.add(g)
            divmap.append([g, glist])
        if len(divmap) < 2:
            return (divmap, T["TOO_FEW_GROUPS"].format(div=div))
        return (divmap, "")

    def division_lines(self, with_extras=True) -> list[str]:
        """Return a list of the divisions as text lines.
        If <with_extras> is true, any "extra" groups will be included.
        """
        divs = []
        for div in self.divisions:
            glist = []
            sclist = []
            for g, v in div:
                if v is None:
                    glist.append(g)
                else:
                    # <v> is sorted (see method <check_division>)
                    sclist.append(f"{g}={'+'.join(v)}")
            pgroups = "+".join(glist)
            if with_extras and sclist:
                divs.append('/'.join([pgroups] + sclist))
            else:
                divs.append(pgroups)
        return divs
        
    def text_value(self) -> str:
        """Return a text representation of the data:
            - divisions as '+'-separated primary groups
            - followed by optional "shortcuts"
            - divisions seprated by ';'
        """
        return ';'.join(self.division_lines())

    def group_atoms(self):
        """Build a mapping from the primary groups – including the
        "shortcuts" – to their constituent "atomic groups",
            {group: [atom, ... ]}
        """
        g2a = {}
        for ag in self.atomic_groups:
            for g in ag.split('.'):
                try:
                    g2a[g].append(ag)
                except KeyError:
                    g2a[g] = [ag]
        # Add "shortcuts"
        for div in self.divisions:
            for g, v in div:
                if v is None:
                    continue
                ggs = set()
                for gg in v:
                    ggs.update(g2a[gg])
                g2a[g] = sorted(ggs)
        return g2a


class ClassData(NamedTuple):
    klass: str
    name: str
    divisions: ClassGroups
    classroom: str


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":

    for cglist in (
        "A+BG+R/G=A+BG/B=BG+R",
        "A+BG+R/G=A+BG/B=BG+R;I+II+III",
        "",
        "A+B;G+R",
        "E+e;k+m+s/K=m+s/M=k+s/S=k+m",
    ):
        cg = ClassGroups(cglist)
        print("\ndivisions:", cg.divisions)
        print("atomic groups:", cg.atomic_groups)
        print(" -->", cg.text_value())

        for g, alist in cg.group_atoms().items():
            print(f" *** {g} ->", alist)



    quit(0)
   
    if True:

        for g, alist in cg.group2atoms.items():
            print(
#                cg.set2group(g),
                g,
                "::",
#                [cg.set2group(a) for a in alist]
                alist
            )
        print("%TEXT%", cg.text_value())
