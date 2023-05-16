"""
core/classes.py - last updated 2023-05-01

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

#deprecated?
class Subgroup(frozenset):
    """This <frozenset> wrapper is used for groups and subgroups within
    a class.
    The <__str__> method does not follow the intentions of <ClassGroups>, it
    is primarily for testing purposes within this module itself. For
    "correctness" use the <set2group> method of <ClassGroups>.
    """
    def __str__(self):
        return '.'.join(sorted(self))

#deprecated?
class Groupset(frozenset):
    """A <frozenset> wrapper  modifying the <__str__> method.
    The <__str__> method does not follow the intentions of <ClassGroups>, it
    is primarily for testing purposes within this module itself.
    """
    def __str__(self):
        return f"<<{' + '.join(sorted((str(m) for m in self)))}>>"

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
        
        
        return
#?
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
                div0.append(tuple(g for g, v in gmap.items() if v is None))
            self.atomic_groups = ['.'.join(ag) for ag in product(*div0)]
        else:
            self.atomic_groups = []
        return ""

    def check_division(
        self,
        div:str,
        all_groups:set[str]
    ) -> tuple[set[str],str]:
        divmap = {}
        d_shortcuts = div.split('/')
        for g in d_shortcuts[0].split('+'):
            if not g.isalnum():
                return (
                    divmap,
                    T["INVALID_GROUP_TAG"].format(
                        div=div,
                        g=g
                    )
                )
            if g in all_groups:
                return (
                    divmap,
                    T["REPEATED_GROUP"].format(
                        div=div,
                        g=g
                    )
                )
            divmap[g] = None
            all_groups.add(g)
        # Manage group "shortcuts"
        sclist = []
        for sc in d_shortcuts[1:]:
            try:
                g, gs = sc.split('=', 1)
                if g in all_groups:
                    return (
                        divmap,
                        T["REPEATED_GROUP"].format(
                            div=div,
                            g=g
                        )
                    )
                
                glist = sorted(gs.split('+'))
                if len(glist) < 2:
                    raise ValueError
                for gg in glist:
                    if gg not in divmap:
                        raise ValueError
                for _g, scx in sclist:
                    if scx == glist:
                        raise ValueError
            except ValueError:
                return (
                    divmap,
                    T["INVALID_GROUP_SHORTCUT"].format(text=sc)
                )
            all_groups.add(g)
            sclist.append((g, glist))
            divmap[g] = glist
        if len(divmap) > 1:
            return (divmap, "")
        return (divmap, T["TOO_FEW_GROUPS"].format(div=div))

    def division_lines(self) -> list[str]:
        """Return a list of the divisions as text lines.
        """
        divs = []
        for div in self.divisions:
            glist = []
            sclist = []
            for g in sorted(div):
                v = div[g]
                if v is None:
                    glist.append(g)
                else:
                    # <v> is sorted (see method <check_division>)
                    sclist.append(f"{g}={'+'.join(v)}")
            
            divs.append('/'.join(["+".join(glist)] + sclist))
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
            for g, v in div.items():
                if v is None:
                    continue
                ggs = set()
                for gg in v:
                    ggs.update(g2a[gg])
                g2a[g] = sorted(ggs)
        return g2a


#???
    def group2set(self, g:str) -> Subgroup[str]:
        return Subgroup(g.split('.'))

#???
    def set2group(self, s:set) -> str:
        if str(s) == "*": return "*"
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

#deprecated???
    def filter_atomic_groups(self) -> list[str]:
        filtered_atomic_groups = {
            Subgroup(ag) for ag in self.atomic_groups
        }
        elist = []
        if self.subgroup_empties:
            # Remove the specified empty atomic groups
            duds = set()
            for fs, sub in self.subgroup_empties.items():
                try:
                    filtered_atomic_groups.remove(fs)
                except KeyError:
                    duds.add(fs)
                    elist.append(T["FILTER_NOT_ATOM"].format(sub=sub))
            for fs in duds:
                del(self.subgroup_empties[fs])
        # Get the (filtered) atomic groups for the primary groups
        gdict = {}
        for bg in self.primary_groups:
            faglist = []
            for fag in filtered_atomic_groups:
                if bg in fag:
                    faglist.append(fag)
            if faglist:
                gdict[Groupset(faglist)] = Subgroup([bg])
            else:
                elist.append(T["EMPTY_GROUP"].format(g=bg))
        # Add the atomic groups for all possible subgroups, starting
        # with the shortest
        for l in range(2, len(self.divisions)):
            c_set = set()
            for fag in filtered_atomic_groups:
                for c in combinations(fag, l):
                    c_set.add(Subgroup(c))
            for c in c_set:
                faglist = []
                for fag in filtered_atomic_groups:
                    if c < fag:
                        faglist.append(fag)
                if faglist:
                    fs = Groupset(faglist)
                    if fs not in gdict:
                        gdict[fs] = c
        self.filtered_atomic_groups = Groupset(filtered_atomic_groups)
        # Add atomic groups, if they are not already represented by
        # shorter group tags
        for fag in filtered_atomic_groups:
            fs = Groupset([fag])
            if fs not in gdict:
                gdict[fs] = fag
        gdict[self.filtered_atomic_groups] = Subgroup(["*"])
        self.atoms2group = gdict
        # Reverse the mapping to get the group -> atoms mapping
        self.group2atoms = {v: k for k, v in gdict.items()}
        return elist

    def atoms2grouplist(self):
        """Return a mapping {(atom, ... ): (group, ... )} where the keys
        are all possible (sorted) combinations of the minimal subgroups.
        The corresponding value is a minimal list of groups representing
        the key.
        """

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
