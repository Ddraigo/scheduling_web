"""
Core CB-CTT Solver Algorithm (refactored from ctt_solver_3.py)
Chỉ chứa logic toán học thuần, không phụ thuộc Django
"""

import random
import math
import time
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class Room:
    """Phòng học"""
    id: str
    capacity: int
    index: int
    equipment: str = ""  # Thiết bị: "PC", "TV, Máy chiếu", etc.
    room_type: str = "LT"  # Loại phòng: "LT" (Lý thuyết) hoặc "TH" (Thực hành)


@dataclass(frozen=True)
class Course:
    """Khóa học"""
    id: str
    teacher: str
    lectures: int
    min_working_days: int  
    students: int
    index: int
    teacher_index: int
    so_ca_tuan: int = 1  # Số ca/tuần (để kiểm tra clustering)
    equipment: str = ""  # Thiết bị yêu cầu: "PC", "TV, Máy chiếu", etc.
    course_type: str = "LT"  # Loại khóa học: "LT" (Lý thuyết) hoặc "TH" (Thực hành)


@dataclass(frozen=True)
class Curriculum:
    """Nhóm khóa học không được trùng lịch"""
    name: str
    courses: List[int]
    index: int


@dataclass(frozen=True)
class Lecture:
    """Một buổi học"""
    id: int
    course: int
    index: int


@dataclass
class CBCTTInstance:
    """Instance dữ liệu CB-CTT"""
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
    course_so_ca_tuan: List[int] = field(default_factory=list)  # Số ca/tuần cho mỗi course
    teacher_preferred_periods: Dict[str, Set[int]] = field(default_factory=dict)  # teacher_id -> set(preferred periods từ NguyenVong)
    total_periods: int = field(init=False)

    def __post_init__(self) -> None:
        self.total_periods = self.days * self.periods_per_day

    def period_to_slot(self, period: int) -> Tuple[int, int]:
        """Convert flat period index to (day, slot)"""
        day = period // self.periods_per_day
        slot = period % self.periods_per_day
        return day, slot


@dataclass
class ScoreBreakdown:
    """Chi tiết chi phí ràng buộc mềm"""
    room_capacity: int = 0
    min_working_days: int = 0
    curriculum_compactness: int = 0
    room_stability: int = 0
    lecture_clustering: int = 0  # Phạt khi các tiết của cùng lớp trong tuần không liền nhau cùng ngày/phòng
    preference_violations: int = 0  # Phạt khi xếp ngoài NguyenVong (nguyện vọng GV)

    @property
    def total(self) -> int:
        return (self.room_capacity + self.min_working_days + self.curriculum_compactness + 
                self.room_stability + self.lecture_clustering + self.preference_violations)


