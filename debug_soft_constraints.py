#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import json
import django
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.models import NguyenVong, PhanCong
from apps.scheduling.validators.validation_framework_v2 import ScheduleData

# Load schedule
schedule_json_path = 'output/schedule_llm_2025-2026-HK1.json'
with open(schedule_json_path, 'r', encoding='utf-8') as f:
    schedule_dict = json.load(f)

schedule_data = ScheduleData(schedule_dict)

# Load preferences
teacher_preferences = {}
preferences = NguyenVong.objects.select_related('ma_gv', 'time_slot_id').all()
for pref in preferences:
    if pref.ma_gv and pref.time_slot_id:
        ma_gv = pref.ma_gv.ma_gv
        slot_id = pref.time_slot_id.time_slot_id
        if ma_gv not in teacher_preferences:
            teacher_preferences[ma_gv] = set()
        teacher_preferences[ma_gv].add(slot_id)

# Load assignments
teacher_classes = {}
phan_cong_all = PhanCong.objects.select_related('ma_lop', 'ma_gv').all()
for pc in phan_cong_all:
    if pc.ma_gv and pc.ma_lop:
        ma_gv = pc.ma_gv.ma_gv
        ma_lop = pc.ma_lop.ma_lop
        if ma_gv not in teacher_classes:
            teacher_classes[ma_gv] = []
        teacher_classes[ma_gv].append(ma_lop)

print(f"✓ Teachers with preferences: {len(teacher_preferences)}")
print(f"✓ Teachers with class assignments: {len(teacher_classes)}")
print(f"✓ Schedule assignments: {len(schedule_data.get_all_assignments())}")

# Find overlap
overlap = set(teacher_preferences.keys()) & set(teacher_classes.keys())
print(f"✓ Teachers with BOTH: {len(overlap)}")

# Check violations
violations = []
checked_count = 0
for i, assignment in enumerate(schedule_data.get_all_assignments()):
    ma_lop = assignment.get('class')  # NOT 'MaLop'
    slot_id = assignment.get('slot')  # NOT 'MaSlot'
    
    # Find teacher
    teacher_id = None
    for ma_gv, classes in teacher_classes.items():
        if ma_lop in classes:
            teacher_id = ma_gv
            break
    
    if i < 5:
        print(f"  Assignment {i}: Class={ma_lop}, Slot={slot_id}, Teacher={teacher_id}")
    
    if teacher_id:
        checked_count += 1
        if teacher_id in teacher_preferences:
            preferred_slots = teacher_preferences[teacher_id]
            if slot_id not in preferred_slots:
                violations.append({
                    'class': ma_lop,
                    'slot': slot_id,
                    'teacher': teacher_id
                })

print(f"\n✓ Checked {checked_count} schedule assignments")
print(f"✓ Found {len(violations)} violations")

if violations:
    print(f"\nFirst 10 violations:")
    for v in violations[:10]:
        print(f"  - Class {v['class']} slot {v['slot']} (teacher {v['teacher']})")
