#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script kiểm tra dữ liệu của 6 courses bị lỗi
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
workspace = Path(__file__).parent
sys.path.insert(0, str(workspace))
os.chdir(str(workspace))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django.setup()

from apps.scheduling.models import LopMonHoc

def main():
    courses = [
        'LOP-00000157', 'LOP-00000160', 'LOP-00000163',
        'LOP-00000166', 'LOP-00000187', 'LOP-00000190'
    ]
    
    print("=" * 80)
    print("📊 KIỂM TRA 6 COURSES BỊ LỖI")
    print("=" * 80)
    
    for ma_lop in courses:
        try:
            lop = LopMonHoc.objects.get(ma_lop=ma_lop)
            mon = lop.ma_mon_hoc
            
            so_tiet_lt = mon.so_tiet_lt if mon else 0
            so_tiet_th = mon.so_tiet_th if mon else 0
            to_mh = lop.to_mh if hasattr(lop, 'to_mh') else 'N/A'
            thiet_bi = lop.thiet_bi_yeu_cau or ""
            
            # Xác định course_type theo logic
            if so_tiet_th == 0 and to_mh == 0:
                course_type = "LT"
            elif so_tiet_lt == 0 and so_tiet_th > 0:
                course_type = "TH"
            elif so_tiet_lt > 0 and so_tiet_th > 0 and to_mh == 0:
                course_type = "LT"
            else:
                course_type = "TH"
            
            print(f"\n{ma_lop}:")
            print(f"  - so_tiet_lt: {so_tiet_lt}")
            print(f"  - so_tiet_th: {so_tiet_th}")
            print(f"  - to_mh: {to_mh}")
            print(f"  - thiet_bi_yeu_cau: '{thiet_bi}'")
            print(f"  - => course_type: {course_type}")
            
            # Phân tích logic
            if so_tiet_th == 0 and to_mh == 0:
                print(f"  - Logic: so_tiet_th=0 AND to_mh=0 → LT ✅")
            elif so_tiet_lt == 0 and so_tiet_th > 0:
                print(f"  - Logic: so_tiet_lt=0 AND so_tiet_th>0 → TH")
            elif so_tiet_lt > 0 and so_tiet_th > 0 and to_mh == 0:
                print(f"  - Logic: so_tiet_lt>0 AND so_tiet_th>0 AND to_mh=0 → LT")
            else:
                print(f"  - Logic: Fallback else → TH ⚠️")
                print(f"    (Có thể do to_mh != 0 hoặc điều kiện khác)")
        
        except LopMonHoc.DoesNotExist:
            print(f"\n{ma_lop}: ❌ KHÔNG TÌM THẤY!")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
