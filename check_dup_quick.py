#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm tra trùng GV, TimeSlot - Version nhanh"""
import os, sys, django
from pathlib import Path
from collections import defaultdict

workspace = Path(__file__).parent
sys.path.insert(0, str(workspace))
os.chdir(str(workspace))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.scheduling.models import PhanCong, DotXep, NguyenVong, TimeSlot

dot_xep = DotXep.objects.get(ma_dot="DOT1_2025-2026_HK1")
pcs = list(PhanCong.objects.filter(ma_dot=dot_xep).select_related('ma_gv', 'ma_lop'))

print(f"Total PhanCong: {len(pcs)}\n")

# 1. GV thống kê
gv_map = defaultdict(list)
for pc in pcs:
    if pc.ma_gv:
        gv_map[pc.ma_gv.ma_gv].append(pc)

print(f"1. Tổng GV dạy: {len(gv_map)}")
sorted_gv = sorted(gv_map.items(), key=lambda x: len(x[1]), reverse=True)[:10]
print("   Top 10 GV:\n")
for idx, (gv_id, pc_list) in enumerate(sorted_gv, 1):
    gv_name = pc_list[0].ma_gv.ten_gv if pc_list[0].ma_gv else "?"
    print(f"   {idx:2d}. {gv_name:30s} ({gv_id}): {len(pc_list):2d} lớp")

# 2. Kiểm tra NULL
null_gv = sum(1 for pc in pcs if not pc.ma_gv)
null_lop = sum(1 for pc in pcs if not pc.ma_lop)
print(f"\n2. NULL values:")
print(f"   GV = NULL: {null_gv}")
print(f"   Lớp = NULL: {null_lop}")

# 3. Kiểm tra NguyenVong (Preferred periods)
nvs = list(NguyenVong.objects.filter(ma_dot=dot_xep).select_related('ma_gv', 'time_slot_id__ca'))
print(f"\n3. Nguyện vọng (NguyenVong):")
print(f"   Total: {len(nvs)}")

# Đếm GV có nguyện vọng
nv_gv_count = len(set(nv.ma_gv.ma_gv for nv in nvs if nv.ma_gv))
print(f"   GV có nguyện vọng: {nv_gv_count}")

# Kiểm tra TimeSlot
ts_list = list(TimeSlot.objects.all())
print(f"\n4. TimeSlot:")
print(f"   Total trong DB: {len(ts_list)}")

print("\n✅ Done!")

