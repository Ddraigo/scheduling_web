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
#
# You can run this cell as-is. At the end, it prints a timetable and metrics.
#
# NOTE: No external optimization libraries used. Pure Python.
#
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional
import math
import random
import json

from src.validation.constraint_checker import validate_all_constraints, ConstraintViolation


# ------------------------------
# Global Config
# ------------------------------
class GlobalConfig:
    # Randomness
    SEED: int = None  # Set to None for random behavior, or specific int for reproducibility

    # Calendar
    DAYS: int = 6            # Mon..Sat
    SLOTS: int = 4           # 4 timeslots per day (e.g., 8:00, 10:00, 13:00, 15:00)

    # Teacher weekly/day slot limits (set to None to disable per-day)
    # Relaxed limits to improve feasibility with multi-meeting units
    MAX_TEACHER_SLOTS_PER_WEEK: Optional[int] = 16
    MAX_TEACHER_SLOTS_PER_DAY: Optional[int] = 5

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

 

    

# Module-level aliases for minimal code changes
DAYS = GlobalConfig.DAYS
SLOTS = GlobalConfig.SLOTS
T = DAYS * SLOTS

MAX_TEACHER_SLOTS_PER_WEEK = GlobalConfig.MAX_TEACHER_SLOTS_PER_WEEK
MAX_TEACHER_SLOTS_PER_DAY = GlobalConfig.MAX_TEACHER_SLOTS_PER_DAY

# Honor global seed for reproducibility (only if explicitly set)
if GlobalConfig.SEED is not None:
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
    room_type: str                     # SQL: tb_PHONG_HOC.LoaiPhong (e.g., "Lý thuyết", "Thực hành")
    equipment: str                     # SQL: tb_PHONG_HOC.ThietBi (e.g., "Máy chiếu, TV, máy lạnh")

@dataclass
class Course:
    id: int
    name: str
    dept: str
    size: int
    duration: int                      # slots per class meeting (1 or 2 for demo)
    room_type_required: str            # SQL: từ tb_LOP_MONHOC.To_MH (To_MH=0 → "", To_MH>0 → "Thực hành")
    equipment_required: str            # SQL: tb_LOP_MONHOC.ThietBiYeuCau (e.g., "TV, Máy chiếu")
    candidate_teachers: Set[int]       # teacher IDs who can teach

# NOTE: We will expand base course specs into per-meeting units (lectures/labs, groups/sections)
# to support multi-meeting per week and practicals.

# ------------------------------
# SQL Data Injection Point
# ------------------------------
# ✅ VERSION FOR SQL DATA - NO RANDOM GENERATION
# Data will be injected from schedule_generator.py via:
#   - teachers: List[Teacher]
#   - rooms: List[Room]
#   - courses: List[Course]
# ⚠️ DO NOT initialize these variables here!

# Initialize as empty - will be populated by injection
teachers: List[Teacher] = []
rooms: List[Room] = []
courses: List[Course] = []

# ✅ SQL weights injection point (injected from schedule_generator.py via ga_adapter)
# This dict is populated dynamically from tb_RANG_BUOC_MEM or tb_RANG_BUOC_TRONG_DOT
sql_weights: Dict[str, float] = {}

# ------------------------------
# Precomputation
# ------------------------------

# Candidate rooms per course (capacity, room_type, and equipment)
candidate_rooms_for_course: Dict[int, Set[int]] = {}
for c in courses:
    room_ids = set()
    for r in rooms:
        # 1. Check capacity
        if r.capacity < c.size:
            continue
        
        # 2. Check room_type (STRICT matching)
        # Course với room_type_required='Lý thuyết' CHỈ match phòng 'Lý thuyết'
        # Course với room_type_required='Thực hành' CHỈ match phòng 'Thực hành'
        if c.room_type_required and c.room_type_required.strip():
            # Normalize để so sánh
            required_type = c.room_type_required.strip().lower()
            room_type = r.room_type.strip().lower()
            if required_type not in room_type:
                continue
        
        # 3. Check equipment: So sánh đơn giản - mọi item trong equipment_required phải có trong equipment
        if c.equipment_required:
            # Normalize: lowercase và loại bỏ khoảng trắng thừa
            required_lower = c.equipment_required.lower().strip()
            room_equip_lower = r.equipment.lower() if r.equipment else ""
            
            # Split theo dấu phẩy và check từng item
            required_items = [item.strip() for item in required_lower.split(',') if item.strip()]
            
            # Kiểm tra: mọi required item phải xuất hiện trong room equipment
            if not all(req_item in room_equip_lower for req_item in required_items):
                continue
        
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
            # Check if course requires TH room
            need_th = bool(c.room_type_required and 'thực hành' in c.room_type_required.lower())
            # Check if room is TH room
            room_th = bool('thực hành' in r.room_type.lower())
            # Penalty: 0 if match, 1 if non-TH course uses TH room (waste)
            th_pen = 0 if (need_th == room_th) else (0 if need_th else (1 if room_th else 0))
            slack = r.capacity - c.size
            return (th_pen, slack, d, s, tid)
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
        # Check if course needs TH room
        need_th = bool(c.room_type_required and 'thực hành' in c.room_type_required.lower())
        room_is_th = bool('thực hành' in r.room_type.lower())
        
        # Strong penalty for room type mismatch (both directions)
        if need_th != room_is_th:
            pen += 1.0  # Increased from 1.0 to prioritize correct room type
            
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
        # Check if course is TH (lab) type
        is_th_unit = bool(c.room_type_required and 'thực hành' in c.room_type_required.lower())
        # Prefer TH classes in early slots (morning)
        if not is_th_unit:
            pen += s * 0.05
    return pen

