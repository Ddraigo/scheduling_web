# University Course Timetabling - Standalone Prototype (Steps 1–6)
# -----------------------------------------------------------------
# This script demonstrates:
# 1) Input modeling (teachers/rooms/courses, availability, wishes, room features)
# 2) Runtime data structures (reservation tables, bitsets, undo log)
# 3) Feasible picking & initialization with fairness-aware random choices
# 4) Fitness (fairness, wish satisfaction, compactness) with delta-friendly updates
# 5) Feasible mutation (local search) using undo/rollback
# 6) Performance-minded structures (ints for bitsets, sets for O(1) membership)
#
# The dataset is synthetic but crafted to be feasible, including room features and multi-slot classes.

from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional
import math
import random
import json


# ------------------------------
# Global Config
# ------------------------------
class GlobalConfig:
    # Randomness
    SEED: int = None

    # Calendar
    DAYS: int = 5            # Mon..Fri
    SLOTS: int = 4           # 4 timeslots per day (e.g., 8:00, 10:00, 13:00, 15:00)

    # Teacher weekly/day slot limits (set to None to disable per-day)
    # Relaxed limits to improve feasibility with multi-meeting units
    MAX_TEACHER_SLOTS_PER_WEEK: Optional[int] = 16
    MAX_TEACHER_SLOTS_PER_DAY: Optional[int] = 4

    # Wish handling & moves
    WISH_SLOT_MULTIPLIER: float = 2.5   # weighting for wish slots in greedy choices
    WISH_MOVE_MULTIPLIER: float = 2.2   # weighting when mutating moves

    # Fitness weights
    FITNESS_WEIGHTS = (1.0, 1.2, 0.5, 0.8)  # (fairness, wish_reward, compactness, unmet_wish_penalty)
    W_SCARCITY: float = 0.6
    W_TIME: float = 0.2

    # Local search & GA
    LS_STEPS_INIT: int = 100
    LS_STEPS_EVAL: int = 80
    LS_STEPS_FINAL: int = 200
    MUTATION_RATE: float = 0.05
    GA_POP: int = 40
    GA_OFFSPRING: int = 40
    GA_GENERATIONS: int = 40
    GA_EARLY_STOP: int = 10
    MULTI_START_N: int = 12

    # Output
    OUTPUT_TIMETABLE_FILE: str = 'timetable_by_dept.xlsx'
    OUTPUT_DATASET_FILE: str = 'dataset.xlsx'
    OUTPUT_TIMETABLE_JSON: str = 'timetable_by_dept.json'
    OUTPUT_DATASET_JSON: str = 'dataset.json'

    # Dataset sizes (demo generator)
    NUM_TEACHERS: int = 60
    NUM_ROOMS: int = 146
    NUM_BASE_COURSES: int = 48

# Module-level aliases for minimal code changes
DAYS = GlobalConfig.DAYS
SLOTS = GlobalConfig.SLOTS
T = DAYS * SLOTS

MAX_TEACHER_SLOTS_PER_WEEK = GlobalConfig.MAX_TEACHER_SLOTS_PER_WEEK
MAX_TEACHER_SLOTS_PER_DAY = GlobalConfig.MAX_TEACHER_SLOTS_PER_DAY

# Honor global seed for reproducibility
random.seed(GlobalConfig.SEED)

# ------------------------------
# Helpers: indexing and bitset
# ------------------------------
def idx(day: int, slot: int) -> int:
    return day * SLOTS + slot

def bitset_from_pairs(pairs: Set[Tuple[int, int]]) -> int:
    """Build a T-bit int where bit(t)=1 if (day,slot) allowed."""
    b = 0
    for d, s in pairs:
        b |= (1 << idx(d, s))
    return b

def bitset_test(bitset: int, day: int, slot: int) -> bool:
    return (bitset >> idx(day, slot)) & 1 == 1

def window_available(bitset: int, day: int, slot: int, m: int) -> bool:
    """Check if m consecutive slots starting at (day,slot) are available in bitset."""
    if slot + m - 1 >= SLOTS:
        return False
    for k in range(m):
        if not bitset_test(bitset, day, slot + k):
            return False
    return True

# ------------------------------
# Data Classes
# ------------------------------
@dataclass
class Teacher:
    id: int
    name: str
    dept: str
    availability_bits: int             # T-bit int
    wishes: Set[Tuple[int, int]] = field(default_factory=set)  # preferred (day, slot)

@dataclass
class Room:
    id: int
    name: str
    capacity: int
    features: Set[str]                 # e.g., {"lab", "projector"}

@dataclass
class Course:
    id: int
    name: str
    dept: str
    size: int
    duration: int                      # slots per class meeting (1 or 2 for demo)
    required_features: Set[str]        # e.g., {"lab"} if lab required
    candidate_teachers: Set[int]       # teacher IDs who can teach

# NOTE: We will expand base course specs into per-meeting units (lectures/labs, groups/sections)
# to support multi-meeting per week and practicals.

# ------------------------------
# Synthetic Demo Dataset
# ------------------------------


# --- Sử dụng dữ liệu sinh ngẫu nhiên từ input_genearator.py ---
import sys
import os
import string

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Số lượng phần tử có thể chỉnh tùy ý
def random_specs(num_teachers, num_rooms, num_courses):

    # Tạo teacher_specs
    teacher_specs = []
    for i in range(num_teachers):
        name = f"T_{random.choice(string.ascii_uppercase)}{i+1}"
        dept = random.choice(["A", "B", "C"])
        dmax = GlobalConfig.DAYS
        smax = GlobalConfig.SLOTS
        # Clamp sensible ranges relative to DAYS/SLOTS
        days_count = random.randint(min(3, dmax), dmax)
        slots_count = random.randint(min(2, smax), smax)
        available_days = sorted(random.sample(range(dmax), days_count))
        available_slots = sorted(random.sample(range(smax), slots_count))
        wishes = set((random.choice(available_days), random.choice(available_slots)) for _ in range(random.randint(1, 2)))
        teacher_specs.append((i, name, dept, available_days, available_slots, wishes))

    # Tạo room_specs
    room_specs = []
    used_numbers = set()
    feature_pool = ["projector", "lab", "audio", "ac"]
    for i in range(num_rooms):
        while True:
            num = random.randint(100, 499)
            if num not in used_numbers:
                used_numbers.add(num)
                break
        name = f"R-{num}"
        capacity = random.randrange(20, 71, 10)
        features = set(random.sample(feature_pool, random.randint(1, min(2, len(feature_pool)))))
        room_specs.append((i, name, capacity, features))

    # Tạo course_specs đảm bảo khả thi
    course_specs = []
    course_prefixes = ["MTH", "PHY", "CSE", "AI", "ML", "DB", "HIS", "IOT", "SE", "CHE"]
    for i in range(num_courses):
        # Sinh ngẫu nhiên các thuộc tính cơ bản
        prefix = random.choice(course_prefixes)
        code = random.randint(100, 499)
        name = f"{prefix}-{code}"
        dept = random.choice(["A", "B", "C"])
        size = random.randint(20, 70)
        duration = random.choice([1, 2])
        feature_choices = [set(), {"projector"}, {"lab"}, {"audio"}, {"lab", "projector"}]

        # Đảm bảo có ít nhất 1 phòng phù hợp, giới hạn số lần thử
        max_room_attempts = 100
        for _ in range(max_room_attempts):
            required_features = random.choice(feature_choices)
            suitable_rooms = [r for r in room_specs if r[2] >= size and required_features.issubset(r[3])]
            if suitable_rooms:
                break
        else:
            # Nếu không tìm được phòng phù hợp, bỏ qua course này
            continue

        # Đảm bảo có ít nhất 1 giáo viên phù hợp, giới hạn số lần thử
        max_teacher_attempts = 100
        for _ in range(max_teacher_attempts):
            # Broaden teacher pool to increase feasibility
            n_teachers = random.randint(3, min(6, num_teachers))
            candidate_teachers = set(random.sample(range(num_teachers), n_teachers))
            if candidate_teachers:
                break
        else:
            continue

        course_specs.append((i, name, dept, size, duration, required_features, candidate_teachers))

    return teacher_specs, room_specs, course_specs

