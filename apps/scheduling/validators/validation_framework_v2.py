"""
Unified Validation Framework - IMPROVED VERSION
Cung cấp một framework chung để validate lịch xếp với metrics_calculator
Sử dụng được cho cả validate_detailed.py và validate_algorithm_output.py

Đảm bảo cùng logic khi so sánh kết quả giữa LLM và Algorithm

HARD CONSTRAINTS CHECKED:
  ✅ HC-01: Teacher conflict (check_teacher_conflicts)
  ✅ HC-02: Room conflict (check_room_conflicts)
  ✅ HC-03: Room capacity (check_room_capacity)
  ✅ HC-04: Equipment mismatch (check_room_equipment)
  ✅ HC-05: TH class → LT room (check_room_type_mismatch)
  ✅ HC-06: LT class → TH room (check_room_type_mismatch)
  ✅ HC-08: Sunday assignment (check_sunday_classes)
  ✅ HC-13: Session requirements SoCaTuan=2 (check_session_requirements) [ADDED]
  ✅ MISSING: Class not scheduled (check_missing_classes) [ADDED]

SOFT CONSTRAINTS CHECKED:
  ✅ RBM-NGUYEN-VONG: Teacher preferences
  ✅ RBM-MIN-WORKING-DAYS: Minimum working days (via MetricsCalculator)
  ✅ RBM-CURRICULUM-COMPACTNESS: Curriculum compactness (via MetricsCalculator)
  ✅ RBM-ROOM-STABILITY: Room stability (via MetricsCalculator)
  ✅ RBM-LECTURE-CLUSTERING: Lecture clustering (via MetricsCalculator)
"""

import json
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

import django
import os
import sys

# Setup Django
if not django.apps.apps.ready:
    sys.path.insert(0, str(Path(__file__).parent))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

from apps.scheduling.models import (
    LopMonHoc, MonHoc, GiangVien, PhongHoc, TimeSlot, 
    PhanCong, DotXep, ThoiKhoaBieu, NguyenVong, NgayNghiDot
)
from apps.scheduling.validators import MetricsCalculator
from apps.scheduling.validators.unified_output_format import UnifiedValidationOutput

logger = logging.getLogger(__name__)


class ScheduleData:
    """Lưu trữ dữ liệu lịch xếp từ JSON schedule output"""
    def __init__(self, schedule_dict: Dict):
        self.schedule = schedule_dict.get('schedule', [])
        self.validation = schedule_dict.get('validation', {})
        self.metrics = schedule_dict.get('metrics', {})
        self.errors = schedule_dict.get('errors', [])
        
        # Index by class
        self.schedule_by_class = {}
        for entry in self.schedule:
            ma_lop = entry.get('class')
            if ma_lop not in self.schedule_by_class:
                self.schedule_by_class[ma_lop] = []
            self.schedule_by_class[ma_lop].append(entry)
    
    def get_assignments_for_class(self, ma_lop: str) -> List[Dict]:
        return self.schedule_by_class.get(ma_lop, [])
    
    def get_all_assignments(self) -> List[Dict]:
        return self.schedule