def daily_limit_compliance() -> int:
    """
    RBM-001: Giới hạn ca/ngày (≤4 slots per day per teacher)
    
    Count the number of teacher-days that comply with MAX_TEACHER_SLOTS_PER_DAY limit.
    
    Returns:
        Number of (teacher, day) pairs where teaching slots ≤ MAX_TEACHER_SLOTS_PER_DAY
        Higher is better (more compliance)
    """
    if MAX_TEACHER_SLOTS_PER_DAY is None:
        # No limit set, all days comply by default
        return sum(1 for t in teachers for d in range(DAYS) if teacher_day_slots[t.id][d] > 0)
    
    compliant_count = 0
    for t in teachers:
        for d in range(DAYS):
            slots_on_day = teacher_day_slots[t.id][d]
            if slots_on_day > 0 and slots_on_day <= MAX_TEACHER_SLOTS_PER_DAY:
                compliant_count += 1
    
    return compliant_count

def compact_days_score() -> float:
    """
    RBM-002: Giảm số ngày lên trường (minimize teaching days per teacher)
    
    Calculate score that rewards teachers with fewer teaching days per week.
    Formula: Σ(1 / days_teaching) for each teacher
    
    Example:
        - Teacher A: 3 days/week → contributes 1/3 = 0.333
        - Teacher B: 5 days/week → contributes 1/5 = 0.200
        Higher score = more teachers with concentrated schedules
    
    Returns:
        Sum of (1/days_teaching) across all teachers
        Higher is better (more compact schedules)
    """
    total_score = 0.0
    
    for t in teachers:
        # Count how many different days this teacher teaches
        days_teaching = sum(1 for d in range(DAYS) if teacher_day_slots[t.id][d] > 0)
        
        if days_teaching > 0:
            # Reward fewer days: 1 day = 1.0, 2 days = 0.5, 3 days = 0.333, etc.
            total_score += 1.0 / days_teaching
    
    return total_score

