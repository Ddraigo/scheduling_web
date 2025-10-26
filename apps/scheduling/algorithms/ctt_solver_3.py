"""
Inspired by Tomas Muller's ITC-2007 hybrid constraint-based + local search approach; ITC-2007 Track 3 (CB-CTT) specification.
References:
- Muller, T. (2009). ITC-2007 solver description (unitime.org).
- ITC-2007 Track 3 Curriculum-Based Course Timetabling specification (unitime.org).
- Schaerf, A. (1999). A survey of automated timetabling. Artificial Intelligence Review.

>>> inst = parse_instance(None)
>>> inst.days, inst.periods_per_day, len(inst.courses)
(2, 3, 2)
>>> rng = random.Random(1)
>>> start = time.time()
>>> state = build_initial_solution(inst, rng, "greedy-cprop", start, 3.0)
>>> state.check_hard_constraints()
True
>>> from pathlib import Path
>>> tmp = Path("_ctt_solver_doctest.sol")
>>> write_solution(inst, state.clone_assignments(), tmp)
>>> tmp.read_text().strip().splitlines()[0].count(" ")
3
>>> tmp.unlink()
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import sys
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

STRICT_SAMPLE_INSTANCE = """Name: Tiny
Courses: 2
Rooms: 2
Days: 2
Periods_per_day: 3
Curricula: 1
Constraints: 1

COURSES:
C1 T1 2 2 10
C2 T2 1 1 5

ROOMS:
R1 15
R2 8

CURRICULA:
CUR1 2 C1 C2

UNAVAILABILITY_CONSTRAINTS:
C1 0 0

