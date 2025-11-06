#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug: Tại sao 79 NguyenVong bị lọc vì ngày/period ngoài phạm vi?
"""

import os, sys, django
from pathlib import Path
from collections import defaultdict

workspace = Path(__file__).parent
sys.path.insert(0, str(workspace))
os.chdir(str(workspace))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.scheduling.models import NguyenVong, DotXep

print("=" * 80)
print("🔍 DEBUG: Tại sao 79 NguyenVong bị lọc?")
print("=" * 80)

dot_xep = DotXep.objects.get(ma_dot="DOT1_2025-2026_HK1")

# Lấy tất cả NguyenVong
all_nvs = list(NguyenVong.objects.filter(ma_dot=dot_xep).select_related('ma_gv', 'time_slot_id__ca'))
print(f"\n📊 Tổng NguyenVong: {len(all_nvs)}")

thu_map = {2: "T2", 3: "T3", 4: "T4", 5: "T5", 6: "T6", 7: "T7", 8: "CN"}

# Phân tích
invalid_by_day = defaultdict(list)
invalid_by_period = defaultdict(list)
valid_count = 0

for nv in all_nvs:
    if not nv.time_slot_id or not nv.time_slot_id.ca:
        continue
    
    day_db = nv.time_slot_id.thu
    period_db = nv.time_slot_id.ca.ma_khung_gio
    
    # Check day
    if day_db < 2 or day_db > 6:
        reason = f"Day={day_db}({thu_map.get(day_db, '?')})"
        invalid_by_day[reason].append(nv)
        continue
    
    # Check period
    if period_db < 1 or period_db > 5:
        reason = f"Period={period_db}"
        invalid_by_period[reason].append(nv)
        continue
    
    valid_count += 1

print(f"\n✅ Valid: {valid_count}")
print(f"❌ Invalid Day: {sum(len(v) for v in invalid_by_day.values())}")
print(f"❌ Invalid Period: {sum(len(v) for v in invalid_by_period.values())}")

print(f"\n📋 Chi tiết bị lọc vì DAY ngoài phạm vi:")
for reason in sorted(invalid_by_day.keys()):
    nvs = invalid_by_day[reason]
    print(f"\n  {reason}: {len(nvs)} cái")
    # Sample
    for nv in nvs[:5]:
        gv_name = nv.ma_gv.ten_gv if nv.ma_gv else "?"
        ca = nv.time_slot_id.ca.ma_khung_gio if nv.time_slot_id and nv.time_slot_id.ca else "?"
        print(f"    - GV: {gv_name:20s}, Ca: {ca}")
    if len(nvs) > 5:
        print(f"    ... và {len(nvs) - 5} cái khác")

print(f"\n📋 Chi tiết bị lọc vì PERIOD ngoài phạm vi:")
for reason in sorted(invalid_by_period.keys()):
    nvs = invalid_by_period[reason]
    print(f"\n  {reason}: {len(nvs)} cái")
    for nv in nvs[:5]:
        gv_name = nv.ma_gv.ten_gv if nv.ma_gv else "?"
        day = nv.time_slot_id.thu if nv.time_slot_id else "?"
        print(f"    - GV: {gv_name:20s}, Day: {day}")
    if len(nvs) > 5:
        print(f"    ... và {len(nvs) - 5} cái khác")

print("\n" + "=" * 80)
