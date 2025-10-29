#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verify course LT/TH logic matches SQL"""

import os
import sys
import django
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.models import LopMonHoc, PhanCong, DotXep

MA_DOT = 'DOT1_2025-2026_HK1'

print("\n" + "="*100)
print("VERIFY COURSE LT/TH LOGIC")
print("="*100)

dot_xep = DotXep.objects.get(ma_dot=MA_DOT)
phan_congs = PhanCong.objects.filter(ma_dot=dot_xep).select_related('ma_lop__ma_mon_hoc')

print(f"\nTotal classes: {phan_congs.count()}")

# Sample classes
print("\n[Sample Classes]")
sample_count = 0
for phan_cong in phan_congs:
    lop = phan_cong.ma_lop
    mon = lop.ma_mon_hoc
    
    so_tiet_lt = mon.so_tiet_lt or 0
    so_tiet_th = mon.so_tiet_th or 0
    to_mh = lop.to_mh or 0
    
    # Apply SQL logic
    if so_tiet_th == 0:
        course_type = "LT"
    elif so_tiet_lt == 0 and so_tiet_th > 0:
        course_type = "TH"
    elif so_tiet_lt > 0 and so_tiet_th > 0 and to_mh == 0:
        course_type = "LT"
    else:
        course_type = "TH"
    
    print(f"  {lop.ma_lop:<15} Mon={mon.ma_mon_hoc:<10} LT={so_tiet_lt:<2} TH={so_tiet_th:<2} To={to_mh:<2} → Type={course_type}")
    sample_count += 1
    if sample_count >= 15:
        break

# Count by type
print("\n[Count by Course Type]")
lt_count = 0
th_count = 0
for phan_cong in phan_congs:
    lop = phan_cong.ma_lop
    mon = lop.ma_mon_hoc
    
    so_tiet_lt = mon.so_tiet_lt or 0
    so_tiet_th = mon.so_tiet_th or 0
    to_mh = lop.to_mh or 0
    
    if so_tiet_th == 0:
        course_type = "LT"
    elif so_tiet_lt == 0 and so_tiet_th > 0:
        course_type = "TH"
    elif so_tiet_lt > 0 and so_tiet_th > 0 and to_mh == 0:
        course_type = "LT"
    else:
        course_type = "TH"
    
    if course_type == "LT":
        lt_count += 1
    else:
        th_count += 1

print(f"  LT courses: {lt_count}")
print(f"  TH courses: {th_count}")

# Compare with rooms
print("\n[Compatibility Check]")
print(f"  LT courses: {lt_count}, LT rooms: 93 → {'OK' if lt_count <= 93 else 'PROBLEM'}")
print(f"  TH courses: {th_count}, TH rooms: 108 → {'OK' if th_count <= 108 else 'PROBLEM'}")

print("\n" + "="*100)