END.
"""


@dataclass(frozen=True)
class Room:
    """Teaching room descriptor."""

    id: str
    capacity: int
    index: int


@dataclass(frozen=True)
class Course:
    """Curriculum-based course descriptor."""

    id: str
    teacher: str
    lectures: int
    min_working_days: int
    students: int
    index: int
    teacher_index: int


@dataclass(frozen=True)
class Curriculum:
    """Curriculum grouping courses that must not clash."""

    name: str
    courses: List[int]
    index: int


@dataclass(frozen=True)
class Lecture:
    """Single lecture occurrence for a course."""

    id: int
    course: int
    index: int


@dataclass
class CBCTTInstance:
    """Immutable instance data for CB-CTT."""

    name: str
    days: int
    periods_per_day: int
    courses: List[Course]
    rooms: List[Room]
    curriculums: List[Curriculum]
    unavailability: List[Set[int]]
    lectures: List[Lecture]
    course_curriculums: List[List[int]]
    feasible_periods: List[List[int]]
    course_room_preference: List[List[int]]
    course_teachers: List[str]
    course_students: List[int]
    course_lecture_ids: List[List[int]]
    lecture_neighbors: List[Set[int]]
    course_by_id: Dict[str, int]
    room_by_id: Dict[str, int]
    curriculum_by_id: Dict[str, int]
    teacher_by_id: Dict[str, int]
    teachers: List[str]
    total_periods: int = field(init=False)

    def __post_init__(self) -> None:
        self.total_periods = self.days * self.periods_per_day

    def period_to_slot(self, period: int) -> Tuple[int, int]:
        """Return (day, slot) for a flat period index."""

        day = period // self.periods_per_day
        slot = period % self.periods_per_day
        return day, slot


@dataclass
class ScoreBreakdown:
    """Soft-constraint breakdown for CB-CTT."""

    room_capacity: int = 0
    min_working_days: int = 0
    curriculum_compactness: int = 0
    room_stability: int = 0

    @property
    def total(self) -> int:
        return self.room_capacity + self.min_working_days + self.curriculum_compactness + self.room_stability


class ProgressLogger:
    """CSV + console progress logger."""

    def __init__(self, path: Optional[Path]) -> None:
        self.path = path
        self._file = None
        self._writer: Optional[csv.writer] = None
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._file = path.open("w", newline="", encoding="utf-8")
            self._writer = csv.writer(self._file)
            self._writer.writerow(["elapsed", "best_cost", "current_cost", "hard_ok", "accept_rate", "operator"])
            self._file.flush()

    def log(self, elapsed: float, best_cost: int, current_cost: int, hard_ok: bool, accept_rate: float, operator: str) -> None:
        line = f"[{elapsed:7.2f}s] best={best_cost} current={current_cost} hard_ok={hard_ok} accept_rate={accept_rate*100:5.1f}% op={operator}"
        print(line, flush=True)
        if self._writer is not None:
            self._writer.writerow([f"{elapsed:.3f}", best_cost, current_cost, int(hard_ok), f"{accept_rate:.4f}", operator])
            self._file.flush()

    def close(self) -> None:
        if self._file is not None:
            self._file.close()

    def __enter__(self) -> "ProgressLogger":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def parse_instance(path: Optional[str]) -> CBCTTInstance:
    """Parse an ITC-2007 Track 3 instance from disk using the official specification."""

    if path is None:
        content = STRICT_SAMPLE_INSTANCE
    else:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Không tìm thấy file instance: {path}")
        content = p.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.replace("\r", "").splitlines()]
    expected_headers = {
        "name",
        "courses",
        "rooms",
        "days",
        "periods_per_day",
        "curricula",
        "constraints",
    }
    header: Dict[str, str] = {}
    idx = 0

    def skip_empty(position: int) -> int:
        while position < len(lines) and not lines[position]:
            position += 1
        return position

    while idx < len(lines):
        idx = skip_empty(idx)
        if idx >= len(lines):
            break
        line = lines[idx]
        if line.upper() == "COURSES:":
            break
        if ":" not in line:
            raise ValueError(f"Invalid header line: '{line}'")
        key, value = line.split(":", 1)
        key = key.strip().lower()
        if key not in expected_headers:
            raise ValueError(f"Unexpected header key '{key}'")
        value = value.strip()
        if not value:
            raise ValueError(f"Missing value for header '{key}'")
        header[key] = value
        idx += 1
    missing_headers = expected_headers - set(header.keys())
    if missing_headers:
        missing = ", ".join(sorted(missing_headers))
        raise ValueError(f"Missing required header fields: {missing}")

    name = header["name"]
    try:
        courses_expected = int(header["courses"])
        rooms_expected = int(header["rooms"])
        days = int(header["days"])
        periods_per_day = int(header["periods_per_day"])
        curricula_expected = int(header["curricula"])
        constraints_expected = int(header["constraints"])
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError("Header values must be integers where applicable") from exc
    if courses_expected <= 0 or rooms_expected <= 0 or days <= 0 or periods_per_day <= 0 or curricula_expected < 0 or constraints_expected < 0:
        raise ValueError("Header counts must be non-negative and days/periods positive")

    def expect_section(keyword: str) -> None:
        nonlocal idx
        idx = skip_empty(idx)
        if idx >= len(lines) or lines[idx].upper() != keyword:
            raise ValueError(f"Expected section '{keyword}'")
        idx += 1

    expect_section("COURSES:")
    courses: List[Course] = []
    course_by_id: Dict[str, int] = {}
    teacher_by_id: Dict[str, int] = {}
    teachers: List[str] = []
    while True:
        idx = skip_empty(idx)
        if idx >= len(lines):
            raise ValueError("Unexpected end of file while reading COURSES section")
        if lines[idx].upper() == "ROOMS:":
            break
        parts = lines[idx].split()
        if len(parts) != 5:
            raise ValueError(f"Invalid course line: '{lines[idx]}'")
        course_id, teacher_id, lectures_str, mwd_str, students_str = parts
        if course_id in course_by_id:
            raise ValueError(f"Duplicate course identifier '{course_id}'")
        try:
            lectures = int(lectures_str)
            min_working = int(mwd_str)
            students = int(students_str)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Invalid integer in course definition '{lines[idx]}'") from exc
        if lectures <= 0:
            raise ValueError(f"Course '{course_id}' must have at least one lecture")
        if min_working < 0:
            raise ValueError(f"Course '{course_id}' minimum working days must be >= 0")
        if students <= 0:
            raise ValueError(f"Course '{course_id}' must have positive number of students")
        teacher_idx = teacher_by_id.get(teacher_id)
        if teacher_idx is None:
            teacher_idx = len(teachers)
            teacher_by_id[teacher_id] = teacher_idx
            teachers.append(teacher_id)
        course = Course(course_id, teacher_id, lectures, min_working, students, len(courses), teacher_idx)
        course_by_id[course_id] = course.index
        courses.append(course)
        idx += 1
    if len(courses) != courses_expected:
        raise ValueError(f"Expected {courses_expected} courses, found {len(courses)}")

    expect_section("ROOMS:")
    rooms: List[Room] = []
    room_by_id: Dict[str, int] = {}
    while True:
        idx = skip_empty(idx)
        if idx >= len(lines):
            raise ValueError("Unexpected end of file while reading ROOMS section")
        if lines[idx].upper() == "CURRICULA:":
            break
        parts = lines[idx].split()
        if len(parts) != 2:
            raise ValueError(f"Invalid room line: '{lines[idx]}'")
        room_id, capacity_str = parts
        if room_id in room_by_id:
            raise ValueError(f"Duplicate room identifier '{room_id}'")
        try:
            capacity = int(capacity_str)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Invalid room capacity in '{lines[idx]}'") from exc
        if capacity <= 0:
            raise ValueError(f"Room '{room_id}' must have positive capacity")
        room = Room(room_id, capacity, len(rooms))
        rooms.append(room)
        room_by_id[room_id] = room.index
        idx += 1
    if len(rooms) != rooms_expected:
        raise ValueError(f"Expected {rooms_expected} rooms, found {len(rooms)}")

    expect_section("CURRICULA:")
    curriculums: List[Curriculum] = []
    curriculum_by_id: Dict[str, int] = {}
    course_curriculums: List[List[int]] = [[] for _ in courses]
    while True:
        idx = skip_empty(idx)
        if idx >= len(lines):
            raise ValueError("Unexpected end of file while reading CURRICULA section")
        if lines[idx].upper() == "UNAVAILABILITY_CONSTRAINTS:":
            break
        parts = lines[idx].split()
        if len(parts) < 3:
            raise ValueError(f"Invalid curriculum line: '{lines[idx]}'")
        curriculum_id = parts[0]
        if curriculum_id in curriculum_by_id:
            raise ValueError(f"Duplicate curriculum identifier '{curriculum_id}'")
        try:
            member_count = int(parts[1])
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Invalid curriculum size in '{lines[idx]}'") from exc
        if member_count < 0:
            raise ValueError(f"Curriculum '{curriculum_id}' must have non-negative size")
        expected_len = 2 + member_count
        if len(parts) != expected_len:
            raise ValueError(
                f"Curriculum '{curriculum_id}' expects {member_count} courses but found {len(parts) - 2}"
            )
        members: List[int] = []
        for course_id in parts[2:]:
            course_idx = course_by_id.get(course_id)
            if course_idx is None:
                raise ValueError(f"Curriculum '{curriculum_id}' references unknown course '{course_id}'")
            members.append(course_idx)
            course_curriculums[course_idx].append(len(curriculums))
        curriculum = Curriculum(curriculum_id, members, len(curriculums))
        curriculum_by_id[curriculum_id] = curriculum.index
        curriculums.append(curriculum)
        idx += 1
    if len(curriculums) != curricula_expected:
        raise ValueError(f"Expected {curricula_expected} curricula, found {len(curriculums)}")

    expect_section("UNAVAILABILITY_CONSTRAINTS:")
    total_periods = days * periods_per_day
    unavailability: List[Set[int]] = [set() for _ in courses]
    constraint_count = 0
    while True:
        idx = skip_empty(idx)
        if idx >= len(lines):
            raise ValueError("Unexpected end of file while reading UNAVAILABILITY_CONSTRAINTS section")
        if lines[idx].upper() == "END.":
            break
        parts = lines[idx].split()
        if len(parts) != 3:
            raise ValueError(f"Invalid unavailability line: '{lines[idx]}'")
        course_id, day_str, slot_str = parts
        course_idx = course_by_id.get(course_id)
        if course_idx is None:
            raise ValueError(f"Unavailability references unknown course '{course_id}'")
        try:
            day = int(day_str)
            slot = int(slot_str)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Invalid day/period in '{lines[idx]}'") from exc
        if not (0 <= day < days):
            raise ValueError(f"Unavailability day {day} out of range for course '{course_id}'")
        if not (0 <= slot < periods_per_day):
            raise ValueError(f"Unavailability period {slot} out of range for course '{course_id}'")
        period = day * periods_per_day + slot
        unavailability[course_idx].add(period)
        constraint_count += 1
        idx += 1
    if constraint_count != constraints_expected:
        raise ValueError(f"Expected {constraints_expected} unavailability constraints, found {constraint_count}")

    idx = skip_empty(idx)
    if idx >= len(lines) or lines[idx].upper() != "END.":
        raise ValueError("Missing END. terminator")

    lectures: List[Lecture] = []
    course_lecture_ids: List[List[int]] = [[] for _ in courses]
    for course in courses:
        for lec_index in range(course.lectures):
            lecture = Lecture(len(lectures), course.index, lec_index)
            lectures.append(lecture)
            course_lecture_ids[course.index].append(lecture.id)

    feasible_periods: List[List[int]] = []
    for course in courses:
        allowed = [p for p in range(total_periods) if p not in unavailability[course.index]]
        if not allowed:
            raise ValueError(f"Course '{course.id}' has no feasible periods after applying unavailability")
        feasible_periods.append(allowed)

    course_room_preference: List[List[int]] = []
    for course in courses:
        students = course.students
        order = sorted(
            range(len(rooms)),
            key=lambda r: (
                0 if rooms[r].capacity >= students else 1,
                abs(rooms[r].capacity - students),
                rooms[r].capacity,
            ),
        )
        course_room_preference.append(order)

    course_teachers = [course.teacher for course in courses]
    course_students = [course.students for course in courses]
    teacher_to_lectures: Dict[str, List[int]] = defaultdict(list)
    for course in courses:
        teacher_to_lectures[course.teacher].extend(course_lecture_ids[course.index])

    lecture_neighbors: List[Set[int]] = [set() for _ in lectures]
    for lecture_ids in teacher_to_lectures.values():
        for lid in lecture_ids:
            lecture_neighbors[lid].update(lecture_ids)
    for curriculum in curriculums:
        lecture_ids: List[int] = []
        for course_idx in curriculum.courses:
            lecture_ids.extend(course_lecture_ids[course_idx])
        for lid in lecture_ids:
            lecture_neighbors[lid].update(lecture_ids)
    for lid, neighbors in enumerate(lecture_neighbors):
        neighbors.discard(lid)

    return CBCTTInstance(
        name=name,
        days=days,
        periods_per_day=periods_per_day,
        courses=courses,
        rooms=rooms,
        curriculums=curriculums,
        unavailability=unavailability,
        lectures=lectures,
        course_curriculums=course_curriculums,
        feasible_periods=feasible_periods,
        course_room_preference=course_room_preference,
        course_teachers=course_teachers,
        course_students=course_students,
        course_lecture_ids=course_lecture_ids,
        lecture_neighbors=lecture_neighbors,
        course_by_id=course_by_id,
        room_by_id=room_by_id,
        curriculum_by_id=curriculum_by_id,
        teacher_by_id=teacher_by_id,
        teachers=teachers,
    )


class TimetableState:
    """Mutable timetable with incremental scoring."""

    def __init__(self, instance: CBCTTInstance) -> None:
        self.instance = instance
        self.assignments: Dict[int, Tuple[int, int]] = {}
        total_periods = instance.total_periods
        self.period_rooms: List[Dict[int, int]] = [dict() for _ in range(total_periods)]
        self.period_teachers: List[Set[str]] = [set() for _ in range(total_periods)]
        self.period_teacher_owner: List[Dict[str, int]] = [dict() for _ in range(total_periods)]
        self.period_curriculums: List[Set[int]] = [set() for _ in range(total_periods)]
        self.period_curriculum_owner: List[Dict[int, int]] = [dict() for _ in range(total_periods)]
        course_count = len(instance.courses)
        self.course_day_counts: List[List[int]] = [[0] * instance.days for _ in range(course_count)]
        self.course_active_days: List[int] = [0] * course_count
        self.course_room_counts: List[Dict[int, int]] = [defaultdict(int) for _ in range(course_count)]
        self.course_mwd_penalty: List[int] = [0] * course_count
        self.course_room_penalty: List[int] = [0] * course_count
        curriculum_count = len(instance.curriculums)
        self.curriculum_day_slots: List[List[Set[int]]] = [
            [set() for _ in range(instance.days)]
            for _ in range(curriculum_count)
        ]
        self.curriculum_day_penalty: List[List[int]] = [
            [0] * instance.days for _ in range(curriculum_count)
        ]
        lecture_count = len(instance.lectures)
        self.lecture_room_penalty: List[int] = [0] * lecture_count
        self.soft_room_capacity = 0
        self.soft_min_working_days = 0
        self.soft_curriculum_compactness = 0
        self.soft_room_stability = 0

    def clone_assignments(self) -> Dict[int, Tuple[int, int]]:
        return dict(self.assignments)

    def _compute_course_mwd_penalty(self, course_idx: int) -> int:
        course = self.instance.courses[course_idx]
        missing = max(0, course.min_working_days - self.course_active_days[course_idx])
        return missing * 5

    def _compute_course_room_penalty(self, course_idx: int) -> int:
        rooms_used = sum(1 for count in self.course_room_counts[course_idx].values() if count > 0)
        return max(0, rooms_used - 1)

    @staticmethod
    def _compute_curriculum_day_penalty(slots: Set[int]) -> int:
        penalty = 0
        for slot in slots:
            if (slot - 1) not in slots and (slot + 1) not in slots:
                penalty += 2
        return penalty

    def _can_place(self, lecture_id: int, period: int, room_idx: int) -> bool:
        lecture = self.instance.lectures[lecture_id]
        course_idx = lecture.course
        if period in self.instance.unavailability[course_idx]:
            return False
        if room_idx in self.period_rooms[period]:
            return False
        teacher = self.instance.course_teachers[course_idx]
        owner = self.period_teacher_owner[period].get(teacher)
        if owner is not None and owner != lecture_id:
            return False
        for curriculum_idx in self.instance.course_curriculums[course_idx]:
            owner = self.period_curriculum_owner[period].get(curriculum_idx)
            if owner is not None and owner != lecture_id:
                return False
        return True

    def unassign(self, lecture_id: int) -> None:
        if lecture_id in self.assignments:
            self._remove_assignment(lecture_id)

    def move_lecture(self, lecture_id: int, period: int, room_idx: int, commit: bool = True) -> Optional[int]:
        current = self.assignments.get(lecture_id)
        if current is not None and current == (period, room_idx):
            return 0
        delta = 0
        if current is not None:
            delta += self._remove_assignment(lecture_id)
        if not self._can_place(lecture_id, period, room_idx):
            if current is not None:
                self._insert_assignment(lecture_id, current[0], current[1])
            return None
        delta += self._insert_assignment(lecture_id, period, room_idx)
        if not commit:
            self._remove_assignment(lecture_id)
            if current is not None:
                self._insert_assignment(lecture_id, current[0], current[1])
        return delta

    def swap_lectures(self, lecture_a: int, lecture_b: int, commit: bool = True) -> Optional[int]:
        if lecture_a == lecture_b:
            return 0
        assign_a = self.assignments.get(lecture_a)
        assign_b = self.assignments.get(lecture_b)
        if assign_a is None or assign_b is None:
            return None
        if assign_a == assign_b:
            return 0
        delta = 0
        delta += self._remove_assignment(lecture_a)
        delta += self._remove_assignment(lecture_b)
        inserted_a = False
        if self._can_place(lecture_a, assign_b[0], assign_b[1]):
            delta += self._insert_assignment(lecture_a, assign_b[0], assign_b[1])
            inserted_a = True
        else:
            self._insert_assignment(lecture_a, assign_a[0], assign_a[1])
            self._insert_assignment(lecture_b, assign_b[0], assign_b[1])
            return None
        if self._can_place(lecture_b, assign_a[0], assign_a[1]):
            delta += self._insert_assignment(lecture_b, assign_a[0], assign_a[1])
        else:
            self._remove_assignment(lecture_a)
            self._insert_assignment(lecture_a, assign_a[0], assign_a[1])
            self._insert_assignment(lecture_b, assign_b[0], assign_b[1])
            return None
        if not commit:
            self._remove_assignment(lecture_a)
            self._remove_assignment(lecture_b)
            self._insert_assignment(lecture_a, assign_a[0], assign_a[1])
            self._insert_assignment(lecture_b, assign_b[0], assign_b[1])
        return delta

    def kempe_chain(self, mapping: Dict[int, Tuple[int, Optional[int]]], commit: bool = True) -> Optional[int]:
        originals: Dict[int, Tuple[int, int]] = {}
        for lecture_id in mapping:
            original = self.assignments.get(lecture_id)
            if original is None:
                return None
            originals[lecture_id] = original
        delta = 0
        for lecture_id in mapping:
            delta += self._remove_assignment(lecture_id)
        inserted: List[int] = []
        for lecture_id, (period, room_idx) in mapping.items():
            if room_idx is None:
                room_idx = self._select_feasible_room(lecture_id, period)
                if room_idx is None:
                    for assigned in inserted:
                        self._remove_assignment(assigned)
                    for restore_id, assign in originals.items():
                        self._insert_assignment(restore_id, assign[0], assign[1])
                    return None
            if not self._can_place(lecture_id, period, room_idx):
                for assigned in inserted:
                    self._remove_assignment(assigned)
                for restore_id, assign in originals.items():
                    self._insert_assignment(restore_id, assign[0], assign[1])
                return None
            delta += self._insert_assignment(lecture_id, period, room_idx)
            inserted.append(lecture_id)
        if not commit:
            for lecture_id in mapping:
                self._remove_assignment(lecture_id)
            for lecture_id, (period, room_idx) in originals.items():
                self._insert_assignment(lecture_id, period, room_idx)
        return delta

    def _select_feasible_room(self, lecture_id: int, period: int) -> Optional[int]:
        lecture = self.instance.lectures[lecture_id]
        course_idx = lecture.course
        students = self.instance.course_students[course_idx]
        preference = self.instance.course_room_preference[course_idx]
        adequate: List[int] = []
        fallback: List[int] = []
        for room_idx in preference:
            capacity = self.instance.rooms[room_idx].capacity
            if capacity >= students:
                adequate.append(room_idx)
            else:
                fallback.append(room_idx)
        for room_idx in adequate + fallback:
            if self._can_place(lecture_id, period, room_idx):
                return room_idx
        return None

    def conflicts_for(self, lecture_id: int, period: int, room_idx: int) -> Optional[Set[int]]:
        """Return conflicting lecture ids for placing lecture at period/room, or None if forbidden."""

        course_idx = self.instance.lectures[lecture_id].course
        if period in self.instance.unavailability[course_idx]:
            return None
        conflicts: Set[int] = set()
        occupant = self.period_rooms[period].get(room_idx)
        if occupant is not None and occupant != lecture_id:
            conflicts.add(occupant)
        teacher = self.instance.course_teachers[course_idx]
        owner = self.period_teacher_owner[period].get(teacher)
        if owner is not None and owner != lecture_id:
            conflicts.add(owner)
        for curriculum_idx in self.instance.course_curriculums[course_idx]:
            owner = self.period_curriculum_owner[period].get(curriculum_idx)
            if owner is not None and owner != lecture_id:
                conflicts.add(owner)
        return conflicts

    def _remove_assignment(self, lecture_id: int) -> int:
        period, room_idx = self.assignments.pop(lecture_id)
        course_idx = self.instance.lectures[lecture_id].course
        teacher = self.instance.course_teachers[course_idx]
        self.period_rooms[period].pop(room_idx, None)
        self.period_teachers[period].discard(teacher)
        self.period_teacher_owner[period].pop(teacher, None)
        for curriculum_idx in self.instance.course_curriculums[course_idx]:
            self.period_curriculums[period].discard(curriculum_idx)
            self.period_curriculum_owner[period].pop(curriculum_idx, None)
        delta = 0
        old_room_penalty = self.lecture_room_penalty[lecture_id]
        self.soft_room_capacity -= old_room_penalty
        delta -= old_room_penalty
        self.lecture_room_penalty[lecture_id] = 0
        day, slot = self.instance.period_to_slot(period)
        old_penalty = self.course_mwd_penalty[course_idx]
        self.course_day_counts[course_idx][day] -= 1
        if self.course_day_counts[course_idx][day] == 0:
            self.course_active_days[course_idx] -= 1
        new_penalty = self._compute_course_mwd_penalty(course_idx)
        self.course_mwd_penalty[course_idx] = new_penalty
        self.soft_min_working_days += new_penalty - old_penalty
        delta += new_penalty - old_penalty
        old_penalty = self.course_room_penalty[course_idx]
        counts = self.course_room_counts[course_idx]
        counts[room_idx] -= 1
        if counts[room_idx] == 0:
            del counts[room_idx]
        new_penalty = self._compute_course_room_penalty(course_idx)
        self.course_room_penalty[course_idx] = new_penalty
        self.soft_room_stability += new_penalty - old_penalty
        delta += new_penalty - old_penalty
        for curriculum_idx in self.instance.course_curriculums[course_idx]:
            slots = self.curriculum_day_slots[curriculum_idx][day]
            old_penalty = self.curriculum_day_penalty[curriculum_idx][day]
            slots.discard(slot)
            new_penalty = self._compute_curriculum_day_penalty(slots)
            self.curriculum_day_penalty[curriculum_idx][day] = new_penalty
            self.soft_curriculum_compactness += new_penalty - old_penalty
            delta += new_penalty - old_penalty
        return delta

    def _insert_assignment(self, lecture_id: int, period: int, room_idx: int) -> int:
        self.assignments[lecture_id] = (period, room_idx)
        course_idx = self.instance.lectures[lecture_id].course
        teacher = self.instance.course_teachers[course_idx]
        self.period_rooms[period][room_idx] = lecture_id
        self.period_teachers[period].add(teacher)
        self.period_teacher_owner[period][teacher] = lecture_id
        for curriculum_idx in self.instance.course_curriculums[course_idx]:
            self.period_curriculums[period].add(curriculum_idx)
            self.period_curriculum_owner[period][curriculum_idx] = lecture_id
        delta = 0
        students = self.instance.course_students[course_idx]
        capacity = self.instance.rooms[room_idx].capacity
        overflow = max(0, students - capacity)
        self.lecture_room_penalty[lecture_id] = overflow
        self.soft_room_capacity += overflow
        delta += overflow
        day, slot = self.instance.period_to_slot(period)
        old_penalty = self.course_mwd_penalty[course_idx]
        self.course_day_counts[course_idx][day] += 1
        if self.course_day_counts[course_idx][day] == 1:
            self.course_active_days[course_idx] += 1
        new_penalty = self._compute_course_mwd_penalty(course_idx)
        self.course_mwd_penalty[course_idx] = new_penalty
        self.soft_min_working_days += new_penalty - old_penalty
        delta += new_penalty - old_penalty
        old_penalty = self.course_room_penalty[course_idx]
        counts = self.course_room_counts[course_idx]
        counts[room_idx] += 1
        new_penalty = self._compute_course_room_penalty(course_idx)
        self.course_room_penalty[course_idx] = new_penalty
        self.soft_room_stability += new_penalty - old_penalty
        delta += new_penalty - old_penalty
        for curriculum_idx in self.instance.course_curriculums[course_idx]:
            slots = self.curriculum_day_slots[curriculum_idx][day]
            old_penalty = self.curriculum_day_penalty[curriculum_idx][day]
            slots.add(slot)
            new_penalty = self._compute_curriculum_day_penalty(slots)
            self.curriculum_day_penalty[curriculum_idx][day] = new_penalty
            self.soft_curriculum_compactness += new_penalty - old_penalty
            delta += new_penalty - old_penalty
        return delta

    @property
    def current_cost(self) -> int:
        return self.soft_room_capacity + self.soft_min_working_days + self.soft_curriculum_compactness + self.soft_room_stability

    def score_breakdown(self) -> ScoreBreakdown:
        return ScoreBreakdown(
            room_capacity=self.soft_room_capacity,
            min_working_days=self.soft_min_working_days,
            curriculum_compactness=self.soft_curriculum_compactness,
            room_stability=self.soft_room_stability,
        )

    def check_hard_constraints(self) -> bool:
        if len(self.assignments) != len(self.instance.lectures):
            return False
        for period in range(self.instance.total_periods):
            room_map = self.period_rooms[period]
            if len(room_map) != len(set(room_map.keys())):
                return False
            if len(self.period_teachers[period]) != len(self.period_teacher_owner[period]):
                return False
            if len(self.period_curriculums[period]) != len(self.period_curriculum_owner[period]):
                return False
        for lecture_id, (period, _room_idx) in self.assignments.items():
            course_idx = self.instance.lectures[lecture_id].course
            if period in self.instance.unavailability[course_idx]:
                return False
        return True


def _candidate_order(instance: CBCTTInstance) -> List[int]:
    order = list(range(len(instance.lectures)))
    domain_size: List[int] = []
    for lecture in instance.lectures:
        course = instance.courses[lecture.course]
        domain_size.append(len(instance.feasible_periods[lecture.course]) * len(instance.course_room_preference[lecture.course]))
    order.sort(
        key=lambda lid: (
            domain_size[lid],
            -instance.courses[instance.lectures[lid].course].min_working_days,
            -instance.courses[instance.lectures[lid].course].students,
            lid,
        ),
    )
    return order


def _build_initial_solution(instance: CBCTTInstance, rng: random.Random, strategy: str, builder_deadline: float) -> TimetableState:
    state = TimetableState(instance)
    order = _candidate_order(instance)
    sys.setrecursionlimit(max(10000, len(order) * 20))

    def backtrack(index: int) -> bool:
        if time.time() > builder_deadline:
            return False
        if index >= len(order):
            return True
        lecture_id = order[index]
        course_idx = instance.lectures[lecture_id].course
        feasible_periods = instance.feasible_periods[course_idx]
        candidates: List[Tuple[int, int, int]] = []
        for period in feasible_periods:
            for room_idx in instance.course_room_preference[course_idx]:
                delta = state.move_lecture(lecture_id, period, room_idx, commit=False)
                if delta is None:
                    continue
                candidates.append((delta, period, room_idx))
        if not candidates:
            return False
        rng.shuffle(candidates)
        candidates.sort(key=lambda entry: entry[0])
        if strategy == "random-repair":
            rng.shuffle(candidates)
        limit = min(len(candidates), 30)
        for delta, period, room_idx in candidates[:limit]:
            result = state.move_lecture(lecture_id, period, room_idx, commit=True)
            if result is None:
                continue
            if backtrack(index + 1):
                return True
            state.unassign(lecture_id)
        return False

    attempts = 0
    deadline = builder_deadline
    while time.time() <= deadline and attempts < 4:
        if backtrack(0):
            return state
        attempts += 1
        rng.shuffle(order)
        state = TimetableState(instance)
    raise RuntimeError("Failed to build initial feasible solution within budget")


def _repair_initial_solution(instance: CBCTTInstance, rng: random.Random, builder_deadline: float) -> TimetableState:
    """Fallback constructor using ejection-based repairs when pure backtracking fails."""

    state = TimetableState(instance)
    order = _candidate_order(instance)
    queue = deque(order)
    retries: Dict[int, int] = defaultdict(int)
    max_retry = max(10, len(order) * 6)
    while queue and time.time() <= builder_deadline:
        lecture_id = queue.popleft()
        if lecture_id in state.assignments:
            continue
        course_idx = instance.lectures[lecture_id].course
        feasible_periods = instance.feasible_periods[course_idx]
        if not feasible_periods:
            raise RuntimeError(f"Course '{instance.courses[course_idx].id}' lacks feasible periods")
        candidates: List[Tuple[int, int, float, int, int, Set[int]]] = []
        for period in feasible_periods:
            for room_idx in instance.course_room_preference[course_idx]:
                conflicts = state.conflicts_for(lecture_id, period, room_idx)
                if conflicts is None:
                    continue
                overflow = max(0, instance.course_students[course_idx] - instance.rooms[room_idx].capacity)
                candidates.append((len(conflicts), overflow, rng.random(), period, room_idx, conflicts))
        if not candidates:
            retries[lecture_id] += 1
            if retries[lecture_id] > max_retry:
                break
            queue.append(lecture_id)
            continue
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        placed = False
        for _, _, _, period, room_idx, conflicts in candidates[: min(12, len(candidates))]:
            removed: List[Tuple[int, Tuple[int, int]]] = []
            for conflict in conflicts:
                assign = state.assignments.get(conflict)
                if assign is None:
                    continue
                removed.append((conflict, assign))
            for conflict, _assign in removed:
                state.unassign(conflict)
            delta = state.move_lecture(lecture_id, period, room_idx, commit=True)
            if delta is not None:
                for conflict, _assign in removed:
                    queue.append(conflict)
                placed = True
                break
            if lecture_id in state.assignments:
                state.unassign(lecture_id)
            for conflict, (p_old, r_old) in reversed(removed):
                state.move_lecture(conflict, p_old, r_old, commit=True)
            if time.time() > builder_deadline:
                break
        if not placed:
            retries[lecture_id] += 1
            if retries[lecture_id] > max_retry:
                break
            queue.append(lecture_id)
    if len(state.assignments) == len(instance.lectures):
        return state
    raise RuntimeError("Fallback repair failed to build feasible solution")


def build_initial_solution(instance: CBCTTInstance, rng: random.Random, strategy: str, start_time: float, time_limit: float) -> TimetableState:
    overall_deadline = start_time + max(time_limit, 0.5)
    now = time.time()
    max_budget = max(0.5, time_limit * 0.35)
    base_deadline = min(overall_deadline - 0.25, now + max_budget)
    builder_deadline = max(now + 0.05, base_deadline)
    builder_deadline = min(builder_deadline, overall_deadline - 0.05)
    if builder_deadline <= now:
        builder_deadline = min(now + 0.05, overall_deadline - 0.01)
    try:
        return _build_initial_solution(instance, rng, strategy, builder_deadline)
    except RuntimeError:
        min_window = max(1.0, time_limit * 0.25)
        fallback_deadline = min(
            overall_deadline - 0.01,
            max(builder_deadline + 0.5, time.time() + min_window),
        )
        fallback_deadline = max(time.time() + 0.05, fallback_deadline)
        return _repair_initial_solution(instance, rng, fallback_deadline)


class Move:
    """Abstract move with evaluation/apply contract."""

    name: str

    def evaluate(self, state: TimetableState) -> Optional[int]:
        raise NotImplementedError

    def apply(self, state: TimetableState) -> int:
        raise NotImplementedError

    def signature(self) -> Tuple:
        raise NotImplementedError


class MoveLectureMove(Move):
    name = "move"

    def __init__(self, lecture: int, period: int, room: int) -> None:
        self.lecture = lecture
        self.period = period
        self.room = room
        self._baseline: Optional[Tuple[int, int]] = None
        self._delta: Optional[int] = None

    def evaluate(self, state: TimetableState) -> Optional[int]:
        self._baseline = state.assignments.get(self.lecture)
        delta = state.move_lecture(self.lecture, self.period, self.room, commit=False)
        if delta is None:
            return None
        self._delta = delta
        return delta

    def apply(self, state: TimetableState) -> int:
        delta = state.move_lecture(self.lecture, self.period, self.room, commit=True)
        if delta is None:
            raise RuntimeError("Unexpected infeasible move during apply")
        self._delta = delta
        return delta

    def signature(self) -> Tuple:
        return (self.name, self.lecture, self.period, self.room)


class SwapLecturesMove(Move):
    name = "swap"

    def __init__(self, lecture_a: int, lecture_b: int) -> None:
        self.lecture_a = lecture_a
        self.lecture_b = lecture_b
        self._delta: Optional[int] = None

    def evaluate(self, state: TimetableState) -> Optional[int]:
        delta = state.swap_lectures(self.lecture_a, self.lecture_b, commit=False)
        if delta is None:
            return None
        self._delta = delta
        return delta

    def apply(self, state: TimetableState) -> int:
        delta = state.swap_lectures(self.lecture_a, self.lecture_b, commit=True)
        if delta is None:
            raise RuntimeError("Unexpected infeasible swap")
        self._delta = delta
        return delta

    def signature(self) -> Tuple:
        a, b = sorted((self.lecture_a, self.lecture_b))
        return (self.name, a, b)


class KempeChainMove(Move):
    name = "kempe"

    def __init__(self, mapping: Dict[int, Tuple[int, Optional[int]]]) -> None:
        self.mapping = mapping
        self._delta: Optional[int] = None

    def evaluate(self, state: TimetableState) -> Optional[int]:
        delta = state.kempe_chain(self.mapping, commit=False)
        if delta is None:
            return None
        self._delta = delta
        return delta

    def apply(self, state: TimetableState) -> int:
        delta = state.kempe_chain(self.mapping, commit=True)
        if delta is None:
            raise RuntimeError("Unexpected infeasible Kempe chain")
        self._delta = delta
        return delta

    def signature(self) -> Tuple:
        items = tuple(sorted((lecture, target[0]) for lecture, target in self.mapping.items()))
        return (self.name, items)


class Neighborhood:
    """Base neighborhood operator."""

    name: str

    def generate_candidate(self, state: TimetableState, rng: random.Random) -> Optional[Move]:
        raise NotImplementedError


class MoveLectureNeighborhood(Neighborhood):
    name = "MoveLecture"

    def generate_candidate(self, state: TimetableState, rng: random.Random) -> Optional[Move]:
        instance = state.instance
        lectures = instance.lectures
        focus_courses = [idx for idx, penalty in enumerate(state.course_mwd_penalty) if penalty > 0]
        focus_courses.extend(idx for idx, penalty in enumerate(state.course_room_penalty) if penalty > 0 and idx not in focus_courses)
        if focus_courses:
            course_idx = rng.choice(focus_courses)
            lecture_id = rng.choice(instance.course_lecture_ids[course_idx])
        else:
            lecture_id = rng.randrange(len(lectures))
        current = state.assignments.get(lecture_id)
        if current is None:
            return None
        course_idx = instance.lectures[lecture_id].course
        periods = instance.feasible_periods[course_idx]
        if not periods:
            return None
        period = rng.choice(periods)
        room = rng.choice(instance.course_room_preference[course_idx])
        tries = 0
        while current == (period, room) and tries < 5:
            period = rng.choice(periods)
            room = rng.choice(instance.course_room_preference[course_idx])
            tries += 1
        return MoveLectureMove(lecture_id, period, room)


class RoomChangeNeighborhood(Neighborhood):
    name = "RoomChange"

    def generate_candidate(self, state: TimetableState, rng: random.Random) -> Optional[Move]:
        candidates = [idx for idx, counts in enumerate(state.course_room_counts) if len(counts) > 1]
        if not candidates:
            return None
        course_idx = rng.choice(candidates)
        lecture_id = rng.choice(state.instance.course_lecture_ids[course_idx])
        current = state.assignments.get(lecture_id)
        if current is None:
            return None
        period, current_room = current
        for room_idx in state.instance.course_room_preference[course_idx]:
            if room_idx == current_room:
                continue
            if state.move_lecture(lecture_id, period, room_idx, commit=False) is not None:
                return MoveLectureMove(lecture_id, period, room_idx)
        return None


class PeriodChangeNeighborhood(Neighborhood):
    name = "PeriodChange"

    def generate_candidate(self, state: TimetableState, rng: random.Random) -> Optional[Move]:
        instance = state.instance
        lectures = instance.lectures
        lecture_id = rng.randrange(len(lectures))
        current = state.assignments.get(lecture_id)
        if current is None:
            return None
        period, room = current
        course_idx = lectures[lecture_id].course
        for _ in range(5):
            new_period = rng.choice(instance.feasible_periods[course_idx])
            if new_period == period:
                continue
            preferred_rooms = instance.course_room_preference[course_idx]
            top_room = room
            if state.move_lecture(lecture_id, new_period, top_room, commit=False) is not None:
                return MoveLectureMove(lecture_id, new_period, top_room)
            for room_idx in preferred_rooms:
                if room_idx == room:
                    continue
                if state.move_lecture(lecture_id, new_period, room_idx, commit=False) is not None:
                    return MoveLectureMove(lecture_id, new_period, room_idx)
        return None


class SwapLecturesNeighborhood(Neighborhood):
    name = "SwapLectures"

    def generate_candidate(self, state: TimetableState, rng: random.Random) -> Optional[Move]:
        lecture_count = len(state.instance.lectures)
        lecture_a = rng.randrange(lecture_count)
        lecture_b = rng.randrange(lecture_count)
        if lecture_a == lecture_b:
            return None
        return SwapLecturesMove(lecture_a, lecture_b)


class KempeChainNeighborhood(Neighborhood):
    name = "KempeChain"

    def generate_candidate(self, state: TimetableState, rng: random.Random) -> Optional[Move]:
        instance = state.instance
        lecture_id = rng.randrange(len(instance.lectures))
        current = state.assignments.get(lecture_id)
        if current is None:
            return None
        current_period = current[0]
        course_idx = instance.lectures[lecture_id].course
        periods = instance.feasible_periods[course_idx]
        if len(periods) <= 1:
            return None
        target_period = rng.choice(periods)
        tries = 0
        while target_period == current_period and tries < 5:
            target_period = rng.choice(periods)
            tries += 1
        if target_period == current_period:
            return None
        color_a, color_b = current_period, target_period
        chain: Set[int] = set()
        queue: List[int] = [lecture_id]
        while queue:
            node = queue.pop()
            if node in chain:
                continue
            chain.add(node)
            for neighbor in instance.lecture_neighbors[node]:
                assignment = state.assignments.get(neighbor)
                if assignment is None:
                    continue
                if assignment[0] in (color_a, color_b) and neighbor not in chain:
                    queue.append(neighbor)
        mapping: Dict[int, Tuple[int, Optional[int]]] = {}
        for node in chain:
            assignment = state.assignments.get(node)
            if assignment is None:
                return None
            period, room = assignment
            course_id = instance.lectures[node].course
            target = color_b if period == color_a else color_a
            if target in state.instance.unavailability[course_id]:
                return None
            mapping[node] = (target, None)
        return KempeChainMove(mapping)


class CapacityFixNeighborhood(Neighborhood):
    name = "CapacityFix"

    def generate_candidate(self, state: TimetableState, rng: random.Random) -> Optional[Move]:
        # Focus on lectures suffering the worst capacity overflow.
        penalized = [
            (state.lecture_room_penalty[lid], lid)
            for lid in range(len(state.lecture_room_penalty))
            if state.lecture_room_penalty[lid] > 0
        ]
        if not penalized:
            return None
        penalized.sort(reverse=True)
        top_penalty = penalized[0][0]
        candidates = [lid for pen, lid in penalized if pen == top_penalty]
        lecture_id = rng.choice(candidates)
        assignment = state.assignments.get(lecture_id)
        if assignment is None:
            return None
        period, current_room = assignment
        course_idx = state.instance.lectures[lecture_id].course
        students = state.instance.course_students[course_idx]
        room_order = state.instance.course_room_preference[course_idx]
        feasible_same_period: List[int] = []
        for room_idx in room_order:
            if room_idx == current_room:
                continue
            if state.instance.rooms[room_idx].capacity < students:
                continue
            if state.move_lecture(lecture_id, period, room_idx, commit=False) is not None:
                feasible_same_period.append(room_idx)
        if feasible_same_period:
            room_idx = feasible_same_period[0]
            return MoveLectureMove(lecture_id, period, room_idx)
        periods = state.instance.feasible_periods[course_idx]
        samples = periods[:]
        rng.shuffle(samples)
        for new_period in samples[: min(6, len(samples))]:
            if new_period == period:
                continue
            room_idx = state._select_feasible_room(lecture_id, new_period)
            if room_idx is None:
                continue
            if state.move_lecture(lecture_id, new_period, room_idx, commit=False) is not None:
                return MoveLectureMove(lecture_id, new_period, room_idx)
        return None


class NeighborhoodManager:
    """Adaptive operator selector."""

    def __init__(self, neighborhoods: Sequence[Neighborhood]) -> None:
        self.neighborhoods = list(neighborhoods)
        self.weights = [1.0 for _ in neighborhoods]
        self.usage = [0 for _ in neighborhoods]

    def select(self, rng: random.Random) -> Tuple[int, Neighborhood]:
        total = sum(self.weights)
        pick = rng.random() * total
        cumulative = 0.0
        for idx, weight in enumerate(self.weights):
            cumulative += weight
            if pick <= cumulative:
                self.usage[idx] += 1
                return idx, self.neighborhoods[idx]
        idx = len(self.neighborhoods) - 1
        self.usage[idx] += 1
        return idx, self.neighborhoods[idx]

    def reward(self, index: int, improvement: bool) -> None:
        if improvement:
            self.weights[index] = min(self.weights[index] * 1.1 + 0.05, 6.0)
        else:
            self.weights[index] = max(self.weights[index] * 0.95, 0.1)


class SimulatedAnnealing:
    """Simulated annealing metaheuristic."""

    def __init__(self, state: TimetableState, neighborhoods: Sequence[Neighborhood], rng: random.Random, logger: ProgressLogger) -> None:
        self.state = state
        self.manager = NeighborhoodManager(neighborhoods)
        self.rng = rng
        self.logger = logger

    def run(self, best_assignments: Dict[int, Tuple[int, int]], best_breakdown: ScoreBreakdown, start_time: float, time_limit: float) -> Tuple[Dict[int, Tuple[int, int]], ScoreBreakdown]:
        state = self.state
        rng = self.rng
        start_temp = max(1.0, state.current_cost / max(1, len(state.assignments)))
        temperature = start_temp
        alpha = 0.995
        min_temp = 0.05
        accepted = 0
        attempted = 0
        best_cost = state.current_cost
        last_improvement_iter = 0
        iteration = 0
        last_log = 0.0
        stagnation_limit = 2000
        while time.time() - start_time < time_limit:
            iteration += 1
            idx, operator = self.manager.select(rng)
            move = operator.generate_candidate(state, rng)
            if move is None:
                continue
            delta = move.evaluate(state)
            if delta is None:
                self.manager.reward(idx, False)
                continue
            attempted += 1
            accept = False
            if delta <= 0:
                accept = True
            else:
                threshold = math.exp(-delta / max(min_temp, temperature))
                if rng.random() < threshold:
                    accept = True
            if accept:
                delta_apply = move.apply(state)
                if delta_apply is None:
                    continue
                accepted += 1
                improvement = False
                if state.current_cost < best_cost:
                    best_cost = state.current_cost
                    best_assignments = state.clone_assignments()
                    best_breakdown = state.score_breakdown()
                    improvement = True
                    last_improvement_iter = iteration
                self.manager.reward(idx, improvement)
            else:
                self.manager.reward(idx, False)
            temperature = max(min_temp, temperature * alpha)
            if iteration - last_improvement_iter > stagnation_limit:
                temperature = max(start_temp, temperature * 1.5)
                last_improvement_iter = iteration
            now = time.time() - start_time
            if now - last_log >= 2.0:
                accept_rate = accepted / attempted if attempted else 0.0
                hard_ok = state.check_hard_constraints()
                self.logger.log(now, best_cost, state.current_cost, hard_ok, accept_rate, operator.name)
                last_log = now
        return best_assignments, best_breakdown


class TabuSearch:
    """Tabu search metaheuristic with adaptive tenure."""

    def __init__(self, state: TimetableState, neighborhoods: Sequence[Neighborhood], rng: random.Random, logger: ProgressLogger) -> None:
        self.state = state
        self.manager = NeighborhoodManager(neighborhoods)
        self.rng = rng
        self.logger = logger

    def run(self, best_assignments: Dict[int, Tuple[int, int]], best_breakdown: ScoreBreakdown, start_time: float, time_limit: float) -> Tuple[Dict[int, Tuple[int, int]], ScoreBreakdown]:
        state = self.state
        rng = self.rng
        iteration = 0
        tabu: Dict[Tuple, int] = {}
        base_tenure = 7
        best_cost = state.current_cost
        last_log = 0.0
        accepted = 0
        attempted = 0
        no_improve = 0
        sample_size = 20
        while time.time() - start_time < time_limit:
            iteration += 1
            candidates: List[Tuple[int, bool, int, Move, Tuple]] = []
            for _ in range(sample_size):
                idx, operator = self.manager.select(rng)
                move = operator.generate_candidate(state, rng)
                if move is None:
                    continue
                delta = move.evaluate(state)
                if delta is None:
                    continue
                signature = move.signature()
                is_tabu = tabu.get(signature, 0) > iteration
                candidates.append((delta, is_tabu, idx, move, signature))
            if not candidates:
                continue
            candidates.sort(key=lambda item: (item[1], item[0]))
            chosen = None
            for delta, is_tabu, idx, move, signature in candidates:
                if not is_tabu or state.current_cost + delta < best_cost:
                    chosen = (delta, is_tabu, idx, move, signature)
                    break
            if chosen is None:
                chosen = candidates[0]
            delta, is_tabu, idx, move, signature = chosen
            delta_apply = move.apply(state)
            if delta_apply is None:
                continue
            attempted += 1
            accepted += 1
            tabu[signature] = iteration + base_tenure + rng.randint(0, 4)
            improvement = False
            if state.current_cost < best_cost:
                best_cost = state.current_cost
                best_assignments = state.clone_assignments()
                best_breakdown = state.score_breakdown()
                improvement = True
                no_improve = 0
            else:
                no_improve += 1
            self.manager.reward(idx, improvement)
            if no_improve > 250:
                base_tenure = min(25, base_tenure + 1)
                no_improve = 0
            elif improvement:
                base_tenure = max(4, base_tenure - 1)
            now = time.time() - start_time
            if now - last_log >= 2.0:
                accept_rate = accepted / attempted if attempted else 0.0
                hard_ok = state.check_hard_constraints()
                self.logger.log(now, best_cost, state.current_cost, hard_ok, accept_rate, move.name)
                last_log = now
        return best_assignments, best_breakdown


def run_metaheuristic(state: TimetableState, meta: str, rng: random.Random, logger: ProgressLogger, remaining_time: float) -> Tuple[Dict[int, Tuple[int, int]], ScoreBreakdown]:
    best_assignments = state.clone_assignments()
    best_breakdown = state.score_breakdown()
    neighborhoods: List[Neighborhood] = [
        MoveLectureNeighborhood(),
        SwapLecturesNeighborhood(),
        RoomChangeNeighborhood(),
        PeriodChangeNeighborhood(),
        KempeChainNeighborhood(),
        CapacityFixNeighborhood(),
    ]
    start_time = time.time()
    if remaining_time <= 0.0:
        return best_assignments, best_breakdown
    if meta.upper() == "TS":
        search = TabuSearch(state, neighborhoods, rng, logger)
    else:
        search = SimulatedAnnealing(state, neighborhoods, rng, logger)
    best_assignments, best_breakdown = search.run(best_assignments, best_breakdown, start_time, remaining_time)
    return best_assignments, best_breakdown


def rebuild_state(instance: CBCTTInstance, assignments: Dict[int, Tuple[int, int]]) -> TimetableState:
    """Create a fresh state from frozen assignments.

    >>> inst = parse_instance(None)
    >>> rng = random.Random(0)
    >>> start = time.time()
    >>> base = build_initial_solution(inst, rng, "greedy-cprop", start, 5.0)
    >>> rebuilt = rebuild_state(inst, base.clone_assignments())
    >>> rebuilt.current_cost == base.current_cost
    True
    """

    state = TimetableState(instance)
    for lecture_id, (period, room) in assignments.items():
        state.move_lecture(lecture_id, period, room, commit=True)
    return state


def write_solution(instance: CBCTTInstance, assignments: Dict[int, Tuple[int, int]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for course in sorted(instance.courses, key=lambda c: c.id):
            for lecture_id in instance.course_lecture_ids[course.index]:
                period, room_idx = assignments[lecture_id]
                day, slot = instance.period_to_slot(period)
                room = instance.rooms[room_idx].id
                handle.write(f"{course.id} {room} {day} {slot}\n")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Curriculum-Based Course Timetabling solver (ITC-2007 Track 3)")
    parser.add_argument("--instance", type=str, default=None, help="Path to .ctt instance file")
    parser.add_argument("--out", type=str, default="solution.sol", help="Output .sol path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--time_limit", type=float, default=180.0, help="Time limit in seconds")
    parser.add_argument("--meta", type=str, default="SA", choices=["SA", "TS"], help="Metaheuristic (SA or TS)")
    parser.add_argument("--init", type=str, default="greedy-cprop", choices=["greedy-cprop", "random-repair"], help="Initial constructor strategy")
    parser.add_argument("--log", type=str, default=None, help="CSV progress log path")
    parser.add_argument("--dry_run_parse", action="store_true", help="Only parse the instance and print counts")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    rng = random.Random(args.seed)
    instance = parse_instance(args.instance)
    if args.dry_run_parse:
        print(f"Tên instance: {instance.name}")
        print(f"Số khóa học: {len(instance.courses)}")
        print(f"Số phòng: {len(instance.rooms)}")
        print(f"Số curricula: {len(instance.curriculums)}")
        print(f"Số ngày: {instance.days}; tiết/ngày: {instance.periods_per_day}")
        print(f"Tổng số tiết: {instance.total_periods}")
        return
    start_time = time.time()
    try:
        state = build_initial_solution(instance, rng, args.init, start_time, args.time_limit)
    except RuntimeError:
        state = build_initial_solution(instance, rng, "random-repair", start_time, args.time_limit)
    elapsed = time.time() - start_time
    remaining_time = max(0.0, args.time_limit - elapsed)
    log_path = Path(args.log) if args.log else None
    with ProgressLogger(log_path) as logger:
        best_assignments, best_breakdown = run_metaheuristic(state, args.meta, rng, logger, remaining_time)
    final_state = rebuild_state(instance, best_assignments)
    if not final_state.check_hard_constraints():
        raise RuntimeError("Final timetable violates hard constraints")
    out_path = Path(args.out)
    write_solution(instance, best_assignments, out_path)
    breakdown = final_state.score_breakdown()
    print("--- Tổng kết mềm ---")
    print(f"Room capacity: {breakdown.room_capacity}")
    print(f"Min working days: {breakdown.min_working_days}")
    print(f"Curriculum compactness: {breakdown.curriculum_compactness}")
    print(f"Room stability: {breakdown.room_stability}")
    print(f"Tổng chi phí: {breakdown.total}")


if __name__ == "__main__":
    main()
