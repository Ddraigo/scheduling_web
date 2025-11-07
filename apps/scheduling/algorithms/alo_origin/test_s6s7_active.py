"""Test script to verify S6 and S7 are actively computed during optimization."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from algo_new import *
import random
import time

def test_s6_s7_tracking():
    """Test that S6/S7 penalties are tracked during optimization."""
    
    # Parse instance
    instance = parse_instance("dot1.ctt")
    rng = random.Random(42)
    
    # Build initial solution
    start = time.time()
    state = build_initial_solution(instance, rng, "greedy-cprop", start, 10.0)
    
    print("=" * 70)
    print("INITIAL SOLUTION (before optimization):")
    print("=" * 70)
    print(f"S6 counter (soft_teacher_lecture_consolidation): {state.soft_teacher_lecture_consolidation}")
    print(f"S7 counter (soft_teacher_working_days): {state.soft_teacher_working_days}")
    
    # Calculate S6/S7 manually to verify
    s6_manual = sum(state._compute_teacher_lecture_consolidation_penalty(t) for t in range(len(instance.teachers)))
    s7_manual = sum(state._compute_teacher_working_days_penalty(t) for t in range(len(instance.teachers)))
    print(f"\nS6 calculated manually: {s6_manual}")
    print(f"S7 calculated manually: {s7_manual}")
    print(f"Current cost (weighted): {state.current_cost}")
    
    # Enable optimization phase
    print("\n" + "=" * 70)
    print("ENABLING OPTIMIZATION PHASE...")
    print("=" * 70)
    state._optimization_phase = True
    
    # Try one move to see if S6/S7 get updated
    print("\nTesting move to verify S6/S7 tracking...")
    neighborhoods = [
        TeacherWorkingDaysNeighborhood(),
        TeacherLectureConsolidationNeighborhood(),
        MoveLectureNeighborhood(),
    ]
    
    # Try to generate a move
    for neighborhood in neighborhoods:
        move = neighborhood.generate_candidate(state, rng)
        if move:
            print(f"\nGenerated move from: {neighborhood.name}")
            
            # Evaluate and apply move
            delta = move.evaluate(state)
            if delta is not None:
                print(f"Move delta: {delta}")
                print(f"S6 before move: {state.soft_teacher_lecture_consolidation}")
                print(f"S7 before move: {state.soft_teacher_working_days}")
                
                actual_delta = move.apply(state)
                
                print(f"S6 after move: {state.soft_teacher_lecture_consolidation}")
                print(f"S7 after move: {state.soft_teacher_working_days}")
                print(f"Actual delta: {actual_delta}")
                
                # Verify manually
                s6_after = sum(state._compute_teacher_lecture_consolidation_penalty(t) for t in range(len(instance.teachers)))
                s7_after = sum(state._compute_teacher_working_days_penalty(t) for t in range(len(instance.teachers)))
                print(f"\nS6 calculated manually after: {s6_after}")
                print(f"S7 calculated manually after: {s7_after}")
                break
    
    print("\n" + "=" * 70)
    print("FINAL VERIFICATION:")
    print("=" * 70)
    breakdown = state.score_breakdown()
    print(f"score_breakdown().teacher_lecture_consolidation (S6): {breakdown.teacher_lecture_consolidation}")
    print(f"score_breakdown().teacher_working_days (S7): {breakdown.teacher_working_days}")
    print(f"Total cost: {breakdown.total}")
    
    # Check if S6/S7 are non-zero
    if breakdown.teacher_lecture_consolidation > 0:
        print("\n✅ S6 (Teacher Lecture Consolidation) IS ACTIVE!")
    else:
        print("\n⚠️  S6 penalty is 0 (may be optimal or not tracking)")
    
    if breakdown.teacher_working_days > 0:
        print("✅ S7 (Teacher Working Days) IS ACTIVE!")
    else:
        print("⚠️  S7 penalty is 0 (may be optimal or not tracking)")
    
    return breakdown

if __name__ == "__main__":
    test_s6_s7_tracking()
