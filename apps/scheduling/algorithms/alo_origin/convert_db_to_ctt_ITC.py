#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert database to ITC-2007 Competition format (standard .ctt format)
WITHOUT extensions (no room types, no equipment, no preferences)

This format is compatible with the original validator.exe

Format:
- COURSES: course_id teacher_id lectures min_wd students
- ROOMS: room_id capacity
- No PREFERENCES section
- No room types or equipment
"""

import os
import sys
import django
from pathlib import Path
from collections import defaultdict

# Setup Django environment - add workspace root to path
workspace = Path(__file__).parent.parent.parent.parent.parent  # Go to project root
sys.path.insert(0, str(workspace))
os.chdir(str(workspace))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.models import (
    Khoa, MonHoc, PhongHoc, LopMonHoc, NguyenVong, DotXep, GiangVien, PhanCong, TimeSlot, KhungTG
)
from django.db.models import Count


def get_or_create_test_data(ma_dot: str = None):
    """Lấy dữ liệu từ DB
    
    Args:
        ma_dot: Mã đợt cần lấy. Nếu None, tự động chọn DotXep có dữ liệu
    """
    if ma_dot:
        # Lấy theo mã đợt được truyền vào
        try:
            dot_xep = DotXep.objects.get(ma_dot=ma_dot)
            print(f"✅ Lấy dữ liệu từ DotXep: {dot_xep.ma_dot} ({dot_xep.ten_dot})")
            return dot_xep
        except DotXep.DoesNotExist:
            print(f"❌ Không tìm thấy DotXep với mã: {ma_dot}")
            print(f"\n📋 Danh sách DotXep có sẵn:")
            all_dot = DotXep.objects.annotate(
                phan_cong_count=Count('phan_cong_list')
            ).order_by('ma_dot')
            for dot in all_dot:
                print(f"  - {dot.ma_dot} ({dot.ten_dot}): {dot.phan_cong_count} phân công")
            return None
    
    # Nếu không truyền ma_dot, tự động chọn DotXep có dữ liệu
    dot_xep_list = DotXep.objects.annotate(
        phan_cong_count=Count('phan_cong_list')
    ).filter(phan_cong_count__gt=0).order_by('-ngay_tao')[:1]
    
    if not dot_xep_list:
        print("❌ Không có DotXep nào có dữ liệu PhanCong!")
        return None
    
    dot_xep = dot_xep_list[0]
    print(f"✅ Lấy dữ liệu từ DotXep: {dot_xep.ma_dot} ({dot_xep.ten_dot})")
    return dot_xep


def export_to_itc_ctt(dot_xep, output_path: str = None):
    """
    Xuất dữ liệu ra file .ctt theo format ITC-2007 chuẩn
    
    Args:
        dot_xep: Instance DotXep
        output_path: Đường dẫn file output (default: dot_ITC.ctt)
    """
    
    if output_path is None:
        output_dir = Path(__file__).parent
        output_path = output_dir / "dot_ITC.ctt"
    
    print(f"\n📋 Bắt đầu xuất dữ liệu sang {output_path}...")
    
    # ===== 1. LẤY CÁC KHÓA HỌC =====
    courses_data = []
    course_id_map = {}
    sample_course_id = None
    sample_teacher_id = None
    
    phan_cong_list = PhanCong.objects.filter(
        ma_dot=dot_xep
    ).select_related('ma_lop__ma_mon_hoc', 'ma_gv')
    print(f"📚 Tìm thấy {len(phan_cong_list)} phân công dạy")
    
    for idx, phan_cong in enumerate(phan_cong_list):
        lop = phan_cong.ma_lop
        gv = phan_cong.ma_gv
        
        # ===== LẤY COURSE_ID THỰC TỬ phan_cong.ma_lop =====
        if lop.ma_lop:
            course_id = lop.ma_lop  # Sử dụng mã lớp thực
        else:
            course_id = f"c{idx:04d}"  # Fallback
        
        # Sample lần đầu tiên
        if idx == 0:
            sample_course_id = course_id
        
        course_id_map[lop.ma_lop] = course_id  # Use ma_lop instead of id
        
        # ===== LẤY TEACHER_ID THỰC =====
        teacher_id = gv.ma_gv if gv else f"t{idx:03d}"
        
        # Sample lần đầu tiên
        if idx == 0:
            sample_teacher_id = teacher_id
        
        num_lectures = lop.so_ca_tuan if lop.so_ca_tuan else 1
        
        # min_working_days
        so_ca_tuan = lop.so_ca_tuan if lop.so_ca_tuan else 1
        min_working_days = 2 if so_ca_tuan > 2 else 1
        
        num_students = lop.so_luong_sv if lop.so_luong_sv else 50
        
        courses_data.append({
            'id': course_id,
            'teacher': teacher_id,
            'lectures': num_lectures,
            'min_wd': min_working_days,
            'students': num_students,
            'lop': lop,
            'gv': gv
        })
    
    # ===== 2. LẤY CÁC PHÒNG HỌC =====
    rooms_data = []
    room_id_map = {}
    sample_room_id = None
    
    phong_hoc_list = PhongHoc.objects.all().order_by('ma_phong')
    print(f"🏫 Tìm thấy {len(phong_hoc_list)} phòng học")
    
    for phong in phong_hoc_list:
        # ===== LẤY ROOM_ID THỰC TỬ phong.ma_phong =====
        if phong.ma_phong:
            room_id = phong.ma_phong  # Sử dụng mã phòng thực
        else:
            room_id = f"r{idx:04d}"  # Fallback
        
        # Sample lần đầu tiên
        if sample_room_id is None:
            sample_room_id = room_id
        
        room_id_map[phong.ma_phong] = room_id  # Use ma_phong instead of id
        
        capacity = phong.suc_chua if phong.suc_chua else 50
        
        rooms_data.append({
            'id': room_id,
            'capacity': capacity
        })
    
    # ===== 3. TẠO CURRICULA (nhóm các môn học cùng MonHoc) =====
    curricula_data = []
    mon_hoc_courses = defaultdict(list)
    mon_hoc_map = {}  # ma_mon_hoc → curriculum_id
    
    for course in courses_data:
        mon_hoc = course['lop'].ma_mon_hoc
        if mon_hoc:
            mon_hoc_courses[mon_hoc.ma_mon_hoc].append(course['id'])
    
    for idx, (ma_mon_hoc, course_ids) in enumerate(sorted(mon_hoc_courses.items())):
        if len(course_ids) > 1:
            # ===== LẤY CURRICULUM_ID THỰC TỬ ma_mon_hoc =====
            # Sử dụng mã môn học thực làm curriculum_id
            curriculum_id = ma_mon_hoc
            mon_hoc_map[ma_mon_hoc] = curriculum_id
            curricula_data.append({
                'id': curriculum_id,
                'courses': course_ids
            })
    
    print(f"📚 Tạo {len(curricula_data)} curricula từ các môn học")
    
    # ===== 4. GHI FILE .CTT (ITC-2007 STANDARD FORMAT) =====
    with open(output_path, 'w', encoding='utf-8') as f:
        # Header
        f.write(f"Name: Export_{dot_xep.ma_dot}\n")
        f.write(f"Courses: {len(courses_data)}\n")
        f.write(f"Rooms: {len(rooms_data)}\n")
        f.write(f"Days: 6\n")  # T2-T7
        f.write(f"Periods_per_day: 5\n")
        f.write(f"Curricula: {len(curricula_data)}\n")
        f.write(f"Constraints: 0\n")  # No unavailability constraints
        f.write(f"\n")
        
        # COURSES section (no room type, no equipment)
        f.write(f"COURSES:\n")
        for course in courses_data:
            f.write(f"{course['id']} {course['teacher']} {course['lectures']} "
                   f"{course['min_wd']} {course['students']}\n")
        f.write(f"\n")
        
        # ROOMS section (no room type, no equipment)
        f.write(f"ROOMS:\n")
        for room in rooms_data:
            f.write(f"{room['id']} {room['capacity']}\n")
        f.write(f"\n")
        
        # CURRICULA section
        f.write(f"CURRICULA:\n")
        for curriculum in curricula_data:
            f.write(f"{curriculum['id']} {len(curriculum['courses'])} ")
            f.write(f"{' '.join(curriculum['courses'])}\n")
        f.write(f"\n")
        
        # UNAVAILABILITY_CONSTRAINTS section (empty)
        f.write(f"UNAVAILABILITY_CONSTRAINTS:\n")
        f.write(f"\n")
        
        # END_OF_FILE
        f.write(f"END.\n")
    
    print(f"✅ Đã xuất file: {output_path}")
    print(f"\n📊 THỐNG KÊ:")
    print(f"  - Courses: {len(courses_data)}")
    print(f"    └─ Sử dụng mã lớp thực (ma_lop) từ database")
    print(f"  - Rooms: {len(rooms_data)}")
    print(f"    └─ Sử dụng mã phòng thực (ma_phong) từ database")
    print(f"  - Curricula: {len(curricula_data)}")
    print(f"    └─ Sử dụng mã môn học thực (ma_mon_hoc) từ database")
    print(f"  - Days: 6 (Thứ 2-7)")
    print(f"  - Periods per day: 5")
    print(f"  - Format: ITC-2007 Standard (no extensions)")
    
    print(f"\n💾 ĐỊNH DẠNG DỮ LIỆU:")
    print(f"  ✓ Courses: {sample_course_id if courses_data else 'N/A'}")
    print(f"  ✓ Teachers: {sample_teacher_id if courses_data else 'N/A'}")
    print(f"  ✓ Rooms: {sample_room_id if rooms_data else 'N/A'}")
    print(f"  ✓ Curricula: {[c['id'] for c in curricula_data[:3]] if curricula_data else 'N/A'}")
    
    return str(output_path)


if __name__ == "__main__":
    # Lấy dữ liệu từ DB
    ma_dot = "DOT1_2025-2026_HK1" if len(sys.argv) < 2 else sys.argv[1]
    dot_xep = get_or_create_test_data(ma_dot)
    
    if dot_xep:
        # Xuất file .ctt
        output_file = export_to_itc_ctt(dot_xep)
        print(f"\n✅ Hoàn thành! File đã được tạo tại: {output_file}")
    else:
        print("\n❌ Không thể xuất file. Vui lòng kiểm tra dữ liệu!")