# Đảm bảo luôn có course, random lại tối đa 10 lần nếu chưa có course nào
max_attempts = 50
for _ in range(max_attempts):
    teacher_specs, room_specs, course_specs = random_specs(
        num_teachers=GlobalConfig.NUM_TEACHERS,
        num_rooms=GlobalConfig.NUM_ROOMS,
        num_courses=GlobalConfig.NUM_BASE_COURSES
    )
    if course_specs:
        break
else:
    raise ValueError("Không sinh được course nào! Hãy tăng số lượng phòng, giáo viên hoặc nới lỏng điều kiện random_specs.")

def mk_avail(days: List[int], slots: List[int]) -> int:
    return bitset_from_pairs({(d, s) for d in days for s in slots})

# Khởi tạo teachers từ teacher_specs
teachers: List[Teacher] = []
for tid, name, dept, ds, ss, wishes in teacher_specs:
    teachers.append(Teacher(
        id=tid,
        name=name,
        dept=dept,
        availability_bits=mk_avail(ds, ss),
        wishes=set(wishes)
    ))

# Khởi tạo rooms từ room_specs
rooms: List[Room] = []
for rid, name, capacity, features in room_specs:
    rooms.append(Room(rid, name, capacity, features))

# Khởi tạo courses từ course_specs
courses: List[Course] = []
def expand_courses_to_units(course_specs):
    """Expand base course specs into per-meeting units (Course objects) including groups/sections and lecture/lab.
    Assumptions:
    - Each base course defines a weekly lecture duration (duration).
    - Randomly assign: lectures_per_week in {1,2}; has_lab ~50%; lab_sections_total in [0..4]; labs_per_week_per_section=1; lab_duration=1.
    - If lab_sections_total > 2, split into multiple groups so that each group has at most 2 lab sections.
    - Group has lecture section (section 0) and lab sections (1..k). Lecture applies per group (not shared across groups).
    - For lab units, required_features will include 'lab'.
    - Size for labs is split per lab section within the same group (ceil division). Lectures keep the base size.
    """
    units: List[Course] = []
    new_id = 0
    for cid, name, dept, size, duration, required_features, candidate_teachers in course_specs:
        # Meeting plan
        lectures_per_week = random.choice([1, 2])
        has_lab = random.choice([True, False])
        # Limit total lab sections per course to avoid excessive grouping at demo scale
        lab_sections_total = random.randint(0, 2) if has_lab else 0
        labs_per_week_per_section = 1
        lab_duration = 1

        # Compute groups
        if lab_sections_total <= 2:
            group_count = 1
        else:
            group_count = math.ceil(lab_sections_total / 2)

        remaining_sections = lab_sections_total

        for g in range(group_count):
            # Lecture units for this group
            for lec_i in range(lectures_per_week):
                unit_name = f"{name}[G{g}-LEC{lec_i+1}]"
                units.append(Course(
                    id=new_id,
                    name=unit_name,
                    dept=dept,
                    size=size,
                    duration=duration,
                    required_features=set(required_features),
                    candidate_teachers=set(candidate_teachers)
                ))
                new_id += 1

            # Lab units for this group (up to 2 sections per group)
            labs_here = min(2, remaining_sections)
            remaining_sections -= labs_here
            if labs_here > 0:
                # Split size across lab sections for capacity realism
                lab_section_size = math.ceil(size / labs_here)
                lab_req = set(required_features)
                lab_req.add('lab')
                for sec in range(1, labs_here+1):
                    for lab_i in range(labs_per_week_per_section):
                        unit_name = f"{name}[G{g}-LAB{sec}-{lab_i+1}]"
                        units.append(Course(
                            id=new_id,
                            name=unit_name,
                            dept=dept,
                            size=lab_section_size,
                            duration=lab_duration,
                            required_features=set(lab_req),
                            candidate_teachers=set(candidate_teachers)
                        ))
                        new_id += 1
    return units

# Expand to per-meeting units
courses: List[Course] = expand_courses_to_units(course_specs)

# ------------------------------
# Precomputation
# ------------------------------

# Candidate rooms per course (capacity and features)
candidate_rooms_for_course: Dict[int, Set[int]] = {}
for c in courses:
    room_ids = set()
    for r in rooms:
        if r.capacity >= c.size and c.required_features.issubset(r.features):
            room_ids.add(r.id)
    candidate_rooms_for_course[c.id] = room_ids

# Feasible (day,slot) starts for each (course, teacher) considering duration and availability
feasible_slots: Dict[int, Dict[int, List[Tuple[int,int]]]] = {c.id: {} for c in courses}
for c in courses:
    for tid in c.candidate_teachers:
        f = []
        t_bits = teachers[tid].availability_bits
        for d in range(DAYS):
            for s in range(SLOTS):
                if window_available(t_bits, d, s, c.duration):
                    f.append((d, s))
        feasible_slots[c.id][tid] = f

# ------------------------------
# OptionList (static feasible choices) for Hybrid-Wish decoding
# ------------------------------
# For each unit (course id): list of options (day, slot, teacher id, room id)
OptionList: Dict[int, List[Tuple[int, int, int, int]]] = {}
# For each unit: boundary index so that [0..WishEnd[u]) are WishOptions
WishEnd: Dict[int, int] = {}

def build_option_lists() -> None:
    """
    For each unit (course):
      1) Enumerate all (d,s,tid,rid) satisfying static hard constraints (teacher window, room capacity/features)
      2) Mark wish if (d,s) in teacher.wishes
      3) Partition into WishOptions vs NonWishOptions
      4) Sort within each partition by:
         - Room: lab-first for lab units; avoid lab for non-lab; tight-fit (capacity - size)
         - Time: (d,s) ascending (optional morning-first policy)
         - Teacher tie-breaker: by id for determinism (do not use dynamic load here)
      5) Concatenate WishOptions + NonWishOptions → OptionList[cid], WishEnd[cid] = len(WishOptions)
    """
    OptionList.clear()
    WishEnd.clear()
    room_map = {r.id: r for r in rooms}
    for c in courses:
        wish_opts: List[Tuple[int,int,int,int]] = []
        nonwish_opts: List[Tuple[int,int,int,int]] = []
        for tid in c.candidate_teachers:
            for (d, s) in feasible_slots[c.id].get(tid, []):
                for rid in candidate_rooms_for_course.get(c.id, []):
                    r = room_map[rid]
                    is_wish = (d, s) in teachers[tid].wishes
                    (wish_opts if is_wish else nonwish_opts).append((d, s, tid, rid))
        def opt_key(opt: Tuple[int,int,int,int]):
            d, s, tid, rid = opt
            r = room_map[rid]
            need_lab = ('lab' in c.required_features)
            room_lab = ('lab' in r.features)
            lab_pen = 0 if (need_lab == room_lab) else (0 if need_lab else (1 if room_lab else 0))
            slack = r.capacity - c.size
            return (lab_pen, slack, d, s, tid)
        wish_opts.sort(key=opt_key)
        nonwish_opts.sort(key=opt_key)
        OptionList[c.id] = wish_opts + nonwish_opts
        WishEnd[c.id] = len(wish_opts)

# ------------------------------
# Runtime State
# ------------------------------

# Free sets per (day,slot)
free_teachers: List[List[Set[int]]] = [[set() for _ in range(SLOTS)] for _ in range(DAYS)]
free_rooms:    List[List[Set[int]]] = [[set() for _ in range(SLOTS)] for _ in range(DAYS)]

# Initialize free sets from availability; rooms assume free by default per slot
for d in range(DAYS):
    for s in range(SLOTS):
        for t in teachers:
            if bitset_test(t.availability_bits, d, s):
                free_teachers[d][s].add(t.id)
        for r in rooms:
            free_rooms[d][s].add(r.id)

# Loads & masks
teacher_load: Dict[int, int] = {t.id: 0 for t in teachers}  # number of units assigned
teacher_day_mask: Dict[int, List[int]] = {t.id: [0]*DAYS for t in teachers}  # per day, S-bit mask
dept_of_teacher: Dict[int, str] = {t.id: t.dept for t in teachers}

