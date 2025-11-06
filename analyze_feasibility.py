#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phân tích feasibility của dot1.ctt
Kiểm tra xem có đủ rooms cho courses không?
"""

import re
from collections import defaultdict

ctt_file = r"D:\HOCTAP\DU_AN_CNTT\scheduling_web\apps\scheduling\algorithms\alo_origin\dot1.ctt"

print("=" * 80)
print("🔍 PHÂN TÍCH FEASIBILITY - dot1.ctt")
print("=" * 80)

# Parse file
with open(ctt_file, 'r', encoding='utf-8') as f:
    lines = [line.strip() for line in f]

# Đọc header
header = {}
for line in lines[:10]:
    if ':' in line:
        key, val = line.split(':', 1)
        header[key.strip()] = val.strip()

days = int(header.get('Days', 5))
periods = int(header.get('Periods_per_day', 5))
total_slots = days * periods

print(f"\n📊 Tổng quan:")
print(f"  - Courses: {header['Courses']}")
print(f"  - Rooms: {header['Rooms']}")
print(f"  - Days: {days}, Periods/day: {periods}, Total slots: {total_slots}")

# Parse COURSES
courses_lt = []
courses_th = []
courses_by_equipment = defaultdict(list)

in_courses = False
for line in lines:
    if line == "COURSES:":
        in_courses = True
        continue
    if in_courses:
        if line == "" or line == "ROOMS:":
            break
        parts = line.split()
        if len(parts) >= 6:
            course_id = parts[0]
            course_type = parts[5]
            equipment = ' '.join(parts[6:]) if len(parts) > 6 else ""
            
            if course_type == "LT":
                courses_lt.append(course_id)
            elif course_type == "TH":
                courses_th.append(course_id)
            
            if equipment:
                courses_by_equipment[equipment].append(course_id)

# Parse ROOMS
rooms_lt = []
rooms_th = []
rooms_by_equipment = defaultdict(list)

in_rooms = False
for line in lines:
    if line == "ROOMS:":
        in_rooms = True
        continue
    if in_rooms:
        if line == "" or line == "CURRICULA:":
            break
        parts = line.split()
        if len(parts) >= 3:
            room_id = parts[0]
            room_type = parts[2]
            equipment = ' '.join(parts[3:]) if len(parts) > 3 else ""
            
            if room_type == "LT":
                rooms_lt.append(room_id)
            elif room_type == "TH":
                rooms_th.append(room_id)
            
            if equipment:
                rooms_by_equipment[equipment].append(room_id)

print(f"\n📚 COURSES:")
print(f"  - LT (Lý thuyết): {len(courses_lt)}")
print(f"  - TH (Thực hành): {len(courses_th)}")
print(f"  - Total: {len(courses_lt) + len(courses_th)}")

print(f"\n🏛️  ROOMS:")
print(f"  - LT (Lý thuyết): {len(rooms_lt)}")
print(f"  - TH (Thực hành): {len(rooms_th)}")
print(f"  - Total: {len(rooms_lt) + len(rooms_th)}")

print(f"\n⚖️  PHÂN BỐ:")
print(f"  - LT: {len(courses_lt)} courses vs {len(rooms_lt)} rooms")
if len(courses_lt) > len(rooms_lt):
    print(f"    ⚠️  THIẾU {len(courses_lt) - len(rooms_lt)} phòng LT!")
else:
    print(f"    ✅ Đủ phòng LT")

print(f"  - TH: {len(courses_th)} courses vs {len(rooms_th)} rooms")
if len(courses_th) > len(rooms_th):
    print(f"    ⚠️  THIẾU {len(courses_th) - len(rooms_th)} phòng TH!")
else:
    print(f"    ✅ Đủ phòng TH")

# Tính capacity per slot
print(f"\n🕐 SLOT CAPACITY:")
print(f"  - Total slots: {total_slots}")
print(f"  - LT capacity per slot: {len(rooms_lt)} courses/slot × {total_slots} slots = {len(rooms_lt) * total_slots} course-slots")
print(f"  - TH capacity per slot: {len(rooms_th)} courses/slot × {total_slots} slots = {len(rooms_th) * total_slots} course-slots")

total_capacity = (len(rooms_lt) + len(rooms_th)) * total_slots
total_courses = len(courses_lt) + len(courses_th)

print(f"\n✅ Total capacity: {total_capacity} course-slots")
print(f"📚 Total courses: {total_courses}")

if total_courses > total_capacity:
    print(f"\n❌ KHÔNG KHẢ THI: Cần {total_courses} slots nhưng chỉ có {total_capacity} slots!")
elif total_courses <= len(rooms_lt) + len(rooms_th):
    print(f"\n✅ KHẢ THI: Có thể xếp tất cả cùng 1 slot (nếu không có conflict)")
else:
    print(f"\n⚠️  CẦN PHÂN BỔ: {total_courses} courses vào {total_slots} slots với {len(rooms_lt) + len(rooms_th)} rooms")

print("\n" + "=" * 80)
