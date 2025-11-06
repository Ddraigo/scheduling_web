#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kiểm tra: GV nào có NguyenVong nhưng KHÔNG có PhanCong?
"""

import os, sys, django
from pathlib import Path
from collections import defaultdict

workspace = Path(__file__).parent
sys.path.insert(0, str(workspace))
os.chdir(str(workspace))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.scheduling.models import NguyenVong, DotXep, PhanCong

dot_xep = DotXep.objects.get(ma_dot="DOT1_2025-2026_HK1")

# GV có NguyenVong
nv_gv_set = set(nv.ma_gv.ma_gv for nv in NguyenVong.objects.filter(ma_dot=dot_xep) if nv.ma_gv)
print(f"👨‍🏫 GV có NguyenVong: {len(nv_gv_set)}")
print(f"   {sorted(nv_gv_set)}\n")

# GV có PhanCong
pc_gv_set = set(pc.ma_gv.ma_gv for pc in PhanCong.objects.filter(ma_dot=dot_xep) if pc.ma_gv)
print(f"👨‍🏫 GV có PhanCong: {len(pc_gv_set)}")
print(f"   {sorted(pc_gv_set)}\n")

# GV trong NguyenVong nhưng KHÔNG trong PhanCong
missing_gv = nv_gv_set - pc_gv_set
print(f"⚠️  GV có NguyenVong nhưng KHÔNG có PhanCong: {len(missing_gv)}")
if missing_gv:
    print(f"   {sorted(missing_gv)}\n")

# Tính nguyện vọng của GV missing
from apps.scheduling.models import NguyenVong
missing_nv_count = NguyenVong.objects.filter(
    ma_dot=dot_xep,
    ma_gv__ma_gv__in=missing_gv
).count()
print(f"   → {missing_nv_count} NguyenVong bị mất vì GV không dạy!\n")

print("=" * 60)
print("🎯 Giải pháp:")
print("=" * 60)
print("""
Converter nên lấy nguyện vọng từ GV_ID trực tiếp,
KHÔNG phải chỉ từ GV dạy lớp.

Thay vì:
  - Chỉ xuất preference cho GV có PhanCong

Nên:
  - Xuất preference cho TẤT CẢ GV có NguyenVong
  - Dùng GV_ID trực tiếp làm key trong PREFERENCES
""")
