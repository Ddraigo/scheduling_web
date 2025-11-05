#!/usr/bin/env python3
import os, sys, django
from pathlib import Path

workspace = Path(__file__).parent
sys.path.insert(0, str(workspace))
os.chdir(str(workspace))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.scheduling.models import DotXep, PhanCong

print("=" * 60)
print("DEBUG: DotXep & PhanCong")
print("=" * 60)

all_dots = DotXep.objects.all()
print(f"\n📍 Total DotXep: {len(all_dots)}")

for dot in all_dots:
    count = PhanCong.objects.filter(ma_dot=dot).count()
    print(f"\n  DotXep: {dot.ma_dot}")
    print(f"    - Ten: {dot.ten_dot}")
    print(f"    - PhanCong count: {count}")

# Lấy DotXep đầu tiên
dot_first = DotXep.objects.first()
if dot_first:
    print(f"\n🔍 Using first DotXep: {dot_first.ma_dot}")
    pc = PhanCong.objects.filter(ma_dot=dot_first)
    print(f"   PhanCong count: {len(pc)}")
    
    if len(pc) > 0:
        print(f"\n📋 Sample PhanCong:")
        for i, p in enumerate(pc[:3]):
            print(f"   {i+1}. Lop: {p.ma_lop.ma_lop}, GV: {p.ma_gv.ten_gv if p.ma_gv else 'N/A'}")
