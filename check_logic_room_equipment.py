#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check room type and equipment logic"""

import os
import sys
import django
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.models import LopMonHoc, MonHoc, PhongHoc
from collections import defaultdict

print("\n" + "="*120)
print("KIỂM TRA LOGIC PHÒNG LT/TH VÀ THIẾT BỊ")
print("="*120)

# 1. Check MonHoc - xem có bao nhiêu mon có TH, LT, hoặc cả hai
print("\n[1. MonHoc Analysis - Số tiết LT và TH]")
mon_stats = defaultdict(lambda: {"LT_only": 0, "TH_only": 0, "Both": 0, "None": 0})

all_mon = MonHoc.objects.all()
for mon in all_mon:
    so_lt = mon.so_tiet_lt or 0
    so_th = mon.so_tiet_th or 0
    
    if so_lt > 0 and so_th > 0:
        mon_stats["Both"]["Both"] += 1
    elif so_lt > 0:
        mon_stats["LT_only"]["LT_only"] += 1
    elif so_th > 0:
        mon_stats["TH_only"]["TH_only"] += 1
    else:
        mon_stats["None"]["None"] += 1

print("  - Có cả LT và TH: ", sum(1 for m in all_mon if (m.so_tiet_lt or 0) > 0 and (m.so_tiet_th or 0) > 0))
print("  - Chỉ LT: ", sum(1 for m in all_mon if (m.so_tiet_lt or 0) > 0 and (m.so_tiet_th or 0) == 0))
print("  - Chỉ TH: ", sum(1 for m in all_mon if (m.so_tiet_lt or 0) == 0 and (m.so_tiet_th or 0) > 0))
print("  - Không có TH/LT: ", sum(1 for m in all_mon if (m.so_tiet_lt or 0) == 0 and (m.so_tiet_th or 0) == 0))

# 2. Check LopMonHoc - xem logicxác định LT/TH
print("\n[2. LopMonHoc Classification - Logic xác định LT/TH]")

lop_stats = {"LT": 0, "TH": 0, "Both_classified_as_TH": 0, "None_classified_as_LT": 0}

all_lop = LopMonHoc.objects.all().select_related('ma_mon_hoc')
for lop in all_lop:
    mon = lop.ma_mon_hoc
    so_lt = mon.so_tiet_lt or 0
    so_th = mon.so_tiet_th or 0
    
    # Logic từ adapter: course_type = "TH" if so_tiet_th > 0 else "LT"
    predicted_type = "TH" if so_th > 0 else "LT"
    
    if so_lt > 0 and so_th > 0:
        lop_stats["Both_classified_as_TH"] += 1
    elif so_th > 0:
        lop_stats["TH"] += 1
    elif so_lt > 0:
        lop_stats["LT"] += 1
    else:
        lop_stats["None_classified_as_LT"] += 1

print("  - LT only: ", lop_stats["LT"])
print("  - TH only: ", lop_stats["TH"])
print("  - Both (classified as TH): ", lop_stats["Both_classified_as_TH"])
print("  - None (classified as LT): ", lop_stats["None_classified_as_LT"])

# 3. Check PhongHoc - xem phòng được phân loại như thế nào
print("\n[3. PhongHoc Classification - Logic xác định LT/TH]")

room_stats = {"LT": 0, "TH": 0}
room_by_type = {"LT": [], "TH": []}

all_phong = PhongHoc.objects.all()
for phong in all_phong:
    loai = phong.loai_phong or ""
    # Logic từ adapter: room_type = "TH" if ("Thực hành" in loai or "TH" in loai) else "LT"
    predicted_type = "TH" if ("Thực hành" in loai or "TH" in loai) else "LT"
    
    room_stats[predicted_type] += 1
    room_by_type[predicted_type].append((phong.ma_phong, loai))

print("  - LT: ", room_stats["LT"])
print("  - TH: ", room_stats["TH"])

# 4. Check equipment
print("\n[4. Equipment Analysis - Thiết bị]")

lop_with_equip = 0
phong_with_equip = 0
equip_types = defaultdict(int)
phong_equip_types = defaultdict(int)

