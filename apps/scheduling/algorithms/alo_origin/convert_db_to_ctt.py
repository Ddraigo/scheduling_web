#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script để chuyển đổi dữ liệu từ Django DB sang format .ctt cho algo_new.py

Format .ctt (ITC-2007 Track 3):
- COURSES: course_id teacher_id num_lectures min_working_days num_students
- ROOMS: room_id capacity
- CURRICULA: curriculum_id num_courses course1 course2 ...
- UNAVAILABILITY_CONSTRAINTS: course_id day period

Dữ liệu được lấy từ models:
- KhoaHoc, GiangVien, Phong, NhomHoc, KhoaHocNhomHoc, NguyenVong
"""

import os
import sys
import django
from pathlib import Path
from collections import defaultdict

# Setup Django
workspace = Path(__file__).parent.parent.parent.parent.parent  # Go to project root
sys.path.insert(0, str(workspace))
os.chdir(str(workspace))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django.setup()

from apps.scheduling.models import (
    Khoa, MonHoc, PhongHoc, LopMonHoc, NguyenVong, DotXep, GiangVien, PhanCong, TimeSlot, KhungTG
)
from django.db.models import Count, Q, F


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
    from django.db.models import Count
    dot_xep_list = DotXep.objects.annotate(
        phan_cong_count=Count('phan_cong_list')
    ).filter(phan_cong_count__gt=0).order_by('-ngay_tao')[:1]
    
    if not dot_xep_list:
        print("❌ Không có DotXep nào có dữ liệu PhanCong!")
        print(f"\n📋 Danh sách tất cả DotXep:")
        all_dot = DotXep.objects.all()
        for dot in all_dot:
            print(f"  - {dot.ma_dot} ({dot.ten_dot})")
        return None
    
    dot_xep = dot_xep_list[0]
    print(f"✅ Lấy dữ liệu từ DotXep: {dot_xep.ma_dot} ({dot_xep.ten_dot})")
    return dot_xep


def export_to_ctt(dot_xep, output_path: str = None):
    """
    Xuất dữ liệu ra file .ctt
    
    Args:
        dot_xep: Instance DotXep
        output_path: Đường dẫn file output (default: output_{ma_dot}.ctt)
    """
    
    if output_path is None:
        output_dir = Path(__file__).parent
        output_path = output_dir / f"dot1.ctt"
    
    print(f"\n📋 Bắt đầu xuất dữ liệu sang {output_path}...")
    
    # ===== 1. LẤY CÁC KHÓA HỌC =====
    courses_data = []
    course_id_map = {}  # id_lop -> course_id (c0001, c0002, ...)
    
    # Filter LopMonHoc thông qua PhanCong (phân công)
    phan_cong_list = PhanCong.objects.filter(
        ma_dot=dot_xep
    ).select_related('ma_lop__ma_mon_hoc', 'ma_gv')
    print(f"📚 Tìm thấy {len(phan_cong_list)} phân công dạy")
    
    for idx, phan_cong in enumerate(phan_cong_list):
        lop = phan_cong.ma_lop
        gv = phan_cong.ma_gv
        
        course_id = f"c{idx:04d}"
        
        # Lấy giảng viên từ phân công
        # Dùng ma_gv hoặc course_id nếu không có GV
        if gv:
            teacher_id = gv.ma_gv[:10]  # Lấy 10 ký tự đầu của ma_gv
        else:
            teacher_id = f"t{idx:03d}"
        
        # Lấy số tiết từ lớp - so_ca_tuan (số ca/tuần) là số tiết cần xếp
        num_lectures = lop.so_ca_tuan if lop.so_ca_tuan else 1  # Số ca/tuần = số tiết
        
        # ===== TÍNH min_working_days dựa trên so_ca_tuan =====
        so_ca_tuan = lop.so_ca_tuan if lop.so_ca_tuan else 1
        
        # Quy tắc:
        # - Nếu so_ca_tuan > 2: min_working_days = 2 (phân bổ ra nhiều ngày)
        # - Nếu so_ca_tuan <= 2: min_working_days = 1 (có thể xếp cùng 1 ngày)
        if so_ca_tuan > 2:
            min_working_days = 2
        else:
            min_working_days = 1
        
        # Số sinh viên từ so_luong_sv
        num_students = lop.so_luong_sv if lop.so_luong_sv else 50  # Default
        
        course_id_map[lop.ma_lop] = course_id  # Use ma_lop as key, not id
        courses_data.append({
            'id': course_id,
            'teacher': teacher_id,
            'lectures': num_lectures,
            'min_working_days': min_working_days,
            'students': num_students,
            'lop': lop,
            'so_ca_tuan': so_ca_tuan,
            'phan_cong': phan_cong
        })
    
    print(f"✅ Xuất {len(courses_data)} lớp môn học")
    
    # Debug: Hiển thị thông tin chi tiết
    print(f"\n📊 Chi tiết min_working_days:")
    min_wd_1 = sum(1 for c in courses_data if c['min_working_days'] == 1)
    min_wd_2 = sum(1 for c in courses_data if c['min_working_days'] == 2)
    print(f"  - min_working_days = 1 (so_ca_tuan <= 2): {min_wd_1} lớp")
    print(f"  - min_working_days = 2 (so_ca_tuan > 2): {min_wd_2} lớp")
    
    # Hiển thị top 10 lớp để debug
    print(f"\n📋 Top 10 lớp môn học (đầu tiên):")
    for i, course in enumerate(courses_data[:10]):
        print(f"  {i+1}. {course['id']} ({course['lop'].ma_lop}) - "
              f"so_ca_tuan={course.get('so_ca_tuan', 1)}, "
              f"min_wd={course['min_working_days']}, "
              f"lectures={course['lectures']}, "
              f"students={course['students']}")
    
    # ===== 2. LẤY CÁC PHÒNG =====
    rooms_data = []
    room_id_map = {}  # ma_phong -> room_id
    
    phong_list = PhongHoc.objects.all()
    print(f"🏛️  Tìm thấy {len(phong_list)} phòng")
    
    for idx, phong in enumerate(phong_list):
        room_id = phong.ma_phong[:10]  # Lấy 10 ký tự đầu
        capacity = phong.suc_chua if phong.suc_chua else 50
        
        room_id_map[phong.ma_phong] = room_id  # Use ma_phong as key, not id
        rooms_data.append({
            'id': room_id,
            'capacity': capacity,
            'phong': phong
        })
    
    print(f"✅ Xuất {len(rooms_data)} phòng")
    
    # ===== 3. LẤY CÁC NGÀNH (CURRICULA) =====
    # Một ngành = một MonHoc - các lớp của cùng 1 môn không được trùng lịch (HC-02: Curriculum Conflict)
    curricula_data = []
    curriculum_id_map = {}
    
    # Nhóm lớp học theo MonHoc (đây là ngành)
    lop_by_mon = defaultdict(list)
    for phan_cong in phan_cong_list:
        lop = phan_cong.ma_lop
        mon_hoc = lop.ma_mon_hoc
        if lop.ma_lop in course_id_map:
            lop_by_mon[mon_hoc.ma_mon_hoc].append(course_id_map[lop.ma_lop])
    
    print(f"🎓 Tìm thấy {len(lop_by_mon)} môn học (ngành)")
    
    for idx, (mon_hoc_id, lop_ids) in enumerate(lop_by_mon.items()):
        curriculum_id = f"q{idx:03d}"
        
        # lop_ids đã là course_ids rồi
        course_ids = lop_ids
        
        if course_ids:
            curriculum_id_map[mon_hoc_id] = curriculum_id
            curricula_data.append({
                'id': curriculum_id,
                'courses': course_ids,
                'mon_hoc_id': mon_hoc_id
            })
    
    print(f"✅ Xuất {len(curricula_data)} ngành (curricula)")
    
    # ===== 4. LẤY NGUYỆN VỌNG (PREFERRED PERIODS) =====
    # Nguyện vọng của GV = các slot MONG MUỐN dạy (soft constraint)
    # Trong SQL: tb_NGUYEN_VONG(MaGV, MaDot, TimeSlotID)
    # => Một nguyện vọng = (GV, TimeSlot) chứ KHÔNG phải (GV, TimeSlot, LopMonHoc)
    # => Áp dụng cho tất cả lớp mà GV dạy trong đợt đó
    
    unavailability_constraints = []
    preferred_periods = []  # Lưu nguyện vọng
    
    nguyen_vong_list = NguyenVong.objects.filter(
        ma_dot=dot_xep
    ).select_related('ma_gv', 'time_slot_id__ca')
    print(f"🗓️  Tìm thấy {len(nguyen_vong_list)} nguyện vọng (preferred periods)")
    
    # Map: gv_id -> list of course_ids dạy bởi GV đó
    gv_courses = defaultdict(list)
    for phan_cong in phan_cong_list:
        if phan_cong.ma_gv and phan_cong.ma_lop.ma_lop in course_id_map:
            course_id = course_id_map[phan_cong.ma_lop.ma_lop]
            gv_courses[phan_cong.ma_gv.ma_gv].append(course_id)
    
    # Xử lý từng nguyện vọng: ghi 1 lần per (GV, day, period)
    # Chọn 1 course representative để ghi vào file .ctt
    # (Thuật toán sẽ hiểu rằng GV rảnh vào lúc đó, có thể xếp bất kỳ lớp nào)
    unique_prefs = set()
    for nv in nguyen_vong_list:
        time_slot = nv.time_slot_id
        # Convert ngày từ database (2-8: Thứ 2 - CN) sang .ctt format (0-4: Day 0-4)
        # Thứ 2=2→0, Thứ 3=3→1, Thứ 4=4→2, Thứ 5=5→3, Thứ 6=6→4, Thứ 7=7→5, CN=8→6
        day_db = time_slot.thu if time_slot and time_slot.thu else 0
        day = min(day_db - 2, 4) if day_db >= 2 else 0  # Convert and cap at 4
        
        # Convert period từ database (1-5) sang .ctt format (0-4)
        period_db = time_slot.ca.ma_khung_gio if time_slot and time_slot.ca else 1
        period = period_db - 1  # Convert: 1→0, 2→1, ..., 5→4
        
        # Skip nếu period ngoài phạm vi (>= 6)
        if period >= 6:
            continue
        
        gv_id = nv.ma_gv.ma_gv if nv.ma_gv else None
        
        if not gv_id or gv_id not in gv_courses or not gv_courses[gv_id]:
            continue
        
        # Kiểm tra đã có preference này chưa
        pref_key = (gv_id, day, period)
        if pref_key in unique_prefs:
            continue
        unique_prefs.add(pref_key)
        
        # Chọn lớp đầu tiên của GV này làm representative
        course_id = gv_courses[gv_id][0]
        preferred_periods.append({
            'course': course_id,
            'day': day,
            'period': period,
            'teacher': nv.ma_gv.ten_gv if nv.ma_gv else 'Unknown',
            'gv_id': gv_id
        })
    
    # Debug: Hiển thị chi tiết nguyện vọng
    print(f"\n📋 Chi tiết nguyện vọng (sample):")
    for i, pref in enumerate(preferred_periods[:10]):
        print(f"  {i+1}. {pref['course']} - GV: {pref['teacher']} ({pref['gv_id']}), "
              f"Thu: {pref['day']}, Ca: {pref['period']}")
    
    print(f"\n💡 Ghi chú:")
    print(f"  - NguyenVong = soft constraint (ưu tiên, không bắt buộc)")
    print(f"  - Unavailability = hard constraint (slot cấm)")
    print(f"  - Hiện tại database không có thông tin slot cấm → unavailability để trống")
    print(f"  - Mỗi nguyện vọng là (GV, TimeSlot) → áp dụng cho tất cả lớp GV dạy")
    
    # ===== 5. GHI FILE =====
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"Name: Export_{dot_xep.ma_dot}\n")
        f.write(f"Courses: {len(courses_data)}\n")
        f.write(f"Rooms: {len(rooms_data)}\n")
        f.write(f"Days: 5\n")  # 5 ngày trong tuần (Thứ 2 - CN)
        f.write(f"Periods_per_day: 5\n")  # 5 ca/ngày (từ database)
        f.write(f"Curricula: {len(curricula_data)}\n")
        f.write(f"Constraints: {len(unavailability_constraints)}\n")
        f.write(f"Preferences: {len(preferred_periods)}\n\n")
        
        # COURSES
        f.write("COURSES:\n")
        for course in courses_data:
            f.write(f"{course['id']} {course['teacher']} {course['lectures']} {course['min_working_days']} {course['students']}\n")
        f.write("\n")
        
        # ROOMS
        f.write("ROOMS:\n")
        for room in rooms_data:
            f.write(f"{room['id']} {room['capacity']}\n")
        f.write("\n")
        
        # CURRICULA
        f.write("CURRICULA:\n")
        for curriculum in curricula_data:
            course_str = " ".join(curriculum['courses'])
            f.write(f"{curriculum['id']} {len(curriculum['courses'])} {course_str}\n")
        f.write("\n")
        
        # UNAVAILABILITY
        f.write("UNAVAILABILITY_CONSTRAINTS:\n")
        for constraint in unavailability_constraints:
            f.write(f"{constraint['course']} {constraint['day']} {constraint['period']}\n")
        f.write("\n")
        
        # PREFERENCES (NEW: Nguyện vọng của GV - format: teacher_id day period)
        f.write("PREFERENCES:\n")
        for pref in preferred_periods:
            f.write(f"{pref['gv_id']} {pref['day']} {pref['period']}\n")
        
        f.write("\nEND.\n")
    
    print(f"\n✅ Xuất thành công sang {output_path}")
    print(f"\n📊 Thống kê:")
    print(f"  - Khóa học: {len(courses_data)}")
    print(f"  - Phòng: {len(rooms_data)}")
    print(f"  - Ngành: {len(curricula_data)}")
    print(f"  - Unavailability: {len(unavailability_constraints)}")
    print(f"  - Preferences (Nguyện vọng): {len(preferred_periods)}")
    print(f"  - Total periods: 5 × 5 = 25")
    
    return output_path


def main():
    """Main entry point"""
    print("=" * 60)
    print("🔄 CONVERTER: Database → .ctt format")
    print("=" * 60)
    
    # Hardcode mã đợt
    ma_dot = "DOT1_2025-2026_HK1"
    print(f"\n📌 Sử dụng: ma_dot = '{ma_dot}'")
    
    dot_xep = get_or_create_test_data(ma_dot=ma_dot)
    if not dot_xep:
        print("❌ Không thể lấy dữ liệu test!")
        sys.exit(1)
    
    output_file = export_to_ctt(dot_xep)
    
    print(f"\n✨ Dữ liệu đã sẵn sàng tại: {output_file}")
    print("Bây giờ bạn có thể chạy algo_new.py với:")
    print(f"  python apps/scheduling/algorithms/alo_origin/algo_new.py --instance {output_file}")


if __name__ == "__main__":
    main()
