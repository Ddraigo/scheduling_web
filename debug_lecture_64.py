#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Debug Lecture 64 issue"""

import os
import sys
import django
import io

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.models import LopMonHoc, MonHoc, PhongHoc
from apps.scheduling.algorithms.algorithms_data_adapter import AlgorithmsDataAdapter

MA_DOT = 'DOT1_2025-2026_HK1'

print("\n" + "="*100)
print("DEBUG LECTURE 64 ISSUE")
print("="*100)

# Build instance
instance = AlgorithmsDataAdapter.build_cbctt_instance_from_db(MA_DOT)

print(f"\nTotal courses: {len(instance.courses)}")
print(f"Total rooms: {len(instance.rooms)}")

# Find course 64
if len(instance.courses) > 64:
    course = instance.courses[64]
    print(f"\n[Course 64]")
    print(f"  ID: {course.id}")
    print(f"  Students: {course.students}")
    print(f"  Equipment Required: '{course.equipment}'")
    print(f"  Course Type: {course.course_type}")
    print(f"  Teacher: {course.teacher}")
    
    # Check room preferences
    prefs = instance.course_room_preference[64]
    print(f"\n[Room Preferences] (first 10 of {len(prefs)})")
    for i, room_idx in enumerate(prefs[:10]):
        room = instance.rooms[room_idx]
        match_equip = "✓" if course.equipment == "" or course.equipment in room.equipment else "✗"
        match_type = "✓" if room.room_type == course.course_type else "✗"
        match_cap = "✓" if room.capacity >= course.students else "✗"
        print(f"    {i}: {room.id:<10} Cap={room.capacity:<3} Type={room.room_type:<3} ({match_type}) Equip='{room.equipment[:30] if room.equipment else 'NONE'}' ({match_equip}) Cap OK ({match_cap})")
    
    print(f"\n[Analysis]")
    # Count rooms by criteria
    equip_match = sum(1 for idx in prefs if course.equipment == "" or course.equipment in instance.rooms[idx].equipment)
    type_match = sum(1 for idx in prefs if instance.rooms[idx].room_type == course.course_type)
    cap_match = sum(1 for idx in prefs if instance.rooms[idx].capacity >= course.students)
    
    print(f"  Rooms with equipment match: {equip_match}/{len(prefs)}")
    print(f"  Rooms with type match: {type_match}/{len(prefs)}")
    print(f"  Rooms with capacity adequate: {cap_match}/{len(prefs)}")
    
    # Find rooms matching ALL criteria
    all_match = 0
    for idx in prefs:
        room = instance.rooms[idx]
        has_equip = course.equipment == "" or course.equipment in room.equipment
        has_type = room.room_type == course.course_type
        has_cap = room.capacity >= course.students
        if has_equip and has_type and has_cap:
            all_match += 1
    
    print(f"  Rooms matching ALL criteria: {all_match}/{len(prefs)}")
    
    # Show all rooms of matching type
    print(f"\n[All Rooms by Type]")
    by_type = {}
    for idx, room in enumerate(instance.rooms):
        if room.room_type not in by_type:
            by_type[room.room_type] = []
        by_type[room.room_type].append((idx, room))
    
    for room_type, rooms_list in sorted(by_type.items()):
        print(f"  {room_type}: {len(rooms_list)} rooms")
        # Check if any match equipment
        equip_rooms = [r for _, r in rooms_list if course.equipment == "" or course.equipment in r.equipment]
        print(f"    - With equipment '{course.equipment}': {len(equip_rooms)}")

else:
    print(f"ERROR: Course 64 not found (only {len(instance.courses)} courses)")

print("\n" + "="*100)
