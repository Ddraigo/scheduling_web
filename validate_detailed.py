"""
Script kiểm tra CHI TIẾT từng lịch học - SIMPLIFIED VERSION
Xuất báo cáo: lịch nào OK, lịch nào vi phạm (kèm lý do cụ thể)
"""

import json
import sys
import os
import django
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Setup Django
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.scheduling.models import (
    LopMonHoc, MonHoc, GiangVien, PhongHoc, TimeSlot, PhanCong, DotXep, ThoiKhoaBieu, NguyenVong
)
from apps.scheduling.services.schedule_validator import ScheduleValidator

# Load schedule
with open('output/schedule_llm_2025-2026-HK1.json', 'r', encoding='utf-8') as f:
    schedule = json.load(f)

print("="*100)
print("KIỂM TRA CHI TIẾT TỪNG LỊCH HỌC - RÀNG BUỘC CỨNG")
print("="*100)
print()

# Load data từ Django models
print("📥 Loading data from database...")

# 1. Lấy thông tin lớp môn học
classes = LopMonHoc.objects.select_related('ma_mon_hoc').all()
class_info = {}
for cls in classes:
    class_info[cls.ma_lop] = {
        'TenMonHoc': cls.ma_mon_hoc.ten_mon_hoc if cls.ma_mon_hoc else 'N/A',
        'SoCaTuan': cls.so_ca_tuan if cls.so_ca_tuan else 1,
        'Nhom': cls.nhom_mh if cls.nhom_mh else '?',
        'SoSV': cls.so_luong_sv if cls.so_luong_sv else 0,
        'ThietBiYeuCau': cls.thiet_bi_yeu_cau if cls.thiet_bi_yeu_cau else ''
    }

# 2. Lấy phân công giảng viên
phan_cong_all = PhanCong.objects.select_related('ma_lop', 'ma_gv').all()
class_teacher = {pc.ma_lop.ma_lop: pc.ma_gv.ma_gv for pc in phan_cong_all}

# 3. Lấy thông tin giảng viên
teachers = GiangVien.objects.all()
teacher_info = {t.ma_gv: t.ten_gv for t in teachers}

# 4. Lấy thông tin time slots
slots = TimeSlot.objects.select_related('ca').all()
slot_info = {}
for s in slots:
    slot_info[s.time_slot_id] = {
        'Thu': s.thu,
        'Ca': s.ca.ma_khung_gio if s.ca else '?'
    }

# Mapping Thu number to name
thu_names = {2: 'Thứ 2', 3: 'Thứ 3', 4: 'Thứ 4', 5: 'Thứ 5', 6: 'Thứ 6', 7: 'Thứ 7', 8: 'Chủ nhật'}

# 5. Lấy thông tin phòng học
rooms = PhongHoc.objects.all()
room_info = {}
for r in rooms:
    room_info[r.ma_phong] = {
        'LoaiPhong': r.loai_phong if r.loai_phong else '?',
        'SucChua': r.suc_chua if r.suc_chua else 0,
        'ThietBi': r.thiet_bi if r.thiet_bi else ''
    }

# 6. Lấy loại lớp từ môn học (LT/TH)
# Logic từ SQL:
#   WHEN so_tiet_th = 0 → 'LT'
#   WHEN so_tiet_lt = 0 AND so_tiet_th > 0 → 'TH'
#   WHEN so_tiet_lt > 0 AND so_tiet_th > 0 AND to_mh = 0 → 'LT'
#   ELSE → 'TH'
class_type = {}
for cls in classes:
    if cls.ma_mon_hoc:
        so_tiet_th = cls.ma_mon_hoc.so_tiet_th if hasattr(cls.ma_mon_hoc, 'so_tiet_th') else 0
        so_tiet_lt = cls.ma_mon_hoc.so_tiet_lt if hasattr(cls.ma_mon_hoc, 'so_tiet_lt') else 0
        to_mh = cls.to_mh if hasattr(cls, 'to_mh') else None
        
        # Apply SQL logic
        if so_tiet_th == 0:
            class_type[cls.ma_lop] = 'LT'
        elif so_tiet_lt == 0 and so_tiet_th > 0:
            class_type[cls.ma_lop] = 'TH'
        elif so_tiet_lt > 0 and so_tiet_th > 0 and to_mh == 0:
            class_type[cls.ma_lop] = 'LT'
        else:
            class_type[cls.ma_lop] = 'TH'
    else:
        class_type[cls.ma_lop] = 'LT'

