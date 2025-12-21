#!/usr/bin/env python3
"""Analyze S7 penalty in solution to debug TeacherWorkingDaysNeighborhood."""

import sys
from pathlib import Path
from collections import Counter

# Import from algo_new
from algo_new import parse_instance, TimetableState

def main():
    instance = parse_instance(Path('dot1.ctt'))
    
    # Load solution
    state = TimetableState(instance)
    with open('test_dot_2.sol', 'r') as f:
        lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line or line == '0':
                continue
            parts = line.split()
            if len(parts) == 3:
                course_id, room_id, period = parts
                # Find course_idx
                course_idx = next((i for i, c in enumerate(instance.courses) if c.id == course_id), None)
                if course_idx is not None:
                    for lid in instance.course_lecture_ids[course_idx]:
                        if lid not in state.assignments:
                            room_idx = next((i for i, r in enumerate(instance.rooms) if r.id == room_id), 0)
                            state.move_lecture(lid, int(period), room_idx, commit=True)
                            break
    
    print('=== ANALYSIS: Teacher Working Days (S7) ===')
    print(f'Total lectures: {len(state.assignments)}')
    
    # Analyze S7
    teacher_penalties = []
    for teacher_name in instance.teachers:
        penalty = state._compute_teacher_working_days_penalty(teacher_name)
        if penalty > 0:
            teacher_penalties.append((penalty, teacher_name))
    
    teacher_penalties.sort(reverse=True)
    print(f'\nTotal teachers with penalty: {len(teacher_penalties)}')
    print(f'Total S7 penalty: {sum(p for p, _ in teacher_penalties)}')
    
    print('\n=== Top 15 Teachers with S7 Penalty ===')
    for i, (penalty, teacher_name) in enumerate(teacher_penalties[:15], 1):
        # Get lectures
        lectures = []
        if teacher_name in state.teacher_course_lectures:
            for course_idx, lecs in state.teacher_course_lectures[teacher_name].items():
                for lid, assign in lecs.items():
                    if assign:
                        period, room = assign
                        day, slot = instance.period_to_slot(period)
                        lectures.append({'lid': lid, 'day': day, 'slot': slot, 'period': period, 'room': room})
        
        if not lectures:
            continue
        
        lectures.sort(key=lambda x: (x['day'], x['slot']))
        
        # Count days
        day_counts = Counter(lec['day'] for lec in lectures)
        days_used = len(day_counts)
        
        # Check preferences
        preferred_periods = instance.teacher_preferred_periods.get(teacher_name, set())
        preferred_days = set(instance.period_to_slot(p)[0] for p in preferred_periods) if preferred_periods else set()
        
        # Calculate theoretical min
        theoretical_min = (len(lectures) + instance.periods_per_day - 1) // instance.periods_per_day
        
        # Calculate preference-based min
        if preferred_days:
            # Count capacity per preferred day
            days_capacity = []
            for day in sorted(preferred_days):
                capacity = sum(1 for p in preferred_periods if instance.period_to_slot(p)[0] == day)
                days_capacity.append((day, capacity))
            
            days_capacity.sort(key=lambda x: -x[1])
            
            remaining = len(lectures)
            min_pref_days = 0
            for day, cap in days_capacity:
                if remaining <= 0:
                    break
                remaining -= cap
                min_pref_days += 1
            
            min_feasible = max(min_pref_days, theoretical_min)
        else:
            min_feasible = theoretical_min
        
        print(f'\n{i}. Teacher: {teacher_name}')
        print(f'   Penalty: {penalty} | Lectures: {len(lectures)} | Days used: {days_used}')
        print(f'   Theoretical min: {theoretical_min} | Preference-based min: {min_feasible}')
        print(f'   Preferred days: {sorted(preferred_days) if preferred_days else "NONE"}')
        print(f'   Day distribution: {dict(sorted(day_counts.items()))}')
        
        # Identify sparse days (1-2 lectures)
        sparse_days = [(day, count) for day, count in day_counts.items() if count <= 2]
        dense_days = [(day, count) for day, count in day_counts.items() if count >= 3]
        
        if sparse_days:
            print(f'   SPARSE days (≤2 lecs): {sparse_days}')
        if dense_days:
            print(f'   DENSE days (≥3 lecs): {dense_days}')
        
        # Show sample lectures on sparse days
        if sparse_days:
            sparse_day = sparse_days[0][0]
            lecs_on_sparse = [lec for lec in lectures if lec['day'] == sparse_day]
            print(f'   Sample sparse day {sparse_day}: {lecs_on_sparse}')
            
            # Check if we can move these lectures
            for lec in lecs_on_sparse[:2]:
                lid = lec['lid']
                course_idx = instance.lectures[lid].course
                feasible_periods = instance.feasible_periods[course_idx]
                
                # Count how many feasible periods on dense days
                if dense_days:
                    dense_day = dense_days[0][0]
                    feasible_on_dense = [p for p in feasible_periods if instance.period_to_slot(p)[0] == dense_day]
                    print(f'      Lecture {lid}: {len(feasible_on_dense)} feasible periods on dense day {dense_day}')

    print('\n=== Teacher Preference Coverage ===')
    teachers_with_prefs = sum(1 for t in instance.teachers if instance.teacher_preferred_periods.get(t))
    print(f'Teachers with preferences: {teachers_with_prefs}/{len(instance.teachers)}')
    
    # Sample some preferences
    print('\nSample teacher preferences:')
    count = 0
    for teacher_name in instance.teachers[:10]:
        prefs = instance.teacher_preferred_periods.get(teacher_name, set())
        if prefs:
            pref_days = set(instance.period_to_slot(p)[0] for p in prefs)
            print(f'  {teacher_name}: {len(prefs)} periods across {len(pref_days)} days')
            count += 1
            if count >= 5:
                break

if __name__ == '__main__':
    main()