# Slot counters for max-teaching constraints
teacher_week_slots: Dict[int, int] = {t.id: 0 for t in teachers}
teacher_day_slots: Dict[int, List[int]] = {t.id: [0]*DAYS for t in teachers}

# Assignments (genome-like arrays)
assign_teacher: Dict[int, Optional[int]] = {c.id: None for c in courses}
assign_day:     Dict[int, Optional[int]] = {c.id: None for c in courses}
assign_slot:    Dict[int, Optional[int]] = {c.id: None for c in courses}
assign_room:    Dict[int, Optional[int]] = {c.id: None for c in courses}

# Undo log for rollback
undo_stack: List[Tuple] = []

def log(op, *args):
    undo_stack.append((op, *args))

# ------------------------------
# Reserve/Release helpers (with UNDO)
# ------------------------------
def reserve_teacher(tid: int, d: int, s: int, duration: int) -> bool:
    # Must be free for every slot in [s, s+duration)
    for k in range(duration):
        if tid not in free_teachers[d][s+k]:
            return False
    # Check slot limits
    if MAX_TEACHER_SLOTS_PER_WEEK is not None:
        if teacher_week_slots[tid] + duration > MAX_TEACHER_SLOTS_PER_WEEK:
            return False
    if MAX_TEACHER_SLOTS_PER_DAY is not None:
        if teacher_day_slots[tid][d] + duration > MAX_TEACHER_SLOTS_PER_DAY:
            return False
    # Apply reservations with logging
    for k in range(duration):
        free_teachers[d][s+k].remove(tid)
        log("free_teacher_add", tid, d, s+k)  # to re-add on rollback
    teacher_load[tid] += 1
    log("teacher_load_dec", tid)              # to dec on rollback
    # Update slot counters
    teacher_week_slots[tid] += duration
    log("teacher_week_slots_sub", tid, duration)  # subtract on rollback
    teacher_day_slots[tid][d] += duration
    log("teacher_day_slots_sub", tid, d, duration)
    # Update day mask
    prev = teacher_day_mask[tid][d]
    for k in range(duration):
        prev |= (1 << (s+k))
    teacher_day_mask[tid][d] = prev
    # Log OLD mask value so rollback can restore directly
    old_mask = teacher_day_mask[tid][d]
    log("teacher_day_mask_set", tid, d, old_mask)
    return True

def reserve_room(rid: int, d: int, s: int, duration: int) -> bool:
    for k in range(duration):
        if rid not in free_rooms[d][s+k]:
            return False
    for k in range(duration):
        free_rooms[d][s+k].remove(rid)
        log("free_room_add", rid, d, s+k)
    return True

def release_teacher(tid: int, d: int, s: int, duration: int):
    for k in range(duration):
        free_teachers[d][s+k].add(tid)
    teacher_load[tid] -= 1
    # WARNING: teacher_day_mask exact rollback is handled by undo() via stored old value

def rollback():
    # Revert all operations in reverse order
    while undo_stack:
        op, *args = undo_stack.pop()
        if op == "free_teacher_add":
            tid, d, s = args
            free_teachers[d][s].add(tid)
        elif op == "teacher_load_dec":
            tid, = args
            teacher_load[tid] -= 1
        elif op == "teacher_day_mask_set":
            # For masks, we can't reconstruct the old value from "prev" we stored (that's new value).
            # So we need to recompute from current reservations — to keep it simple here, we recompute day mask.
            tid, d, _new_value = args
            # recompute from assignments for that tid & day
            mask = 0
            for cid in assignments_by_teacher.get(tid, []):
                if assign_day[cid] == d:
                    s = assign_slot[cid]
                    dur = course_by_id[cid].duration
                    for k in range(dur):
                        mask |= (1 << (s+k))
            teacher_day_mask[tid][d] = mask
        elif op == "teacher_week_slots_sub":
            tid, delta = args
            teacher_week_slots[tid] -= delta
        elif op == "teacher_day_slots_sub":
            tid, d, delta = args
            teacher_day_slots[tid][d] -= delta
        elif op == "free_room_add":
            rid, d, s = args
            free_rooms[d][s].add(rid)
        elif op == "assign_clear":
            cid, old = args
            assign_teacher[cid], assign_day[cid], assign_slot[cid], assign_room[cid] = old
        else:
            pass

# ------------------------------
# Indexes for delta updates
# ------------------------------
course_by_id: Dict[int, Course] = {c.id: c for c in courses}
assignments_by_teacher: Dict[int, Set[int]] = {t.id: set() for t in teachers}

def commit_assignment(cid: int, tid: int, d: int, s: int, rid: int) -> bool:
    c = course_by_id[cid]
    # Log previous assignment (for rollback)
    old = (assign_teacher[cid], assign_day[cid], assign_slot[cid], assign_room[cid])
    log("assign_clear", cid, old)
    assign_teacher[cid], assign_day[cid], assign_slot[cid], assign_room[cid] = tid, d, s, rid
    assignments_by_teacher[tid].add(cid)
    return True

def clear_assignment(cid: int):
    t = assign_teacher[cid]
    if t is not None:
        assignments_by_teacher[t].discard(cid)
    assign_teacher[cid] = assign_day[cid] = assign_slot[cid] = assign_room[cid] = None

# ------------------------------
# Fitness functions
# ------------------------------
def fairness_teacher_load_std() -> float:
    # Use total teaching slots per week for fairness instead of unit count
    loads = list(teacher_week_slots.values())
    if not loads:
        return 0.0
    mean = sum(loads) / len(loads)
    var = sum((x-mean)**2 for x in loads) / len(loads)
    return math.sqrt(var)

def wish_satisfaction_score() -> int:
    score = 0
    for cid, tid in assign_teacher.items():
        if tid is None:
            continue
        d, s = assign_day[cid], assign_slot[cid]
        if (d, s) in teachers[tid].wishes:
            score += 1
    return score

def wish_unsatisfied_count() -> int:
    """Count number of (teacher, wish-slot) pairs that have no course assigned exactly at that (day,slot).
    This lets us penalize unmet wishes explicitly instead of only rewarding satisfied wishes.
    """
    unsat = 0
    for t in teachers:
        if not t.wishes:
            continue
        for ws in t.wishes:
            matched = False
            for cid in assignments_by_teacher[t.id]:
                if assign_day[cid] == ws[0] and assign_slot[cid] == ws[1]:
                    matched = True
                    break
            if not matched:
                unsat += 1
    return unsat

def compactness_penalty() -> int:
    # Penalize gaps inside a day for each teacher
    penalty = 0
    for t in teachers:
        for d in range(DAYS):
            mask = teacher_day_mask[t.id][d]
            if mask == 0:
                continue
            # count gaps between first and last 1-bits
            first = None
            last = None
            for s in range(SLOTS):
                if mask & (1 << s):
                    if first is None:
                        first = s
                    last = s
            # number of zeros between first and last where teacher has no class
            if first is not None and last is not None and last > first:
                gaps = 0
                for s in range(first, last+1):
                    if not (mask & (1 << s)):
                        gaps += 1
                penalty += gaps
    return penalty

def scarcity_penalty() -> float:
    pen = 0.0
    for c in courses:
        tid = assign_teacher[c.id]
        if tid is None:
            continue
        rid = assign_room[c.id]
        if rid is None:
            continue
        r = next(rr for rr in rooms if rr.id == rid)
        is_lab_unit = ('lab' in c.required_features)
        if not is_lab_unit and 'lab' in r.features:
            pen += 1.0
        pool_size = max(1, len(candidate_rooms_for_course.get(c.id, [])))
        pen += 1.0 / pool_size * 0.05
    return pen

def time_policy_penalty() -> float:
    pen = 0.0
    for c in courses:
        tid = assign_teacher[c.id]
        if tid is None:
            continue
        d = assign_day[c.id]
        s = assign_slot[c.id]
        if d is None or s is None:
            continue
        is_lab_unit = ('lab' in c.required_features)
        if not is_lab_unit:
            pen += s * 0.05
    return pen

