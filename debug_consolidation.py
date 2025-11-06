#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script debug Teacher Lecture Consolidation cost
Phân tích tại sao cost lại cao và có phải do nguyện vọng ảnh hưởng không
"""

import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / 'apps' / 'scheduling' / 'algorithms' / 'alo_origin'))

from validator import Faculty, Timetable


def analyze_teacher_consolidation(instance_file: str, solution_file: str):
    """Phân tích chi tiết Teacher Lecture Consolidation violations."""
    
    faculty = Faculty(instance_file)
    timetable = Timetable(faculty, solution_file)
    
    ppd = faculty.periods_per_day
    
    print("=" * 100)
    print("🔍 PHÂN TÍCH TEACHER LECTURE CONSOLIDATION")
    print("=" * 100)
    
    # Group lectures by teacher
    teacher_lectures: Dict[str, List[Tuple]] = {}
    
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
                    'course_idx': c,
                    'course_name': course.name
                })
    
    # Analyze consolidation violations
    total_violations = 0
    total_consecutive_pairs = 0
    total_room_changes = 0
    
    teachers_with_violations = []
    
    for teacher_name, lectures in teacher_lectures.items():
        if len(lectures) <= 1:
            continue
        
        # Sort by day, then period
        lectures.sort(key=lambda x: (x['day'], x['period_in_day']))
        
        # Count consecutive pairs and room changes
        consecutive_pairs = 0
        room_changes = 0
        violations_detail = []
        
        for i in range(len(lectures) - 1):
            lec1 = lectures[i]
            lec2 = lectures[i + 1]
            
            # Check if consecutive (same day, consecutive periods)
            if lec1['day'] == lec2['day'] and lec2['period_in_day'] == lec1['period_in_day'] + 1:
                consecutive_pairs += 1
                
                # Check if room changes
                if lec1['room_id'] != lec2['room_id']:
                    room_changes += 1
                    violations_detail.append({
                        'day': lec1['day'],
                        'period1': lec1['period_in_day'],
                        'period2': lec2['period_in_day'],
                        'course1': lec1['course_name'],
                        'course2': lec2['course_name'],
                        'room1': lec1['room_name'],
                        'room2': lec2['room_name']
                    })
        
        if room_changes > 0:
            teachers_with_violations.append({
                'teacher': teacher_name,
                'total_lectures': len(lectures),
                'consecutive_pairs': consecutive_pairs,
                'room_changes': room_changes,
                'violations': violations_detail,
                'lectures': lectures
            })
        
        total_consecutive_pairs += consecutive_pairs
        total_room_changes += room_changes
        total_violations += room_changes
    
    # Print summary
    print(f"\n📊 TỔNG QUAN:")
    print(f"  - Tổng số giảng viên: {len(teacher_lectures)}")
    print(f"  - GV có consecutive pairs: {sum(1 for t, l in teacher_lectures.items() if len(l) > 1)}")
    print(f"  - Tổng consecutive pairs: {total_consecutive_pairs}")
    print(f"  - Tổng room changes (violations): {total_room_changes}")
    print(f"  - GV có violations: {len(teachers_with_violations)}")
    
    # Sort by most violations
    teachers_with_violations.sort(key=lambda x: x['room_changes'], reverse=True)
    
    # Print top violators
    print(f"\n{'=' * 100}")
    print(f"📋 TOP 10 GIẢNG VIÊN CÓ NHIỀU ROOM CHANGES NHẤT:")
    print(f"{'=' * 100}")
    
    for i, teacher_data in enumerate(teachers_with_violations[:10], 1):
        print(f"\n{i}. Giảng viên: {teacher_data['teacher']}")
        print(f"   - Tổng lectures: {teacher_data['total_lectures']}")
        print(f"   - Consecutive pairs: {teacher_data['consecutive_pairs']}")
        print(f"   - Room changes: {teacher_data['room_changes']} ⚠️")
        
        print(f"   - Chi tiết violations:")
        for v in teacher_data['violations']:
            print(f"     • Day {v['day']}, Period {v['period1']}→{v['period2']}: "
                  f"{v['course1']} ({v['room1']}) → {v['course2']} ({v['room2']})")
    
    # Check if teacher preferences are causing the problem
    print(f"\n{'=' * 100}")
    print(f"🎯 PHÂN TÍCH ẢNH HƯỞNG CỦA NGUYỆN VỌNG:")
    print(f"{'=' * 100}")
    
    # Get teacher preferences
    teacher_preferences = timetable.teacher_preferred_periods
    
    print(f"\nTổng số GV có nguyện vọng: {len(teacher_preferences)}")
    
    # Check if violating teachers have preferences
    violators_with_prefs = []
    violators_without_prefs = []
    
    for teacher_data in teachers_with_violations:
        teacher_name = teacher_data['teacher']
        if teacher_name in teacher_preferences:
            violators_with_prefs.append(teacher_data)
        else:
            violators_without_prefs.append(teacher_data)
    
    print(f"  - GV có violations + có nguyện vọng: {len(violators_with_prefs)}")
    print(f"  - GV có violations + KHÔNG có nguyện vọng: {len(violators_without_prefs)}")
    
    # Analyze if preferences force room changes
    print(f"\n📍 PHÂN TÍCH CHI TIẾT 5 GV CÓ NGUYỆN VỌNG VÀ NHIỀU VIOLATIONS:")
    
    for i, teacher_data in enumerate(violators_with_prefs[:5], 1):
        teacher_name = teacher_data['teacher']
        prefs = teacher_preferences[teacher_name]
        
        print(f"\n{i}. {teacher_name}:")
        print(f"   - Nguyện vọng: {len(prefs)} periods")
        print(f"   - Violations: {teacher_data['room_changes']}")
        
        # Check each violation
        for v in teacher_data['violations']:
            day = v['day']
            p1 = v['period1']
            p2 = v['period2']
            
            pref1 = (day, p1) in prefs
            pref2 = (day, p2) in prefs
            
            print(f"     • Day {day}, P{p1}→P{p2}: {v['course1']}→{v['course2']}")
            print(f"       Room: {v['room1']} → {v['room2']}")
            print(f"       Preferred? P{p1}={'✅' if pref1 else '❌'}, P{p2}={'✅' if pref2 else '❌'}")
    
    # Check room availability patterns
    print(f"\n{'=' * 100}")
    print(f"🏛️  PHÂN TÍCH KHẢ NĂNG PHÒNG TRỐNG:")
    print(f"{'=' * 100}")
    
    # For top 3 violators, check if room was available
    for i, teacher_data in enumerate(teachers_with_violations[:3], 1):
        print(f"\n{i}. {teacher_data['teacher']}:")
        
        for v in teacher_data['violations']:
            day = v['day']
            p1 = v['period1']
            p2 = v['period2']
            
            # Check if room1 was available at period2
            abs_p2 = day * ppd + p2
            room1_id = next((l['room_id'] for l in teacher_data['lectures'] 
                           if l['day'] == day and l['period_in_day'] == p1), None)
            
            if room1_id:
                lectures_in_room1_at_p2 = timetable.room_lectures_at(room1_id, abs_p2)
                
                print(f"   Day {day}, P{p1}→P{p2}:")
                print(f"     - Room {v['room1']} at P{p2}: {lectures_in_room1_at_p2} lectures")
                if lectures_in_room1_at_p2 > 0:
                    print(f"       ⚠️ Phòng đã bị chiếm → buộc đổi phòng")
                else:
                    print(f"       ✅ Phòng trống → có thể dùng (nhưng đã đổi)")
    
    # Conclusion
    print(f"\n{'=' * 100}")
    print(f"💡 KẾT LUẬN:")
    print(f"{'=' * 100}")
    
    print(f"\n1. NGUYÊN NHÂN CHÍNH:")
    if len(violators_with_prefs) > len(violators_without_prefs):
        print(f"   ⚠️  NGUYỆN VỌNG ẢNH HƯỞNG NHIỀU!")
        print(f"   - {len(violators_with_prefs)}/{len(teachers_with_violations)} GV có violations có nguyện vọng")
        print(f"   - Nguyện vọng ép GV phải xếp vào slot cụ thể → không thể chọn phòng liên tục")
    else:
        print(f"   ℹ️  NGUYỆN VỌNG KHÔNG PHẢI NGUYÊN NHÂN CHÍNH")
        print(f"   - Chỉ {len(violators_with_prefs)}/{len(teachers_with_violations)} GV có violations có nguyện vọng")
        print(f"   - Có thể do: (1) Phòng không đủ, (2) Constraint khác ưu tiên cao hơn")
    
    print(f"\n2. GIẢI PHÁP:")
    print(f"   - Nếu nguyện vọng là nguyên nhân:")
    print(f"     → Giảm trọng số WEIGHT_TEACHER_PREFERENCE (hiện: 2.0)")
    print(f"     → Tăng trọng số WEIGHT_TEACHER_LECTURE_CONSOLIDATION (hiện: 1.8)")
    print(f"   - Nếu do phòng không đủ:")
    print(f"     → Tăng số phòng hoặc nới lỏng room type constraint")
    print(f"   - Neighborhood TeacherConsolidation có thể cải thiện trong optimization phase")
    
    return total_violations


def main():
    if len(sys.argv) != 3:
        print("Usage: python debug_consolidation.py <instance.ctt> <solution.sol>")
        sys.exit(1)
    
    instance_file = sys.argv[1]
    solution_file = sys.argv[2]
    
    try:
        total = analyze_teacher_consolidation(instance_file, solution_file)
        print(f"\n✅ Tổng violations: {total}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
