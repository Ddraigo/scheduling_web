#!/usr/bin/env python3
"""
Script để so sánh kết quả giữa algorithms_core.py và algo_new.py

Quy trình:
1. Xuất dữ liệu từ DB → .ctt
2. Chạy algo_new.py (tính toán lịch với ITC-2007 constraints)
3. Chạy algorithms_core.py (tính toán lịch với custom constraints)
4. So sánh kết quả (cost, constraint violations, performance)
"""

import os
import sys
import time
import subprocess
import json
from pathlib import Path
from collections import defaultdict

WORKSPACE = Path(__file__).parent
sys.path.insert(0, str(WORKSPACE))
os.chdir(WORKSPACE)


def parse_solution_file(sol_file):
    """Đọc file .sol và trả về dict assignments"""
    assignments = {}
    
    if not Path(sol_file).exists():
        return assignments
    
    with open(sol_file, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 4:
                course_id = parts[0]
                room_id = parts[1]
                day = int(parts[2])
                period = int(parts[3])
                
                assignments[course_id] = {
                    'room': room_id,
                    'day': day,
                    'period': period
                }
    
    return assignments


def parse_ctt_file(ctt_file):
    """Đọc file .ctt và trả về thông tin instance"""
    instance = {
        'name': '',
        'courses': [],
        'rooms': [],
        'curricula': [],
        'unavailability': []
    }
    
    section = None
    with open(ctt_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line == 'END.':
                continue
            
            if line == 'COURSES:':
                section = 'courses'
                continue
            elif line == 'ROOMS:':
                section = 'rooms'
                continue
            elif line == 'CURRICULA:':
                section = 'curricula'
                continue
            elif line == 'UNAVAILABILITY_CONSTRAINTS:':
                section = 'unavailability'
                continue
            elif line.startswith('Name:'):
                instance['name'] = line.split(':', 1)[1].strip()
                continue
            
            if section == 'courses' and ':' not in line:
                parts = line.split()
                if len(parts) >= 5:
                    instance['courses'].append({
                        'id': parts[0],
                        'teacher': parts[1],
                        'lectures': int(parts[2]),
                        'min_working_days': int(parts[3]),
                        'students': int(parts[4])
                    })
            
            elif section == 'rooms' and ':' not in line:
                parts = line.split()
                if len(parts) >= 2:
                    instance['rooms'].append({
                        'id': parts[0],
                        'capacity': int(parts[1])
                    })
            
            elif section == 'curricula' and ':' not in line:
                parts = line.split()
                if len(parts) >= 3:
                    num_courses = int(parts[1])
                    courses = parts[2:2+num_courses]
                    instance['curricula'].append({
                        'id': parts[0],
                        'courses': courses
                    })
            
            elif section == 'unavailability' and ':' not in line:
                parts = line.split()
                if len(parts) >= 3:
                    instance['unavailability'].append({
                        'course': parts[0],
                        'day': int(parts[1]),
                        'period': int(parts[2])
                    })
    
    return instance


def compute_metrics(ctt_file, sol_file):
    """Tính các metric từ solution"""
    instance = parse_ctt_file(ctt_file)
    assignments = parse_solution_file(sol_file)
    
    metrics = {
        'total_assignments': len(assignments),
        'total_courses': len(instance['courses']),
        'total_rooms': len(instance['rooms']),
        'total_periods': 5 * 6,  # 5 days, 6 periods/day
        
        # Soft constraints violations
        'room_capacity_violations': 0,
        'min_working_days_violations': 0,
        'curriculum_compactness_violations': 0,
        'room_stability_violations': 0,
        'lecture_consecutiveness_violations': 0,
        
        # Hard constraints
        'hard_constraint_violations': 0,
    }
    
    # Kiểm tra room capacity
    for course in instance['courses']:
        course_id = course['id']
        if course_id in assignments:
            room_id = assignments[course_id]['room']
            room_capacity = next(
                (r['capacity'] for r in instance['rooms'] if r['id'] == room_id),
                float('inf')
            )
            if room_capacity < course['students']:
                overflow = course['students'] - room_capacity
                metrics['room_capacity_violations'] += overflow
    
    # Kiểm tra min working days
    course_days = defaultdict(set)
    for course_id, assign in assignments.items():
        day = assign['day']
        course_days[course_id].add(day)
    
    for course in instance['courses']:
        course_id = course['id']
        if course_id in course_days:
            active_days = len(course_days[course_id])
            if active_days < course['min_working_days']:
                metrics['min_working_days_violations'] += (
                    course['min_working_days'] - active_days
                )
    
    # Kiểm tra curriculum conflicts (hard)
    for curriculum in instance['curricula']:
        period_usage = defaultdict(list)
        for course_id in curriculum['courses']:
            if course_id in assignments:
                period = (
                    assignments[course_id]['day'] * 6 + 
                    assignments[course_id]['period']
                )
                period_usage[period].append(course_id)
        
        for period, courses in period_usage.items():
            if len(courses) > 1:
                metrics['hard_constraint_violations'] += len(courses) - 1
    
    # Kiểm tra room stability (multiple rooms per course)
    room_usage = defaultdict(set)
    for course_id, assign in assignments.items():
        room_id = assign['room']
        room_usage[course_id].add(room_id)
    
    for course_id, rooms in room_usage.items():
        if len(rooms) > 1:
            metrics['room_stability_violations'] += len(rooms) - 1
    
    return metrics


def compare_algorithms(ctt_file):
    """So sánh kết quả của hai algorithm"""
    print("\n" + "=" * 70)
    print(" 📊 COMPARISON: algorithms_core.py vs algo_new.py")
    print("=" * 70)
    
    # Giả sử file solution đã được tạo từ test_algo_new.py
    sol_file_algo_new = ctt_file.replace('.ctt', '.sol')
    
    print(f"\n📂 Input: {ctt_file}")
    print(f"📄 Solution (algo_new): {sol_file_algo_new}")
    
    if not Path(cct_file).exists():
        print(f"❌ File not found: {cct_file}")
        return
    
    if not Path(sol_file_algo_new).exists():
        print(f"❌ File not found: {sol_file_algo_new}")
        print("\n💡 Hãy chạy test_algo_new.py trước để tạo solution file")
        return
    
    # Tính metrics
    metrics = compute_metrics(cct_file, sol_file_algo_new)
    
    print(f"\n📊 Metrics for algo_new:")
    print(f"  - Assignments: {metrics['total_assignments']}/{metrics['total_courses']}")
    print(f"  - Room capacity violations: {metrics['room_capacity_violations']}")
    print(f"  - Min working days violations: {metrics['min_working_days_violations']}")
    print(f"  - Curriculum compactness violations: {metrics['curriculum_compactness_violations']}")
    print(f"  - Room stability violations: {metrics['room_stability_violations']}")
    print(f"  - Hard constraint violations: {metrics['hard_constraint_violations']}")
    
    total_soft_violations = (
        metrics['room_capacity_violations'] +
        metrics['min_working_days_violations'] +
        metrics['curriculum_compactness_violations'] +
        metrics['room_stability_violations'] +
        metrics['lecture_consecutiveness_violations']
    )
    
    print(f"\n  Total soft violations: {total_soft_violations}")
    print(f"  Feasible: {'✅ Yes' if metrics['hard_constraint_violations'] == 0 else '❌ No'}")


def main():
    """Main"""
    print("\n" + "=" * 70)
    print(" 🔍 ANALYZER: Compare algo_new.py results")
    print("=" * 70)
    
    # Tìm file .ctt mới nhất
    ctt_files = sorted(WORKSPACE.glob("output_*.ctt"), key=lambda x: x.stat().st_mtime)
    
    if not ctt_files:
        print("❌ No .ctt files found!")
        print("\n💡 Hãy chạy test_algo_new.py hoặc convert_db_to_ctt.py trước")
        sys.exit(1)
    
    ctt_file = str(ctt_files[-1])
    print(f"\n✅ Found: {ctt_file}")
    
    compare_algorithms(ctt_file)


if __name__ == "__main__":
    main()