def fitness(weights=GlobalConfig.FITNESS_WEIGHTS, w_scarcity: float = GlobalConfig.W_SCARCITY, w_time: float = GlobalConfig.W_TIME) -> float:
    """Overall objective (lower is better).
    weights = (w_fair, w_wish_reward, w_compact, w_unsatisfied_penalty)
    We minimize fairness std & compactness, maximize wish satisfaction, and penalize unmet wishes.
    """
    fair = fairness_teacher_load_std()
    wish = wish_satisfaction_score()
    compact = compactness_penalty()
    unsat = wish_unsatisfied_count()
    w_fair, w_wish, w_comp, w_unsat = weights
    return w_fair * fair + w_comp * compact - w_wish * wish + w_unsat * unsat \
           + w_scarcity * scarcity_penalty() + w_time * time_policy_penalty()

# ------------------------------
# Utility: feasibility checks
# ------------------------------
def check_hard_constraints() -> Tuple[bool, List[str]]:
    errors = []
    # Build occupancy maps
    occ_teacher = {(d, s): set() for d in range(DAYS) for s in range(SLOTS)}
    occ_room    = {(d, s): set() for d in range(DAYS) for s in range(SLOTS)}
    for c in courses:
        tid = assign_teacher[c.id]
        if tid is None:
            continue
        d, s, rid = assign_day[c.id], assign_slot[c.id], assign_room[c.id]
        # teacher availability and single occupancy
        for k in range(c.duration):
            if not bitset_test(teachers[tid].availability_bits, d, s+k):
                errors.append(f"Teacher {tid} not available for course {c.id} at {(d,s+k)}")
            if tid in occ_teacher[(d, s+k)]:
                errors.append(f"Teacher {tid} double-booked at {(d,s+k)}")
            occ_teacher[(d, s+k)].add(tid)
            # room occupancy
            if rid in occ_room[(d, s+k)]:
                errors.append(f"Room {rid} double-booked at {(d,s+k)}")
            occ_room[(d, s+k)].add(rid)
        # room capacity and features
        room_obj = next(r for r in rooms if r.id == rid)
        if room_obj.capacity < c.size:
            errors.append(f"Room {rid} too small for course {c.id}")
        if not c.required_features.issubset(room_obj.features):
            errors.append(f"Room {rid} lacks features for course {c.id}")
    return (len(errors) == 0, errors)

# ------------------------------
# Weighted random utility
# ------------------------------
def weighted_choice(items: List, weights: List[float]):
    total = sum(weights)
    if total <= 0:
        return random.choice(items)
    r = random.uniform(0, total)
    upto = 0.0
    for item, w in zip(items, weights):
        upto += w
        if upto >= r:
            return item
    return items[-1]

# ------------------------------
# Picking logic for a course
# ------------------------------
def try_assign_course(cid: int, max_attempts: int = 120) -> bool:
    """Attempt to assign a course with priority:
    1) Favor slots that match at least one candidate teacher's wish.
    2) Within a slot, favor teachers with lower load AND whose wish matches the slot.
    3) Fallback to any feasible slot if no wish slot can be used after some tries.
    """
    c = course_by_id[cid]

    # Build candidate (d,s) along with a flag if it's a wish of any candidate teacher
    cand_slots = []  # list[((d,s), wish_flag)]
    union_slots = set()
    for tid in c.candidate_teachers:
        union_slots.update(feasible_slots[c.id][tid])

    for (d, s) in union_slots:
        teacher_pool = [t for t in c.candidate_teachers
                        if all(t in free_teachers[d][s+k] for k in range(c.duration))]
        if not teacher_pool:
            continue
        room_pool = [r for r in candidate_rooms_for_course[c.id]
                     if all(r in free_rooms[d][s+k] for k in range(c.duration))]
        if not room_pool:
            continue
        wish_flag = any((d, s) in teachers[t].wishes for t in teacher_pool)
        cand_slots.append(((d, s), wish_flag))

    if not cand_slots:
        return False

    # Separate wish vs non-wish for early attempt
    wish_slots = [x for x in cand_slots if x[1]]
    non_wish_slots = [x for x in cand_slots if not x[1]]

    # Helper to pick a slot with weighting (wish slots get a multiplier even inside groups if mixed)
    def pick_slot(pool):
        slots, flags = zip(*pool)
        weights = [GlobalConfig.WISH_SLOT_MULTIPLIER if f else 1.0 for f in flags]
        return weighted_choice(slots, weights)

    attempts = 0
    # Phase 1: try wish slots first (up to half of max_attempts or until exhausted)
    phase1_limit = max_attempts // 2
    while attempts < max_attempts:
        if attempts < phase1_limit and wish_slots:
            d, s = pick_slot(wish_slots)
        else:
            d, s = pick_slot(cand_slots)

        attempts += 1

        # Teacher pool for this slot
        pool_t = [t for t in c.candidate_teachers
                  if all(t in free_teachers[d][s+k] for k in range(c.duration))
                  and (MAX_TEACHER_SLOTS_PER_WEEK is None or teacher_week_slots[t] + c.duration <= MAX_TEACHER_SLOTS_PER_WEEK)
                  and (MAX_TEACHER_SLOTS_PER_DAY is None or teacher_day_slots[t][d] + c.duration <= MAX_TEACHER_SLOTS_PER_DAY)
                 ]
        if not pool_t:
            continue
        loads = [teacher_load[t] for t in pool_t]
        max_load = max(loads) if loads else 0
        weights_t = []
        for t in pool_t:
            base = 1 + (max_load - teacher_load[t])  # fairness
            if (d, s) in teachers[t].wishes:
                base *= 2.0  # wish bonus
            weights_t.append(base)
        tid = weighted_choice(pool_t, weights_t)

        pool_r = [r for r in candidate_rooms_for_course[c.id]
                  if all(r in free_rooms[d][s+k] for k in range(c.duration))]
        if not pool_r:
            continue
        # Prefer to avoid using LAB rooms for non-lab classes to preserve scarce resources
        def room_key(rid: int):
            r = next(rr for rr in rooms if rr.id == rid)
            lab_penalty = 0 if ('lab' in c.required_features) else (1 if 'lab' in r.features else 0)
            slack = r.capacity - c.size
            return (lab_penalty, slack)
        pool_r.sort(key=room_key)
        rid = pool_r[0]

        before_len = len(undo_stack)
        if not reserve_teacher(tid, d, s, c.duration):
            continue
        if not reserve_room(rid, d, s, c.duration):
            rollback_to(before_len)
            continue
        commit_assignment(cid, tid, d, s, rid)
        return True
    return False

def rollback_to(stack_len: int):
    while len(undo_stack) > stack_len:
        op, *args = undo_stack.pop()
        if op == "free_teacher_add":
            tid, d, s = args
            free_teachers[d][s].add(tid)
        elif op == "teacher_load_dec":
            tid, = args
            teacher_load[tid] -= 1
        elif op == "teacher_day_mask_set":
            tid, d, old_mask = args
            teacher_day_mask[tid][d] = old_mask
        elif op == "free_room_add":
            rid, d, s = args
            free_rooms[d][s].add(rid)
        elif op == "assign_clear":
            cid, old = args
            assign_teacher[cid], assign_day[cid], assign_slot[cid], assign_room[cid] = old
        elif op == "free_teacher_remove":
            tid, d, s = args
            if tid in free_teachers[d][s]:
                free_teachers[d][s].remove(tid)
        elif op == "free_room_remove":
            rid, d, s = args
            if rid in free_rooms[d][s]:
                free_rooms[d][s].remove(rid)
        elif op == "teacher_load_inc":
            tid, = args
            teacher_load[tid] += 1
        elif op == "teacher_week_slots_add":
            tid, delta = args
            teacher_week_slots[tid] += delta
        elif op == "teacher_day_slots_add":
            tid, d, delta = args
            teacher_day_slots[tid][d] += delta
        elif op == "teacher_week_slots_sub":
            tid, delta = args
            teacher_week_slots[tid] -= delta
        elif op == "teacher_day_slots_sub":
            tid, d, delta = args
            teacher_day_slots[tid][d] -= delta
        elif op == "teacher_day_mask_restore":
            tid, d, prev_mask = args
            teacher_day_mask[tid][d] = prev_mask
        else:
            pass