class TimetableState:
    """Trạng thái lịch có thể thay đổi với scoring gia tăng"""

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
            [set() for _ in range(instance.days)] for _ in range(curriculum_count)
        ]
        self.curriculum_day_penalty: List[List[int]] = [
            [0] * instance.days for _ in range(curriculum_count)
        ]
        lecture_count = len(instance.lectures)
        self.lecture_room_penalty: List[int] = [0] * lecture_count
        # Tracking cho lecture clustering (tiết của cùng lớp trong tuần)
        self.course_day_room_slots: List[Dict[Tuple[int, int], Set[int]]] = [
            {} for _ in range(course_count)
        ]  # course_idx -> {(day, room): set of slots}
        self.course_clustering_penalty: List[int] = [0] * course_count
        self.soft_room_capacity = 0
        self.soft_min_working_days = 0
        self.soft_curriculum_compactness = 0
        self.soft_room_stability = 0
        self.soft_lecture_clustering = 0
        self.soft_preference_violations = 0  # Tracking nguyện vọng GV

    def clone_assignments(self) -> Dict[int, Tuple[int, int]]:
        return dict(self.assignments)

    def _compute_preference_violation(self, course_idx: int, period: int) -> int:
        """Tính penalty nếu xếp lớp ngoài NguyenVong preferences"""
        teacher = self.instance.course_teachers[course_idx]
        preferred_periods = self.instance.teacher_preferred_periods.get(teacher, set())
        
        # Nếu GV có nguyện vọng nhưng period này không nằm trong đó → penalty = 1
        if preferred_periods and period not in preferred_periods:
            return 1
        return 0

    def _compute_course_mwd_penalty(self, course_idx: int) -> int:
        """
        🟢 Tính penalty cho ràng buộc min_working_days.
        
        min_working_days = Số ngày tối thiểu các LỚP CỦA CÙNG MỘT MÔN phải phân bổ trong tuần.
        Ví dụ: Toán có 3 lớp (Toán_01, Toán_02, Toán_03), min_working_days=2
               → 3 lớp này phải xếp vào ít nhất 2 ngày khác nhau trong tuần
        
        Penalty = số ngày còn thiếu để đạt mục tiêu min_working_days.
        Nếu course_active_days >= min_working_days → penalty = 0 (OK)
        Nếu course_active_days < min_working_days → penalty = min_working_days - course_active_days
        """
        course = self.instance.courses[course_idx]
        missing = max(0, course.min_working_days - self.course_active_days[course_idx])
        return missing * 3  # Giảm penalty từ 5 xuống 3 để không quá khắt khe

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

    def _compute_course_clustering_penalty(self, course_idx: int) -> int:
        """
        Tính penalty khi các tiết của một course không được clustering tốt trong tuần.
        Nếu course có so_ca_tuan > 1, các tiết trong cùng (day, room) nên liền nhau.
        Penalty = số lần các tiết bị ngắt quãng trong cùng (day, room)
        """
        so_ca_tuan = self.instance.course_so_ca_tuan[course_idx] if course_idx < len(self.instance.course_so_ca_tuan) else 1
        if so_ca_tuan <= 1:
            return 0
        
        penalty = 0
        day_room_slots = self.course_day_room_slots[course_idx]
        
        for (day, room), slots in day_room_slots.items():
            if len(slots) > 1:
                # Kiểm tra xem các slots có liền nhau không
                slots_sorted = sorted(slots)
                for i in range(len(slots_sorted) - 1):
                    if slots_sorted[i+1] - slots_sorted[i] > 1:
                        # Có lỗ hổng giữa các slots
                        penalty += 1
        return penalty

    def _can_place(self, lecture_id: int, period: int, room_idx: int) -> bool:
        lecture = self.instance.lectures[lecture_id]
        course_idx = lecture.course
        
        # Check 1: Period availability
        if period in self.instance.unavailability[course_idx]:
            return False
        
        # Check 2: Room not already booked at this period
        if room_idx in self.period_rooms[period]:
            return False
        
        # Check 3: Teacher conflict
        teacher = self.instance.course_teachers[course_idx]
        owner = self.period_teacher_owner[period].get(teacher)
        if owner is not None and owner != lecture_id:
            return False
        
        # Check 4: Curriculum conflict
        for curriculum_idx in self.instance.course_curriculums[course_idx]:
            owner = self.period_curriculum_owner[period].get(curriculum_idx)
            if owner is not None and owner != lecture_id:
                return False
        
        # Check 5: HC-03 - Capacity must be adequate (hard constraint)
        course = self.instance.courses[course_idx]
        room = self.instance.rooms[room_idx]
        if room.capacity < course.students:
            return False
        
        # Check 6: HC-05/HC-06 - Room type must match (hard constraint)
        # CRITICAL: Type mismatch is a hard constraint violation
        if course.course_type != room.room_type:
            return False
        
        # NOTE: HC-04 (Equipment) is NOT a hard constraint in _can_place()
        # Reason: Database doesn't have enough rooms with required equipment
        # Equipment is handled as soft constraint via penalty calculation in _insert_assignment()
        
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
        """Swap assignments of two lectures"""
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
        """Apply Kempe chain move - reassign multiple lectures to new periods"""
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
        course = self.instance.courses[course_idx]
        preference = self.instance.course_room_preference[course_idx]
        
        # Try 1: Search in preference list (sorted by equipment, type, capacity)
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
        
        # Try 2: If not found in preference, search ALL rooms of matching type
        # This is a fallback for cases where preference list doesn't have feasible room
        # (e.g., equipment requirements can't be satisfied)
        matching_rooms = [
            i for i in range(len(self.instance.rooms))
            if self.instance.rooms[i].room_type == course.course_type
        ]
        
        # Sort matching rooms by capacity (adequate first)
        matching_adequate = [r for r in matching_rooms if self.instance.rooms[r].capacity >= students]
        matching_fallback = [r for r in matching_rooms if self.instance.rooms[r].capacity < students]
        
        for room_idx in matching_adequate + matching_fallback:
            if self._can_place(lecture_id, period, room_idx):
                return room_idx
        
        return None

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
        # Update clustering penalty
        key = (day, room_idx)
        day_room_slots = self.course_day_room_slots[course_idx]
        if key in day_room_slots:
            day_room_slots[key].discard(slot)
            if len(day_room_slots[key]) == 0:
                del day_room_slots[key]
        old_clustering_penalty = self.course_clustering_penalty[course_idx]
        new_clustering_penalty = self._compute_course_clustering_penalty(course_idx)
        self.course_clustering_penalty[course_idx] = new_clustering_penalty
        self.soft_lecture_clustering += new_clustering_penalty - old_clustering_penalty
        delta += new_clustering_penalty - old_clustering_penalty
        # Update preference violations
        old_pref_violation = self._compute_preference_violation(course_idx, period)
        self.soft_preference_violations -= old_pref_violation
        delta -= old_pref_violation
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
        # Update clustering penalty
        key = (day, room_idx)
        day_room_slots = self.course_day_room_slots[course_idx]
        if key not in day_room_slots:
            day_room_slots[key] = set()
        day_room_slots[key].add(slot)
        old_clustering_penalty = self.course_clustering_penalty[course_idx]
        new_clustering_penalty = self._compute_course_clustering_penalty(course_idx)
        self.course_clustering_penalty[course_idx] = new_clustering_penalty
        self.soft_lecture_clustering += new_clustering_penalty - old_clustering_penalty
        delta += new_clustering_penalty - old_clustering_penalty
        
        # Tính preference violations (nếu xếp ngoài NguyenVong)
        pref_penalty = self._compute_preference_violation(course_idx, period)
        self.soft_preference_violations += pref_penalty
        delta += pref_penalty * 10  # Weight cao để ưu tiên NguyenVong
        
        return delta

    @property
    def current_cost(self) -> int:
        return (self.soft_room_capacity + self.soft_min_working_days + self.soft_curriculum_compactness + 
                self.soft_room_stability + self.soft_lecture_clustering + self.soft_preference_violations)

    def score_breakdown(self) -> ScoreBreakdown:
        return ScoreBreakdown(
            room_capacity=self.soft_room_capacity,
            min_working_days=self.soft_min_working_days,
            curriculum_compactness=self.soft_curriculum_compactness,
            room_stability=self.soft_room_stability,
            lecture_clustering=self.soft_lecture_clustering,
            preference_violations=self.soft_preference_violations,
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
    """Sắp xếp thứ tự ưu tiên xếp lịch - ưu tiên lớp khó trước
    
    Độ khó được đánh giá dựa trên:
    1. Tỷ lệ lectures/periods của giáo viên - GV dạy nhiều lớp nhưng ít periods
    2. Số periods khả dụng (feasible_periods) - càng ít càng khó
    3. Số curriculum conflicts - càng nhiều càng khó (nhiều lớp cùng GV/khoa)
    4. min_working_days - càng cao càng khó phân bổ
    """
    order = list(range(len(instance.lectures)))
    
    # Đếm số lớp mỗi giáo viên phải dạy
    teacher_lecture_count: Dict[str, int] = {}
    for lecture in instance.lectures:
        course = instance.courses[lecture.course]
        teacher_id = course.teacher
        teacher_lecture_count[teacher_id] = teacher_lecture_count.get(teacher_id, 0) + 1
    
    # Tính số curriculum conflicts cho mỗi course
    curriculum_conflicts: Dict[int, int] = {}
    for course_idx in range(len(instance.courses)):
        conflict_count = 0
        for curriculum in instance.curriculums:
            if course_idx in curriculum.courses:
                # Đếm số course khác trong cùng curriculum
                conflict_count += len(curriculum.courses) - 1
        curriculum_conflicts[course_idx] = conflict_count
    
    # Sắp xếp: khó trước
    order.sort(
        key=lambda lid: (
            # 1. Tỷ lệ lectures/periods của GV (càng cao càng khó - nhiều lớp ít slots)
            -teacher_lecture_count[instance.courses[instance.lectures[lid].course].teacher] 
                / max(1, len(instance.feasible_periods[instance.lectures[lid].course])),
            # 2. Ít periods trước (GV bận)
            len(instance.feasible_periods[instance.lectures[lid].course]),
            # 3. Nhiều conflicts trước
            -curriculum_conflicts[instance.lectures[lid].course],
            # 4. min_working_days cao trước
            -instance.courses[instance.lectures[lid].course].min_working_days,
            # 5. Lớp đông trước
            -instance.courses[instance.lectures[lid].course].students,
            lid,
        ),
    )
    return order


def build_initial_solution(instance: CBCTTInstance, rng: random.Random, time_limit: float = 10.0) -> TimetableState:
    """Xây dựng lời giải khởi tạo hợp lệ"""
    import logging
    logger = logging.getLogger(__name__)
    
    state = TimetableState(instance)
    order = _candidate_order(instance)
    
    # Đếm số lớp mỗi GV dạy để debug
    teacher_lecture_count: Dict[str, int] = {}
    for lecture in instance.lectures:
        course = instance.courses[lecture.course]
        teacher_id = course.teacher
        teacher_lecture_count[teacher_id] = teacher_lecture_count.get(teacher_id, 0) + 1
    
    # Debug: log 10 lớp đầu tiên (khó nhất)
    logger.info("🎯 Top 10 khó nhất (xếp trước):")
    for i in range(min(10, len(order))):
        lid = order[i]
        course_idx = instance.lectures[lid].course
        course = instance.courses[course_idx]
        periods = len(instance.feasible_periods[course_idx])
        teacher_classes = teacher_lecture_count[course.teacher]
        ratio = teacher_classes / max(1, periods)
        logger.info(f"  {i+1}. {course.id} GV:{course.teacher} - {teacher_classes} lớp/{periods} periods (ratio={ratio:.2f}), min_days={course.min_working_days}")
    
    sys.setrecursionlimit(max(10000, len(order) * 20))
    
    start_time = time.time()
    deadline = start_time + time_limit
    max_depth = [0]

    def backtrack(index: int) -> bool:
        if time.time() > deadline:
            return False
        if index >= len(order):
            return True
        
        max_depth[0] = max(max_depth[0], index)
        
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
            if index < 10:
                logger.debug(f"Lecture {lecture_id} (course {course_idx}): No feasible placements found")
            return False
        
        rng.shuffle(candidates)
        candidates.sort(key=lambda entry: entry[0])
        limit = min(len(candidates), 50)  # Tăng từ 30 lên 50 để có nhiều lựa chọn hơn
        
        for delta, period, room_idx in candidates[:limit]:
            result = state.move_lecture(lecture_id, period, room_idx, commit=True)
            if result is None:
                continue
            if backtrack(index + 1):
                return True
            state.unassign(lecture_id)
        return False

    attempts = 0
    max_attempts = 10  # Tăng từ 5 lên 10 để có nhiều cơ hội hơn
    while time.time() <= deadline and attempts < max_attempts:
        attempts += 1
        max_depth[0] = 0
        if backtrack(0):
            elapsed = time.time() - start_time
            logger.info(f"✅ Initial solution found in {elapsed:.2f}s, attempt {attempts}")
            return state
        
        elapsed = time.time() - start_time
        logger.warning(f"❌ Attempt {attempts} failed: max depth {max_depth[0]}/{len(order)} lectures, "
                       f"assigned {len(state.assignments)}/{len(order)}, time {elapsed:.2f}s")
        
        rng.shuffle(order)
        state = TimetableState(instance)
    
    final_time = time.time() - start_time
    raise RuntimeError(f"Không thể xây dựng lời giải khởi tạo hợp lệ (depth {max_depth[0]}/{len(order)}, time {final_time:.2f}s)")


# ==================== PROGRESS LOGGER ====================

class ProgressLogger:
    """Simple progress logger for metaheuristic"""
    
    def __init__(self, log_path=None):
        self.log_path = log_path
        self.handle = None
        if log_path:
            self.handle = open(log_path, 'w')
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        if self.handle:
            self.handle.close()
    
    def log(self, elapsed_time: float, best_cost: int, current_cost: int, hard_ok: bool, accept_rate: float, operator: str):
        """Log progress"""
        msg = f"{elapsed_time:.2f},{best_cost},{current_cost},{hard_ok},{accept_rate:.2f},{operator}"
        if self.handle:
            self.handle.write(msg + '\n')
            self.handle.flush()
    
    def debug(self, msg: str):
        pass
    
    def info(self, msg: str):
        pass


def rebuild_state(instance: CBCTTInstance, assignments: Dict[int, Tuple[int, int]]) -> TimetableState:
    """Tạo state từ assignments"""
    state = TimetableState(instance)
    for lecture_id, (period, room) in assignments.items():
        state.move_lecture(lecture_id, period, room, commit=True)
    return state


# ==================== MOVE CLASSES ====================

class Move:
    """Abstract move with evaluation/apply contract"""
    
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


# ==================== NEIGHBORHOOD CLASSES ====================

class Neighborhood:
    """Base neighborhood operator"""
    
    name: str
    
    def generate_candidate(self, state: TimetableState, rng: random.Random) -> Optional[Move]:
        raise NotImplementedError


class MoveLectureNeighborhood(Neighborhood):
    name = "MoveLecture"
    
    def generate_candidate(self, state: TimetableState, rng: random.Random) -> Optional[Move]:
        instance = state.instance
        lectures = instance.lectures
        
        # Ưu tiên lớp có penalty cao
        focus_courses = [idx for idx, penalty in enumerate(state.course_mwd_penalty) if penalty > 0]
        focus_courses.extend(idx for idx, penalty in enumerate(state.course_room_penalty) 
                           if penalty > 0 and idx not in focus_courses)
        
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
        # Tìm những lớp dùng nhiều phòng
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
        # Ưu tiên các lớp bị quá tải
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
        
        # Cố gắng tìm phòng lớn hơn trong cùng period
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
        
        # Nếu không, thử đổi period
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


# ==================== METAHEURISTIC SEARCH ====================

class NeighborhoodManager:
    """Adaptive operator selector với dynamic weights"""
    
    def __init__(self, neighborhoods: List[Neighborhood]) -> None:
        self.neighborhoods = list(neighborhoods)
        self.weights = [1.0 for _ in neighborhoods]
        self.usage = [0 for _ in neighborhoods]
    
    def select(self, rng: random.Random) -> Tuple[int, Neighborhood]:
        """Chọn neighborhood dựa trên weights"""
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
        """Cập nhật weights dựa trên kết quả"""
        if improvement:
            self.weights[index] = min(self.weights[index] * 1.1 + 0.05, 6.0)
        else:
            self.weights[index] = max(self.weights[index] * 0.95, 0.1)


class SimulatedAnnealing:
    """Simulated Annealing metaheuristic"""
    
    def __init__(self, state: TimetableState, neighborhoods: List[Neighborhood], 
                 rng: random.Random, logger: ProgressLogger) -> None:
        self.state = state
        self.manager = NeighborhoodManager(neighborhoods)
        self.rng = rng
        self.logger = logger
    
    def run(self, best_assignments: Dict[int, Tuple[int, int]], best_breakdown: ScoreBreakdown, 
            start_time: float, time_limit: float) -> Tuple[Dict[int, Tuple[int, int]], ScoreBreakdown]:
        state = self.state
        rng = self.rng
        
        # Khởi tạo nhiệt độ
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
            
            # Quyết định chấp nhận
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
            
            # Giảm nhiệt độ
            temperature = max(min_temp, temperature * alpha)
            
            # Reset nhiệt độ nếu stagnation
            if iteration - last_improvement_iter > stagnation_limit:
                temperature = max(start_temp, temperature * 1.5)
                last_improvement_iter = iteration
            
            # Log
            now = time.time() - start_time
            if now - last_log >= 2.0:
                accept_rate = accepted / attempted if attempted else 0.0
                hard_ok = state.check_hard_constraints()
                self.logger.log(now, best_cost, state.current_cost, hard_ok, accept_rate, operator.name)
                last_log = now
        
        return best_assignments, best_breakdown


class TabuSearch:
    """Tabu Search metaheuristic with adaptive tenure"""
    
    def __init__(self, state: TimetableState, neighborhoods: List[Neighborhood], 
                 rng: random.Random, logger: ProgressLogger) -> None:
        self.state = state
        self.manager = NeighborhoodManager(neighborhoods)
        self.rng = rng
        self.logger = logger
    
    def run(self, best_assignments: Dict[int, Tuple[int, int]], best_breakdown: ScoreBreakdown, 
            start_time: float, time_limit: float) -> Tuple[Dict[int, Tuple[int, int]], ScoreBreakdown]:
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
            
            # Sinh candidates
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
            
            # Sắp xếp: tabu cuối, cost tốt trước
            candidates.sort(key=lambda item: (item[1], item[0]))
            
            # Chọn move tốt nhất (aspiration criteria)
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
            
            # Điều chỉnh tenure
            if no_improve > 250:
                base_tenure = min(25, base_tenure + 1)
                no_improve = 0
            elif improvement:
                base_tenure = max(4, base_tenure - 1)
            
            # Log
            now = time.time() - start_time
            if now - last_log >= 2.0:
                accept_rate = accepted / attempted if attempted else 0.0
                hard_ok = state.check_hard_constraints()
                self.logger.log(now, best_cost, state.current_cost, hard_ok, accept_rate, move.name)
                last_log = now
        
        return best_assignments, best_breakdown


def run_metaheuristic(state: TimetableState, meta: str, rng: random.Random, 
                     logger: ProgressLogger, remaining_time: float) -> Tuple[Dict[int, Tuple[int, int]], ScoreBreakdown]:
    """Chạy metaheuristic optimization (Tabu Search hoặc Simulated Annealing)"""
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
