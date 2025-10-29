#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import django

sys.path.insert(0, str(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.models import NguyenVong, PhanCong

print(f"NguyenVong count: {NguyenVong.objects.count()}")
print(f"PhanCong count: {PhanCong.objects.count()}")

if NguyenVong.objects.count() > 0:
    print("\nSample NguyenVong (first 10):")
    for nv in NguyenVong.objects.select_related('ma_gv', 'time_slot_id')[:10]:
        print(f"  - Teacher {nv.ma_gv.ma_gv if nv.ma_gv else 'N/A'}: Slot {nv.time_slot_id.time_slot_id if nv.time_slot_id else 'N/A'}")
else:
    print("\n❌ NO NguyenVong records found in database!")
    print("\nSample PhanCong (first 5):")
    for pc in PhanCong.objects.select_related('ma_gv', 'ma_lop')[:5]:
        print(f"  - Teacher {pc.ma_gv.ma_gv if pc.ma_gv else 'N/A'} teaches class {pc.ma_lop.ma_lop if pc.ma_lop else 'N/A'}")
