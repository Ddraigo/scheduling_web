#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script phân tích dữ liệu CTT file để debug initial solution failure.

Kiểm tra:
1. Số lượng courses LT vs TH
2. Số lượng rooms LT vs TH  
3. Equipment requirements của courses
4. Capacity mismatches
5. Feasibility analysis
"""

import sys
from pathlib import Path
from collections import defaultdict, Counter

def parse_ctt_file(file_path):
    """Parse CTT file và trả về dữ liệu cấu trúc"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines()]
    
    # Parse header
    header = {}
    idx = 0
    while idx < len(lines) and not lines[idx].startswith('COURSES:'):
        if ':' in lines[idx]:
            key, value = lines[idx].split(':', 1)
            header[key.strip().lower()] = value.strip()
        idx += 1
    
    # Parse courses
    courses = []
    idx += 1  # Skip "COURSES:"
    while idx < len(lines) and not lines[idx].startswith('ROOMS:'):
        if lines[idx] and not lines[idx].startswith('#'):
            parts = lines[idx].split()
            if len(parts) >= 5:
                course = {
                    'id': parts[0],
                    'teacher': parts[1],
                    'lectures': int(parts[2]),
                    'min_wd': int(parts[3]),
                    'students': int(parts[4]),
                    'course_type': parts[5] if len(parts) > 5 else 'LT',
                    'equipment': ' '.join(parts[6:]) if len(parts) > 6 else ''
                }
                courses.append(course)
        idx += 1
    
    # Parse rooms
    rooms = []
    idx += 1  # Skip "ROOMS:"
    while idx < len(lines) and not lines[idx].startswith('CURRICULA:'):
        if lines[idx] and not lines[idx].startswith('#'):
            parts = lines[idx].split()
            if len(parts) >= 2:
                room = {
                    'id': parts[0],
                    'capacity': int(parts[1]),
                    'room_type': parts[2] if len(parts) > 2 else 'LT',
                    'equipment': ' '.join(parts[3:]) if len(parts) > 3 else ''
                }
                rooms.append(room)
        idx += 1
    
    return header, courses, rooms