# ------------------------------
# Initialization (ordering + assignment)
# ------------------------------
def difficulty_key(c: Course) -> Tuple:
    # fewer teachers -> harder; longer duration -> harder; fewer candidate rooms -> harder; lab requirement earlier
    requires_lab = 1 if ('lab' in c.required_features) else 0
    return (len(c.candidate_teachers), -c.duration, len(candidate_rooms_for_course[c.id]), -requires_lab)

def initialize_schedule() -> bool:
    # Clear current assignments
    global undo_stack
    undo_stack = []
    for cid in list(assign_teacher.keys()):
        clear_assignment(cid)
    for d in range(DAYS):
        for s in range(SLOTS):
            free_teachers[d][s].clear()
            free_rooms[d][s].clear()
            for t in teachers:
                if bitset_test(t.availability_bits, d, s):
                    free_teachers[d][s].add(t.id)
            for r in rooms:
                free_rooms[d][s].add(r.id)
    for t in teachers:
        teacher_load[t.id] = 0
        teacher_day_mask[t.id] = [0]*DAYS
        assignments_by_teacher[t.id].clear()
        teacher_week_slots[t.id] = 0
        teacher_day_slots[t.id] = [0]*DAYS

    # Order by "hard first"
    order = sorted(courses, key=difficulty_key)
    # Simple fairness across departments: round-robin by dept bucket at init
    buckets: Dict[str, List[Course]] = {}
    for c in order:
        buckets.setdefault(c.dept, []).append(c)
    depts = list(buckets.keys())
    ptr = {d:0 for d in depts}

    assigned = 0
    while True:
        progressed = False
        for dept in depts:
            if ptr[dept] >= len(buckets[dept]):
                continue
            c = buckets[dept][ptr[dept]]
            ok = try_assign_course(c.id, 100)
            ptr[dept] += 1
            if ok:
                assigned += 1
            progressed = True
        if not progressed:
            break

    # Check if all assigned
    all_assigned = all(assign_teacher[c.id] is not None for c in courses)
    return all_assigned

# ------------------------------
# Reset state (blank slate)
# ------------------------------
def reset_state():
    global undo_stack
    undo_stack = []
    for cid in list(assign_teacher.keys()):
        clear_assignment(cid)
    for d in range(DAYS):
        for s in range(SLOTS):
            free_teachers[d][s].clear()
            free_rooms[d][s].clear()
            for t in teachers:
                if bitset_test(t.availability_bits, d, s):
                    free_teachers[d][s].add(t.id)
            for r in rooms:
                free_rooms[d][s].add(r.id)
    for t in teachers:
        teacher_load[t.id] = 0
        teacher_day_mask[t.id] = [0]*DAYS
        assignments_by_teacher[t.id].clear()
        teacher_week_slots[t.id] = 0
        teacher_day_slots[t.id] = [0]*DAYS

# ------------------------------
# Units order and Decoder (Hybrid-Wish)
# ------------------------------
def units_order() -> List[int]:
    order = sorted(courses, key=difficulty_key)
    buckets: Dict[str, List[Course]] = {}
    for c in order:
        buckets.setdefault(c.dept, []).append(c)
    depts = list(buckets.keys())
    ptr = {d: 0 for d in depts}
    seq: List[int] = []
    progressed = True
    while progressed:
        progressed = False
        for dept in depts:
            if ptr[dept] < len(buckets[dept]):
                seq.append(buckets[dept][ptr[dept]].id)
                ptr[dept] += 1
                progressed = True
    return seq

def _option_indices_for_unit(u: int, start_idx: int) -> List[int]:
    L = len(OptionList.get(u, []))
    if L == 0:
        return []
    wend = WishEnd.get(u, 0)
    res: List[int] = []
    if wend > 0 and start_idx < wend:
        res.extend(range(start_idx, wend))
        res.extend(range(0, start_idx))
        res.extend(range(wend, L))
    else:
        res.extend(range(0, wend))
        start2 = max(wend, start_idx)
        if start2 < L:
            res.extend(range(start2, L))
        if start2 > wend:
            res.extend(range(wend, start2))
    return list(res)

def decode_greedy(gene: List[int]) -> bool:
    order = units_order()
    for u in order:
        c = course_by_id[u]
        opts = OptionList.get(u, [])
        if not opts:
            return False
        start_idx = 0
        if u < len(gene):
            start_idx = max(0, min(gene[u], len(opts)-1))
        tried = _option_indices_for_unit(u, start_idx)
        placed = False
        for oi in tried:
            d, s, tid, rid = opts[oi]
            if not all(tid in free_teachers[d][s+k] for k in range(c.duration)):
                continue
            if not all(rid in free_rooms[d][s+k] for k in range(c.duration)):
                continue
            if MAX_TEACHER_SLOTS_PER_WEEK is not None and teacher_week_slots[tid] + c.duration > MAX_TEACHER_SLOTS_PER_WEEK:
                continue
            if MAX_TEACHER_SLOTS_PER_DAY is not None and teacher_day_slots[tid][d] + c.duration > MAX_TEACHER_SLOTS_PER_DAY:
                continue
            before = len(undo_stack)
            if not reserve_teacher(tid, d, s, c.duration):
                rollback_to(before)
                continue
            if not reserve_room(rid, d, s, c.duration):
                rollback_to(before)
                continue
            commit_assignment(u, tid, d, s, rid)
            placed = True
            break
        if not placed:
            return False
    return True

def snapshot_solution():
    return [(c.id, assign_teacher[c.id], assign_day[c.id], assign_slot[c.id], assign_room[c.id]) for c in courses]

def restore_solution(snap):
    reset_state()
    for (cid, tid, d, s, rid) in snap:
        if tid is None:
            continue
        c = course_by_id[cid]
        if not all(tid in free_teachers[d][s+k] for k in range(c.duration)):
            continue
        if not all(rid in free_rooms[d][s+k] for k in range(c.duration)):
            continue
        before = len(undo_stack)
        if not reserve_teacher(tid, d, s, c.duration):
            rollback_to(before)
            continue
        if not reserve_room(rid, d, s, c.duration):
            rollback_to(before)
            continue
        commit_assignment(cid, tid, d, s, rid)

def local_search_short(steps=GlobalConfig.LS_STEPS_INIT):
    for _ in range(steps):
        cid = random.choice([c.id for c in courses])
        feasible_mutation(cid, tries=20)

def init_hybrid(seed=None) -> Tuple[bool, List[int]]:
    if seed is not None:
        random.seed(seed)
    gene: List[int] = [0]*len(courses)
    for u in units_order():
        L = len(OptionList.get(u, []))
        if L == 0:
            return False, []
        wend = WishEnd.get(u, 0)
        gene[u] = random.randrange(0, wend) if wend > 0 else random.randrange(0, L)
    reset_state()
    ok = decode_greedy(gene)
    if ok:
        local_search_short(steps=GlobalConfig.LS_STEPS_INIT)
    return ok, gene

def multi_start_best_of_n(N=GlobalConfig.MULTI_START_N):
    best = None
    best_fit = float('inf')
    for s in range(N):
        ok, g = init_hybrid(seed=s)
        if not ok:
            continue
        f = fitness()
        if f < best_fit:
            best_fit = f
            best = snapshot_solution()
    if best is None:
        print("[INFO] Multi-start failed; falling back to greedy initializer...")
        # Fallback to the older greedy initialize_schedule()
        ok2 = initialize_schedule()
        if not ok2:
            raise RuntimeError("Initialization failed: both multi-start decoder and greedy initializer could not build a feasible schedule.")
        return
    restore_solution(best)

# ------------------------------
# Memetic GA (μ+λ)
# ------------------------------
# GA config is centralized in GlobalConfig

@dataclass
class Individual:
    gene: List[int]
    fitness: float = float('inf')
    pheno: Optional[int] = None

def random_gene_from_optionlist() -> List[int]:
    g: List[int] = [0]*len(courses)
    for u in units_order():
        L = len(OptionList.get(u, []))
        g[u] = random.randrange(0, L) if L > 0 else 0
    return g

def make_individual_from_gene(gene: List[int]) -> Individual:
    return Individual(gene=list(gene), fitness=float('inf'))

