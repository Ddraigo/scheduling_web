#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script kiểm tra logic TeacherConsolidation constraint
Phân tích xem violations có hợp lý không (cùng course type hay khác course type)
"""

import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent / 'apps' / 'scheduling' / 'algorithms' / 'alo_origin'))

from validator import Faculty, Timetable


def analyze_consolidation_logic(instance_file: str, solution_file: str):
    """Phân tích chi tiết logic của TeacherConsolidation constraint."""
    
    faculty = Faculty(instance_file)
    timetable = Timetable(faculty, solution_file)
    
    ppd = faculty.periods_per_day
    
    print("=" * 100)
    print("🔍 PHÂN TÍCH LOGIC TEACHER CONSOLIDATION CONSTRAINT")
    print("=" * 100)
    
    # Group lectures by teacher
    teacher_lectures: Dict[str, List[Dict]] = {}
    
    for c in range(faculty.courses):
        course = faculty.course_vect[c]
        teacher_name = course.teacher
        
        if teacher_name not in teacher_lectures:
            teacher_lectures[teacher_name] = []
        
        for p in range(faculty.periods):
            room_id = timetable(c, p)
            if room_id != 0:
                day = p // ppd
                period_in_day = p % ppd
                teacher_lectures[teacher_name].append({
                    'day': day,
                    'period_in_day': period_in_day,
                    'absolute_period': p,
                    'room_id': room_id,
                    'room_name': faculty.room_vect[room_id - 1].name,
                    'room_type': faculty.room_vect[room_id - 1].room_type,
                    'course_idx': c,
                    'course_name': course.name,
                    'course_type': course.course_type,
                    'equipment': course.equipment
                })
    
    # Analyze violations
    legitimate_violations = []  # Cùng type, nên dùng cùng phòng
    justified_changes = []       # Khác type, phải đổi phòng
    
    for teacher_name, lectures in teacher_lectures.items():
        if len(lectures) <= 1:
            continue
        
        # Sort by day, then period
        lectures.sort(key=lambda x: (x['day'], x['period_in_day']))
        
        # Check consecutive pairs
        for i in range(len(lectures) - 1):
            lec1 = lectures[i]
            lec2 = lectures[i + 1]
            
            # Only check consecutive lectures on same day
            if lec1['day'] == lec2['day'] and lec2['period_in_day'] == lec1['period_in_day'] + 1:
                
                # Check if room changes
                if lec1['room_id'] != lec2['room_id']:
                    violation = {
                        'teacher': teacher_name,
                        'day': lec1['day'],
                        'period1': lec1['period_in_day'],
                        'period2': lec2['period_in_day'],
                        'course1': lec1['course_name'],
                        'course2': lec2['course_name'],
                        'course1_type': lec1['course_type'],
                        'course2_type': lec2['course_type'],
                        'room1': lec1['room_name'],
                        'room2': lec2['room_name'],
                        'room1_type': lec1['room_type'],
                        'room2_type': lec2['room_type'],
                        'equipment1': lec1['equipment'],
                        'equipment2': lec2['equipment']
                    }
                    
                    # Check if same course type
                    if lec1['course_type'] == lec2['course_type']:
                        # Same type → should use same room → LEGITIMATE VIOLATION
                        legitimate_violations.append(violation)
                    else:
                        # Different type → must change room → JUSTIFIED CHANGE
                        justified_changes.append(violation)
    
    # Print statistics
    print(f"\n📊 THỐNG KÊ:")
    print(f"  - Tổng violations: {len(legitimate_violations) + len(justified_changes)}")
    print(f"  - ✅ Legitimate violations (cùng type, nên dùng cùng phòng): {len(legitimate_violations)}")
    print(f"  - ❌ Justified changes (khác type, phải đổi phòng): {len(justified_changes)}")
    
    # Print legitimate violations
    if legitimate_violations:
        print(f"\n{'=' * 100}")
        print(f"✅ LEGITIMATE VIOLATIONS (NÊN PHẠT - cùng course type):")
        print(f"{'=' * 100}")
        
        for i, v in enumerate(legitimate_violations[:20], 1):
            print(f"\n{i}. {v['teacher']} - Day {v['day']}, P{v['period1']}→P{v['period2']}:")
            print(f"   - Course 1: {v['course1']} (type={v['course1_type']})")
            print(f"   - Course 2: {v['course2']} (type={v['course2_type']})")
            print(f"   - Room: {v['room1']} ({v['room1_type']}) → {v['room2']} ({v['room2_type']})")
            print(f"   - Equipment: {v['equipment1']} → {v['equipment2']}")
            print(f"   💡 Cùng type {v['course1_type']} → NÊN dùng cùng phòng")
    
    # Print justified changes
    if justified_changes:
        print(f"\n{'=' * 100}")
        print(f"❌ JUSTIFIED CHANGES (KHÔNG NÊN PHẠT - khác course type):")
        print(f"{'=' * 100}")
        
        for i, v in enumerate(justified_changes[:20], 1):
            print(f"\n{i}. {v['teacher']} - Day {v['day']}, P{v['period1']}→P{v['period2']}:")
            print(f"   - Course 1: {v['course1']} (type={v['course1_type']})")
            print(f"   - Course 2: {v['course2']} (type={v['course2_type']})")
            print(f"   - Room: {v['room1']} ({v['room1_type']}) → {v['room2']} ({v['room2_type']})")
            print(f"   - Equipment: {v['equipment1']} → {v['equipment2']}")
            print(f"   💡 Khác type ({v['course1_type']}→{v['course2_type']}) → PHẢI đổi phòng")
    
    # Conclusion
    print(f"\n{'=' * 100}")
    print(f"💡 KẾT LUẬN:")
    print(f"{'=' * 100}")
    
    if justified_changes:
        print(f"\n⚠️  CONSTRAINT LOGIC SAI!")
        print(f"   - Có {len(justified_changes)} room changes BẮT BUỘC do khác course type")
        print(f"   - Những trường hợp này KHÔNG NÊN bị phạt")
        print(f"\n📝 CÁCH SỬA:")
        print(f"   1. Trong validator.py, hàm costs_on_teacher_lecture_consolidation():")
        print(f"      → Chỉ phạt nếu course1.course_type == course2.course_type")
        print(f"   2. Trong algo_new.py, hàm _compute_teacher_lecture_consolidation_penalty():")
        print(f"      → Chỉ phạt nếu cùng course type")
    else:
        print(f"\n✅ CONSTRAINT LOGIC ĐÚNG!")
        print(f"   - Tất cả {len(legitimate_violations)} violations đều hợp lý")
        print(f"   - Không có room changes bắt buộc do khác course type")
    
    print(f"\n📈 ĐIỂM CẢI THIỆN:")
    if justified_changes:
        print(f"   - Cost hiện tại: {len(legitimate_violations) + len(justified_changes)}")
        print(f"   - Cost sau khi sửa: {len(legitimate_violations)}")
        print(f"   - Giảm: {len(justified_changes)} điểm ({len(justified_changes) / (len(legitimate_violations) + len(justified_changes)) * 100:.1f}%)")
    
    return len(legitimate_violations), len(justified_changes)


def main():
    if len(sys.argv) != 3:
        print("Usage: python check_consolidation_logic.py <instance.ctt> <solution.sol>")
        sys.exit(1)
    
    instance_file = sys.argv[1]
    solution_file = sys.argv[2]
    
    try:
        legit, justified = analyze_consolidation_logic(instance_file, solution_file)
        print(f"\n✅ Phân tích hoàn tất:")
        print(f"   - Legitimate: {legit}")
        print(f"   - Justified: {justified}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
