#!/usr/bin/env python3
"""
Diagnostic script để kiểm tra initial solution quality.

Chạy:
  python diagnose_init.py dot1.ctt
"""

import sys
import time
import random
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from algo_new import (
    parse_instance, build_initial_solution, TimetableState
)


def diagnose_initial_solution(ctt_file: str, seed: int = 42):
    """Diagnose initial solution quality."""
    print(f"=" * 70)
    print(f" Diagnostics: Initial Solution Quality")
    print(f"=" * 70)
    
    # Parse instance
    print(f"\n📖 Parsing instance: {ctt_file}")
    instance = parse_instance(ctt_file)
    print(f"  ✓ Courses: {len(instance.courses)}")
    print(f"  ✓ Rooms: {len(instance.rooms)}")
    print(f"  ✓ Days: {instance.days}")
    print(f"  ✓ Periods: {instance.periods_per_day}")
    print(f"  ✓ Total slots: {instance.days * instance.periods_per_day}")
    
    # Build initial solution
    print(f"\n🔨 Building initial solution (greedy-cprop)...")
    rng = random.Random(seed)
    start_time = time.time()
    state = build_initial_solution(instance, rng, "greedy-cprop", start_time, 30.0)  # Increased from 5.0 to 30.0
    elapsed = time.time() - start_time
    
    print(f"  ✓ Elapsed: {elapsed:.2f}s")
    print(f"  ✓ Initial cost: {state.current_cost}")
    
    # Breakdown
    print(f"\n Cost breakdown:")
    breakdown = state.score_breakdown()
    print(f"  - Room Capacity: {breakdown.room_capacity}")
    print(f"  - Min Working Days: {breakdown.min_working_days}")
    print(f"  - Curriculum Compactness: {breakdown.curriculum_compactness}")
    print(f"  - Lecture Consecutiveness: {breakdown.lecture_consecutiveness}")
    print(f"  - Room Stability: {breakdown.room_stability}")
    print(f"  - Teacher Preferences: {breakdown.teacher_preference_violations}")
    print(f"  - TOTAL SOFT: {breakdown.total}")
    
    # Hard constraints
    print(f"\n✅ Hard constraints check:")
    hard_ok = state.check_hard_constraints()
    print(f"  - Valid: {hard_ok}")
    
    # Utilization
    print(f"\n📈 Utilization:")
    scheduled = len(state.assignments)
    total_lectures = sum(c.lectures for c in instance.courses)
    print(f"  - Scheduled lectures: {scheduled}/{total_lectures}")
    print(f"  - Coverage: {100*scheduled/total_lectures:.1f}%")
    
    # Room utilization
    room_usage = {}
    for course_id, (room_id, _) in state.assignments.items():
        room_usage[room_id] = room_usage.get(room_id, 0) + 1
    
    if room_usage:
        avg_usage = sum(room_usage.values()) / len(room_usage)
        print(f"  - Avg lectures per room: {avg_usage:.1f}")
        print(f"  - Max usage: {max(room_usage.values())}")
        print(f"  - Min usage: {min(room_usage.values())}")
    
    # Try alternative init strategy
    print(f"\n🔨 Building initial solution (random-repair)...")
    rng2 = random.Random(seed)
    start_time2 = time.time()
    state2 = build_initial_solution(instance, rng2, "random-repair", start_time2, 30.0)  # Increased from 5.0
    elapsed2 = time.time() - start_time2
    
    print(f"  ✓ Elapsed: {elapsed2:.2f}s")
    print(f"  ✓ Initial cost: {state2.current_cost}")
    
    breakdown2 = state2.score_breakdown()
    print(f"\n Cost breakdown (random-repair):")
    print(f"  - Room Capacity: {breakdown2.room_capacity}")
    print(f"  - Min Working Days: {breakdown2.min_working_days}")
    print(f"  - Curriculum Compactness: {breakdown2.curriculum_compactness}")
    print(f"  - Lecture Consecutiveness: {breakdown2.lecture_consecutiveness}")
    print(f"  - Room Stability: {breakdown2.room_stability}")
    print(f"  - Teacher Preferences: {breakdown2.teacher_preference_violations}")
    total2 = breakdown2.total
    print(f"  - TOTAL SOFT: {total2}")
    
    # Comparison
    print(f"\n🔄 Comparison:")
    print(f"  - greedy-cprop: {state.current_cost}")
    print(f"  - random-repair: {state2.current_cost}")
    if state.current_cost < state2.current_cost:
        print(f"  - Winner: greedy-cprop ({state2.current_cost - state.current_cost} better)")
    else:
        print(f"  - Winner: random-repair ({state.current_cost - state2.current_cost} better)")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    if state.current_cost > 100000:
        print(f"  ⚠️  Initial solution quality is POOR (cost > 100K)")
        print(f"      - Increase initial construction time")
        print(f"      - Or use better heuristic for greedy assignment")
    elif state.current_cost > 50000:
        print(f"  ⚠️  Initial solution quality is FAIR (cost 50-100K)")
    else:
        print(f"  ✓ Initial solution quality is GOOD (cost < 50K)")
    
    if not hard_ok:
        print(f"  ⚠️  Hard constraints violated!")
        print(f"      - Check constraint propagation")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {Path(__file__).name} <instance.ctt>")
        sys.exit(1)
    
    ctt_file = sys.argv[1]
    if not Path(ctt_file).exists():
        print(f"❌ File not found: {ctt_file}")
        sys.exit(1)
    
    diagnose_initial_solution(ctt_file)