def evaluate(ind: Individual, ls_steps=GlobalConfig.LS_STEPS_EVAL):
    reset_state()
    ok = decode_greedy(ind.gene)
    if not ok:
        ind.fitness = 1e12
        ind.pheno = None
        return
    for _ in range(ls_steps):
        cid = random.choice([c.id for c in courses])
        feasible_mutation(cid, tries=20)
    ind.fitness = fitness()
    # phenotype: assignment mapping (day,slot,room) for units that are assigned
    pheno_tuple = tuple(sorted(
        (
            c.id,
            assign_day[c.id],
            assign_slot[c.id],
            assign_room[c.id]
        )
        for c in courses if assign_teacher[c.id] is not None
    ))
    ind.pheno = hash(pheno_tuple)

def ga_init_population(mu=GlobalConfig.GA_POP, greedy_share=0.6) -> List[Individual]:
    pop: List[Individual] = []
    seeds = int(mu*greedy_share)
    for s in range(seeds):
        ok, g = init_hybrid(seed=1000+s)
        if ok:
            ind = make_individual_from_gene(g)
            evaluate(ind, ls_steps=GlobalConfig.LS_STEPS_EVAL)
            pop.append(ind)
    while len(pop) < mu:
        g = random_gene_from_optionlist()
        ind = make_individual_from_gene(g)
        evaluate(ind, ls_steps=GlobalConfig.LS_STEPS_EVAL)
        pop.append(ind)
    return pop

def tournament_select(pop: List[Individual], k=3) -> Individual:
    cand = random.sample(pop, k)
    return min(cand, key=lambda x: x.fitness)

def crossover(g1: List[int], g2: List[int], mode="1p") -> List[int]:
    n = len(g1)
    if n == 0:
        return []
    if mode == "uniform":
        return [g1[i] if random.random() < 0.5 else g2[i] for i in range(n)]
    cut = random.randrange(1, n)
    return g1[:cut] + g2[cut:]

def mutate(g: List[int], rate=GlobalConfig.MUTATION_RATE):
    for i in range(len(g)):
        if random.random() < rate:
            u = i
            L = len(OptionList.get(u, []))
            if L > 0:
                wend = WishEnd.get(u, 0)
                if g[i] < wend and wend > 0:
                    g[i] = random.randrange(0, wend)
                else:
                    g[i] = random.randrange(wend, L) if L > wend else g[i]

def ga_step(pop: List[Individual], mu=GlobalConfig.GA_POP, lamb=GlobalConfig.GA_OFFSPRING, k=3) -> List[Individual]:
    elites = sorted(pop, key=lambda x: x.fitness)[:2]
    seen = {e.pheno for e in elites if e.pheno is not None}
    children: List[Individual] = []
    attempts = 0
    max_attempts = lamb * 5
    while len(children) < lamb and attempts < max_attempts:
        attempts += 1
        p1, p2 = tournament_select(pop, k), tournament_select(pop, k)
        g = crossover(p1.gene, p2.gene, mode="1p")
        mutate(g, rate=GlobalConfig.MUTATION_RATE)
        child = make_individual_from_gene(g)
        evaluate(child, ls_steps=GlobalConfig.LS_STEPS_EVAL)
        if child.pheno is not None and child.pheno in seen:
            continue
        seen.add(child.pheno)
        children.append(child)
    pool = elites + children
    # enforce uniqueness again when selecting next_pop
    uniq_pool: List[Individual] = []
    seen2 = set()
    for ind in sorted(pool, key=lambda x: x.fitness):
        if ind.pheno is not None and ind.pheno in seen2:
            continue
        seen2.add(ind.pheno)
        uniq_pool.append(ind)
        if len(uniq_pool) >= mu:
            break
    # if uniqueness filtered too many, fill with best remaining regardless
    if len(uniq_pool) < mu:
        rest = [x for x in sorted(pool, key=lambda x: x.fitness) if x not in uniq_pool]
        uniq_pool.extend(rest[: max(0, mu - len(uniq_pool))])
    return uniq_pool

def run_ga(generations=GlobalConfig.GA_GENERATIONS, mu=GlobalConfig.GA_POP, lamb=GlobalConfig.GA_OFFSPRING, early_stop=GlobalConfig.GA_EARLY_STOP):
    pop = ga_init_population(mu=mu)
    best = min(pop, key=lambda x: x.fitness)
    stall = 0
    for g in range(generations):
        pop = ga_step(pop, mu=mu, lamb=lamb, k=3)
        cur = min(pop, key=lambda x: x.fitness)
        if cur.fitness + 1e-9 < best.fitness:
            best, stall = cur, 0
        else:
            stall += 1
        if stall >= early_stop:
            break
    reset_state()
    ok = decode_greedy(best.gene)
    if not ok:
        print("[INFO] GA best gene failed to decode; trying greedy initializer...")
        if not initialize_schedule():
            print("[INFO] Greedy initializer failed; trying multi-start fallback...")
            multi_start_best_of_n(N=GlobalConfig.MULTI_START_N)
    local_search_short(steps=GlobalConfig.LS_STEPS_FINAL)

# ------------------------------
# Local Search (Feasible Mutation)
# ------------------------------
def feasible_mutation(cid: int, tries: int = 50) -> bool:
    """Try moving a course to another feasible (d,s,rid) and/or teacher, accepting if feasible & improves fitness."""
    c = course_by_id[cid]
    # Current
    old_tid = assign_teacher[cid]
    old_d, old_s, old_r = assign_day[cid], assign_slot[cid], assign_room[cid]

    if old_tid is None:
        return False

    best_before = fitness()
    for _ in range(tries):
        # Choose a neighbor move:
        move_type = random.choice(["slot", "teacher", "room", "slot_teacher"])
        # Snapshot stack for rollback
        snapshot = len(undo_stack)

        # Release current reservations (simulate change)
        # We'll "virtually" free the teacher/room for trying new spot by temporarily adding to free sets.
        # Easiest way: actually rollback the current assignment and try a fresh assignment for this course, then compare fitness.
        # Steps:
        # 1) Temporarily free current (teacher, room) reservations for this course
        # (We do NOT have a per-course reservation tracking to free slot-by-slot here,
        #  so we will rebuild free sets by performing a rollback to snapshot saved at init is complex.
        #  Practical approach: we attempt to assign the course anew without touching the old ones by requiring new pick != old.)
        # Simpler approach: Try to pick a new (d,s,tid,rid) that is currently free including old one's slots (i.e., we can't reuse current slots for this check).
        # To keep correctness, we'll perform a two-phase: 1) temporarily mark current slots as free (push log), 2) reserve new, 3) if fail, rollback.
        # Free teacher & room for their occupied slots:
        # We need to actually add back to free sets and adjust loads/masks; push inverse ops into log to allow rollback.
        # -- Free teacher:
        for k in range(c.duration):
            # Re-add to free sets
            free_teachers[old_d][old_s+k].add(old_tid)
            log("free_teacher_remove", old_tid, old_d, old_s+k)  # inverse to remove on rollback
            free_rooms[old_d][old_s+k].add(old_r)
            log("free_room_remove", old_r, old_d, old_s+k)
        # Adjust load/mask downward
        teacher_load[old_tid] -= 1
        log("teacher_load_inc", old_tid)
        # Update slot counters (temporary free)
        teacher_week_slots[old_tid] -= c.duration
        log("teacher_week_slots_add", old_tid, c.duration)  # add back on rollback
        teacher_day_slots[old_tid][old_d] -= c.duration
        log("teacher_day_slots_add", old_tid, old_d, c.duration)
        # Remove bits from day mask
        mask = teacher_day_mask[old_tid][old_d]
        for k in range(c.duration):
            mask &= ~(1 << (old_s+k))
        prev_mask = teacher_day_mask[old_tid][old_d]
        teacher_day_mask[old_tid][old_d] = mask
        log("teacher_day_mask_restore", old_tid, old_d, prev_mask)

        # Now attempt a new place:
        # Depending on move_type, either change slot, teacher, room or both
        if move_type in ("slot", "slot_teacher"):
            # pick a new start time (d,s) with wish preference
            union_slots = set()
            for tid in c.candidate_teachers:
                union_slots.update(feasible_slots[c.id][tid])
            union_slots.discard((old_d, old_s))
            if not union_slots:
                rollback_to(snapshot)
                continue
            # Build weighted list
            temp = []
            for (d0, s0) in union_slots:
                wish_flag = any((d0, s0) in teachers[t].wishes for t in c.candidate_teachers)
                temp.append(((d0, s0), wish_flag))
            slots, flags = zip(*temp)
            weights = [GlobalConfig.WISH_MOVE_MULTIPLIER if f else 1.0 for f in flags]
            d, s = weighted_choice(slots, weights)
        else:
            d, s = old_d, old_s

        # Teacher selection
        if move_type in ("teacher", "slot_teacher"):
            pool_t = [t for t in c.candidate_teachers
                      if all(t in free_teachers[d][s+k] for k in range(c.duration))
                      and (MAX_TEACHER_SLOTS_PER_WEEK is None or teacher_week_slots[t] + c.duration <= MAX_TEACHER_SLOTS_PER_WEEK)
                      and (MAX_TEACHER_SLOTS_PER_DAY is None or teacher_day_slots[t][d] + c.duration <= MAX_TEACHER_SLOTS_PER_DAY)
                     ]
            if not pool_t:
                rollback_to(snapshot)
                continue
            loads = [teacher_load[t] for t in pool_t]
            max_load = max(loads) if loads else 0
            weights_t = []
            for t in pool_t:
                w = 1 + (max_load - teacher_load[t])
                if (d, s) in teachers[t].wishes:
                    w *= 2.0
                weights_t.append(w)
            tid = weighted_choice(pool_t, weights_t)
        else:
            tid = old_tid
            # Ensure tid is free at new slot
            if not all(tid in free_teachers[d][s+k] for k in range(c.duration)):
                rollback_to(snapshot)
                continue

        # Room selection
        if move_type in ("room", "slot", "slot_teacher", "teacher"):
            pool_r = [r for r in candidate_rooms_for_course[c.id]
                      if all(r in free_rooms[d][s+k] for k in range(c.duration))]
            if not pool_r:
                rollback_to(snapshot)
                continue
            def room_key2(rid: int):
                r = next(rr for rr in rooms if rr.id == rid)
                lab_penalty = 0 if ('lab' in c.required_features) else (1 if 'lab' in r.features else 0)
                slack = r.capacity - c.size
                return (lab_penalty, slack)
            pool_r.sort(key=room_key2)
            rid = pool_r[0]
        else:
            rid = old_r
            if not all(rid in free_rooms[d][s+k] for k in range(c.duration)):
                rollback_to(snapshot)
                continue

        # Reserve new
        if not reserve_teacher(tid, d, s, c.duration):
            rollback_to(snapshot)
            continue
        if not reserve_room(rid, d, s, c.duration):
            rollback_to(snapshot)
            continue

        # Commit to new assignment
        # Remove the course from the old teacher's assignment set, add to the new teacher
        assignments_by_teacher[old_tid].discard(cid)
        assignments_by_teacher[tid].add(cid)
        # Update gene (log old for rollback via "assign_clear")
        old_assign = (old_tid, old_d, old_s, old_r)
        log("assign_clear", cid, old_assign)
        assign_teacher[cid], assign_day[cid], assign_slot[cid], assign_room[cid] = tid, d, s, rid

        # Evaluate
        new_fit = fitness()
        if new_fit <= best_before:
            # Accept (improved or equal)
            return True
        else:
            # Revert
            rollback_to(snapshot)
            continue
    return False

