#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kiểm tra cấu trúc TimeSlot và KhungTG trong database
"""

import os
import sys
import django
from pathlib import Path

workspace = Path(__file__).parent
sys.path.insert(0, str(workspace))
os.chdir(str(workspace))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.scheduling.models import TimeSlot, KhungTG, NguyenVong, DotXep
from django.db.models import Count

print("=" * 70)
print("🕐 KIỂM TRA KHUNG THỜI GIAN (KhungTG)")
print("=" * 70)

khung_tg_list = KhungTG.objects.all().order_by('ma_khung_gio')
print(f"\n✅ Tổng số KhungTG: {khung_tg_list.count()}\n")

for kt in khung_tg_list:
    print(f"  ma_khung_gio={kt.ma_khung_gio}, gio_bat_dau={kt.gio_bat_dau}, gio_ket_thuc={kt.gio_ket_thuc}")

print("\n" + "=" * 70)
print("📅 KIỂM TRA TIMESLOT")
print("=" * 70)

timeslot_list = TimeSlot.objects.all().select_related('ca').order_by('thu', 'ca__ma_khung_gio')[:50]
print(f"\n✅ Tổng số TimeSlot: {TimeSlot.objects.count()}\n")
print("Sample 50 TimeSlot đầu tiên:\n")

# Tạo mapping thu
thu_map = {
    2: "Thứ 2",
    3: "Thứ 3",
    4: "Thứ 4",
    5: "Thứ 5",
    6: "Thứ 6",
    7: "Thứ 7",
    8: "CN"
}

for ts in timeslot_list:
    if ts.ca:
        thu_name = thu_map.get(ts.thu, f"Unknown({ts.thu})")
        print(f"  TimeSlot: thu={ts.thu} ({thu_name}), ca={ts.ca.ma_khung_gio} "
              f"({ts.ca.gio_bat_dau}-{ts.ca.gio_ket_thuc})")
    else:
        print(f"  TimeSlot: thu={ts.thu}, ca=NULL")

print("\n" + "=" * 70)
print("📊 THỐNG KÊ TIMESLOT THEO THỨ")
print("=" * 70)

for day_num in [2, 3, 4, 5, 6, 7, 8]:
    count = TimeSlot.objects.filter(thu=day_num).count()
    thu_name = thu_map.get(day_num, f"Unknown({day_num})")
    print(f"  {thu_name}: {count} slots")

print("\n" + "=" * 70)
print("📊 THỐNG KÊ TIMESLOT THEO CA")
print("=" * 70)

ca_stats = TimeSlot.objects.values('ca__ma_khung_gio').annotate(count=Count('time_slot_id')).order_by('ca__ma_khung_gio')
for stat in ca_stats:
    ca_num = stat['ca__ma_khung_gio']
    count = stat['count']
    print(f"  Ca {ca_num}: {count} slots")

print("\n" + "=" * 70)
print("🔍 KIỂM TRA NGUYEN_VONG DETAIL")
print("=" * 70)

dot_xep = DotXep.objects.get(ma_dot="DOT1_2025-2026_HK1")
nv_list = NguyenVong.objects.filter(ma_dot=dot_xep).select_related('time_slot_id', 'time_slot_id__ca', 'ma_gv')[:20]

print(f"\n✅ Sample 20 NguyenVong từ {dot_xep.ma_dot}:\n")

for nv in nv_list:
    if nv.time_slot_id:
        ts = nv.time_slot_id
        ca_num = ts.ca.ma_khung_gio if ts.ca else "NULL"
        thu_name = thu_map.get(ts.thu, f"Unknown({ts.thu})")
        gv_name = nv.ma_gv.ten_gv if nv.ma_gv else "None"
        gv_id = nv.ma_gv.ma_gv if nv.ma_gv else "None"
        print(f"  GV: {gv_name} ({gv_id}), Thu={ts.thu} ({thu_name}), Ca={ca_num}")
    else:
        print(f"  GV: {nv.ma_gv}, TimeSlot=NULL")

print("\n" + "=" * 70)
print("✅ Kiểm tra xong!")
print("=" * 70)