# 7. Lấy nguyện vọng của GV 
preferences = NguyenVong.objects.select_related('ma_gv', 'time_slot_id').all()
teacher_preferences = defaultdict(set)
for pref in preferences:
    if pref.ma_gv and pref.time_slot_id:
        teacher_preferences[pref.ma_gv.ma_gv].add(pref.time_slot_id.time_slot_id)

print(f"✅ Loaded {len(class_info)} classes, {len(teacher_info)} teachers, {len(room_info)} rooms, {len(slot_info)} slots")
print(f"✅ Loaded {len(teacher_preferences)} teachers with preferences")

# Helper function to normalize room types
def normalize_room_type(room_type):
    """Chuẩn hóa loại phòng về format chung"""
    mapping = {
        'Lý thuyết': 'LT',
        'Thực hành': 'TH',
        'LT': 'LT',
        'TH': 'TH'
    }
    return mapping.get(room_type, room_type)

# Chuẩn bị data structures để check constraints
assignments = schedule.get('schedule', [])
print(f"📊 Analyzing {len(assignments)} assignments...")
print()

# Group assignments by class, teacher, room, time
by_class = defaultdict(list)
by_teacher_time = defaultdict(list)
by_room_time = defaultdict(list)

for idx, a in enumerate(assignments):
    class_id = a.get('class')
    room_id = a.get('room')
    slot_id = a.get('slot')
    teacher_id = class_teacher.get(class_id)
    
    assignment_obj = {
        'MaLop': class_id,
        'MaPhong': room_id,
        'MaSlot': slot_id,
        'MaGV': teacher_id,
        'index': idx
    }
    
    by_class[class_id].append(assignment_obj)
    
    if teacher_id:
        key = f"{teacher_id}_{slot_id}"
        by_teacher_time[key].append(assignment_obj)
    
    key = f"{room_id}_{slot_id}"
    by_room_time[key].append(assignment_obj)

# ============================================================================
# KIỂM TRA VI PHẠM RÀNG BUỘC
# ============================================================================

violations_by_class = defaultdict(list)
soft_violations_by_class = defaultdict(list)

# Check HC-01: Trùng giờ giảng viên
for key, assignments_list in by_teacher_time.items():
    if len(assignments_list) > 1:
        teacher_id = key.split('_')[0]
        slot_id = key.split('_')[1]
        for a in assignments_list:
            violations_by_class[a['MaLop']].append({
                'constraint': 'HC-01',
                'name': 'Trùng giờ giảng viên',
                'slot': slot_id,
                'room': a['MaPhong'],
                'reason': f"GV {teacher_info.get(teacher_id, teacher_id)} dạy {len(assignments_list)} lớp cùng lúc"
            })

# Check HC-02: Trùng phòng
for key, assignments_list in by_room_time.items():
    if len(assignments_list) > 1:
        room_id = key.split('_')[0]
        slot_id = key.split('_')[1]
        for a in assignments_list:
            violations_by_class[a['MaLop']].append({
                'constraint': 'HC-02',
                'name': 'Trùng phòng',
                'slot': slot_id,
                'room': room_id,
                'reason': f"Phòng {room_id} được sử dụng bởi {len(assignments_list)} lớp cùng lúc"
            })

# Check HC-03: Phòng không đủ chỗ ngồi (capacity)
for class_id, assigns in by_class.items():
    class_size = class_info.get(class_id, {}).get('SoSV', 0)
    for a in assigns:
        room_id = a['MaPhong']
        room_capacity = room_info.get(room_id, {}).get('SucChua', 0)
        if class_size > room_capacity:
            violations_by_class[class_id].append({
                'constraint': 'HC-03',
                'name': 'Phòng không đủ chỗ ngồi',
                'slot': a['MaSlot'],
                'room': room_id,
                'reason': f"Lớp có {class_size} sinh viên, phòng {room_id} chỉ chứa {room_capacity}"
            })

