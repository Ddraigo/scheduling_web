#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Debug: Why can't assign when rooms are available?"""

import os
import sys
import django
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.models import DotXep, TimeSlot
from apps.scheduling.algorithms.algorithms_data_adapter import AlgorithmsDataAdapter
from apps.scheduling.algorithms.algorithms_core import TimetableState

MA_DOT = 'DOT1_2025-2026_HK1'

print("\n" + "="*100)
print("DEBUG: ROOM CAPACITY ANALYSIS")
print("="*100)

# Calculate total time slots
time_slots = TimeSlot.objects.all().select_related('ca')
days = len(set(ts.thu for ts in time_slots))
periods_per_day = time_slots.filter(thu=time_slots.first().thu).count()
total_periods = days * periods_per_day

print(f"\nTime Structure:")
print(f"  Days: {days}")
print(f"  Periods/day: {periods_per_day}")
print(f"  Total periods/week: {total_periods}")

# Build instance
instance = AlgorithmsDataAdapter.build_cbctt_instance_from_db(MA_DOT)

print(f"\nCourses & Rooms:")
print(f"  Total courses: {len(instance.courses)}")
print(f"  Total lectures needed: {sum(c.lectures for c in instance.courses)}")
print(f"  Total rooms: {len(instance.rooms)}")

lt_rooms = sum(1 for r in instance.rooms if r.room_type == "LT")
th_rooms = sum(1 for r in instance.rooms if r.room_type == "TH")
print(f"  LT rooms: {lt_rooms}")
print(f"  TH rooms: {th_rooms}")

print(f"\nRoom Capacity Analysis:")
print(f"  LT capacity: {lt_rooms} rooms × {total_periods} periods = {lt_rooms * total_periods} slots")
print(f"  TH capacity: {th_rooms} rooms × {total_periods} periods = {th_rooms * total_periods} slots")
print(f"  Total slots: {(lt_rooms + th_rooms) * total_periods}")

lt_courses = sum(1 for c in instance.courses if c.course_type == "LT")
th_courses = sum(1 for c in instance.courses if c.course_type == "TH")
lt_lectures = sum(instance.courses[i].lectures for i in range(len(instance.courses)) if instance.courses[i].course_type == "LT")
th_lectures = sum(instance.courses[i].lectures for i in range(len(instance.courses)) if instance.courses[i].course_type == "TH")

print(f"\nLecture Requirements:")
print(f"  LT: {lt_courses} courses, {lt_lectures} lectures needed")
print(f"  TH: {th_courses} courses, {th_lectures} lectures needed")
print(f"  Total: {lt_lectures + th_lectures} lectures")

print(f"\nCapacity vs Requirement:")
print(f"  LT: Need {lt_lectures}, Available {lt_rooms * total_periods} → {'✓ OK' if lt_lectures <= lt_rooms * total_periods else '✗ NOT ENOUGH'}")
print(f"  TH: Need {th_lectures}, Available {th_rooms * total_periods} → {'✓ OK' if th_lectures <= th_rooms * total_periods else '✗ NOT ENOUGH'}")

print(f"\nConclusion:")
if (lt_lectures <= lt_rooms * total_periods) and (th_lectures <= th_rooms * total_periods):
    print("  ✓ PLENTY OF CAPACITY! Problem is NOT room shortage.")
    print("  Problem must be in algorithm logic or constraints!")
else:
    print("  ✗ INSUFFICIENT CAPACITY - needs investigation")

print("\n" + "="*100)
