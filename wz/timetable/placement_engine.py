"""
timetable/placement_engine.py - last updated 2023-05-29

Manage placement of "activities" within the week, including,
where appropriate, room allocation.

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

ACTIVITIES_ENDING = "_activities.xml"

########################################################################

import sys, os

if __name__ == "__main__":
    # Enable package import if running as module
    this = sys.path[0]
    appdir = os.path.dirname(this)
    sys.path[0] = appdir
    basedir = os.path.dirname(appdir)
    from core.base import start

    # TODO: Temporary redirection to use real data (there isn't any test data yet!)
    start.setup(os.path.join(basedir, 'TESTDATA'))

#from typing import Optional
#from array import array

from core.basic_data import (
    get_days,
    get_periods,
    get_rooms,
    get_classes,
    get_teachers,
    get_subjects,
    timeslot2index,
)
#T = TRANSLATIONS("timetable.placement_engine")

### +++++

### -----

class PlacementEngine:
    def __init__(self, days, periods):
        self.day_list = days
        #print("§days", days)
        self.period_list = periods
        #print("§periods", periods)
        self.week_size = len(days) * len(periods)

    def setup_structures(self,
        classes=None,
        teachers=None,
        subjects=None,
        rooms=None,
    ):
        self.set_classes(classes)
        self.set_teachers(teachers)
        self.set_subjects(subjects)
        self.set_rooms(rooms)

    def week_array(self, n):
        return [0]*(n*self.week_size)
        return array('i', (0,)*(n*self.week_size))

    def set_classes(self, classes):
        """Build structures for handling classes and groups.
        Each atomic group within a class has its own week-array.
        """
# An alternative would be to have bitmaps for the groups within each class
# or even for all atomic groups (the latter would probably require multiple
# storage words). This method can be better for automatic allocation, but
# the blocking activities are not directly available.

        self.group_list = []
        self.group_map = {}
        i = 0
        for k in get_classes():
            try:
                agroups = classes[k]
            except KeyError:
                continue
            except TypeError: ## <classes> not provided (<None>)
                agroups = []
            self.group_map[k] = (kg := {})
            if agroups:
                for ag in agroups:
                    i = len(self.group_list)
                    self.group_list.append((k, ag))
                    kg[ag] = i
                    i += 1
            else:
                # Only whole class, no divisions
                i = len(self.group_list)
                self.group_list.append((k, ''))
                kg[''] = i
                i += 1
        ## Make allocation array
        self.group_week = self.week_array(i)
        
        #print("\n§classes", self.group_list)
        #print("\n§classes map", self.group_map)

    def set_teachers(self, teachers):
        self.teacher_list = []
        self.teacher_map = {}
        i = 0
        for t in get_teachers():
            if teachers and not teachers[t]:
                continue
            self.teacher_list.append(t)
            self.teacher_map[t] = i
            i += 1
        ## Make allocation array
        self.teacher_week = self.week_array(i)

        #print("\n§teachers", self.teacher_list)
        #print("\n§teachers map", self.teacher_map)

    def set_subjects(self, subjects):
        self.subject_list = []
        self.subject_map = {}
        i = 0
        for s in get_subjects().key_list():
            if subjects and not subjects[s]:
                continue
            self.subject_list.append(s)
            self.subject_map[s] = i
            i += 1

        #print("\n§subjects", self.subject_list)
        #print("\n§subjects map", self.subject_map)

    def set_rooms(self, rooms):
        self.room_list = []
        self.room_map = {}
        i = 0
        for r in get_rooms():
            if rooms and not rooms[r]:
                continue
            self.room_list.append(r[0])
            self.room_map[r[0]] = i
            i += 1
        ## Make allocation array
        self.room_week = self.week_array(i)

        #print("\n§rooms", self.room_list)
        #print("\n§rooms map", self.room_map)

#TODO
    def set_activities(self, activities):
        print("TODO: activities")
        # An activitiy has a time – which can be fixed – and a length.
        # It also has 0 or more rooms, which can be selected from
        # a list of possibilities or a "joker" ('+'). A joker room
        # should not be selected automatically – rather flag the
        # activity as having an unresolved room requirement.
        # If a fixed time cannot be allocated because of a clash, this
        # should be reported as an error. To ensure this works correctly,
        # all fixed allocations should be done first.
        # Perhaps an unresolvable room should be reported as an error too.

        ## Time: fixed, allocated, length
        # Rooms are more complicated because of the variable lists.
        # Should I handle that using python lists or devise a low-level
        # approach (linked lists?)?
        # One possibility would be to allocate a bunch of nodes which can be
        # expanded if necessary (that would require copying the existing nodes).
        # Shrinking would not then be trivial, but perhaps not a problem. If
        # I started with a fairly large block (using 32-bit indexes?), I could
        # start testing without expansion code ... I suppose free nodes would
        # need to be linked initially.
        # Linked lists are quite straightforward to implement, especially
        # using indexes to link (all nodes in a single vector), variable length
        # lists could be trickier.
        # Actually array-module arrays can be extended ... I could even do
        # linear lists with special termination.
        
        #self.placements = array('i', (0,)*(n*self.week_size))
        #self.placements = [0]*(n*self.week_size)
        self.activities = []
        for activity in activities:
#TODO--
            print("  --", activity)

            self.activities.append([])

        #return
        #if True:


            lesson_data = activity.lesson_info
            fixed_time = lesson_data.time

#TODO: Keep non-fixed times separate from the database? When would they
# be saved, then?
            if fixed_time:
                d, p = timeslot2index(fixed_time)
                print("   @", d, p)

            else:
                slot_time = lesson_data.placement
                if slot_time:
                    d, p = timeslot2index(slot_time)
                    print("   (@)", d, p)

#TODO: rooms? Shouldn't the rooms per group be available????
# Via the workload entry ... this can, however, be '$', potentially
# leading to multiple rooms.

            groups = activity.group_sets
            roomlists = activity.roomlists
            tids = activity.teacher_set

#            sid = activity.sid


            return


#TODO: tool-tip (or whatever) to show parallel courses?
            t_rooms = lesson_data.rooms
            t_tids = ','.join(sorted(tids)) or '–'
            t_groups, tile_divisions = self.tile_division(klass, groups)
            #t_groups = ','.join(sorted(groups))
            if x:
                t_groups += ",+"
#TODO--
            print("  ...", sid, t_tids, t_groups, t_rooms, tile_divisions)


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":
    from core.db_access import open_database
    open_database()
    pe = PlacementEngine(get_days().key_list(), get_periods().key_list())
    pe.setup_structures()

