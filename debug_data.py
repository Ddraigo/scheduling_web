#!/usr/bin/env python
"""
Debug script để kiểm tra dữ liệu trong database
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.models import DotXep, PhanCong, LopMonHoc, PhongHoc, TimeSlot, MonHoc

print("=" * 80)
print("📊 KIỂM TRA DỮ LIỆU DATABASE")
print("=" * 80)

# 1. Danh sách đợt xếp
print("\n1️⃣ DANH SÁCH ĐỢT XẾP:")
dots = DotXep.objects.all()
for dot in dots:
    phan_cong_count = PhanCong.objects.filter(ma_dot=dot).count()
    print(f"   - {dot.ma_dot}: {dot.ten_dot} ({phan_cong_count} phân công)")

if not dots.exists():
    print("   ❌ KHÔNG CÓ ĐỢT XẾP NÀO!")

# 2. Chi tiết một đợt (nếu có)
if dots.exists():
    first_dot = dots.first()
    ma_dot = first_dot.ma_dot
    print(f"\n2️⃣ CHI TIẾT ĐỢT: {ma_dot}")
    
    phan_congs = PhanCong.objects.filter(ma_dot=first_dot).select_related('ma_lop', 'ma_gv')
    print(f"   Phân công: {phan_congs.count()}")
    for i, pc in enumerate(phan_congs[:5]):
        print(f"      {i+1}. Lớp {pc.ma_lop.ma_lop}, GV: {pc.ma_gv.ten_gv if pc.ma_gv else 'N/A'}, SV: {pc.ma_lop.so_luong_sv}, Ca/tuần: {pc.ma_lop.so_ca_tuan}")
    if phan_congs.count() > 5:
        print(f"      ... và {phan_congs.count() - 5} phân công khác")

# 3. Phòng học
print(f"\n3️⃣ PHÒNG HỌC:")
rooms = PhongHoc.objects.all()
print(f"   Tổng phòng: {rooms.count()}")
for i, room in enumerate(rooms[:5]):
    print(f"      {i+1}. {room.ma_phong}: {room.suc_chua} chỗ")
if rooms.count() > 5:
    print(f"      ... và {rooms.count() - 5} phòng khác")

if not rooms.exists():
    print("   ❌ KHÔNG CÓ PHÒNG NÀO!")

# 4. Time slots
print(f"\n4️⃣ TIME SLOTS:")
slots = TimeSlot.objects.all()
print(f"   Tổng time slot: {slots.count()}")
for i, slot in enumerate(slots[:5]):
    print(f"      {i+1}. {slot.time_slot_id}")
if slots.count() > 5:
    print(f"      ... và {slots.count() - 5} time slot khác")

if not slots.exists():
    print("   ❌ KHÔNG CÓ TIME SLOT NÀO!")

# 5. Môn học
print(f"\n5️⃣ MÔN HỌC:")
mons = MonHoc.objects.all()
print(f"   Tổng môn: {mons.count()}")
for i, mon in enumerate(mons[:5]):
    print(f"      {i+1}. {mon.ma_mon_hoc}: {mon.ten_mon_hoc} ({mon.so_tuan} tuần)")
if mons.count() > 5:
    print(f"      ... và {mons.count() - 5} môn khác")

print("\n" + "=" * 80)
print("✅ Kiểm tra hoàn tất!")
print("=" * 80)
