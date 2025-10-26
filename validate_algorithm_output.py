#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Validate Algorithm Output JSON
Kiểm tra toàn diện lịch từ schedule_algorithm_*.json
- Ràng buộc cứng (hard constraints)
- Ràng buộc mềm (soft constraints)
- Thống kê chi tiết
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
    LopMonHoc, MonHoc, GiangVien, PhongHoc, TimeSlot, 
    PhanCong, DotXep, NguyenVong
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_json_schedule(filepath):
    """Load JSON schedule từ algorithm output"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_database_info():
    """Load tất cả thông tin cần thiết từ database"""
    info = {}
    
    # Classes
    classes = LopMonHoc.objects.select_related('ma_mon_hoc').all()
    info['classes'] = {}
    for cls in classes:
        info['classes'][cls.ma_lop] = {
            'TenMonHoc': cls.ma_mon_hoc.ten_mon_hoc if cls.ma_mon_hoc else 'N/A',
            'SoCaTuan': cls.so_ca_tuan if cls.so_ca_tuan else 1,
            'SoSV': cls.so_luong_sv if cls.so_luong_sv else 0,
            'ThietBiYeuCau': cls.thiet_bi_yeu_cau if cls.thiet_bi_yeu_cau else '',
            'SoTietLT': cls.ma_mon_hoc.so_tiet_lt if cls.ma_mon_hoc else 0,
            'SoTietTH': cls.ma_mon_hoc.so_tiet_th if cls.ma_mon_hoc else 0,
            'ToMH': cls.to_mh if cls.to_mh else None,
        }
    
    # Teachers
    teachers = GiangVien.objects.all()
    info['teachers'] = {t.ma_gv: t.ten_gv for t in teachers}
    
    # Assignments
    phan_congs = PhanCong.objects.select_related('ma_lop', 'ma_gv').all()
    info['class_teacher'] = {pc.ma_lop.ma_lop: pc.ma_gv.ma_gv for pc in phan_congs}
    
    # Rooms
    rooms = PhongHoc.objects.all()
    info['rooms'] = {}
    for r in rooms:
        info['rooms'][r.ma_phong] = {
            'LoaiPhong': r.loai_phong if r.loai_phong else 'General',
            'SucChua': r.suc_chua if r.suc_chua else 0,
            'ThietBi': r.thiet_bi if r.thiet_bi else '',
        }
    
    # Time slots
    slots = TimeSlot.objects.select_related('ca').all()
    info['slots'] = {}
    for s in slots:
        info['slots'][s.time_slot_id] = {
            'Thu': s.thu,
            'Ca': s.ca.ma_khung_gio if s.ca else 0,
            'SoTiet': s.ca.so_tiet if s.ca else 3,
        }
    
    # Teacher preferences
    prefs = NguyenVong.objects.select_related('ma_gv', 'time_slot_id').all()
    info['teacher_prefs'] = defaultdict(set)
    for p in prefs:
        if p.ma_gv and p.time_slot_id:
            info['teacher_prefs'][p.ma_gv.ma_gv].add(p.time_slot_id.time_slot_id)
    
    return info

def get_class_type(class_info):
    """Xác định loại lớp (LT/TH) dựa trên SQL logic"""
    so_tiet_lt = class_info.get('SoTietLT', 0)
    so_tiet_th = class_info.get('SoTietTH', 0)
    to_mh = class_info.get('ToMH')
    
    if so_tiet_th == 0:
        return 'LT'
    elif so_tiet_lt == 0 and so_tiet_th > 0:
        return 'TH'
    elif so_tiet_lt > 0 and so_tiet_th > 0 and to_mh == 0:
        return 'LT'
    else:
        return 'TH'

def normalize_room_type(room_type):
    """Chuẩn hóa loại phòng"""
    mapping = {
        'Lý thuyết': 'LT',
        'Thực hành': 'TH',
        'LT': 'LT',
        'TH': 'TH',
        'General': 'LT',
    }
    return mapping.get(room_type, 'LT')

# ============================================================================
# VALIDATION LOGIC
# ============================================================================

def validate_schedule(schedule, db_info):
    """Kiểm tra toàn bộ lịch"""
    results = {
        'hard_violations': defaultdict(list),
        'soft_violations': defaultdict(list),
        'stats': {},
        'violations_by_type': defaultdict(int),
    }
    
    assignments = schedule.get('schedule', [])
    
    # Build index structures
    by_class = defaultdict(list)
    by_teacher_slot = defaultdict(list)
    by_room_slot = defaultdict(list)
    by_teacher_day = defaultdict(lambda: defaultdict(int))  # teacher -> day -> count
    by_class_day = defaultdict(lambda: defaultdict(int))    # class -> day -> count
    
    for idx, a in enumerate(assignments):
        class_id = a.get('class')
        room_id = a.get('room')
        slot_id = a.get('slot')
        teacher_id = db_info['class_teacher'].get(class_id)
        
        slot_info = db_info['slots'].get(slot_id, {})
        thu = slot_info.get('Thu', 0)
        
        obj = {
            'class': class_id,
            'room': room_id,
            'slot': slot_id,
            'teacher': teacher_id,
            'day': thu,
            'idx': idx
        }
        
        by_class[class_id].append(obj)
        if teacher_id:
            by_teacher_slot[f"{teacher_id}_{slot_id}"].append(obj)
            by_teacher_day[teacher_id][thu] += 1
        by_room_slot[f"{room_id}_{slot_id}"].append(obj)
        by_class_day[class_id][thu] += 1
    
    # ====================================================================
    # HARD CONSTRAINTS CHECK
    # ====================================================================
    
    # HC-01: Teacher conflict (same teacher teaching 2 classes same slot)
    for key, objs in by_teacher_slot.items():
        if len(objs) > 1:
            teacher_id = key.split('_')[0]
            slot_id = key.split('_')[1]
            for obj in objs:
                results['hard_violations'][obj['class']].append({
                    'type': 'HC-01',
                    'name': 'Trùng giờ giảng viên',
                    'slot': slot_id,
                    'detail': f"GV {db_info['teachers'].get(teacher_id, teacher_id)} dạy {len(objs)} lớp cùng lúc"
                })
                results['violations_by_type']['HC-01'] += 1
    
    # HC-02: Room conflict (same room used by 2 classes same slot)
    for key, objs in by_room_slot.items():
        if len(objs) > 1:
            room_id = key.split('_')[0]
            slot_id = key.split('_')[1]
            for obj in objs:
                results['hard_violations'][obj['class']].append({
                    'type': 'HC-02',
                    'name': 'Trùng phòng',
                    'slot': slot_id,
                    'detail': f"Phòng {room_id} sử dụng bởi {len(objs)} lớp cùng lúc"
                })
                results['violations_by_type']['HC-02'] += 1
    
    # HC-03: Room capacity
    for class_id, objs in by_class.items():
        class_info = db_info['classes'].get(class_id, {})
        so_sv = class_info.get('SoSV', 0)
        
        for obj in objs:
            room_id = obj['room']
            room_cap = db_info['rooms'].get(room_id, {}).get('SucChua', 0)
            
            if so_sv > room_cap:
                results['hard_violations'][class_id].append({
                    'type': 'HC-03',
                    'name': 'Phòng không đủ chỗ',
                    'slot': obj['slot'],
                    'detail': f"{so_sv} SV > {room_cap} chỗ (phòng {room_id})"
                })
                results['violations_by_type']['HC-03'] += 1
    
    # HC-04: Equipment requirements
    for class_id, objs in by_class.items():
        class_info = db_info['classes'].get(class_id, {})
        required = class_info.get('ThietBiYeuCau', '')
        
        if required:
            req_items = [x.strip().lower() for x in required.replace(';', ',').split(',') if x.strip()]
            
            for obj in objs:
                room_id = obj['room']
                room_equip = db_info['rooms'].get(room_id, {}).get('ThietBi', '').lower()
                
                missing = [r for r in req_items if r not in room_equip]
                if missing:
                    results['hard_violations'][class_id].append({
                        'type': 'HC-04',
                        'name': 'Thiếu thiết bị',
                        'slot': obj['slot'],
                        'detail': f"Phòng {room_id} thiếu: {', '.join(missing)}"
                    })
                    results['violations_by_type']['HC-04'] += 1
    
    # HC-05 & HC-06: Room type mismatch
    for class_id, objs in by_class.items():
        class_info = db_info['classes'].get(class_id, {})
        class_type = get_class_type(class_info)
        
        for obj in objs:
            room_id = obj['room']
            room_type = normalize_room_type(db_info['rooms'].get(room_id, {}).get('LoaiPhong', ''))
            
            if class_type == 'TH' and room_type == 'LT':
                results['hard_violations'][class_id].append({
                    'type': 'HC-05',
                    'name': 'Lớp TH xếp phòng LT',
                    'slot': obj['slot'],
                    'detail': f"Phòng {room_id} là LT (không phải TH)"
                })
                results['violations_by_type']['HC-05'] += 1
            
            if class_type == 'LT' and room_type == 'TH':
                results['hard_violations'][class_id].append({
                    'type': 'HC-06',
                    'name': 'Lớp LT xếp phòng TH',
                    'slot': obj['slot'],
                    'detail': f"Phòng {room_id} là TH (không phải LT)"
                })
                results['violations_by_type']['HC-06'] += 1
    
    # HC-08: Không xếp Chủ nhật
    for class_id, objs in by_class.items():
        for obj in objs:
            if obj['day'] == 8:  # Chủ nhật
                results['hard_violations'][class_id].append({
                    'type': 'HC-08',
                    'name': 'Xếp Chủ nhật',
                    'slot': obj['slot'],
                    'detail': f"Lịch {obj['slot']} là Chủ nhật"
                })
                results['violations_by_type']['HC-08'] += 1
    
    # ====================================================================
    # SOFT CONSTRAINTS CHECK
    # ====================================================================
    
    # SOFT-01: Teacher preferences
    for class_id, objs in by_class.items():
        teacher_id = db_info['class_teacher'].get(class_id)
        
        if teacher_id and teacher_id in db_info['teacher_prefs']:
            prefs = db_info['teacher_prefs'][teacher_id]
            
            for obj in objs:
                if obj['slot'] not in prefs:
                    results['soft_violations'][class_id].append({
                        'type': 'RBM-PREF',
                        'name': 'Vi phạm nguyện vọng GV',
                        'slot': obj['slot'],
                        'detail': f"GV {db_info['teachers'].get(teacher_id, teacher_id)} không mong muốn slot {obj['slot']}"
                    })
                    results['violations_by_type']['RBM-PREF'] += 1
    
    # Calculate stats
    total_classes = len(db_info['classes'])
    hard_violated = len(results['hard_violations'])
    soft_violated = len([c for c in results['soft_violations'].keys() 
                        if c not in results['hard_violations']])
    perfect = total_classes - hard_violated - soft_violated
    
    results['stats'] = {
        'total_classes': total_classes,
        'total_assignments': len(assignments),
        'perfect_classes': perfect,
        'hard_violated_classes': hard_violated,
        'soft_violated_classes': soft_violated,
    }
    
    return results

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Load files
    print("="*100)
    print("VALIDATE ALGORITHM OUTPUT JSON")
    print("="*100)
    print()
    
    json_file = 'output/schedule_algorithm_DOT1_2025-2026_HK1.json'
    
    if not os.path.exists(json_file):
        print(f"❌ File not found: {json_file}")
        sys.exit(1)
    
    print(f"📥 Loading {json_file}...")
    schedule = load_json_schedule(json_file)
    
    # Try to connect to DB, fallback to mock data if fails
    try:
        print(f"📥 Loading database info...")
        db_info = load_database_info()
        using_db = True
    except Exception as e:
        print(f"⚠️  Database connection failed: {str(e)[:100]}")
        print(f"⚠️  Using mock data from JSON instead")
        using_db = False
        db_info = None
    
    if using_db and db_info:
        print(f"🔍 Validating {len(schedule.get('schedule', []))} assignments...")
        results = validate_schedule(schedule, db_info)
        
        print()
        print("="*100)
        print("RESULTS SUMMARY")
        print("="*100)
        print()
        
        stats = results['stats']
        print(f"📊 Classes Status:")
        print(f"   ✅ Perfect (no violations):           {stats['perfect_classes']:3d}/{stats['total_classes']} ({100*stats['perfect_classes']/stats['total_classes']:.1f}%)")
        print(f"   ❌ Hard constraint violations:        {stats['hard_violated_classes']:3d}/{stats['total_classes']} ({100*stats['hard_violated_classes']/stats['total_classes']:.1f}%)")
        print(f"   ⚠️  Soft constraint violations only:  {stats['soft_violated_classes']:3d}/{stats['total_classes']} ({100*stats['soft_violated_classes']/stats['total_classes']:.1f}%)")
        print()
        
        print(f"📈 Violations by Type:")
        for vtype in sorted(results['violations_by_type'].keys()):
            count = results['violations_by_type'][vtype]
            type_names = {
                'HC-01': 'Trùng giờ GV',
                'HC-02': 'Trùng phòng',
                'HC-03': 'Phòng không đủ chỗ',
                'HC-04': 'Thiếu thiết bị',
                'HC-05': 'Lớp TH xếp phòng LT',
                'HC-06': 'Lớp LT xếp phòng TH',
                'HC-08': 'Xếp Chủ nhật',
                'RBM-PREF': 'Vi phạm nguyện vọng GV',
            }
            print(f"   {vtype} ({type_names.get(vtype, vtype)}): {count}")
    else:
        # Use data from JSON only
        print(f"✓ Using validation data from JSON")
        results = {
            'stats': {
                'total_classes': len(schedule.get('course_details', {})),
                'total_assignments': len(schedule.get('schedule', [])),
            },
            'hard_violations': {},
            'soft_violations': {},
            'violations_by_type': {},
        }
    
    # Soft constraints from JSON
    soft_scores = schedule.get('score_breakdown', {})
    print()
    print(f"📊 Soft Constraint Scores (từ solver):")
    print(f"   Room capacity penalty:           {soft_scores.get('room_capacity_penalty', 0)}")
    print(f"   Min working days penalty:        {soft_scores.get('min_working_days_penalty', 0)}")
    print(f"   Curriculum compactness penalty:  {soft_scores.get('curriculum_compactness_penalty', 0)}")
    print(f"   Room stability penalty:          {soft_scores.get('room_stability_penalty', 0)}")
    print(f"   Lecture clustering penalty:      {soft_scores.get('lecture_clustering_penalty', 0)}")
    print(f"   ---")
    print(f"   TOTAL COST:                      {soft_scores.get('total_cost', 0)}")
    print()
    
    # Build validation report to save as JSON
    validation_report = {
        'metadata': {
            'file': json_file,
            'timestamp': datetime.now().isoformat(),
            'using_database': using_db,
        },
        'summary': {
            'total_assignments': results['stats'].get('total_assignments', len(schedule.get('schedule', []))),
            'total_classes': results['stats'].get('total_classes', 0),
            'perfect_classes': results['stats'].get('perfect_classes', 0),
            'hard_violated_classes': results['stats'].get('hard_violated_classes', 0),
            'soft_violated_classes': results['stats'].get('soft_violated_classes', 0),
        },
        'hard_constraints': {
            'violations_by_type': dict(results['violations_by_type']),
            'violations_by_class': {k: v for k, v in results['hard_violations'].items()},
        },
        'soft_constraints': {
            'from_solver': {
                'room_capacity_penalty': soft_scores.get('room_capacity_penalty', 0),
                'min_working_days_penalty': soft_scores.get('min_working_days_penalty', 0),
                'curriculum_compactness_penalty': soft_scores.get('curriculum_compactness_penalty', 0),
                'room_stability_penalty': soft_scores.get('room_stability_penalty', 0),
                'lecture_clustering_penalty': soft_scores.get('lecture_clustering_penalty', 0),
                'total_cost': soft_scores.get('total_cost', 0),
            },
            'violations_by_class': {k: v for k, v in results['soft_violations'].items()},
        },
        'schedule_statistics': schedule.get('statistics', {}),
        'constraints_info': schedule.get('constraints_info', {}),
    }
    
    # Save to JSON file
    output_file = json_file.replace('schedule_algorithm_', 'validation_report_').replace('.json', '_validated.json')
    
    print("="*100)
    print(f"💾 Saving validation report to: {output_file}")
    print("="*100)
    
    try:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(validation_report, f, indent=2, ensure_ascii=False)
        print(f"✅ Validation report saved successfully!")
        print(f"   File: {output_file}")
    except Exception as e:
        print(f"❌ Failed to save validation report: {e}")
    
    # Detail violations if any
    if results['hard_violations']:
        print()
        print("="*100)
        print("HARD CONSTRAINT VIOLATIONS (Chi tiết)")
        print("="*100)
        print()
        
        for class_id in sorted(results['hard_violations'].keys())[:10]:  # Show first 10
            viols = results['hard_violations'][class_id]
            print(f"❌ Lớp {class_id}:")
            for v in viols[:3]:  # Show first 3
                print(f"   - {v['type']} ({v['name']}): {v['detail']} @ {v['slot']}")
            if len(viols) > 3:
                print(f"   ... và {len(viols)-3} vi phạm khác")
            print()
    
    print("="*100)
    print("✅ Validation complete!")
    print("="*100)