class UnifiedValidator:
    """
    Validator chung sử dụng cùng logic với MetricsCalculator + Hard Constraint Checking
    """
    
    def __init__(self, ma_dot: str, schedule_data: ScheduleData):
        self.ma_dot = ma_dot
        self.schedule_data = schedule_data
        self._load_database_info()
        
        try:
            # NEW: Pass schedule_data to MetricsCalculator để validate lịch mới từ JSON
            self.metrics_calc = MetricsCalculator(ma_dot=ma_dot, schedule_data=schedule_data)
        except Exception as e:
            logger.warning(f"MetricsCalculator initialization failed: {e}")
            self.metrics_calc = None
        
        # Index assignments by teacher, room, time for fast lookup
        self._build_indices()
    
    def _load_database_info(self):
        """Load thông tin từ database"""
        # Lớp môn học - ONLY của đợt này (filter by ma_dot)
        try:
            dot_obj = DotXep.objects.get(ma_dot=self.ma_dot)
            phan_congs = PhanCong.objects.filter(ma_dot=dot_obj).select_related('ma_lop', 'ma_lop__ma_mon_hoc')
            self.classes = [pc.ma_lop for pc in phan_congs]
        except DotXep.DoesNotExist:
            logger.warning(f"DotXep {self.ma_dot} not found, loading all classes")
            self.classes = LopMonHoc.objects.select_related('ma_mon_hoc').all()
            
        self.class_info = {}
        self.class_type = {}
        
        for cls in self.classes:
            self.class_info[cls.ma_lop] = {
                'TenMonHoc': cls.ma_mon_hoc.ten_mon_hoc if cls.ma_mon_hoc else 'N/A',
                'SoCaTuan': cls.so_ca_tuan or 1,
                'Nhom': cls.nhom_mh or '?',
                'SoSV': cls.so_luong_sv or 0,
                'ThietBiYeuCau': cls.thiet_bi_yeu_cau or '',
                'SoTinChi': cls.ma_mon_hoc.so_tin_chi if cls.ma_mon_hoc else 0,
            }
            
            # Determine class type (LT/TH) - same logic as validate_detailed.py
            if cls.ma_mon_hoc:
                so_tiet_th = cls.ma_mon_hoc.so_tiet_th or 0
                so_tiet_lt = cls.ma_mon_hoc.so_tiet_lt or 0
                to_mh = cls.to_mh
                
                if so_tiet_th == 0:
                    self.class_type[cls.ma_lop] = 'LT'
                elif so_tiet_lt == 0 and so_tiet_th > 0:
                    self.class_type[cls.ma_lop] = 'TH'
                elif so_tiet_lt > 0 and so_tiet_th > 0 and to_mh == 0:
                    self.class_type[cls.ma_lop] = 'LT'
                else:
                    self.class_type[cls.ma_lop] = 'TH'
        
        # Phân công giảng viên
        self.class_teacher = {}
        for pc in PhanCong.objects.select_related('ma_lop', 'ma_gv'):
            self.class_teacher[pc.ma_lop.ma_lop] = pc.ma_gv.ma_gv if pc.ma_gv else None
        
        # Giảng viên
        self.teachers = {t.ma_gv: t.ten_gv for t in GiangVien.objects.all()}
        
        # Time slots
        self.slots = {}
        for s in TimeSlot.objects.select_related('ca'):
            self.slots[s.time_slot_id] = {
                'Thu': s.thu,
                'Ca': s.ca.ma_khung_gio if s.ca else '?'
            }
        
        # Phòng học
        self.rooms = {}
        for r in PhongHoc.objects.all():
            self.rooms[r.ma_phong] = {
                'LoaiPhong': r.loai_phong or '?',
                'SucChua': r.suc_chua or 0,
                'ThietBi': r.thiet_bi or ''
            }
        
        # Nguyện vọng GV
        self.teacher_preferences = defaultdict(set)
        for pref in NguyenVong.objects.select_related('ma_gv', 'time_slot_id'):
            if pref.ma_gv and pref.time_slot_id:
                self.teacher_preferences[pref.ma_gv.ma_gv].add(pref.time_slot_id.time_slot_id)
        
        # Ngày nghỉ
        self.holidays = set()
        for day in NgayNghiDot.objects.filter(ma_dot__ma_dot=self.ma_dot):
            self.holidays.add(day.ngay_bd)
        
        logger.info(f"Loaded: {len(self.classes)} classes, {len(self.teachers)} teachers, {len(self.rooms)} rooms")
    
    def _build_indices(self):
        """Build fast lookup indices"""
        self.by_teacher_slot = defaultdict(list)
        self.by_room_slot = defaultdict(list)
        self.by_class = defaultdict(list)
        
        for idx, assignment in enumerate(self.schedule_data.get_all_assignments()):
            ma_lop = assignment.get('class')
            ma_phong = assignment.get('room')
            slot_id = assignment.get('slot')
            ma_gv = self.class_teacher.get(ma_lop)
            
            assignment_obj = {
                'MaLop': ma_lop,
                'MaPhong': ma_phong,
                'MaSlot': slot_id,
                'MaGV': ma_gv,
                'index': idx,
                'raw': assignment
            }
            
            self.by_class[ma_lop].append(assignment_obj)
            
            if ma_gv:
                key = f"{ma_gv}_{slot_id}"
                self.by_teacher_slot[key].append(assignment_obj)
            
            key = f"{ma_phong}_{slot_id}"
            self.by_room_slot[key].append(assignment_obj)
    
    def validate_schedule(self) -> Dict:
        """Validate toàn bộ lịch xếp"""
        result = {
            'ma_dot': self.ma_dot,
            'timestamp': datetime.now().isoformat(),
            'total_assignments': len(self.schedule_data.get_all_assignments()),
            'violations': [],
            'warnings': [],
            'status': 'PASS'
        }
        
        # 1. Check HARD CONSTRAINTS
        logger.info("🔍 Checking hard constraints...")
        
        # HC-01: Teacher conflict
        for key, assigns in self.by_teacher_slot.items():
            if len(assigns) > 1:
                for a in assigns:
                    result['violations'].append({
                        'type': 'HC-01_TEACHER_CONFLICT',
                        'class': a['MaLop'],
                        'teacher': a['MaGV'],
                        'slot': a['MaSlot'],
                        'room': a['MaPhong'],
                        'message': f"Teacher {a['MaGV']} teaching {len(assigns)} classes at same slot {a['MaSlot']}"
                    })
        
        # HC-02: Room conflict
        for key, assigns in self.by_room_slot.items():
            if len(assigns) > 1:
                for a in assigns:
                    result['violations'].append({
                        'type': 'HC-02_ROOM_CONFLICT',
                        'class': a['MaLop'],
                        'room': a['MaPhong'],
                        'slot': a['MaSlot'],
                        'message': f"Room {a['MaPhong']} booked {len(assigns)} times at slot {a['MaSlot']}"
                    })
        
        # HC-03, HC-04, HC-05, HC-06, HC-08 - per assignment checks
        for assignment in self.schedule_data.get_all_assignments():
            ma_lop = assignment.get('class')
            ma_phong = assignment.get('room')
            slot_id = assignment.get('slot')
            
            # HC-03: Capacity
            class_size = self.class_info.get(ma_lop, {}).get('SoSV', 0)
            room_capacity = self.rooms.get(ma_phong, {}).get('SucChua', 0)
            if class_size > 0 and class_size > room_capacity:
                result['violations'].append({
                    'type': 'HC-03_INSUFFICIENT_CAPACITY',
                    'class': ma_lop,
                    'room': ma_phong,
                    'message': f"Class {ma_lop} ({class_size} students) > Room capacity ({room_capacity})"
                })
            
            # HC-04: Equipment
            required_equip = self.class_info.get(ma_lop, {}).get('ThietBiYeuCau', '')
            if required_equip:
                room_equip = self.rooms.get(ma_phong, {}).get('ThietBi', '')
                if not self._check_equipment_match(required_equip, room_equip):
                    result['violations'].append({
                        'type': 'HC-04_EQUIPMENT_MISMATCH',
                        'class': ma_lop,
                        'room': ma_phong,
                        'required': required_equip,
                        'available': room_equip,
                        'message': f"Room {ma_phong} missing equipment: {required_equip}"
                    })
            
            # HC-05 & HC-06: Room type
            class_type_req = self.class_type.get(ma_lop, 'LT')
            room_type_str = self.rooms.get(ma_phong, {}).get('LoaiPhong', '')
            room_type = 'TH' if ('Thực hành' in room_type_str or 'TH' in room_type_str) else 'LT'
            
            if class_type_req == 'TH' and room_type == 'LT':
                result['violations'].append({
                    'type': 'HC-05_TH_IN_LT_ROOM',
                    'class': ma_lop,
                    'room': ma_phong,
                    'message': f"Practical class {ma_lop} assigned to lecture room {ma_phong}"
                })
            elif class_type_req == 'LT' and room_type == 'TH':
                result['violations'].append({
                    'type': 'HC-06_LT_IN_TH_ROOM',
                    'class': ma_lop,
                    'room': ma_phong,
                    'message': f"Lecture class {ma_lop} assigned to practical room {ma_phong}"
                })
            
            # HC-08: Sunday
            if slot_id in self.slots:
                thu = self.slots[slot_id].get('Thu', 0)
                if thu == 8:  # Sunday
                    result['violations'].append({
                        'type': 'HC-08_SUNDAY_ASSIGNMENT',
                        'class': ma_lop,
                        'slot': slot_id,
                        'message': f"Class {ma_lop} assigned to Sunday slot {slot_id}"
                    })
        
        # HC-13: Session requirements (SoCaTuan=2 must be consecutive same day)
        try:
            hc13_violations = self._check_session_requirements(self.schedule_data)
            result['violations'].extend(hc13_violations)
            logger.info(f"✓ Session requirements check: {len(hc13_violations)} violations")
        except Exception as e:
            logger.error(f"❌ Session requirements check failed: {e}", exc_info=True)
        
        # MISSING: Classes not scheduled
        try:
            missing_violations = self._check_missing_classes(self.schedule_data)
            result['violations'].extend(missing_violations)
            logger.info(f"✓ Missing classes check: {len(missing_violations)} violations")
        except Exception as e:
            logger.error(f"❌ Missing classes check failed: {e}", exc_info=True)
        
        if result['violations']:
            result['status'] = 'FAIL'
        
        # 2. Check SOFT CONSTRAINTS via MetricsCalculator + Manual checks
        soft_violations_list = []
        soft_violation_count = 0
        
        # 2a. Check soft constraint: RBM-NGUYEN-VONG (Teacher Preferences)
        try:
            teacher_preference_violations = self._check_teacher_preferences(self.schedule_data)
            logger.info(f"✓ Teacher preference check: {len(teacher_preference_violations)} violations")
            
            # Format soft violations giống hard violations
            for pref_violation in teacher_preference_violations:
                soft_violation_data = {
                    'type': pref_violation.get('type', 'RBM-NGUYEN-VONG'),
                    'class': pref_violation.get('class'),
                    'slot': pref_violation.get('slot'),
                    'teacher': pref_violation.get('teacher'),
                    'message': pref_violation.get('message', f"Class {pref_violation.get('class')} assigned to non-preferred slot"),
                }
                soft_violations_list.append(soft_violation_data)
            
            soft_violation_count += len(teacher_preference_violations)
        except Exception as e:
            logger.error(f"❌ Teacher preference check failed: {e}", exc_info=True)
        
        # 2b. Check soft constraints from MetricsCalculator (RBM-001 đến RBM-007)
        soft_fitness = None
        if self.metrics_calc:
            try:
                # 🔥 PHẢI gọi calculate_fitness() TRƯỚC để populate self.violations
                soft_fitness = self.metrics_calc.calculate_fitness()
                logger.info(f"✓ MetricsCalculator soft fitness: {soft_fitness:.4f}")
                
                # Giờ gọi get_violations_report() để lấy chi tiết violations
                metrics_report = self.metrics_calc.get_violations_report()
                result['metrics'] = metrics_report
                
                # Extract soft violations và thêm vào result
                soft_violations = metrics_report.get('violations', [])
                soft_violation_count += len(soft_violations)
                logger.info(f"✓ MetricsCalculator violations: {len(soft_violations)}")
                
                # 🔥 THÊM RBM-001 đến RBM-007 vào soft_violations_list
                for sv in soft_violations:
                    soft_violation_data = {
                        'type': sv.get('constraint_id', 'RBM-UNKNOWN'),
                        'constraint_name': sv.get('constraint_name', ''),
                        'violation_count': sv.get('violation_count', 0),
                        'weight': sv.get('weight', 0),
                        'penalty': sv.get('penalty', 0),
                        'message': f"{sv.get('constraint_name', 'Unknown')}: {sv.get('violation_count', 0)} violations × {sv.get('weight', 0)} = {sv.get('penalty', 0):.2f} penalty"
                    }
                    soft_violations_list.append(soft_violation_data)
            except Exception as e:
                logger.error(f"❌ Metrics report failed: {e}", exc_info=True)
                soft_fitness = None  # Explicit set to None if error
        
        # 🔥 Nếu không có soft violations → soft_fitness = 1.0 (perfect)
        if soft_fitness is None:
            soft_fitness = 1.0 if not soft_violations_list else 0.0
            logger.info(f"📊 Using fallback soft_fitness: {soft_fitness:.4f} (violations: {len(soft_violations_list)})")
        
        result['soft_violations'] = soft_violations_list
        
        # 3. Lưu soft_fitness vào result (đã được tính từ MetricsCalculator)
        result['soft_fitness'] = soft_fitness  # 🔥 soft_fitness từ MetricsCalculator
        
        # Update status based on hard violations
        if result['violations']:
            result['status'] = 'FAIL'
        
        return result
    
    def to_unified_format(self, source: str = "LLM") -> Dict:
        """
        Convert validation result to unified format
        
        Args:
            source: "LLM" or "Algorithm"
            
        Returns:
            dict: Unified format output
        """
        # Get basic validation result
        result = self.validate_schedule()
        
        # 🔥 Extract soft_fitness từ result (đã tính trong validate_schedule)
        soft_fitness = result.get('soft_fitness', 1.0)
        
        # 🔥 Chỉ giữ soft_fitness (bỏ hard_fitness và combined_fitness)
        fitness_data = {
            'soft_fitness': soft_fitness
        }
        
        # Create unified output với fitness_data
        total_classes = result.get('total_assignments', 0)
        unified = UnifiedValidationOutput(
            source=source,
            ma_dot=self.ma_dot,
            total_classes=total_classes,
            fitness_data=fitness_data  # 🔥 Pass fitness data
        )
        
        # Add violations
        violations = result.get('violations', [])
        for violation in violations:
            unified.add_hard_violation(violation)
        
        # Add soft violations
        soft_violations = result.get('soft_violations', [])
        for sv in soft_violations:
            unified.add_soft_violation(sv)
        
        # Add OK classes
        violated_class_ids = set(v.get('class') for v in violations)
        all_classes = LopMonHoc.objects.select_related('ma_mon_hoc').all()
        
        for cls in all_classes:
            if cls.ma_lop not in violated_class_ids:
                class_info = {
                    'MaLop': cls.ma_lop,
                    'info': {
                        'TenMonHoc': cls.ma_mon_hoc.ten_mon_hoc if cls.ma_mon_hoc else 'N/A',
                        'SoCaTuan': cls.so_ca_tuan or 1,
                        'Nhom': cls.nhom_mh or '?',
                        'SoSV': cls.so_luong_sv or 0,
                        'ThietBiYeuCau': cls.thiet_bi_yeu_cau or '',
                        'SoTinChi': cls.ma_mon_hoc.so_tin_chi if cls.ma_mon_hoc else 0,
                    }
                }
                unified.add_ok_class(class_info)
        
        return unified.generate()
    @staticmethod
    def _check_equipment_match(required: str, available: str) -> bool:
        """Kiểm tra equipment matching"""
        if not required:
            return True
        if not available:
            return False
        
        required_items = [x.strip().lower() for x in required.replace(';', ',').split(',') if x.strip()]
        available_lower = available.lower()
        
        return all(item in available_lower for item in required_items)
    
    def print_validation_report(self):
        """In báo cáo validation"""
        result = self.validate_schedule()
        
        print("\n" + "="*100)
        print(f"VALIDATION REPORT - {self.ma_dot}")
        print("="*100)
        
        print(f"\n📊 Summary:")
        print(f"   Status: {result['status']}")
        print(f"   Total Assignments: {result['total_assignments']}")
        print(f"   Hard Constraint Violations: {len(result['violations'])}")
        
        if 'fitness_score' in result:
            fitness = result['fitness_score']
            symbol = '🟢' if fitness > 0.9 else '🟡' if fitness > 0.7 else '🔴'
            print(f"   {symbol} Fitness Score: {fitness:.4f}")
        
        # Violations by type
        if result['violations']:
            print(f"\n❌ Hard Constraint Violations by Type:")
            violation_types = defaultdict(int)
            for v in result['violations']:
                v_type = v.get('type', 'UNKNOWN')
                violation_types[v_type] += 1
            
            for v_type in sorted(violation_types.keys()):
                count = violation_types[v_type]
                print(f"   {v_type}: {count}")
        
        print("\n" + "="*100 + "\n")
        
        return result
    
    def _check_session_requirements(self, schedule_data) -> List[Dict]:
        """
        HC-13: Kiểm tra yêu cầu SoCaTuan=2 (2 ca liên tiếp cùng ngày)
        
        Nếu một lớp có SoCaTuan=2, phải xếp đúng 2 buổi, cùng ngày, liên tiếp (Ca1-Ca2 hoặc Ca2-Ca3, v.v.)
        
        Returns:
            List[Dict]: Violations với loại 'HC-13_SESSION_REQUIREMENT'
        """
        violations = []
        
        # Group assignments by class
        assignments_by_class = defaultdict(list)
        for assignment in schedule_data.get_all_assignments():
            ma_lop = assignment.get('class')
            if ma_lop:
                assignments_by_class[ma_lop].append(assignment)
        
        # Check each class
        for ma_lop, assignments in assignments_by_class.items():
            so_ca_tuan = self.class_info.get(ma_lop, {}).get('SoCaTuan', 1)
            
            # Chỉ check SoCaTuan=2
            if so_ca_tuan != 2:
                continue
            
            # Phải có đúng 2 buổi
            if len(assignments) != 2:
                violations.append({
                    'type': 'HC-13_SESSION_REQUIREMENT',
                    'class': ma_lop,
                    'message': f"SoCaTuan=2 but {len(assignments)} sessions assigned (expected 2)",
                    'required': 2,
                    'actual': len(assignments)
                })
                continue
            
            # Parse slots
            slots_info = []
            for assignment in assignments:
                slot_id = assignment.get('slot', '')
                if slot_id in self.slots:
                    thu = self.slots[slot_id].get('Thu', 0)
                    ca_str = self.slots[slot_id].get('Ca', '')
                    
                    # Extract Ca number (e.g., "Ca1" → 1, "Ca2" → 2)
                    ca_num = int(''.join(filter(str.isdigit, ca_str))) if ca_str else 0
                    slots_info.append({
                        'slot_id': slot_id,
                        'day': thu,
                        'ca': ca_num
                    })
            
            if len(slots_info) != 2:
                continue
            
            slot1, slot2 = slots_info[0], slots_info[1]
            
            # Phải cùng ngày
            if slot1['day'] != slot2['day']:
                violations.append({
                    'type': 'HC-13_SESSION_REQUIREMENT',
                    'class': ma_lop,
                    'message': f"SoCaTuan=2: 2 sessions not on same day (Thu{slot1['day']} vs Thu{slot2['day']})",
                    'slot1': slot1['slot_id'],
                    'slot2': slot2['slot_id']
                })
                continue
            
            # Phải liên tiếp: |Ca1 - Ca2| = 1
            if abs(slot1['ca'] - slot2['ca']) != 1:
                violations.append({
                    'type': 'HC-13_SESSION_REQUIREMENT',
                    'class': ma_lop,
                    'message': f"SoCaTuan=2: 2 sessions not consecutive (Ca{slot1['ca']} and Ca{slot2['ca']})",
                    'slot1': slot1['slot_id'],
                    'slot2': slot2['slot_id']
                })
        
        return violations
    
    def _check_missing_classes(self, schedule_data) -> List[Dict]:
        """
        MISSING: Kiểm tra lớp chưa được xếp lịch
        
        Nếu lớp trong class_info nhưng KHÔNG trong schedule → Missing
        
        Returns:
            List[Dict]: Violations với loại 'MISSING_CLASS'
        """
        violations = []
        
        # Get all scheduled classes
        scheduled_classes = set()
        for assignment in schedule_data.get_all_assignments():
            ma_lop = assignment.get('class')
            if ma_lop:
                scheduled_classes.add(ma_lop)
        
        # Get all classes from database
        all_classes = set(self.class_info.keys())
        
        # Find missing classes
        missing_classes = all_classes - scheduled_classes
        
        for ma_lop in sorted(missing_classes):
            class_info = self.class_info.get(ma_lop, {})
            violations.append({
                'type': 'MISSING_CLASS',
                'class': ma_lop,
                'message': f"Class {ma_lop} not scheduled",
                'course_name': class_info.get('TenMonHoc', 'N/A'),
                'group': class_info.get('Nhom', '?'),
                'students': class_info.get('SoSV', 0)
            })
        
        return violations
    
    def _check_teacher_preferences(self, schedule_data) -> list:
        """
        Kiểm tra nguyện vọng giảng viên (RBM-NGUYEN-VONG)
        
        Nếu giảng viên không được phân công hoặc không có nguyện vọng → Không vi phạm
        Nếu lớp học được xếp vào slot KHÔNG trong nguyện vọng → Vi phạm
        """
        from apps.scheduling.models import NguyenVong, PhanCong
        
        violations = []
        teacher_preferences = {}  # {ma_gv: set(preferred_slots)}
        
        # Load teacher preferences from database
        preferences = NguyenVong.objects.select_related('ma_gv', 'time_slot_id').all()
        for pref in preferences:
            if pref.ma_gv and pref.time_slot_id:
                ma_gv = pref.ma_gv.ma_gv
                slot_id = pref.time_slot_id.time_slot_id
                if ma_gv not in teacher_preferences:
                    teacher_preferences[ma_gv] = set()
                teacher_preferences[ma_gv].add(slot_id)
        
        # Load teacher assignments from database
        teacher_classes = {}  # {ma_gv: [ma_lop]}
        phan_cong_all = PhanCong.objects.select_related('ma_lop', 'ma_gv').all()
        for pc in phan_cong_all:
            if pc.ma_gv and pc.ma_lop:
                ma_gv = pc.ma_gv.ma_gv
                ma_lop = pc.ma_lop.ma_lop
                if ma_gv not in teacher_classes:
                    teacher_classes[ma_gv] = []
                teacher_classes[ma_gv].append(ma_lop)
        
        # Check each assignment in schedule
        for assignment in schedule_data.get_all_assignments():
            ma_lop = assignment.get('class')  # Schedule JSON uses 'class', not 'MaLop'
            slot_id = assignment.get('slot')  # Schedule JSON uses 'slot', not 'MaSlot'
            
            # Find teacher for this class
            teacher_id = None
            for ma_gv, classes in teacher_classes.items():
                if ma_lop in classes:
                    teacher_id = ma_gv
                    break
            
            # Check if teacher has preferences and this slot violates them
            if teacher_id and teacher_id in teacher_preferences:
                preferred_slots = teacher_preferences[teacher_id]
                if slot_id not in preferred_slots:
                    violation = {
                        'type': 'RBM-NGUYEN-VONG',
                        'class': ma_lop,
                        'slot': slot_id,
                        'teacher': teacher_id,
                        'message': f"Class {ma_lop} assigned to non-preferred slot {slot_id} for teacher {teacher_id}"
                    }
                    violations.append(violation)
        
        return violations


# Utility functions
def load_schedule_from_json(filepath: str) -> ScheduleData:
    """Load schedule từ JSON file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        schedule_dict = json.load(f)
    return ScheduleData(schedule_dict)


def validate_schedule_file(filepath: str, ma_dot: str) -> Dict:
    """Validate schedule từ JSON file"""
    schedule_data = load_schedule_from_json(filepath)
    validator = UnifiedValidator(ma_dot=ma_dot, schedule_data=schedule_data)
    return validator.validate_schedule()