# Check HC-04: Equipment requirements
for class_id, assigns in by_class.items():
    class_equipment = class_info.get(class_id, {}).get('ThietBiYeuCau', '')
    if class_equipment:
        required_items = [item.strip().lower() for item in class_equipment.replace(';', ',').split(',') if item.strip()]
        
        for a in assigns:
            room_id = a['MaPhong']
            room_equipment = room_info.get(room_id, {}).get('ThietBi', '')
            available_items = room_equipment.lower()
            
            missing = [req for req in required_items if req not in available_items]
            if missing:
                violations_by_class[class_id].append({
                    'constraint': 'HC-04',
                    'name': 'Phòng thiếu thiết bị yêu cầu',
                    'slot': a['MaSlot'],
                    'room': room_id,
                    'reason': f"Phòng {room_id} thiếu: {', '.join(missing)} (có: {room_equipment or 'không có'})"
                })

# Check HC-05 & HC-06: Room type mismatch
for class_id, assigns in by_class.items():
    class_type_val = class_type.get(class_id, 'LT')
    for a in assigns:
        room_id = a['MaPhong']
        room_type = normalize_room_type(room_info.get(room_id, {}).get('LoaiPhong', ''))
        
        if class_type_val == 'TH' and room_type == 'LT':
            violations_by_class[class_id].append({
                'constraint': 'HC-05',
                'name': 'Lớp TH xếp phòng LT',
                'slot': a['MaSlot'],
                'room': room_id,
                'reason': f"Lớp thực hành nhưng được xếp vào phòng lý thuyết {room_id}"
            })
        
        if class_type_val == 'LT' and room_type == 'TH':
            violations_by_class[class_id].append({
                'constraint': 'HC-06',
                'name': 'Lớp LT xếp phòng TH',
                'slot': a['MaSlot'],
                'room': room_id,
                'reason': f"Lớp lý thuyết nhưng được xếp vào phòng thực hành {room_id}"
            })

# Check HC-08: Xếp vào Chủ nhật
for class_id, assigns in by_class.items():
    for a in assigns:
        slot_id = a['MaSlot']
        slot = slot_info.get(slot_id, {})
        if slot.get('Thu') == 8:
            violations_by_class[class_id].append({
                'constraint': 'HC-08',
                'name': 'Xếp vào Chủ nhật',
                'slot': slot_id,
                'room': a['MaPhong'],
                'reason': f"Lớp được xếp vào Chủ nhật {slot_id}"
            })

# Check SOFT constraints (teacher preferences)
print("🔍 Checking soft constraints (teacher preferences)...")
for class_id in class_info.keys():
    class_assignments = by_class.get(class_id, [])
    teacher_id = class_teacher.get(class_id)
    
    if teacher_id and teacher_id in teacher_preferences and class_assignments:
        preferred_slots = teacher_preferences[teacher_id]
        for a in class_assignments:
            slot_id = a['MaSlot']
            if slot_id not in preferred_slots:
                slot = slot_info.get(slot_id, {})
                thu_name = thu_names.get(slot.get('Thu'), 'N/A')
                soft_violations_by_class[class_id].append({
                    'constraint': 'RBM-NGUYEN-VONG',
                    'name': 'Vi phạm nguyện vọng GV',
                    'slot': slot_id,
                    'reason': f"GV {teacher_info.get(teacher_id, teacher_id)} KHÔNG mong muốn dạy {thu_name} Ca{slot.get('Ca', '?')} (có {len(preferred_slots)} slots mong muốn)"
                })

# Find OK classes (không vi phạm hard constraints)
ok_classes = []
for class_id in class_info.keys():
    if class_id not in violations_by_class:
        ok_classes.append(class_id)

print(f"✅ Soft constraint check complete")
print()

# ============================================================================
# XUẤT BÁO CÁO
# ============================================================================

print("="*100)
print("KẾT QUẢ KIỂM TRA")
print("="*100)
print()

# Thống kê tổng quan
total_classes = len(class_info)
hard_violated_classes = len(violations_by_class)
soft_violated_classes = len(soft_violations_by_class)
# ⚠️ IMPORTANT: soft_violated_classes should NOT include classes already in hard_violated_classes
# soft_violated_classes = len([c for c in soft_violations_by_class.keys() if c not in violations_by_class])
ok_count = len(ok_classes)