# Extend rollback_to with the extra op types we used in feasible_mutation
def rollback_to(stack_len: int):
    while len(undo_stack) > stack_len:
        op, *args = undo_stack.pop()
        if op == "free_teacher_add":
            tid, d, s = args
            free_teachers[d][s].add(tid)
        elif op == "teacher_load_dec":
            tid, = args
            teacher_load[tid] -= 1
        elif op == "teacher_day_mask_set":
            tid, d, old_mask = args
            teacher_day_mask[tid][d] = old_mask
        elif op == "free_room_add":
            rid, d, s = args
            free_rooms[d][s].add(rid)
        elif op == "assign_clear":
            cid, old = args
            # Restore assignment and teacher assignment list
            new_t = assign_teacher[cid]
            if new_t is not None:
                assignments_by_teacher[new_t].discard(cid)
            # Restore old
            assign_teacher[cid], assign_day[cid], assign_slot[cid], assign_room[cid] = old
            if old[0] is not None:
                assignments_by_teacher[old[0]].add(cid)
        elif op == "free_teacher_remove":
            tid, d, s = args
            if tid in free_teachers[d][s]:
                free_teachers[d][s].remove(tid)
        elif op == "free_room_remove":
            rid, d, s = args
            if rid in free_rooms[d][s]:
                free_rooms[d][s].remove(rid)
        elif op == "teacher_load_inc":
            tid, = args
            teacher_load[tid] += 1
        elif op == "teacher_week_slots_add":
            tid, delta = args
            teacher_week_slots[tid] += delta
        elif op == "teacher_day_slots_add":
            tid, d, delta = args
            teacher_day_slots[tid][d] += delta
        elif op == "teacher_week_slots_sub":
            tid, delta = args
            teacher_week_slots[tid] -= delta
        elif op == "teacher_day_slots_sub":
            tid, d, delta = args
            teacher_day_slots[tid][d] -= delta
        elif op == "teacher_day_mask_restore":
            tid, d, prev_mask = args
            teacher_day_mask[tid][d] = prev_mask
        else:
            pass

# ------------------------------
# Driver
# ------------------------------
def run_demo():
    # Build options
    build_option_lists()
    # Multi-start baseline
    multi_start_best_of_n(N=GlobalConfig.MULTI_START_N)
    # Memetic GA improvement
    run_ga(generations=GlobalConfig.GA_GENERATIONS, mu=GlobalConfig.GA_POP, lamb=GlobalConfig.GA_OFFSPRING, early_stop=GlobalConfig.GA_EARLY_STOP)

    fit0 = fitness()
    feasible0, errs0 = check_hard_constraints()
    assert feasible0, f"Initial schedule violates constraints: {errs0}"

    # Additional local search polishing
    iters = 300
    improves = 0
    for _ in range(iters):
        cid = random.choice([c.id for c in courses])
        if feasible_mutation(cid, tries=20):
            improves += 1

    fit1 = fitness()
    feasible1, errs1 = check_hard_constraints()
    assert feasible1, f"Post-optimization violates constraints: {errs1}"

    # Build printable timetable
    timetable = []
    for c in courses:
        tid = assign_teacher[c.id]
        d  = assign_day[c.id]
        s  = assign_slot[c.id]
        rid = assign_room[c.id]
        timetable.append({
            "Course": c.name,
            "Dept": c.dept,
            "Teacher": teachers[tid].name if tid is not None else None,
            "Day": d,
            "Slot": s,
            "Room": next(r.name for r in rooms if r.id == rid) if rid is not None else None,
            "Duration": c.duration,
            "ReqFeatures": ",".join(sorted(c.required_features)) if c.required_features else "-",
            "Size": c.size,
            "WishHit": 1 if tid is not None and (d, s) in teachers[tid].wishes else 0
        })
    # Sort by day, slot, room name for readability
    timetable.sort(key=lambda x: (x["Day"], x["Slot"], x["Room"] or ""))

    # Metrics
    sat = wish_satisfaction_score()
    unsat = wish_unsatisfied_count()
    coverage = sat / max(1, sat + unsat)
    metrics = {
        "fitness_before": fit0,
        "fitness_after": fit1,
        "improvements": improves,
        "fairness_std": fairness_teacher_load_std(),
        "wish_satisfaction": sat,
        "wish_unsatisfied": unsat,
        "wish_coverage_rate": coverage,
        "compactness_penalty": compactness_penalty(),
        "all_assigned": all(assign_teacher[c.id] is not None for c in courses),
        "feasible": feasible1,
    }

    return timetable, metrics

timetable, metrics = run_demo()

# Pretty print results

# --- Xuất kết quả ra Excel, mỗi khoa một sheet, dạng thời khóa biểu ---
import pandas as pd
from collections import defaultdict

# Nhóm theo khoa
dept_groups = defaultdict(list)
for row in timetable:
    dept_groups[row['Dept']].append(row)