def fitness(w_scarcity: float = GlobalConfig.W_SCARCITY, w_time: float = GlobalConfig.W_TIME) -> float:
    """
    Overall objective (MAXIMIZE fitness).
    
    ✅ Weights are automatically loaded from SQL via sql_weights dict (injected from schedule_generator.py)
    
    Mapping SQL RBM → Weights:
        RBM-001 → w_daily_limit    (Giới hạn ca/ngày)
        RBM-002 → w_compact_days   (Giảm số ngày lên trường)
        RBM-003 → w_fair           (Cân bằng tải giảng dạy)
        RBM-004 → w_wish           (Thưởng nguyện vọng)
        RBM-005 → w_compact        (Tối ưu liên tục)
        RBM-006 → w_unsat          (Phạt ngoài nguyện vọng)
    
    Formula:
        Fitness = REWARDS - PENALTIES
        
        REWARDS:
          + w_fair × fairness_score          (Cân bằng tải)
          + w_wish × wish_hit                (Thưởng nguyện vọng)
          + w_daily_limit × daily_ok         (Tuân thủ giới hạn ca/ngày)
          + w_compact_days × compact_days    (Gom ngày hiệu quả)
        
        PENALTIES:
          - w_compact × gaps                 (Phạt khoảng trống)
          - w_unsat × wish_miss              (Phạt ngoài nguyện vọng)
          - w_scarcity × scarcity            (Phạt phòng khan hiếm)
          - w_time × time_policy             (Phạt thời gian không tối ưu)
    """
    # Get weights from SQL (with fallback defaults if not injected yet)
    weights = sql_weights if sql_weights else {}
    
    w_daily = weights.get('w_daily_limit', 0.90)     # RBM-001
    w_compact_days = weights.get('w_compact_days', 0.85)  # RBM-002
    w_fair = weights.get('w_fair', 1.0)             # RBM-003
    w_wish = weights.get('w_wish', 1.2)             # RBM-004
    w_comp = weights.get('w_compact', 0.5)          # RBM-005
    w_unsat = weights.get('w_unsat', 0.8)           # RBM-006
    
    # Calculate components
    fair_std = fairness_teacher_load_std()
    fair_score = 1.0 / (1.0 + fair_std)  # Convert std to score (lower std = higher score)
    
    wish_hit = wish_satisfaction_score()
    wish_miss = wish_unsatisfied_count()
    gaps = compactness_penalty()
    
    # New components (RBM-001, RBM-002)
    daily_ok = daily_limit_compliance()
    compact_days = compact_days_score()
    
    # Calculate fitness
    fitness_value = (
        # REWARDS (positive contributions)
        w_fair * fair_score +
        w_wish * wish_hit +
        w_daily * daily_ok +
        w_compact_days * compact_days +
        
        # PENALTIES (negative contributions)
        - w_comp * gaps -
        w_unsat * wish_miss -
        w_scarcity * scarcity_penalty() -
        w_time * time_policy_penalty()
    )
    
    return fitness_value


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
        # room capacity and equipment check
        room_obj = next(r for r in rooms if r.id == rid)
        if room_obj.capacity < c.size:
            errors.append(f"Room {rid} too small for course {c.id}")
        
        # Room type check
        if c.room_type_required and c.room_type_required.strip():
            if c.room_type_required.lower() not in room_obj.room_type.lower():
                errors.append(f"Room {rid} type mismatch for course {c.id}")
        
        # Equipment check
        if c.equipment_required and c.equipment_required.strip():
            required_items = [item.strip().lower() for item in c.equipment_required.split(',') if item.strip()]
            if not all(req_item in room_obj.equipment.lower() for req_item in required_items):
                errors.append(f"Room {rid} lacks equipment for course {c.id}")
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
        # Prefer to avoid using TH rooms for non-TH classes to preserve scarce resources
        def room_key(rid: int):
            r = next(rr for rr in rooms if rr.id == rid)
            # Check if course requires TH room
            need_th = bool(c.room_type_required and 'thực hành' in c.room_type_required.lower())
            # Penalty if non-TH course uses TH room
            th_penalty = 0 if need_th else (1 if 'thực hành' in r.room_type.lower() else 0)
            slack = r.capacity - c.size
            return (th_penalty, slack)
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
    # fewer teachers -> harder; longer duration -> harder; fewer candidate rooms -> harder; TH requirement earlier
    requires_th = 1 if (c.room_type_required and 'thực hành' in c.room_type_required.lower()) else 0
    return (len(c.candidate_teachers), -c.duration, len(candidate_rooms_for_course[c.id]), -requires_th)

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
    # ⚠️ DO NOT reset random seed here - it breaks randomness across multiple calls
    # The global seed should only be set once at module level
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
    """
    Multi-start initialization: try N different random initializations and pick the best.
    Each call to init_hybrid uses the current random state (not a fixed seed).
    """
    best = None
    best_fit = float('inf')
    for s in range(N):
        # ✅ No longer passing seed parameter - uses global random state
        ok, g = init_hybrid()
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
    """
    Initialize GA population with a mix of greedy-decoded and random solutions.
    Uses current random state (no fixed seeds) for diversity across runs.
    """
    pop: List[Individual] = []
    seeds = int(mu*greedy_share)
    for s in range(seeds):
        # ✅ No longer passing seed parameter - uses global random state
        ok, g = init_hybrid()
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
                # Check if course requires TH room
                need_th = bool(c.room_type_required and 'thực hành' in c.room_type_required.lower())
                # Penalty if non-TH course uses TH room
                th_penalty = 0 if need_th else (1 if 'thực hành' in r.room_type.lower() else 0)
                slack = r.capacity - c.size
                return (th_penalty, slack)
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
            "RoomType": c.room_type_required or "-",
            "Equipment": c.equipment_required or "-",
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


# ============================================================================
# ✅ SQL VERSION - Module designed for external data injection
# ============================================================================
# This file is a modified version of greedy_heuristic_ga_algorithm.py
# 
# KEY DIFFERENCES:
# 1. NO random data generation (removed lines 142-324 from original)
# 2. NO auto-run on import (removed __main__ block)
# 3. Data (teachers, rooms, courses) must be injected externally
# 4. Algorithm logic is 100% IDENTICAL to original
#
# USAGE:
#   import greedy_heuristic_ga_algorithm_sql as ga_mod
#   ga_mod.teachers = [...]  # Inject from SQL
#   ga_mod.rooms = [...]     # Inject from SQL
#   ga_mod.courses = [...]   # Inject from SQL
#   ga_mod.build_option_lists()