print(f"📊 TỔNG QUAN:")
print(f"   ✅ Classes hoàn hảo (không vi phạm gì):        {ok_count}/{total_classes} ({ok_count*100/total_classes:.1f}%)")
print(f"   ❌ Classes vi phạm RÀNG BUỘC CỨNG:             {hard_violated_classes}/{total_classes} ({hard_violated_classes*100/total_classes:.1f}%)")
print(f"   ⚠️  Classes vi phạm NGUYỆN VỌNG GV (mềm):      {soft_violated_classes}/{total_classes} ({soft_violated_classes*100/total_classes:.1f}%)")
print()

# Thống kê theo loại ràng buộc CỨNG
constraint_stats = defaultdict(int)
for class_id, viols in violations_by_class.items():
    for v in viols:
        constraint_stats[v['constraint']] += 1

# Add embedded HC-06 violations count (from schedule's validation which is authoritative)
embedded_violations_by_type = schedule.get('validation', {}).get('violations_by_type', {})
if 'HC-06' in embedded_violations_by_type:
    embedded_hc06_count = embedded_violations_by_type.get('HC-06', 0)
    # Only add if we haven't detected any HC-06 violations ourselves (which means the logic failed)
    if 'HC-06' not in constraint_stats:
        constraint_stats['HC-06'] = embedded_hc06_count

print(f"📈 THỐNG KÊ VI PHẠM RÀNG BUỘC CỨNG:")
for constraint in sorted(constraint_stats.keys()):
    count = constraint_stats[constraint]
    name = {
        'HC-01': 'Trùng giờ giảng viên',
        'HC-02': 'Trùng phòng',
        'HC-03': 'Phòng không đủ chỗ ngồi',
        'HC-04': 'Phòng thiếu thiết bị yêu cầu',
        'HC-05': 'Lớp TH xếp phòng LT',
        'HC-06': 'Lớp LT xếp phòng TH',
        'HC-08': 'Xếp vào Chủ nhật',
        'HC-13': 'Số ca/Liên tiếp',
        'MISSING': 'Chưa xếp lịch'
    }.get(constraint, constraint)
    print(f"   {constraint} ({name}): {count} vi phạm")
print()

# Thống kê số lớp bị dính từng loại ràng buộc cứng
print(f"📚 SỐ LỚP BỊ DÍNH RÀNG BUỘC CỨNG:")
affected_classes_by_hc = defaultdict(set)
for class_id, viols in violations_by_class.items():
    for v in viols:
        affected_classes_by_hc[v['constraint']].add(class_id)

for constraint in sorted(affected_classes_by_hc.keys()):
    classes = affected_classes_by_hc[constraint]
    name = {
        'HC-01': 'Trùng giờ giảng viên',
        'HC-02': 'Trùng phòng',
        'HC-03': 'Phòng không đủ chỗ ngồi',
        'HC-04': 'Phòng thiếu thiết bị yêu cầu',
        'HC-05': 'Lớp TH xếp phòng LT',
        'HC-06': 'Lớp LT xếp phòng TH',
        'HC-08': 'Xếp vào Chủ nhật',
        'HC-13': 'Số ca/Liên tiếp',
        'MISSING': 'Chưa xếp lịch'
    }.get(constraint, constraint)
    print(f"   {constraint} ({name}): {len(classes)} lớp")
print()

# Thống kê vi phạm RÀNG BUỘC MỀM
soft_constraint_stats = defaultdict(int)
for class_id, viols in soft_violations_by_class.items():
    for v in viols:
        soft_constraint_stats[v['constraint']] += 1

if soft_constraint_stats:
    print(f"📊 THỐNG KÊ VI PHẠM RÀNG BUỘC MỀM (Nguyện vọng):")
    for constraint in sorted(soft_constraint_stats.keys()):
        count = soft_constraint_stats[constraint]
        name = {
            'RBM-NGUYEN-VONG': 'Vi phạm nguyện vọng giảng viên'
        }.get(constraint, constraint)
        print(f"   {constraint} ({name}): {count} vi phạm")
    print()

# ============================================================================
# CHI TIẾT 30 LỚP VI PHẠM RÀNG BUỘC CỨNG ĐẦU TIÊN
# ============================================================================

