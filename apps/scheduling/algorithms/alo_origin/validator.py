"""
Python implementation of ITC-2007 Timetabling Competition validator.
Rewritten from validator.cc to provide same validation logic in Python.

This validator checks both hard constraints (violations) and soft constraints (costs).
Compatible with extended .ctt format that includes room types, equipment, and teacher preferences.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
import sys
from pathlib import Path


@dataclass
class Course:
    """Represents a course with its properties."""
    name: str
    teacher: str
    lectures: int
    min_working_days: int
    students: int
    course_type: str = ""  # Extended: LT or TH
    equipment: List[str] = field(default_factory=list)  # Extended: equipment list


@dataclass
class Room:
    """Represents a room with its properties."""
    name: str
    capacity: int
    room_type: str = ""  # Extended: LT or TH
    equipment: List[str] = field(default_factory=list)  # Extended: equipment list


@dataclass
class Curriculum:
    """Represents a curriculum (a group of courses that cannot overlap)."""
    name: str
    members: List[int] = field(default_factory=list)  # List of course indices


class Faculty:
    """
    Represents the problem instance data.
    Parses .ctt file and builds availability/conflict matrices.
    """
    
    def __init__(self, filename: str):
        self.file_path = filename  # Store filename for later reference
        self.course_vect: List[Course] = []
        self.room_vect: List[Room] = []
        self.curricula_vect: List[Curriculum] = []
        
        self.courses = 0
        self.rooms = 0
        self.days = 0
        self.periods_per_day = 0
        self.periods = 0
        self.curricula = 0
        self.constraints = 0
        self.preferences = 0  # Extended: teacher preferences count
        
        # Cost constants for soft constraints
        self.MIN_WORKING_DAYS_COST = 5
        self.CURRICULUM_COMPACTNESS_COST = 2
        self.ROOM_STABILITY_COST = 1
        
        # 2D matrices: [course][period] -> bool
        self.availability: List[List[bool]] = []
        # 2D matrix: [course1][course2] -> bool (conflict if same teacher or same curriculum)
        self.conflict: List[List[bool]] = []
        
        self._parse_file(filename)
    
    def _parse_file(self, filename: str):
        """Parse the .ctt instance file."""
        with open(filename, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        
        idx = 0
        
        # Parse header
        while idx < len(lines):
            line = lines[idx]
            if line.startswith('Name:'):
                idx += 1
            elif line.startswith('Courses:'):
                self.courses = int(line.split(':')[1].strip())
                idx += 1
            elif line.startswith('Rooms:'):
                self.rooms = int(line.split(':')[1].strip())
                idx += 1
            elif line.startswith('Days:'):
                self.days = int(line.split(':')[1].strip())
                idx += 1
            elif line.startswith('Periods_per_day:'):
                self.periods_per_day = int(line.split(':')[1].strip())
                self.periods = self.days * self.periods_per_day
                idx += 1
            elif line.startswith('Curricula:'):
                self.curricula = int(line.split(':')[1].strip())
                idx += 1
            elif line.startswith('Constraints:'):
                self.constraints = int(line.split(':')[1].strip())
                idx += 1
            elif line.startswith('Preferences:'):
                self.preferences = int(line.split(':')[1].strip())
                idx += 1
            elif line == 'COURSES:':
                idx += 1
                break
            else:
                idx += 1
        
        # Parse COURSES section
        for _ in range(self.courses):
            if idx >= len(lines):
                break
            parts = lines[idx].split(maxsplit=6)  # Split only first 6 spaces, keep equipment as one string
            
            # Format: course_id teacher_id lectures min_wd students [type] [equipment...]
            course = Course(
                name=parts[0],
                teacher=parts[1],
                lectures=int(parts[2]),
                min_working_days=int(parts[3]),
                students=int(parts[4])
            )
            
            # Extended format: course_type and equipment
            if len(parts) >= 6:
                course.course_type = parts[5]
            if len(parts) >= 7:
                # Equipment is everything after position 6, may contain spaces and commas
                equipment_str = parts[6].strip()
                course.equipment = [e.strip() for e in equipment_str.split(',')] if equipment_str else []
            
            self.course_vect.append(course)
            idx += 1
        
        # Skip to ROOMS section
        while idx < len(lines) and lines[idx] != 'ROOMS:':
            idx += 1
        idx += 1
        
        # Parse ROOMS section
        for _ in range(self.rooms):
            if idx >= len(lines):
                break
            parts = lines[idx].split(maxsplit=3)  # Split only first 3 spaces, keep equipment as one string
            
            # Format: room_id capacity [type] [equipment...]
            room = Room(
                name=parts[0],
                capacity=int(parts[1])
            )
            
            # Extended format: room_type and equipment
            if len(parts) >= 3:
                room.room_type = parts[2]
            if len(parts) >= 4:
                # Equipment is everything after position 3, may contain spaces and commas
                equipment_str = parts[3].strip()
                room.equipment = [e.strip() for e in equipment_str.split(',')] if equipment_str else []
            
            self.room_vect.append(room)
            idx += 1
        
        # Skip to CURRICULA section
        while idx < len(lines) and lines[idx] != 'CURRICULA:':
            idx += 1
        idx += 1
        
        # Parse CURRICULA section
        curricula_courses: List[List[int]] = []
        for _ in range(self.curricula):
            if idx >= len(lines):
                break
            parts = lines[idx].split()
            
            # Format: curriculum_id num_members course1 course2 ...
            curriculum = Curriculum(name=parts[0])
            num_members = int(parts[1])
            course_names = parts[2:2+num_members]
            
            course_indices = []
            for course_name in course_names:
                course_idx = self.course_index(course_name)
                if course_idx >= 0:
                    course_indices.append(course_idx)
            
            curriculum.members = course_indices
            curricula_courses.append(course_indices)
            self.curricula_vect.append(curriculum)
            idx += 1
        
        # Initialize availability matrix (all true initially)
        self.availability = [[True] * self.periods for _ in range(self.courses)]
        
        # Initialize conflict matrix (all false initially)
        self.conflict = [[False] * self.courses for _ in range(self.courses)]
        
        # Build curriculum conflicts: courses in same curriculum cannot overlap
        for curriculum_members in curricula_courses:
            for i in range(len(curriculum_members)):
                for j in range(len(curriculum_members)):
                    if i != j:
                        c1 = curriculum_members[i]
                        c2 = curriculum_members[j]
                        self.conflict[c1][c2] = True
                        self.conflict[c2][c1] = True
        
        # Skip to UNAVAILABILITY_CONSTRAINTS section
        while idx < len(lines) and lines[idx] != 'UNAVAILABILITY_CONSTRAINTS:':
            idx += 1
        idx += 1
        
        # Parse UNAVAILABILITY_CONSTRAINTS section
        for _ in range(self.constraints):
            if idx >= len(lines):
                break
            parts = lines[idx].split()
            
            # Format: course_name day period
            course_name = parts[0]
            day_index = int(parts[1])
            period_index = int(parts[2])
            p = day_index * self.periods_per_day + period_index
            c = self.course_index(course_name)
            
            if c >= 0 and 0 <= p < self.periods:
                self.availability[c][p] = False
            
            idx += 1
        
        # Add same-teacher conflicts
        for c1 in range(self.courses - 1):
            for c2 in range(c1 + 1, self.courses):
                if self.course_vect[c1].teacher == self.course_vect[c2].teacher:
                    self.conflict[c1][c2] = True
                    self.conflict[c2][c1] = True
    
    def course_index(self, name: str) -> int:
        """Find course index by name."""
        for i, course in enumerate(self.course_vect):
            if course.name == name:
                return i
        return -1
    
    def curriculum_index(self, name: str) -> int:
        """Find curriculum index by name."""
        for i, curriculum in enumerate(self.curricula_vect):
            if curriculum.name == name:
                return i
        return -1
    
    def room_index(self, name: str) -> int:
        """Find room index by name."""
        for i, room in enumerate(self.room_vect):
            if room.name == name:
                return i
        return -1
    
    def curriculum_member(self, course_idx: int, curriculum_idx: int) -> bool:
        """Check if course is member of curriculum."""
        return course_idx in self.curricula_vect[curriculum_idx].members


class Timetable:
    """
    Represents the solution (timetable assignments).
    Parses .sol file and builds timetable matrix plus redundant data structures.
    """
    
    def __init__(self, faculty: Faculty, filename: str):
        self.faculty = faculty
        
        # 2D matrix: [course][period] -> room (0 means not scheduled, 1-N means room index)
        # NOTE: To match C++ validator, room IDs are 1-based
        self.tt: List[List[int]] = [[0] * faculty.periods for _ in range(faculty.courses)]
        
        # Redundant data structures for fast validation
        # room_lectures[room][period] -> count of lectures in that room at that period
        # Index 0 is unused, rooms are 1-N
        self.room_lectures: List[List[int]] = [[0] * faculty.periods for _ in range(faculty.rooms + 1)]
        
        # curriculum_period_lectures[curriculum][period] -> count of lectures in that curriculum at that period
        self.curriculum_period_lectures: List[List[int]] = [[0] * faculty.periods for _ in range(faculty.curricula)]
        
        # course_daily_lectures[course][day] -> count of lectures on that day
        self.course_daily_lectures: List[List[int]] = [[0] * faculty.days for _ in range(faculty.courses)]
        
        # working_days[course] -> number of days course has lectures
        self.working_days_count: List[int] = [0] * faculty.courses
        
        # used_rooms[course] -> set of rooms used by course
        self.used_rooms: List[Set[int]] = [set() for _ in range(faculty.courses)]
        
        # teacher_preferred_periods[teacher] -> set of (day, period_in_day) tuples
        self.teacher_preferred_periods: Dict[str, Set[tuple]] = {}
        
        self._parse_solution(filename)
        self._parse_preferences()
    
    def _parse_solution(self, filename: str):
        """Parse the .sol solution file."""
        with open(filename, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        
        for line in lines:
            parts = line.split()
            if len(parts) < 4:
                continue
            
            # Format: course_name room_name day period
            course_name = parts[0]
            room_name = parts[1]
            day = int(parts[2])
            period_in_day = int(parts[3])
            
            c = self.faculty.course_index(course_name)
            r = self.faculty.room_index(room_name)
            p = day * self.faculty.periods_per_day + period_in_day
            
            if c < 0:
                print(f"Warning: Unknown course '{course_name}' in solution", file=sys.stderr)
                continue
            if r < 0:
                print(f"Warning: Unknown room '{room_name}' in solution", file=sys.stderr)
                continue
            if p < 0 or p >= self.faculty.periods:
                print(f"Warning: Invalid period (day={day}, period={period_in_day}) in solution", file=sys.stderr)
                continue
            
            # Convert room index from 0-based to 1-based (to match C++ validator)
            room_id = r + 1
            
            # Update timetable matrix
            self.tt[c][p] = room_id
            
            # Update redundant data structures
            self.room_lectures[room_id][p] += 1
            
            # Update curriculum lectures
            for g in range(self.faculty.curricula):
                if self.faculty.curriculum_member(c, g):
                    self.curriculum_period_lectures[g][p] += 1
            
            # Update daily lectures
            self.course_daily_lectures[c][day] += 1
            
            # Update used rooms (using 1-based room_id)
            self.used_rooms[c].add(room_id)
        
        # Calculate working days
        for c in range(self.faculty.courses):
            days_with_lectures = sum(1 for d in range(self.faculty.days) if self.course_daily_lectures[c][d] > 0)
            self.working_days_count[c] = days_with_lectures
    
    def _parse_preferences(self):
        """Parse teacher preferences from extended .ctt format."""
        # Parse PREFERENCES section if it exists in the instance file
        # Format: TEACHER_NAME day period_in_day (1 per line)
        preferences_file = Path(self.faculty.file_path)
        
        if not preferences_file.exists():
            return
        
        with open(preferences_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        
        in_preferences = False
        for line in lines:
            if line == 'PREFERENCES:':
                in_preferences = True
                continue
            if line in ['END.', 'COURSES:', 'ROOMS:', 'CURRICULA:', 'UNAVAILABILITY_CONSTRAINTS:']:
                if in_preferences:
                    break
                in_preferences = False
                continue
            
            if in_preferences:
                parts = line.split()
                if len(parts) >= 3:
                    teacher_name = parts[0]
                    day = int(parts[1])
                    period_in_day = int(parts[2])
                    
                    if teacher_name not in self.teacher_preferred_periods:
                        self.teacher_preferred_periods[teacher_name] = set()
                    
                    self.teacher_preferred_periods[teacher_name].add((day, period_in_day))
    
    def __call__(self, course: int, period: int) -> int:
        """Get room assigned to course at period (0 if not scheduled)."""
        return self.tt[course][period]
    
    def room_lectures_at(self, room: int, period: int) -> int:
        """Get number of lectures in room at period."""
        return self.room_lectures[room][period]
    
    def curriculum_period_lectures_at(self, curriculum: int, period: int) -> int:
        """Get number of curriculum lectures at period."""
        return self.curriculum_period_lectures[curriculum][period]
    
    def working_days(self, course: int) -> int:
        """Get number of working days for course."""
        return self.working_days_count[course]
    
    def used_rooms_no(self, course: int) -> int:
        """Get number of different rooms used by course."""
        return len(self.used_rooms[course])


class Validator:
    """
    Validates a timetable solution and calculates costs.
    Checks hard constraints (violations) and soft constraints (costs).
    """
    
    def __init__(self, instance_file: str, solution_file: str):
        self.faculty = Faculty(instance_file)
        self.timetable = Timetable(self.faculty, solution_file)
    
    # ========== COST CALCULATION METHODS ==========
    
    def costs_on_lectures(self) -> int:
        """
        Check H1: All lectures must be scheduled.
        Returns: count of missing or extra lectures (violations)
        """
        cost = 0
        for c in range(self.faculty.courses):
            scheduled_lectures = sum(1 for p in range(self.faculty.periods) if self.timetable(c, p) != 0)
            required_lectures = self.faculty.course_vect[c].lectures
            
            if scheduled_lectures < required_lectures:
                cost += required_lectures - scheduled_lectures
            elif scheduled_lectures > required_lectures:
                cost += scheduled_lectures - required_lectures
        
        return cost
    
    def costs_on_conflicts(self) -> int:
        """
        Check H2: Conflicting courses cannot be scheduled in same period.
        Conflicts: same teacher OR same curriculum
        Returns: count of conflict violations
        """
        cost = 0
        for c1 in range(self.faculty.courses - 1):
            for c2 in range(c1 + 1, self.faculty.courses):
                if self.faculty.conflict[c1][c2]:
                    for p in range(self.faculty.periods):
                        if self.timetable(c1, p) != 0 and self.timetable(c2, p) != 0:
                            cost += 1
        return cost
    
    def costs_on_availability(self) -> int:
        """
        Check H3: Courses cannot be scheduled in unavailable periods.
        Returns: count of availability violations
        """
        cost = 0
        for c in range(self.faculty.courses):
            for p in range(self.faculty.periods):
                if self.timetable(c, p) != 0 and not self.faculty.availability[c][p]:
                    cost += 1
        return cost
    
    def costs_on_room_occupation(self) -> int:
        """
        Check H4: Room can host at most one lecture per period.
        Returns: count of room double-booking violations
        """
        cost = 0
        for p in range(self.faculty.periods):
            for r in range(1, self.faculty.rooms + 1):
                lectures_in_room = self.timetable.room_lectures_at(r, p)
                if lectures_in_room > 1:
                    cost += lectures_in_room - 1
        return cost
    
    def costs_on_room_type(self) -> int:
        """
        Check HC-05/HC-06: Room type must match course type (Extended constraint).
        - LT courses require LT rooms
        - TH courses require TH rooms
        Returns: count of room type mismatches
        """
        cost = 0
        for c in range(self.faculty.courses):
            course = self.faculty.course_vect[c]
            course_type = course.course_type
            
            # Skip if no type specified
            if not course_type:
                continue
            
            for p in range(self.faculty.periods):
                room_id = self.timetable(c, p)
                if room_id != 0:
                    # Convert 1-based room_id to 0-based index
                    r = room_id - 1
                    room = self.faculty.room_vect[r]
                    room_type = room.room_type
                    
                    # Check type mismatch
                    if room_type and course_type != room_type:
                        cost += 1
        
        return cost
    
    def costs_on_equipment(self) -> int:
        """
        Check HC-04: Room must have required equipment (Extended constraint).
        - Course equipment requirements must be subset of room equipment
        Returns: count of equipment requirement violations
        """
        cost = 0
        for c in range(self.faculty.courses):
            course = self.faculty.course_vect[c]
            required_equipment = set(course.equipment)
            
            # Skip if no equipment required
            if not required_equipment:
                continue
            
            for p in range(self.faculty.periods):
                room_id = self.timetable(c, p)
                if room_id != 0:
                    # Convert 1-based room_id to 0-based index
                    r = room_id - 1
                    room = self.faculty.room_vect[r]
                    available_equipment = set(room.equipment)
                    
                    # Check if all required equipment is available
                    missing_equipment = required_equipment - available_equipment
                    if missing_equipment:
                        cost += 1  # Count as 1 violation per lecture
        
        return cost
    
    def costs_on_room_capacity(self) -> int:
        """
        Check S1: Room capacity should be sufficient for course students.
        Soft constraint: cost = sum of (students - capacity) for violations
        Returns: total capacity shortage
        """
        cost = 0
        for c in range(self.faculty.courses):
            for p in range(self.faculty.periods):
                room_id = self.timetable(c, p)
                if room_id != 0:
                    # Convert 1-based room_id to 0-based index
                    r = room_id - 1
                    room_capacity = self.faculty.room_vect[r].capacity
                    course_students = self.faculty.course_vect[c].students
                    if room_capacity < course_students:
                        cost += course_students - room_capacity
        return cost
    
    def costs_on_min_working_days(self) -> int:
        """
        Check S2: Course lectures should be spread over minimum working days.
        Soft constraint: cost = count of violations (not weighted yet)
        Returns: count of min_working_days violations
        """
        cost = 0
        for c in range(self.faculty.courses):
            working_days = self.timetable.working_days(c)
            min_days = self.faculty.course_vect[c].min_working_days
            if working_days < min_days:
                cost += min_days - working_days
        return cost
    
    def costs_on_curriculum_compactness(self) -> int:
        """
        Check S3: Curriculum lectures should be adjacent (no isolated lectures).
        An isolated lecture is one with no adjacent lectures in same curriculum on same day.
        Soft constraint: cost = count of isolated lectures (not weighted yet)
        Returns: count of isolated curriculum lectures
        """
        cost = 0
        ppd = self.faculty.periods_per_day
        
        for g in range(self.faculty.curricula):
            for p in range(self.faculty.periods):
                if self.timetable.curriculum_period_lectures_at(g, p) > 0:
                    isolated = False
                    
                    # First period of day
                    if p % ppd == 0:
                        if self.timetable.curriculum_period_lectures_at(g, p + 1) == 0:
                            isolated = True
                    # Last period of day
                    elif p % ppd == ppd - 1:
                        if self.timetable.curriculum_period_lectures_at(g, p - 1) == 0:
                            isolated = True
                    # Middle period of day
                    else:
                        if (self.timetable.curriculum_period_lectures_at(g, p - 1) == 0 and
                            self.timetable.curriculum_period_lectures_at(g, p + 1) == 0):
                            isolated = True
                    
                    if isolated:
                        cost += self.timetable.curriculum_period_lectures_at(g, p)
        
        return cost
    
    def costs_on_room_stability(self) -> int:
        """
        Check S4: Course lectures should use as few different rooms as possible.
        Soft constraint: cost = count of violations (not weighted yet)
        Returns: sum of (used_rooms - 1) for all courses
        """
        cost = 0
        for c in range(self.faculty.courses):
            used_rooms = self.timetable.used_rooms_no(c)
            if used_rooms > 1:
                cost += used_rooms - 1
        return cost
    
    def costs_on_lecture_consecutiveness(self) -> int:
        """
        Check S5: Lecture Consecutiveness.
        Soft constraint: prefer consecutive lectures (2 slots together).
        Based on Vietnamese high school timetabling rules:
        - 2 lectures/week: must be 1 consecutive pair (2 slots together)
        - 3 lectures/week: must be 1 consecutive pair + 1 isolated, on different days
        - 4 lectures/week: must be 2 consecutive pairs, on different days
        - >=5 lectures/week: must have multiple pairs spread over many days
        
        Returns: total penalty cost for lecture consecutiveness violations
        """
        total_cost = 0
        ppd = self.faculty.periods_per_day
        
        for c in range(self.faculty.courses):
            # Collect all periods where this course is scheduled
            periods = [p for p in range(self.faculty.periods) if self.timetable(c, p) != 0]
            num_lectures = len(periods)
            
            if num_lectures <= 1:
                continue  # No penalty for 0 or 1 lecture
            
            # Group lectures by day
            lectures_by_day: Dict[int, List[int]] = {}
            for period in periods:
                day = period // ppd
                slot_in_day = period % ppd
                if day not in lectures_by_day:
                    lectures_by_day[day] = []
                lectures_by_day[day].append(slot_in_day)
            
            # Sort slots within each day
            for day in lectures_by_day:
                lectures_by_day[day].sort()
            
            # Find consecutive pairs (2 slots with difference of 1)
            pairs_by_day: Dict[int, List[tuple]] = {}
            for day, slots in lectures_by_day.items():
                pairs = []
                i = 0
                while i < len(slots) - 1:
                    if slots[i + 1] - slots[i] == 1:  # Consecutive
                        pairs.append((slots[i], slots[i + 1]))
                        i += 2  # Skip both slots in the pair
                    else:
                        i += 1
                pairs_by_day[day] = pairs
            
            total_pairs = sum(len(pairs) for pairs in pairs_by_day.values())
            days_with_pairs = [day for day, pairs in pairs_by_day.items() if len(pairs) > 0]
            num_days = len(lectures_by_day)
            
            penalty = 0
            
            # === RULE: All lectures on same day = VERY BAD ===
            if num_days == 1 and num_lectures >= 3:
                penalty += 30  # Severe penalty for overloading single day
            
            # === CASE 1: 2 LECTURES ===
            if num_lectures == 2:
                if total_pairs != 1:
                    penalty += 5  # Should be consecutive
            
            # === CASE 2: 3 LECTURES ===
            elif num_lectures == 3:
                if total_pairs == 0:
                    penalty += 8  # No pairs at all (all isolated)
                elif total_pairs == 1 and num_days == 1:
                    penalty += 20  # 1 pair but all on same day
            
            # === CASE 3: 4 LECTURES ===
            elif num_lectures == 4:
                if total_pairs < 2:
                    penalty += (2 - total_pairs) * 8  # Should have 2 pairs
                elif total_pairs == 2 and len(days_with_pairs) == 1:
                    penalty += 15  # 2 pairs but on same day
            
            # === CASE 4: >= 5 LECTURES ===
            elif num_lectures >= 5:
                if total_pairs < 2:
                    penalty += (2 - total_pairs) * 6  # Should have at least 2 pairs
                if len(days_with_pairs) < 2:
                    penalty += 8  # Pairs should be on different days
            
            total_cost += penalty
        
        return total_cost
    
    def costs_on_teacher_preferences(self) -> int:
        """
        Check S8: Teacher Preferences (NEW).
        Soft constraint: prefer assigning lectures to teacher's preferred periods.
        Penalty: +1 for each lecture assigned outside teacher's preferred times.
        Returns: count of lectures assigned outside preferred periods
        """
        cost = 0
        
        for c in range(self.faculty.courses):
            course = self.faculty.course_vect[c]
            teacher_name = course.teacher
            
            # Get teacher's preferred periods if available
            preferred_periods = self.timetable.teacher_preferred_periods.get(teacher_name, set())
            
            # If no preferences are defined for this teacher, no penalty
            if not preferred_periods:
                continue
            
            ppd = self.faculty.periods_per_day
            
            # Check each lecture of this course
            for p in range(self.faculty.periods):
                if self.timetable(c, p) != 0:  # Lecture is scheduled at period p
                    day = p // ppd
                    slot_in_day = p % ppd
                    
                    # Check if this (day, slot_in_day) is in teacher's preferred periods
                    if (day, slot_in_day) not in preferred_periods:
                        cost += 1  # Penalty: 1 point per non-preferred lecture
        
        return cost
    
    def costs_on_teacher_lecture_consolidation(self) -> int:
        """
        Check S6: Teacher Lecture Consolidation (NEW).
        Soft constraint: prefer teachers teaching consecutive lectures in same room.
        Penalty: +1 for each transition where teacher changes room between consecutive lectures.
        
        Logic:
        - Group all lectures by teacher
        - For each teacher, sort lectures by (day, period)
        - For consecutive lectures on same day:
          - If different rooms AND same course type: +1 penalty
          - If different course types (LT↔TH): no penalty (must change room)
          - If not consecutive periods (gap): no penalty (different time slots)
        
        Returns: count of room changes between consecutive teacher lectures of SAME type
        """
        cost = 0
        ppd = self.faculty.periods_per_day
        
        # Group lectures by teacher
        teacher_lectures: Dict[str, List[tuple]] = {}
        
        for c in range(self.faculty.courses):
            course = self.faculty.course_vect[c]
            teacher_name = course.teacher
            
            if teacher_name not in teacher_lectures:
                teacher_lectures[teacher_name] = []
            
            for p in range(self.faculty.periods):
                room_id = self.timetable(c, p)
                if room_id != 0:
                    day = p // ppd
                    period_in_day = p % ppd
                    teacher_lectures[teacher_name].append((day, period_in_day, p, room_id, c))
        
        # Check consolidation for each teacher
        for teacher_name, lectures in teacher_lectures.items():
            if len(lectures) <= 1:
                continue
            
            # Sort by day, then period
            lectures.sort(key=lambda x: (x[0], x[1]))
            
            # Check consecutive lectures
            for i in range(len(lectures) - 1):
                day1, period1, p1, room1, course1 = lectures[i]
                day2, period2, p2, room2, course2 = lectures[i + 1]
                
                # Only check if on same day and consecutive periods
                if day1 == day2 and period2 == period1 + 1:
                    # Consecutive lectures on same day
                    if room1 != room2:
                        # ✅ FIX: Only penalize if SAME course type
                        course1_type = self.faculty.course_vect[course1].course_type
                        course2_type = self.faculty.course_vect[course2].course_type
                        
                        # Only count as violation if same type (should use same room)
                        if course1_type and course2_type and course1_type == course2_type:
                            cost += 1  # Penalty: teacher changes room unnecessarily
        
        return cost
    
    def costs_on_teacher_working_days(self) -> int:
        """
        Check S7: Teacher Working Days Minimization (NEW).
        Soft constraint: minimize number of days teachers come to school.
        Penalty: +1 for each day exceeding theoretical minimum.
        
        Logic:
        - For each teacher, calculate:
          - total_lectures = sum of all lectures
          - actual_days = number of distinct days teacher has lectures
          - min_days_theoretical = ⌈total_lectures / periods_per_day⌉
          - penalty = max(0, actual_days - min_days_theoretical)
        
        Returns: total penalty across all teachers
        """
        cost = 0
        ppd = self.faculty.periods_per_day
        
        # Group lectures by teacher
        teacher_lectures: Dict[str, set] = {}
        
        for c in range(self.faculty.courses):
            course = self.faculty.course_vect[c]
            teacher_name = course.teacher
            
            if teacher_name not in teacher_lectures:
                teacher_lectures[teacher_name] = set()
            
            for p in range(self.faculty.periods):
                room_id = self.timetable(c, p)
                if room_id != 0:
                    day = p // ppd
                    teacher_lectures[teacher_name].add(day)
        
        # Calculate penalty for each teacher
        for teacher_name, days_set in teacher_lectures.items():
            # Count total lectures for this teacher
            total_lectures = 0
            for c in range(self.faculty.courses):
                if self.faculty.course_vect[c].teacher == teacher_name:
                    for p in range(self.faculty.periods):
                        if self.timetable(c, p) != 0:
                            total_lectures += 1
            
            actual_days = len(days_set)
            min_days_theoretical = (total_lectures + ppd - 1) // ppd  # Ceiling division
            penalty = max(0, actual_days - min_days_theoretical)
            cost += penalty
        
        return cost
    
    # ========== TOTAL COST CALCULATION ==========
    
    def total_violations(self) -> int:
        """Get total hard constraint violations."""
        return (self.costs_on_lectures() + 
                self.costs_on_conflicts() + 
                self.costs_on_availability() + 
                self.costs_on_room_occupation() +
                self.costs_on_room_type() +          # HC-05/HC-06 (Extended)
                self.costs_on_equipment())           # HC-04 (Extended)
    
    def total_cost(self) -> int:
        """Get total weighted cost (hard violations + soft costs)."""
        return (self.costs_on_room_capacity() + 
                self.costs_on_min_working_days() * self.faculty.MIN_WORKING_DAYS_COST +
                self.costs_on_curriculum_compactness() * self.faculty.CURRICULUM_COMPACTNESS_COST +
                self.costs_on_room_stability() * self.faculty.ROOM_STABILITY_COST +
                self.costs_on_lecture_consecutiveness() +
                self.costs_on_teacher_lecture_consolidation() +  # S6 (Extended)
                self.costs_on_teacher_working_days() +           # S7 (Extended)
                self.costs_on_teacher_preferences())             # S8 (Extended)
    
    # ========== PRINT METHODS ==========
    
    def print_total_cost(self):
        """Print summary of violations and total cost."""
        violations = self.total_violations()
        
        if violations > 0:
            print(f"Violations = {violations}, ", end="")
        print(f"Total Cost = {self.total_cost()}")
    
    def print_costs(self):
        """Print all constraint costs."""
        print(f"Violations of Lectures (hard) : {self.costs_on_lectures()}")
        print(f"Violations of Conflicts (hard) : {self.costs_on_conflicts()}")
        print(f"Violations of Availability (hard) : {self.costs_on_availability()}")
        print(f"Violations of RoomOccupation (hard) : {self.costs_on_room_occupation()}")
        print(f"Violations of RoomType (hard - extended) : {self.costs_on_room_type()}")
        print(f"Violations of Equipment (hard - extended) : {self.costs_on_equipment()}")
        print(f"Cost of RoomCapacity (soft) : {self.costs_on_room_capacity()}")
        print(f"Cost of MinWorkingDays (soft) : {self.costs_on_min_working_days() * self.faculty.MIN_WORKING_DAYS_COST}")
        print(f"Cost of CurriculumCompactness (soft) : {self.costs_on_curriculum_compactness() * self.faculty.CURRICULUM_COMPACTNESS_COST}")
        print(f"Cost of RoomStability (soft) : {self.costs_on_room_stability() * self.faculty.ROOM_STABILITY_COST}")
        print(f"Cost of LectureConsecutiveness (soft) : {self.costs_on_lecture_consecutiveness()}")
        print(f"Cost of TeacherLectureConsolidation (soft - extended) : {self.costs_on_teacher_lecture_consolidation()}")
        print(f"Cost of TeacherWorkingDays (soft - extended) : {self.costs_on_teacher_working_days()}")
        print(f"Cost of TeacherPreferences (soft - extended) : {self.costs_on_teacher_preferences()}")
    
    # ========== VIOLATION DETAIL METHODS ==========
    
    def print_violations(self):
        """Print all violations with details."""
        self.print_violations_on_lectures()
        self.print_violations_on_conflicts()
        self.print_violations_on_availability()
        self.print_violations_on_room_occupation()
        self.print_violations_on_room_type()
        self.print_violations_on_equipment()
        self.print_violations_on_room_capacity()
        self.print_violations_on_min_working_days()
        self.print_violations_on_curriculum_compactness()
        self.print_violations_on_room_stability()
        self.print_violations_on_lecture_consecutiveness()
        self.print_violations_on_teacher_lecture_consolidation()
        self.print_violations_on_teacher_working_days()
        self.print_violations_on_teacher_preferences()
    
    def print_violations_on_lectures(self):
        """Print detailed lecture count violations."""
        for c in range(self.faculty.courses):
            scheduled_lectures = sum(1 for p in range(self.faculty.periods) if self.timetable(c, p) != 0)
            required_lectures = self.faculty.course_vect[c].lectures
            
            if scheduled_lectures < required_lectures:
                print(f"[H] Too few lectures for course {self.faculty.course_vect[c].name}")
            elif scheduled_lectures > required_lectures:
                print(f"[H] Too many lectures for course {self.faculty.course_vect[c].name}")
    
    def print_violations_on_conflicts(self):
        """Print detailed conflict violations."""
        for c1 in range(self.faculty.courses - 1):
            for c2 in range(c1 + 1, self.faculty.courses):
                if self.faculty.conflict[c1][c2]:
                    for p in range(self.faculty.periods):
                        if self.timetable(c1, p) != 0 and self.timetable(c2, p) != 0:
                            day = p // self.faculty.periods_per_day
                            timeslot = p % self.faculty.periods_per_day
                            print(f"[H] Courses {self.faculty.course_vect[c1].name} and {self.faculty.course_vect[c2].name} "
                                  f"have both a lecture at period {p} (day {day}, timeslot {timeslot})")
    
    def print_violations_on_availability(self):
        """Print detailed availability violations."""
        for c in range(self.faculty.courses):
            for p in range(self.faculty.periods):
                if self.timetable(c, p) != 0 and not self.faculty.availability[c][p]:
                    day = p // self.faculty.periods_per_day
                    timeslot = p % self.faculty.periods_per_day
                    print(f"[H] Course {self.faculty.course_vect[c].name} has a lecture at unavailable period "
                          f"{p} (day {day}, timeslot {timeslot})")
    
    def print_violations_on_room_occupation(self):
        """Print detailed room occupation violations."""
        for p in range(self.faculty.periods):
            for r in range(1, self.faculty.rooms + 1):
                lectures = self.timetable.room_lectures_at(r, p)
                if lectures > 1:
                    day = p // self.faculty.periods_per_day
                    timeslot = p % self.faculty.periods_per_day
                    print(f"[H] {lectures} lectures in room {self.faculty.room_vect[r - 1].name} "
                          f"the period {p} (day {day}, timeslot {timeslot})", end="")
                    if lectures > 2:
                        print(f" [{lectures - 1} violations]", end="")
                    print()
    
    def print_violations_on_room_type(self):
        """Print detailed room type violations."""
        for c in range(self.faculty.courses):
            course = self.faculty.course_vect[c]
            course_type = course.course_type
            
            if not course_type:
                continue
            
            for p in range(self.faculty.periods):
                room_id = self.timetable(c, p)
                if room_id != 0:
                    r = room_id - 1
                    room = self.faculty.room_vect[r]
                    room_type = room.room_type
                    
                    if room_type and course_type != room_type:
                        day = p // self.faculty.periods_per_day
                        timeslot = p % self.faculty.periods_per_day
                        print(f"[H] Room type mismatch: Course {course.name} (type={course_type}) "
                              f"assigned to room {room.name} (type={room_type}) "
                              f"at period {p} (day {day}, timeslot {timeslot})")
    
    def print_violations_on_equipment(self):
        """Print detailed equipment violations."""
        for c in range(self.faculty.courses):
            course = self.faculty.course_vect[c]
            required_equipment = set(course.equipment)
            
            if not required_equipment:
                continue
            
            for p in range(self.faculty.periods):
                room_id = self.timetable(c, p)
                if room_id != 0:
                    r = room_id - 1
                    room = self.faculty.room_vect[r]
                    available_equipment = set(room.equipment)
                    
                    missing_equipment = required_equipment - available_equipment
                    if missing_equipment:
                        day = p // self.faculty.periods_per_day
                        timeslot = p % self.faculty.periods_per_day
                        missing_str = ", ".join(sorted(missing_equipment))
                        print(f"[H] Equipment missing: Course {course.name} requires [{', '.join(sorted(required_equipment))}] "
                              f"but room {room.name} only has [{', '.join(sorted(available_equipment)) if available_equipment else 'none'}]. "
                              f"Missing: [{missing_str}] at period {p} (day {day}, timeslot {timeslot})")
    
    def print_violations_on_room_capacity(self):
        """Print detailed room capacity violations."""
        for c in range(self.faculty.courses):
            for p in range(self.faculty.periods):
                room_id = self.timetable(c, p)
                if room_id != 0:
                    # Convert 1-based room_id to 0-based index
                    r = room_id - 1
                    room_capacity = self.faculty.room_vect[r].capacity
                    course_students = self.faculty.course_vect[c].students
                    if room_capacity < course_students:
                        shortage = course_students - room_capacity
                        day = p // self.faculty.periods_per_day
                        timeslot = p % self.faculty.periods_per_day
                        print(f"[S({shortage})] Room {self.faculty.room_vect[r].name} too small for course "
                              f"{self.faculty.course_vect[c].name} the period {p} (day {day}, timeslot {timeslot})")
    
    def print_violations_on_min_working_days(self):
        """Print detailed min working days violations."""
        for c in range(self.faculty.courses):
            working_days = self.timetable.working_days(c)
            min_days = self.faculty.course_vect[c].min_working_days
            if working_days < min_days:
                print(f"[S({self.faculty.MIN_WORKING_DAYS_COST})] The course {self.faculty.course_vect[c].name} "
                      f"has only {working_days} days of lecture")
    
    def print_violations_on_curriculum_compactness(self):
        """Print detailed curriculum compactness violations."""
        ppd = self.faculty.periods_per_day
        
        for g in range(self.faculty.curricula):
            for p in range(self.faculty.periods):
                if self.timetable.curriculum_period_lectures_at(g, p) > 0:
                    isolated = False
                    
                    # First period of day
                    if p % ppd == 0:
                        if self.timetable.curriculum_period_lectures_at(g, p + 1) == 0:
                            isolated = True
                    # Last period of day
                    elif p % ppd == ppd - 1:
                        if self.timetable.curriculum_period_lectures_at(g, p - 1) == 0:
                            isolated = True
                    # Middle period of day
                    else:
                        if (self.timetable.curriculum_period_lectures_at(g, p - 1) == 0 and
                            self.timetable.curriculum_period_lectures_at(g, p + 1) == 0):
                            isolated = True
                    
                    if isolated:
                        day = p // self.faculty.periods_per_day
                        timeslot = p % self.faculty.periods_per_day
                        print(f"[S({self.faculty.CURRICULUM_COMPACTNESS_COST})] Curriculum {self.faculty.curricula_vect[g].name} "
                              f"has an isolated lecture at period {p} (day {day}, timeslot {timeslot})")
    
    def print_violations_on_room_stability(self):
        """Print detailed room stability violations."""
        for c in range(self.faculty.courses):
            used_rooms = self.timetable.used_rooms_no(c)
            if used_rooms > 1:
                cost = (used_rooms - 1) * self.faculty.ROOM_STABILITY_COST
                print(f"[S({cost})] Course {self.faculty.course_vect[c].name} uses {used_rooms} different rooms")
    
    def print_violations_on_lecture_consecutiveness(self):
        """Print detailed lecture consecutiveness violations."""
        ppd = self.faculty.periods_per_day
        
        for c in range(self.faculty.courses):
            # Collect all periods where this course is scheduled
            periods = [p for p in range(self.faculty.periods) if self.timetable(c, p) != 0]
            num_lectures = len(periods)
            
            if num_lectures <= 1:
                continue
            
            # Group lectures by day
            lectures_by_day: Dict[int, List[int]] = {}
            for period in periods:
                day = period // ppd
                slot_in_day = period % ppd
                if day not in lectures_by_day:
                    lectures_by_day[day] = []
                lectures_by_day[day].append(slot_in_day)
            
            # Sort slots within each day
            for day in lectures_by_day:
                lectures_by_day[day].sort()
            
            # Find consecutive pairs
            pairs_by_day: Dict[int, List[tuple]] = {}
            for day, slots in lectures_by_day.items():
                pairs = []
                i = 0
                while i < len(slots) - 1:
                    if slots[i + 1] - slots[i] == 1:
                        pairs.append((slots[i], slots[i + 1]))
                        i += 2
                    else:
                        i += 1
                pairs_by_day[day] = pairs
            
            total_pairs = sum(len(pairs) for pairs in pairs_by_day.values())
            num_days = len(lectures_by_day)
            
            # Print violations
            has_violation = False
            if num_days == 1 and num_lectures >= 3:
                print(f"[S(30)] Course {self.faculty.course_vect[c].name} has all {num_lectures} lectures on same day")
                has_violation = True
            
            if num_lectures == 2 and total_pairs == 0:
                print(f"[S(5)] Course {self.faculty.course_vect[c].name} has 2 lectures but not consecutive")
                has_violation = True
            
            if num_lectures == 3 and total_pairs == 0:
                print(f"[S(8)] Course {self.faculty.course_vect[c].name} has 3 lectures with no consecutive pairs")
                has_violation = True
            
            if num_lectures == 3 and total_pairs == 1 and num_days == 1:
                print(f"[S(20)] Course {self.faculty.course_vect[c].name} has 1 pair but all on same day")
                has_violation = True
            
            if num_lectures == 4 and total_pairs < 2:
                print(f"[S({(2-total_pairs)*8})] Course {self.faculty.course_vect[c].name} has {total_pairs} pairs (need 2)")
                has_violation = True
            
            if num_lectures == 4 and total_pairs == 2 and len([d for d in pairs_by_day if pairs_by_day[d]]) == 1:
                print(f"[S(15)] Course {self.faculty.course_vect[c].name} has 2 pairs but on same day")
                has_violation = True
    
    def print_violations_on_teacher_preferences(self):
        """Print detailed teacher preferences violations."""
        ppd = self.faculty.periods_per_day
        
        for c in range(self.faculty.courses):
            course = self.faculty.course_vect[c]
            teacher_name = course.teacher
            
            # Get teacher's preferred periods if available
            preferred_periods = self.timetable.teacher_preferred_periods.get(teacher_name, set())
            
            if not preferred_periods:
                continue
            
            violations = []
            for p in range(self.faculty.periods):
                if self.timetable(c, p) != 0:
                    day = p // ppd
                    slot_in_day = p % ppd
                    
                    if (day, slot_in_day) not in preferred_periods:
                        day_name = f"Day{day}"
                        slot_name = f"Slot{slot_in_day}"
                        violations.append((p, day_name, slot_name))
            
            for p, day_name, slot_name in violations:
                print(f"[S(1)] Course {course.name} (Teacher: {teacher_name}) has lecture at non-preferred period "
                      f"{p} ({day_name}, {slot_name})")
    
    def print_violations_on_teacher_lecture_consolidation(self):
        """Print detailed teacher lecture consolidation violations."""
        ppd = self.faculty.periods_per_day
        
        # Group lectures by teacher
        teacher_lectures: Dict[str, List[tuple]] = {}
        
        for c in range(self.faculty.courses):
            course = self.faculty.course_vect[c]
            teacher_name = course.teacher
            
            if teacher_name not in teacher_lectures:
                teacher_lectures[teacher_name] = []
            
            for p in range(self.faculty.periods):
                room_id = self.timetable(c, p)
                if room_id != 0:
                    day = p // ppd
                    period_in_day = p % ppd
                    teacher_lectures[teacher_name].append((day, period_in_day, p, room_id, c))
        
        # Check consolidation for each teacher
        for teacher_name, lectures in teacher_lectures.items():
            if len(lectures) <= 1:
                continue
            
            # Sort by day, then period
            lectures.sort(key=lambda x: (x[0], x[1]))
            
            # Check consecutive lectures
            for i in range(len(lectures) - 1):
                day1, period1, p1, room1, course1 = lectures[i]
                day2, period2, p2, room2, course2 = lectures[i + 1]
                
                # Only check if on same day and consecutive periods
                if day1 == day2 and period2 == period1 + 1:
                    # Consecutive lectures on same day
                    if room1 != room2:
                        # ✅ FIX: Only print if SAME course type
                        course1_type = self.faculty.course_vect[course1].course_type
                        course2_type = self.faculty.course_vect[course2].course_type
                        
                        # Only count as violation if same type
                        if course1_type and course2_type and course1_type == course2_type:
                            course1_name = self.faculty.course_vect[course1].name
                            course2_name = self.faculty.course_vect[course2].name
                            room1_name = self.faculty.room_vect[room1 - 1].name
                            room2_name = self.faculty.room_vect[room2 - 1].name
                            print(f"[S(1)] Teacher {teacher_name} changes room between consecutive lectures of SAME type ({course1_type}): "
                                  f"Day {day1}, Period {period1} ({course1_name} in {room1_name}) -> "
                                  f"Period {period2} ({course2_name} in {room2_name})")
    
    def print_violations_on_teacher_working_days(self):
        """Print detailed teacher working days violations."""
        ppd = self.faculty.periods_per_day
        
        # Group lectures by teacher
        teacher_lectures: Dict[str, set] = {}
        
        for c in range(self.faculty.courses):
            course = self.faculty.course_vect[c]
            teacher_name = course.teacher
            
            if teacher_name not in teacher_lectures:
                teacher_lectures[teacher_name] = set()
            
            for p in range(self.faculty.periods):
                room_id = self.timetable(c, p)
                if room_id != 0:
                    day = p // ppd
                    teacher_lectures[teacher_name].add(day)
        
        # Print violations for each teacher
        for teacher_name, days_set in teacher_lectures.items():
            # Count total lectures for this teacher
            total_lectures = 0
            for c in range(self.faculty.courses):
                if self.faculty.course_vect[c].teacher == teacher_name:
                    for p in range(self.faculty.periods):
                        if self.timetable(c, p) != 0:
                            total_lectures += 1
            
            actual_days = len(days_set)
            min_days_theoretical = (total_lectures + ppd - 1) // ppd  # Ceiling division
            penalty = max(0, actual_days - min_days_theoretical)
            
            if penalty > 0:
                print(f"[S(1)] Teacher {teacher_name}: {actual_days} working days (min: {min_days_theoretical} days) "
                      f"-> penalty +{penalty} (total lectures: {total_lectures})")


def main():
    """Main entry point - mimics C++ validator command line interface."""
    if len(sys.argv) != 3:
        print("Usage: python validator.py <instance_file.ctt> <solution_file.sol>")
        sys.exit(1)
    
    instance_file = sys.argv[1]
    solution_file = sys.argv[2]
    
    try:
        validator = Validator(instance_file, solution_file)
        
        print("=" * 70)
        print("VIOLATIONS:")
        print("=" * 70)
        validator.print_violations()
        
        print("\n" + "=" * 70)
        print("COSTS:")
        print("=" * 70)
        validator.print_costs()
        
        print("\n" + "=" * 70)
        print("SUMMARY:")
        print("=" * 70)
        validator.print_total_cost()
        
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