# Định dạng lại dữ liệu cho đẹp mắt
def format_row(row):
    return {
        'Day': row['Day'],
        'Slot': row['Slot'],
        'Course': row['Course'],
        'Teacher': row['Teacher'],
        'Room': row['Room'],
        'Duration': row['Duration'],
        'Features': row['ReqFeatures'],
        'Size': row['Size'],
        'Wish': row['WishHit']
    }

excel_writer = pd.ExcelWriter(GlobalConfig.OUTPUT_TIMETABLE_FILE, engine='openpyxl')
for dept, rows in dept_groups.items():
    df = pd.DataFrame([format_row(r) for r in rows])
    df = df.sort_values(['Day', 'Slot', 'Room'])
    df.to_excel(excel_writer, sheet_name=f"Dept_{dept}", index=False)

# Extra reporting: NonWishAssignments & UnmetWishes
non_wish_rows = []
for c in courses:
    tid = assign_teacher[c.id]
    if tid is None:
        continue
    d = assign_day[c.id]
    s = assign_slot[c.id]
    if (d, s) not in teachers[tid].wishes:
        non_wish_rows.append({
            'UnitID': c.id,
            'UnitName': c.name,
            'Dept': c.dept,
            'TeacherID': tid,
            'Teacher': teachers[tid].name,
            'Day': d,
            'Slot': s,
            'Room': next(r.name for r in rooms if r.id == assign_room[c.id]) if assign_room[c.id] is not None else None,
            'Duration': c.duration,
            'ReqFeatures': ",".join(sorted(c.required_features)) if c.required_features else "-",
            'Size': c.size,
        })
if non_wish_rows:
    df_nonwish = pd.DataFrame(non_wish_rows).sort_values(['Teacher', 'Day', 'Slot'])
    df_nonwish.to_excel(excel_writer, sheet_name='NonWishAssignments', index=False)

unmet_rows = []
for t in teachers:
    for (d, s) in sorted(t.wishes):
        hit = False
        for cid in assignments_by_teacher[t.id]:
            if assign_day[cid] == d and assign_slot[cid] == s:
                hit = True
                break
        if not hit:
            unmet_rows.append({'TeacherID': t.id, 'Teacher': t.name, 'Day': d, 'Slot': s})
if unmet_rows:
    df_unmet = pd.DataFrame(unmet_rows).sort_values(['Teacher', 'Day', 'Slot'])
    df_unmet.to_excel(excel_writer, sheet_name='UnmetWishes', index=False)
excel_writer.close()

print(f"\n=== Đã xuất file Excel: {GlobalConfig.OUTPUT_TIMETABLE_FILE} (mỗi khoa một sheet) ===")

# --- Xuất thêm ra JSON cho timetable ---
try:
    timetable_json = {
        'departments': {
            dept: [format_row(r) for r in sorted(rows, key=lambda x: (x['Day'], x['Slot'], x['Room'] or ''))]
            for dept, rows in dept_groups.items()
        },
        'metrics': metrics,
    }
    with open(GlobalConfig.OUTPUT_TIMETABLE_JSON, 'w', encoding='utf-8') as f:
        json.dump(timetable_json, f, ensure_ascii=False, indent=2)
    print(f"=== Đã xuất file JSON: {GlobalConfig.OUTPUT_TIMETABLE_JSON} ===")
except Exception as e:
    print(f"[WARN] Không thể xuất {GlobalConfig.OUTPUT_TIMETABLE_JSON}. Lỗi:", e)

# --- Xuất dataset (Teachers, Rooms, Courses, Units) ra Excel ---
try:
    ds_writer = pd.ExcelWriter(GlobalConfig.OUTPUT_DATASET_FILE, engine='openpyxl')

    # Teachers sheet
    df_teachers = pd.DataFrame([
        {
            'TeacherID': t.id,
            'Name': t.name,
            'Dept': t.dept,
            'Wishes': ",".join([f"({d},{s})" for (d,s) in sorted(t.wishes)])
        }
        for t in teachers
    ])
    df_teachers.to_excel(ds_writer, sheet_name='Teachers', index=False)

    # Rooms sheet
    df_rooms = pd.DataFrame([
        {
            'RoomID': r.id,
            'Name': r.name,
            'Capacity': r.capacity,
            'Features': ",".join(sorted(r.features)) if r.features else "-"
        }
        for r in rooms
    ])
    df_rooms.to_excel(ds_writer, sheet_name='Rooms', index=False)

    # Base Courses sheet (from original course_specs)
    df_courses = pd.DataFrame([
        {
            'CourseID': cid,
            'Name': name,
            'Dept': dept,
            'Size': size,
            'Duration': duration,
            'ReqFeatures': ",".join(sorted(required_features)) if required_features else "-",
            'CandidateTeachers': ",".join(map(str, sorted(candidate_teachers)))
        }
        for (cid, name, dept, size, duration, required_features, candidate_teachers) in course_specs
    ])
    df_courses.to_excel(ds_writer, sheet_name='Courses', index=False)

    # Expanded Units sheet (our actual scheduling units)
    df_units = pd.DataFrame([
        {
            'UnitID': c.id,
            'UnitName': c.name,
            'Dept': c.dept,
            'Size': c.size,
            'Duration': c.duration,
            'ReqFeatures': ",".join(sorted(c.required_features)) if c.required_features else "-",
            'CandidateTeachers': ",".join(map(str, sorted(c.candidate_teachers)))
        }
        for c in courses
    ])
    df_units.to_excel(ds_writer, sheet_name='Units', index=False)

    ds_writer.close()
    print(f"=== Đã xuất file Excel: {GlobalConfig.OUTPUT_DATASET_FILE} (Teachers, Rooms, Courses, Units) ===")
except Exception as e:
    print(f"[WARN] Không thể xuất {GlobalConfig.OUTPUT_DATASET_FILE} (cần pandas + openpyxl). Lỗi:", e)

# --- Xuất dataset ra JSON ---
try:
    teachers_json = [
        {
            'TeacherID': t.id,
            'Name': t.name,
            'Dept': t.dept,
            'Wishes': sorted(list(t.wishes))
        } for t in teachers
    ]
    rooms_json = [
        {
            'RoomID': r.id,
            'Name': r.name,
            'Capacity': r.capacity,
            'Features': sorted(list(r.features))
        } for r in rooms
    ]
    courses_json = [
        {
            'CourseID': cid,
            'Name': name,
            'Dept': dept,
            'Size': size,
            'Duration': duration,
            'ReqFeatures': sorted(list(required_features)) if required_features else [],
            'CandidateTeachers': sorted(list(candidate_teachers))
        }
        for (cid, name, dept, size, duration, required_features, candidate_teachers) in course_specs
    ]
    units_json = [
        {
            'UnitID': c.id,
            'UnitName': c.name,
            'Dept': c.dept,
            'Size': c.size,
            'Duration': c.duration,
            'ReqFeatures': sorted(list(c.required_features)) if c.required_features else [],
            'CandidateTeachers': sorted(list(c.candidate_teachers))
        }
        for c in courses
    ]
    dataset_json = {
        'Teachers': teachers_json,
        'Rooms': rooms_json,
        'Courses': courses_json,
        'Units': units_json,
    }
    with open(GlobalConfig.OUTPUT_DATASET_JSON, 'w', encoding='utf-8') as f:
        json.dump(dataset_json, f, ensure_ascii=False, indent=2)
    print(f"=== Đã xuất file JSON: {GlobalConfig.OUTPUT_DATASET_JSON} (Teachers, Rooms, Courses, Units) ===")
except Exception as e:
    print(f"[WARN] Không thể xuất {GlobalConfig.OUTPUT_DATASET_JSON}. Lỗi:", e)
print("\n=== METRICS ===")
for k, v in metrics.items():
    print(f"{k}: {v}")

print("\n=== TIMETABLE (Day, Slot) ===")
print("độ dài của tkb:", len(timetable))
for row in timetable:
    print(f"Day {row['Day']} Slot {row['Slot']} | {row['Course']} ({row['Dept']}) "
          f"-> {row['Teacher']} | {row['Room']} | dur={row['Duration']} | "
          f"features={row['ReqFeatures']} | size={row['Size']} | wish={row['WishHit']}")