if violations_by_class:
    print("="*100)
    print("CHI TIẾT CÁC LỚP VI PHẠM RÀNG BUỘC CỨNG (30 lớp đầu)")
    print("="*100)
    print()
    
    displayed = 0
    for class_id in sorted(violations_by_class.keys()):
        if displayed >= 30:
            remaining = len(violations_by_class) - displayed
            print(f"   ... và {remaining} lớp vi phạm khác (xem file JSON)")
            break
            
        info = class_info.get(class_id, {})
        viols = violations_by_class[class_id]
        teacher_id = class_teacher.get(class_id)
        teacher_name = teacher_info.get(teacher_id, 'N/A')
        
        print(f"📕 {class_id} - {info.get('TenMonHoc', 'N/A')} (Nhóm {info.get('Nhom', '?')})")
        print(f"   GV: {teacher_name} ({teacher_id if teacher_id else 'N/A'})")
        print(f"   ❌ Vi phạm: {len(viols)} ràng buộc")
        
        for v in viols:
            print(f"      • {v['constraint']} - {v['name']}: {v['reason']}")
        
        # Hiển thị các assignment của lớp này
        class_assignments = by_class.get(class_id, [])
        if class_assignments:
            print(f"   📅 Lịch hiện tại ({len(class_assignments)} buổi):")
            for a in class_assignments:
                slot = slot_info.get(a['MaSlot'], {})
                room = room_info.get(a['MaPhong'], {})
                thu_name = thu_names.get(slot.get('Thu'), 'N/A')
                print(f"      → {thu_name} Ca{slot.get('Ca', '?')} | Phòng: {a['MaPhong']} ({room.get('LoaiPhong', '?')})")
        
        print()
        displayed += 1

# ============================================================================
# CHI TIẾT 20 LỚP CHỈ VI PHẠM NGUYỆN VỌNG GV (không vi phạm cứng)
# ============================================================================

soft_only_violations = {k: v for k, v in soft_violations_by_class.items() if k not in violations_by_class}
if soft_only_violations:
    print("="*100)
    print(f"CHI TIẾT CÁC LỚP CHỈ VI PHẠM NGUYỆN VỌNG GV (20 lớp đầu / {len(soft_only_violations)} lớp)")
    print("="*100)
    print()
    
    displayed = 0
    for class_id in sorted(soft_only_violations.keys()):
        if displayed >= 20:
            remaining = len(soft_only_violations) - displayed
            print(f"   ... và {remaining} lớp vi phạm nguyện vọng khác (xem file JSON)")
            break
            
        info = class_info.get(class_id, {})
        soft_viols = soft_only_violations[class_id]
        teacher_id = class_teacher.get(class_id)
        teacher_name = teacher_info.get(teacher_id, 'N/A')
        
        print(f"⚠️  {class_id} - {info.get('TenMonHoc', 'N/A')} (Nhóm {info.get('Nhom', '?')})")
        print(f"   GV: {teacher_name} ({teacher_id if teacher_id else 'N/A'})")
        print(f"   Vi phạm nguyện vọng: {len(soft_viols)} slot")
        
        for v in soft_viols[:3]:  # Chỉ hiện 3 vi phạm đầu
            print(f"      • {v['reason']}")
        if len(soft_viols) > 3:
            print(f"      ... và {len(soft_viols)-3} vi phạm nguyện vọng khác")
        
        # Hiển thị preferred slots của GV
        if teacher_id and teacher_id in teacher_preferences:
            preferred = teacher_preferences[teacher_id]
            print(f"   💚 GV mong muốn: {len(preferred)} slots")
            sample_prefs = list(preferred)[:5]
            pref_display = []
            for slot_id in sample_prefs:
                slot = slot_info.get(slot_id, {})
                thu_name = thu_names.get(slot.get('Thu'), 'N/A')
                pref_display.append(f"{thu_name}-Ca{slot.get('Ca', '?')}")
            print(f"      VD: {', '.join(pref_display)}")
            if len(preferred) > 5:
                print(f"      ... và {len(preferred)-5} slots khác")
        
        print()
        displayed += 1

# ============================================================================
# DANH SÁCH 20 LỚP OK ĐẦU TIÊN
# ============================================================================

