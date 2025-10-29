#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verify room LT/TH logic"""

import os
import sys
import django
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.models import PhongHoc

print("\n" + "="*100)
print("VERIFY ROOM LT/TH LOGIC")
print("="*100)

rooms = PhongHoc.objects.all()

print(f"\nTotal rooms: {rooms.count()}")

# Sample rooms
print("\n[Sample Rooms]")
for room in rooms[:10]:
    loai_str = room.loai_phong or "NONE"
    has_th = "Thực hành" in loai_str or "TH" in loai_str
    room_type = "TH" if has_th else "LT"
    print(f"  {room.ma_phong:<10} LoaiPhong='{loai_str[:30]:<30}' → Type={room_type}")

# Count by type
print("\n[Count by Type]")
lt_count = 0
th_count = 0
for room in rooms:
    loai_str = room.loai_phong or ""
    has_th = "Thực hành" in loai_str or "TH" in loai_str
    if has_th:
        th_count += 1
    else:
        lt_count += 1

print(f"  LT rooms: {lt_count}")
print(f"  TH rooms: {th_count}")

# Check for phòng có "Thực hành" trong tên
print("\n[Rooms with 'Thực hành' in name]")
th_rooms = rooms.filter(loai_phong__icontains="Thực hành")
print(f"  Count: {th_rooms.count()}")
if th_rooms.count() > 0:
    for room in th_rooms[:5]:
        print(f"    {room.ma_phong}: {room.loai_phong}")

print("\n" + "="*100)
