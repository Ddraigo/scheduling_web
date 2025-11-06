#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script kiểm tra phòng TH và thiết bị
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

from apps.scheduling.models import PhongHoc

def main():
    print("=" * 80)
    print("🏛️  KIỂM TRA PHÒNG TH VÀ THIẾT BỊ")
    print("=" * 80)
    
    # Lấy tất cả phòng
    all_rooms = PhongHoc.objects.all()
    print(f"\nTổng số phòng: {all_rooms.count()}")
    
    # Đếm phòng TH
    th_rooms = []
    lt_rooms = []
    
    for phong in all_rooms:
        loai_phong = phong.loai_phong or ""
        room_type = "TH" if ("Thực hành" in loai_phong or "TH" in loai_phong) else "LT"
        
        if room_type == "TH":
            th_rooms.append(phong)
        else:
            lt_rooms.append(phong)
    
    print(f"- Phòng LT: {len(lt_rooms)}")
    print(f"- Phòng TH: {len(th_rooms)}")
    
    # Kiểm tra phòng TH có "TV, Máy chiếu"
    print(f"\n{'='*80}")
    print("📺 PHÒNG TH CÓ 'TV, Máy chiếu':")
    print(f"{'='*80}")
    
    th_with_tv = []
    for phong in th_rooms:
        equipment = phong.thiet_bi or ""
        if "TV" in equipment and "Máy chiếu" in equipment:
            th_with_tv.append(phong)
    
    if th_with_tv:
        print(f"✅ Tìm thấy {len(th_with_tv)} phòng TH có 'TV, Máy chiếu':")
        for phong in th_with_tv[:10]:  # Hiển thị 10 phòng đầu
            print(f"  - {phong.ma_phong} (sức chứa: {phong.suc_chua}) - {phong.thiet_bi}")
    else:
        print("❌ KHÔNG có phòng TH nào có 'TV, Máy chiếu'!")
    
    # Kiểm tra tất cả phòng TH và thiết bị
    print(f"\n{'='*80}")
    print("📋 DANH SÁCH PHÒNG TH VÀ THIẾT BỊ (top 20):")
    print(f"{'='*80}")
    
    for phong in th_rooms[:20]:
        equipment = phong.thiet_bi or "(không có)"
        print(f"  - {phong.ma_phong}: loai_phong='{phong.loai_phong}', thiet_bi='{equipment}'")
    
    # Kiểm tra phòng LT có "TV, Máy chiếu"
    print(f"\n{'='*80}")
    print("📺 PHÒNG LT CÓ 'TV, Máy chiếu':")
    print(f"{'='*80}")
    
    lt_with_tv = []
    for phong in lt_rooms:
        equipment = phong.thiet_bi or ""
        if "TV" in equipment and "Máy chiếu" in equipment:
            lt_with_tv.append(phong)
    
    if lt_with_tv:
        print(f"✅ Tìm thấy {len(lt_with_tv)} phòng LT có 'TV, Máy chiếu':")
        for phong in lt_with_tv[:10]:
            print(f"  - {phong.ma_phong} (sức chứa: {phong.suc_chua}) - {phong.thiet_bi}")
    else:
        print("❌ KHÔNG có phòng LT nào có 'TV, Máy chiếu'!")
    
    # Giải pháp
    print(f"\n{'='*80}")
    print("💡 GIẢI PHÁP:")
    print(f"{'='*80}")
    print("1. Thêm thiết bị 'TV, Máy chiếu' vào phòng TH trong database")
    print("2. Hoặc: Chuyển 6 courses TH cần 'TV, Máy chiếu' thành courses LT (nếu đúng nghiệp vụ)")
    print("3. Hoặc: Xóa yêu cầu thiết bị 'TV, Máy chiếu' khỏi 6 courses này")
    print("4. Hoặc: Nới lỏng constraint HC-04 (Equipment) để không bắt buộc strict matching")

if __name__ == "__main__":
    main()
