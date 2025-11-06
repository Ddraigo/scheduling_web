#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug: Tại sao convert_db_to_ctt.py lọc bỏ 430 nguyện vọng?
"""

import os, sys, django
from pathlib import Path
from collections import defaultdict

workspace = Path(__file__).parent
sys.path.insert(0, str(workspace))
os.chdir(str(workspace))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.scheduling.models import NguyenVong, DotXep, PhanCong, TimeSlot

print("=" * 80)
print("🔍 DEBUG: Tại sao convert_db_to_ctt.py lọc bỏ nguyện vọng?")
print("=" * 80)

dot_xep = DotXep.objects.get(ma_dot="DOT1_2025-2026_HK1")

# Lấy tất cả NguyenVong
all_nvs = list(NguyenVong.objects.filter(ma_dot=dot_xep).select_related('ma_gv', 'time_slot_id__ca'))
print(f"\n📊 Tổng NguyenVong: {len(all_nvs)}")

# Map: GV -> list of courses
pcs = list(PhanCong.objects.filter(ma_dot=dot_xep).select_related('ma_gv', 'ma_lop'))
gv_courses = defaultdict(list)
for pc in pcs:
    if pc.ma_gv:
        gv_courses[pc.ma_gv.ma_gv].append(pc.ma_lop.ma_lop)

print(f"📚 GV dạy: {len(gv_courses)} teachers")

# Phân tích từng NguyenVong
thu_map = {2: "T2", 3: "T3", 4: "T4", 5: "T5", 6: "T6", 7: "T7", 8: "CN"}

invalid_timeslot = 0
invalid_gv = 0
valid = 0
by_reason = defaultdict(list)

for nv in all_nvs:
    reason = None
    
    # Check 1: TimeSlot hợp lệ?
    if not nv.time_slot_id:
        reason = "TimeSlot NULL"
        invalid_timeslot += 1
    elif not nv.time_slot_id.ca:
        reason = "TimeSlot.ca NULL"
        invalid_timeslot += 1
    else:
        day_db = nv.time_slot_id.thu
        period_db = nv.time_slot_id.ca.ma_khung_gio
        
        # Day check: chỉ nhận 2-6 (T2-T6)
        if day_db < 2 or day_db > 6:
            reason = f"Day ngoài phạm vi ({day_db}={thu_map.get(day_db, '?')})"
            invalid_timeslot += 1
        
        # Period check: 1-5
        elif period_db < 1 or period_db > 5:
            reason = f"Period ngoài phạm vi ({period_db})"
            invalid_timeslot += 1
    
    # Check 2: GV có dạy không?
    if not reason:
        gv_id = nv.ma_gv.ma_gv if nv.ma_gv else None
        
        if not gv_id:
            reason = "GV NULL"
            invalid_gv += 1
        elif gv_id not in gv_courses:
            reason = f"GV ({gv_id}) không dạy lớp nào"
            invalid_gv += 1
        elif not gv_courses[gv_id]:
            reason = f"GV ({gv_id}) dạy nhưng list rỗng"
            invalid_gv += 1
        else:
            reason = "VALID ✅"
            valid += 1
    
    by_reason[reason].append(nv)

# Report
print(f"\n📋 Phân tích chi tiết:")
print(f"  - Valid (lưu giữ): {valid}")
print(f"  - Invalid TimeSlot: {invalid_timeslot}")
print(f"  - Invalid GV: {invalid_gv}")

print(f"\n💔 Lý do bị lọc bỏ:\n")
for reason in sorted(by_reason.keys(), key=lambda x: len(by_reason[x]), reverse=True):
    if reason != "VALID ✅":
        count = len(by_reason[reason])
        pct = (count / len(all_nvs)) * 100
        print(f"  {count:3d} ({pct:5.1f}%) - {reason}")
        
        # Sample: hiển thị 2-3 ví dụ
        sample_count = 0
        for nv in by_reason[reason][:3]:
            gv_name = nv.ma_gv.ten_gv if nv.ma_gv else "N/A"
            ts = nv.time_slot_id
            if ts and ts.ca:
                ts_info = f"T{ts.thu}(={thu_map.get(ts.thu, '?')})-Ca{ts.ca.ma_khung_gio}"
            else:
                ts_info = "NULL"
            print(f"       └─ GV: {gv_name:20s}, TS: {ts_info}")
            sample_count += 1
        if len(by_reason[reason]) > 3:
            print(f"       ... và {len(by_reason[reason]) - 3} cái khác")

print("\n" + "=" * 80)
print("✅ Phân tích xong!")
print("=" * 80)