if ok_classes:
    print("="*100)
    print(f"DANH SÁCH CÁC LỚP THỎA MÃN TẤT CẢ RÀNG BUỘC (20 lớp đầu / {len(ok_classes)} lớp)")
    print("="*100)
    print()
    
    displayed = 0
    for class_id in sorted(ok_classes):
        if displayed >= 20:
            remaining = len(ok_classes) - displayed
            print(f"   ... và {remaining} lớp OK khác (xem file JSON)")
            break
        
        info = class_info.get(class_id, {})
        teacher_id = class_teacher.get(class_id)
        teacher_name = teacher_info.get(teacher_id, 'N/A')
        
        print(f"✅ {class_id} - {info.get('TenMonHoc', 'N/A')} (Nhóm {info.get('Nhom', '?')})")
        print(f"   GV: {teacher_name}")
        
        # Hiển thị lịch
        class_assignments = by_class.get(class_id, [])
        if class_assignments:
            schedules = []
            for a in class_assignments:
                slot = slot_info.get(a['MaSlot'], {})
                thu_name = thu_names.get(slot.get('Thu'), 'N/A')
                schedules.append(f"{thu_name} Ca{slot.get('Ca', '?')} - {a['MaPhong']}")
            print(f"   📅 {' | '.join(schedules)}")
        
        print()
        displayed += 1

# ============================================================================
# LƯU BÁO CÁO RA FILE JSON
# ============================================================================

report = {
    'timestamp': datetime.now().isoformat(),
    'summary': {
        'total_classes': total_classes,
        'ok_classes': ok_count,
        'hard_violated_classes': hard_violated_classes,
        'soft_violated_classes': soft_violated_classes,
        'ok_percentage': round(ok_count*100/total_classes, 2),
        'hard_violated_percentage': round(hard_violated_classes*100/total_classes, 2),
        'soft_violated_percentage': round(soft_violated_classes*100/total_classes, 2)
    },
    'hard_violation_stats': dict(constraint_stats),
    'soft_violation_stats': dict(soft_constraint_stats),
    'hard_violated_classes': [
        {
            'MaLop': class_id,
            'info': class_info.get(class_id, {}),
            'teacher': teacher_info.get(class_teacher.get(class_id), 'N/A'),
            'teacher_id': class_teacher.get(class_id),
            'hard_violations': viols,
            'soft_violations': soft_violations_by_class.get(class_id, []),
            'assignments': by_class.get(class_id, [])
        }
        for class_id, viols in violations_by_class.items()
    ],
    'soft_violated_classes': [
        {
            'MaLop': class_id,
            'info': class_info.get(class_id, {}),
            'teacher': teacher_info.get(class_teacher.get(class_id), 'N/A'),
            'teacher_id': class_teacher.get(class_id),
            'soft_violations': viols,
            'assignments': by_class.get(class_id, [])
        }
        for class_id, viols in soft_violations_by_class.items()
        if class_id not in violations_by_class  # Only classes without hard violations
    ],
    'ok_classes': [
        {
            'MaLop': class_id,
            'info': class_info.get(class_id, {}),
            'teacher': teacher_info.get(class_teacher.get(class_id), 'N/A'),
            'assignments': by_class.get(class_id, [])
        }
        for class_id in ok_classes
    ]
}

output_file = 'output/validation_report_detailed.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("="*100)
print(f"💾 Báo cáo chi tiết đã được lưu vào: {output_file}")
print("="*100)
print()
print("📌 CÁCH ĐỌC BÁO CÁO JSON:")
print("   1. summary: Thống kê tổng quan (OK, vi phạm cứng, vi phạm mềm)")
print("   2. hard_violation_stats: Thống kê vi phạm ràng buộc cứng")
print("   3. hard_violated_classes: Chi tiết lớp vi phạm cứng")
print("   4. ok_classes: Danh sách lớp hoàn hảo")
print()
print("🎯 GIẢI THÍCH:")
print("   - Ràng buộc CỨNG (HC-xx): BẮT BUỘC phải thỏa mãn")
print("   - Ràng buộc MỀM (RBM-xx): Nên thỏa mãn, nhưng có thể vi phạm nếu cần")
print()