def analyze_data(header, courses, rooms):
    """Phân tích dữ liệu và in ra báo cáo chi tiết"""
    
    print("=" * 80)
    print("📊 BÁO CÁO PHÂN TÍCH DỮ LIỆU CTT FILE")
    print("=" * 80)
    print()
    
    # 1. THỐNG KÊ TỔNG QUAN
    print("📋 1. THỐNG KÊ TỔNG QUAN")
    print("-" * 80)
    print(f"Tổng số courses: {len(courses)}")
    print(f"Tổng số rooms: {len(rooms)}")
    print(f"Số ngày: {header.get('days', 'N/A')}")
    print(f"Số ca/ngày: {header.get('periods_per_day', 'N/A')}")
    total_periods = int(header.get('days', 0)) * int(header.get('periods_per_day', 0))
    print(f"Tổng số periods: {total_periods}")
    print()
    
    # 2. PHÂN LOẠI COURSES THEO TYPE
    print("📚 2. PHÂN LOẠI COURSES THEO LOẠI (LT vs TH)")
    print("-" * 80)
    course_by_type = Counter([c['course_type'] for c in courses])
    for ctype, count in sorted(course_by_type.items()):
        percentage = (count / len(courses)) * 100
        print(f"  {ctype}: {count} courses ({percentage:.1f}%)")
    print()
    
    # 3. PHÂN LOẠI ROOMS THEO TYPE
    print("🏫 3. PHÂN LOẠI ROOMS THEO LOẠI (LT vs TH)")
    print("-" * 80)
    room_by_type = Counter([r['room_type'] for r in rooms])
    for rtype, count in sorted(room_by_type.items()):
        percentage = (count / len(rooms)) * 100
        print(f"  {rtype}: {count} rooms ({percentage:.1f}%)")
    print()
    
    # 4. PHÂN TÍCH CAPACITY
    print("📐 4. PHÂN TÍCH CAPACITY")
    print("-" * 80)
    
    # Students distribution
    student_counts = [c['students'] for c in courses]
    print(f"Students - Min: {min(student_counts)}, Max: {max(student_counts)}, "
          f"Avg: {sum(student_counts) / len(student_counts):.1f}")
    
    # Room capacity distribution
    capacities = [r['capacity'] for r in rooms]
    print(f"Rooms - Min capacity: {min(capacities)}, Max: {max(capacities)}, "
          f"Avg: {sum(capacities) / len(capacities):.1f}")
    print()
    
    # Capacity bins
    print("Phân bố capacity của rooms:")
    bins = [0, 20, 40, 60, 80, 100, float('inf')]
    bin_labels = ['0-20', '21-40', '41-60', '61-80', '81-100', '>100']
    for i in range(len(bins) - 1):
        count = sum(1 for r in rooms if bins[i] < r['capacity'] <= bins[i+1])
        print(f"  {bin_labels[i]}: {count} rooms")
    print()
    
    # 5. EQUIPMENT ANALYSIS
    print("🔧 5. PHÂN TÍCH THIẾT BỊ (EQUIPMENT)")
    print("-" * 80)
    
    courses_with_equipment = [c for c in courses if c['equipment']]
    print(f"Courses yêu cầu thiết bị: {len(courses_with_equipment)} / {len(courses)} "
          f"({len(courses_with_equipment) / len(courses) * 100:.1f}%)")
    
    if courses_with_equipment:
        equipment_types = Counter()
        for c in courses_with_equipment:
            equipment_types[c['equipment']] += 1
        
        print(f"\nTop 10 yêu cầu thiết bị phổ biến:")
        for eq, count in equipment_types.most_common(10):
            print(f"  '{eq}': {count} courses")
    
    rooms_with_equipment = [r for r in rooms if r['equipment']]
    print(f"\nRooms có thiết bị: {len(rooms_with_equipment)} / {len(rooms)} "
          f"({len(rooms_with_equipment) / len(rooms) * 100:.1f}%)")
    print()
    
    # 6. FEASIBILITY ANALYSIS
    print("⚠️  6. PHÂN TÍCH KHẢ NĂNG XẾP LỊCH (FEASIBILITY)")
    print("-" * 80)
    
    # Check room type matching
    print("🔍 Kiểm tra khớp room type:")
    for ctype in ['LT', 'TH']:
        course_count = course_by_type.get(ctype, 0)
        room_count = room_by_type.get(ctype, 0)
        if course_count > 0:
            ratio = room_count / course_count
            status = "✅ OK" if ratio >= 0.5 else "⚠️  WARNING" if ratio >= 0.3 else "❌ CRITICAL"
            print(f"  {ctype}: {course_count} courses vs {room_count} rooms "
                  f"(ratio: {ratio:.2f}) {status}")
    print()
    
    # Check capacity matching
    print("🔍 Kiểm tra capacity matching:")
    capacity_issues = []
    for course in courses:
        # Find rooms of same type with adequate capacity
        matching_rooms = [r for r in rooms 
                         if r['room_type'] == course['course_type'] 
                         and r['capacity'] >= course['students']]
        
        if not matching_rooms:
            capacity_issues.append({
                'course': course['id'],
                'type': course['course_type'],
                'students': course['students'],
                'equipment': course['equipment']
            })
    
    if capacity_issues:
        print(f"  ❌ Tìm thấy {len(capacity_issues)} courses KHÔNG có room phù hợp!")
        print(f"\n  Top 10 courses có vấn đề:")
        for issue in capacity_issues[:10]:
            print(f"    - {issue['course']}: Type={issue['type']}, "
                  f"Students={issue['students']}, Equipment='{issue['equipment']}'")
    else:
        print(f"  ✅ Tất cả courses đều có ít nhất 1 room phù hợp về capacity và type")
    print()
    
    # 7. EQUIPMENT MATCHING
    print("🔍 Kiểm tra equipment matching:")
    equipment_issues = []
    for course in courses_with_equipment:
        # Find rooms of same type, adequate capacity, AND matching equipment
        required_eq = set(eq.strip() for eq in course['equipment'].split(',') if eq.strip())
        
        matching_rooms = []
        for room in rooms:
            if room['room_type'] != course['course_type']:
                continue
            if room['capacity'] < course['students']:
                continue
            
            room_eq = set(eq.strip() for eq in room['equipment'].split(',') if eq.strip())
            if required_eq.issubset(room_eq):
                matching_rooms.append(room)
        
        if not matching_rooms:
            equipment_issues.append({
                'course': course['id'],
                'type': course['course_type'],
                'students': course['students'],
                'equipment': course['equipment']
            })
    
    if equipment_issues:
        print(f"  ❌ Tìm thấy {len(equipment_issues)} courses KHÔNG có room phù hợp về equipment!")
        print(f"\n  Top 10 courses có vấn đề equipment:")
        for issue in equipment_issues[:10]:
            print(f"    - {issue['course']}: Type={issue['type']}, "
                  f"Students={issue['students']}, Equipment='{issue['equipment']}'")
    else:
        print(f"  ✅ Tất cả courses yêu cầu equipment đều có room phù hợp")
    print()
    
    # 8. SUMMARY & RECOMMENDATIONS
    print("=" * 80)
    print("📝 TỔNG KẾT & KHUYẾN NGHỊ")
    print("=" * 80)
    
    total_issues = len(capacity_issues) + len(equipment_issues)
    
    if total_issues == 0:
        print("✅ KHÔNG tìm thấy vấn đề về data!")
        print("   → Lỗi có thể do: Preferences quá nghiêm ngặt, backtracking timeout, hoặc lỗi logic khác")
    else:
        print(f"❌ Tìm thấy {total_issues} courses CÓ VẤN ĐỀ!")
        print()
        print("🔧 KHUYẾN NGHỊ SỬA LỖI:")
        
        if capacity_issues:
            print(f"\n1. CAPACITY/ROOM TYPE MISMATCH ({len(capacity_issues)} courses):")
            print("   → Thêm rooms có capacity/type phù hợp")
            print("   → Hoặc giảm students của courses")
            print("   → Hoặc cho phép overflow capacity trong initial building (relaxation)")
        
        if equipment_issues:
            print(f"\n2. EQUIPMENT MISMATCH ({len(equipment_issues)} courses):")
            print("   → Thêm equipment vào rooms")
            print("   → Hoặc bỏ yêu cầu equipment của courses")
            print("   → Hoặc relax equipment constraint trong initial building")
    
    print()
    print("=" * 80)
    
    return {
        'total_courses': len(courses),
        'total_rooms': len(rooms),
        'capacity_issues': len(capacity_issues),
        'equipment_issues': len(equipment_issues),
        'total_issues': total_issues
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_ctt_data.py <path_to_ctt_file>")
        print("\nVí dụ:")
        print("  python analyze_ctt_data.py output/ctt_files/DOT1_2025-2026_HK1.ctt")
        sys.exit(1)
    
    ctt_file = Path(sys.argv[1])
    
    if not ctt_file.exists():
        print(f"❌ File không tồn tại: {ctt_file}")
        sys.exit(1)
    
    print(f"\n📂 Đang phân tích file: {ctt_file}")
    print()
    
    try:
        header, courses, rooms = parse_ctt_file(ctt_file)
        results = analyze_data(header, courses, rooms)
        
        # Exit code based on results
        sys.exit(0 if results['total_issues'] == 0 else 1)
        
    except Exception as e:
        print(f"\n❌ LỖI: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == '__main__':
    main()
