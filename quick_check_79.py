#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick check 79 invalid slots"""
import os, sys, django
from pathlib import Path
from collections import Counter

workspace = Path(__file__).parent
sys.path.insert(0, str(workspace))
os.chdir(str(workspace))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.scheduling.models import NguyenVong, DotXep

dot_xep = DotXep.objects.get(ma_dot="DOT1_2025-2026_HK1")
nvs = list(NguyenVong.objects.filter(ma_dot=dot_xep).select_related('time_slot_id__ca'))

print(f"Total NguyenVong: {len(nvs)}\n")

# Đếm theo day
day_counter = Counter()
period_counter = Counter()

invalid_days = []
invalid_periods = []

for nv in nvs:
    if not nv.time_slot_id or not nv.time_slot_id.ca:
        continue
    
    day = nv.time_slot_id.thu
    period = nv.time_slot_id.ca.ma_khung_gio
    
    # Chỉ nhận 2-6 (T2-T6)
    if day < 2 or day > 6:
        invalid_days.append(day)
    # Chỉ nhận 1-5
    elif period < 1 or period > 5:
        invalid_periods.append(period)

print(f"Invalid DAY: {len(invalid_days)}")
print(f"  Distribution: {Counter(invalid_days)}")
print(f"\nInvalid PERIOD: {len(invalid_periods)}")
print(f"  Distribution: {Counter(invalid_periods)}")
print(f"\nTotal invalid: {len(invalid_days) + len(invalid_periods)}")