for lop in LopMonHoc.objects.all():
    if lop.thiet_bi_yeu_cau:
        lop_with_equip += 1
        equip_types[lop.thiet_bi_yeu_cau] += 1

for phong in PhongHoc.objects.all():
    if phong.thiet_bi:
        phong_with_equip += 1
        phong_equip_types[phong.thiet_bi] += 1

print(f"  - Lớp yêu cầu thiết bị: {lop_with_equip}/{len(list(LopMonHoc.objects.all()))}")
print(f"  - Phòng có thiết bị: {phong_with_equip}/{len(list(PhongHoc.objects.all()))}")

print("\n  [Top 10 Loại thiết bị yêu cầu từ Lớp]")
for equip, count in sorted(equip_types.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"    {equip[:40]:<40}: {count} lớp")

print("\n  [Top 10 Loại thiết bị có sẵn từ Phòng]")
for equip, count in sorted(phong_equip_types.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"    {equip[:40]:<40}: {count} phòng")

# 5. Check room type vs equipment matching
print("\n[5. Room Type vs Equipment Matching]")

th_rooms_no_equip = 0
lt_rooms_no_equip = 0
th_rooms_with_pc = 0
th_rooms_with_other = 0

for phong in PhongHoc.objects.all():
    loai = phong.loai_phong or ""
    room_type = "TH" if ("Thực hành" in loai or "TH" in loai) else "LT"
    equip = phong.thiet_bi or ""
    
    if room_type == "TH":
        if not equip:
            th_rooms_no_equip += 1
        elif "PC" in equip:
            th_rooms_with_pc += 1
        else:
            th_rooms_with_other += 1
    else:
        if not equip:
            lt_rooms_no_equip += 1

print(f"  - TH rooms mà không có thiết bị: {th_rooms_no_equip}")
print(f"  - TH rooms có PC: {th_rooms_with_pc}")
print(f"  - TH rooms có thiết bị khác (không PC): {th_rooms_with_other}")
print(f"  - LT rooms mà không có thiết bị: {lt_rooms_no_equip}")

# 6. Check specific course vs room matching
print("\n[6. Sample Courses vs Available Rooms]")

sample_courses = LopMonHoc.objects.all()[:10]
for lop in sample_courses:
    mon = lop.ma_mon_hoc
    so_th = mon.so_tiet_th or 0
    course_type = "TH" if so_th > 0 else "LT"
    equip_req = lop.thiet_bi_yeu_cau or "NONE"
    
    # Find matching rooms
    matching_rooms = 0
    for phong in PhongHoc.objects.all():
        loai = phong.loai_phong or ""
        room_type = "TH" if ("Thực hành" in loai or "TH" in loai) else "LT"
        room_equip = phong.thiet_bi or ""
        
        # Check if room matches
        type_match = room_type == course_type
        equip_match = equip_req == "NONE" or (equip_req in room_equip if equip_req else True)
        
        if type_match and equip_match:
            matching_rooms += 1
    
    print(f"  - {lop.ma_lop} ({course_type}, Equipment: {equip_req[:30]}): {matching_rooms} phòng phù hợp")

print("\n" + "="*120)
print("KẾT LUẬN")
print("="*120)
print("""
1. LOGIC PHÂN LOẠI PHÒNG:
   - Logic: "TH" if "Thực hành" or "TH" in loai_phong else "LT"
   - Cần kiểm tra: Có phòng nào bị phân loại sai không?

2. LOGIC PHÂN LOẠI LỚP:
   - Logic: "TH" if so_tiet_th > 0 else "LT"
   - Cần kiểm tra: Có lớp "Both LT+TH" bị phân loại sai không?

3. THIẾT BỊ:
   - Một số lớp yêu cầu thiết bị (TV, Máy chiếu, PC, etc.)
   - Nhưng phòng TH hầu hết chỉ có PC
   - Này gây infeasibility - lớp yêu cầu "TV, Máy chiếu" nhưng phòng TH không có

4. GỢI Ý SỬA:
   - Equipment không nên là HARD CONSTRAINT (quá chặt)
   - Chỉ Type (LT vs TH) là HARD CONSTRAINT
   - Equipment là SOFT CONSTRAINT (ưu tiên nhưng không bắt buộc)
""")
