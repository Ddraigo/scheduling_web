"""
Validator chuyên biệt cho LLM Schedule Generation
Kiểm tra hard constraints + tính toán metrics
Tích hợp với cấu trúc dữ liệu hiện tại (ma_dot, ma_lop, ma_phong, time_slot_id)
"""

import logging
from typing import Dict, List, Optional
from collections import defaultdict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConstraintViolation:
    """Represents a constraint violation"""
    constraint_type: str
    severity: str  # 'hard' or 'soft'
    message: str
    affected_entities: List[str] = None
    
    def __post_init__(self):
        if self.affected_entities is None:
            self.affected_entities = []


class ScheduleValidator:
    """
    Validator chuyên biệt cho LLM Scheduling
    
    Hard Constraints (phải thỏa mãn):
    1. HC-01: Giảng viên không dạy nhiều lớp cùng lúc
    2. HC-02: Phòng không có 2 lớp cùng lúc
    3. HC-03: Phòng phải đủ sức chứa
    4. HC-04: Phòng phải có thiết bị yêu cầu
    5. HC-05: Tất cả lớp phải được xếp
    
    Soft Constraints (tối ưu hóa):
    1. SC-01: Giảng viên có nguyện vọng time slot
    2. SC-02: Tối ưu hóa số ngày dạy của GV
    3. SC-03: Phân tán lịch đều trong tuần
    """
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset tất cả counters"""
        self.teacher_schedule = {}      # {ma_gv_slot_compact: ma_lop}
        self.room_schedule = {}         # {ma_phong_slot_compact: ma_lop}
        self.class_schedule = {}        # {ma_lop: {'ma_phong': ..., 'time_slot_id': ..., 'ma_gv': ...}}
        self.violations = []
        self.soft_violations = []
    
    def validate_schedule_compact(
        self,
        schedule_assignments: List[Dict],
        prepared_data: Dict,
        phan_cong_dict: Dict[str, Dict]
    ) -> Dict:
        """
        Validate lịch compact từ LLM với dữ liệu prepared
        
        Args:
            schedule_assignments: [{'class': 'ma_lop', 'room': 'ma_phong', 'slot': 'T2-C1'}, ...]
            prepared_data: Dữ liệu prepared từ _prepare_data_for_llm()
            phan_cong_dict: {ma_lop: {'ma_gv': '...', 'ma_dot': '...', ...}}
            
        Returns:
            Dict chứa validation results
        """
        self.reset()
        
        if not schedule_assignments:
            return {
                'feasible': False,
                'total_classes': 0,
                'assigned_classes': 0,
                'hard_violations': 0,
                'soft_violations': 0,
                'violations': [],
                'error_message': 'Không có lịch để validate'
            }
        
        total_classes = len(phan_cong_dict)
        
        # Tính tổng SoCaTuan yêu cầu (total assignments cần thiết)
        total_required_assignments = 0
        for ma_lop, pc_info in phan_cong_dict.items():
            # Mỗi lớp có so_ca_tuan entries (1, 2, 3, ...)
            # Nếu không có so_ca_tuan, mặc định là 1
            so_ca = pc_info.get('so_ca_tuan', 1)
            total_required_assignments += so_ca
        
        # Đếm số LỚPUNIQUE được xếp
        assigned_class_ids = set()
        for assignment in schedule_assignments:
            class_id = assignment.get('class')
            if class_id:
                assigned_class_ids.add(class_id)
        
        assigned_classes = len(assigned_class_ids)
        actual_assignments = len(schedule_assignments)
        
        # 1. Validate Hard Constraints
        for assignment in schedule_assignments:
            self._validate_assignment(assignment, prepared_data, phan_cong_dict)
        
        # 2. Check all classes assigned
        if assigned_classes < total_classes:
            self.violations.append(ConstraintViolation(
                'HC-05',
                f'Chỉ xếp được {assigned_classes}/{total_classes} lớp',
                'OVERALL',
                {'assigned': assigned_classes, 'total': total_classes}
            ))
        
        # 3. Check all required assignments fulfilled
        if actual_assignments < total_required_assignments:
            self.violations.append(ConstraintViolation(
                'HC-05',
                f'Chỉ xếp được {actual_assignments}/{total_required_assignments} ca học',
                'OVERALL',
                {'assigned': actual_assignments, 'total': total_required_assignments}
            ))
        
        # Format output
        return {
            'feasible': len(self.violations) == 0,
            'total_classes': total_classes,
            'assigned_classes': assigned_classes,
            'total_assignments': total_required_assignments,
            'actual_assignments': actual_assignments,
            'hard_violations': len(self.violations),
            'soft_violations': len(self.soft_violations),
            'violations': [
                {'code': v.constraint_code, 'message': v.message, 'class': v.class_id}
                for v in self.violations[:20]
            ],
            'soft_violations': [
                {'code': v.constraint_code, 'message': v.message, 'class': v.class_id}
                for v in self.soft_violations[:20]
            ],
            'metrics': self._calculate_metrics(schedule_assignments, phan_cong_dict),
            'summary': {
                'ok_classes': assigned_classes - len({v.class_id for v in self.violations if v.class_id != 'OVERALL'}),
                'conflicted_classes': len({v.class_id for v in self.violations if v.class_id != 'OVERALL'}),
                'preference_satisfaction': 100 - (len(self.soft_violations) / assigned_classes * 100 if assigned_classes > 0 else 0)
            }
        }
    
    def _validate_assignment(
        self,
        assignment: Dict,
        prepared_data: Dict,
        phan_cong_dict: Dict[str, Dict]
    ):
        """Validate một assignment"""
        ma_lop = assignment.get('class')
        ma_phong = assignment.get('room')
        slot_compact = assignment.get('slot')
        
        if not ma_lop or not ma_phong or not slot_compact:
            return
        
        # Lấy thông tin lớp
        phan_cong = phan_cong_dict.get(ma_lop, {})
        ma_gv = phan_cong.get('ma_gv')
        
        # HC-01: Giảng viên không dạy nhiều lớp cùng lúc
        if ma_gv:
            slot_key = f"{ma_gv}_{slot_compact}"
            if slot_key in self.teacher_schedule:
                # GV đã dạy ở slot này rồi
                self.violations.append(ConstraintViolation(
                    'HC-01',
                    f'GV {ma_gv} dạy nhiều lớp cùng slot {slot_compact}',
                    ma_lop,
                    {'teacher': ma_gv, 'slot': slot_compact}
                ))
            else:
                self.teacher_schedule[slot_key] = ma_lop
        
        # HC-02: Phòng không có 2 lớp cùng lúc
        slot_key = f"{ma_phong}_{slot_compact}"
        if slot_key in self.room_schedule:
            # Phòng đã được sử dụng ở slot này rồi
            self.violations.append(ConstraintViolation(
                'HC-02',
                f'Phòng {ma_phong} có 2 lớp cùng slot {slot_compact}',
                ma_lop,
                {'room': ma_phong, 'slot': slot_compact}
            ))
        else:
            self.room_schedule[slot_key] = ma_lop
        
        # HC-03: Phòng phải đủ sức chứa
        room_obj = self._find_room(ma_phong, prepared_data)
        if room_obj:
            so_sv = phan_cong.get('so_sv', 0)
            if so_sv > room_obj.get('suc_chua', 0):
                self.violations.append(ConstraintViolation(
                    'HC-03',
                    f'Phòng {ma_phong} không đủ sức chứa ({so_sv} > {room_obj.get("suc_chua")})',
                    ma_lop,
                    {'room': ma_phong, 'students': so_sv, 'capacity': room_obj.get('suc_chua')}
                ))
        
        # HC-05 & HC-06: Kiểm tra loại phòng phù hợp với loại lớp
        if room_obj:
            class_type = phan_cong.get('class_type', '')  # 'LT' hoặc 'TH'
            room_type = room_obj.get('loai_phong', '')     # 'LT' hoặc 'TH'
            
            # Normalize room type
            room_type_normalized = room_type.replace('Lý thuyết', 'LT').replace('Thực hành', 'TH')
            
            # HC-05: Lớp TH xếp vào phòng LT
            if class_type == 'TH' and room_type_normalized == 'LT':
                self.violations.append(ConstraintViolation(
                    'HC-05',
                    f'Phòng {ma_phong} là Lý thuyết, nhưng lớp {ma_lop} cần Thực hành',
                    ma_lop,
                    {'room': ma_phong, 'class_type': 'TH', 'room_type': 'LT'}
                ))
            
            # HC-06: Lớp LT xếp vào phòng TH
            elif class_type == 'LT' and room_type_normalized == 'TH':
                self.violations.append(ConstraintViolation(
                    'HC-06',
                    f'Phòng {ma_phong} là Thực hành, nhưng lớp {ma_lop} cần Lý thuyết',
                    ma_lop,
                    {'room': ma_phong, 'class_type': 'LT', 'room_type': 'TH'}
                ))
        
        # HC-04: Phòng phải có thiết bị yêu cầu
        if room_obj:
            thiet_bi_yeu_cau = phan_cong.get('thiet_bi_yeu_cau', '')
            thiet_bi_phong = room_obj.get('thiet_bi', '')
            
            if thiet_bi_yeu_cau and thiet_bi_yeu_cau.strip():
                # Tách thiết bị yêu cầu thành list (có thể phân cách bằng dấu phẩy, chấm phẩy)
                required_items = [item.strip().lower() for item in thiet_bi_yeu_cau.replace(';', ',').split(',') if item.strip()]
                available_items = thiet_bi_phong.lower() if thiet_bi_phong else ''
                
                # Kiểm tra từng thiết bị yêu cầu
                missing_equipment = []
                for req_item in required_items:
                    if req_item not in available_items:
                        missing_equipment.append(req_item)
                
                if missing_equipment:
                    self.violations.append(ConstraintViolation(
                        'HC-04',
                        f'Phòng {ma_phong} thiếu thiết bị: {", ".join(missing_equipment)}',
                        ma_lop,
                        {'room': ma_phong, 'required': thiet_bi_yeu_cau, 'available': thiet_bi_phong, 'missing': missing_equipment}
                    ))
        
        # Store assignment
        self.class_schedule[ma_lop] = {
            'ma_phong': ma_phong,
            'time_slot_id': slot_compact,
            'ma_gv': ma_gv
        }
    
    def _find_room(self, ma_phong: str, prepared_data: Dict) -> Optional[Dict]:
        """Tìm thông tin phòng"""
        for room_type in ['LT', 'TH']:
            for room in prepared_data.get('rooms_by_type', {}).get(room_type, []):
                if room.get('ma_phong') == ma_phong:
                    return room
        return None
    
    def _calculate_metrics(
        self,
        schedule_assignments: List[Dict],
        phan_cong_dict: Dict[str, Dict]
    ) -> Dict:
        """Tính toán metrics tối ưu hóa"""
        if not schedule_assignments:
            return {}
        
        # Số ngày dạy của mỗi GV
        gv_days = defaultdict(set)
        
        for assignment in schedule_assignments:
            ma_lop = assignment.get('class')
            slot_str = assignment.get('slot')  # "T2-C1"
            
            phan_cong = phan_cong_dict.get(ma_lop, {})
            ma_gv = phan_cong.get('ma_gv')
            
            if ma_gv and slot_str:
                # Extract day từ slot (T2 → 2)
                try:
                    day_num = int(slot_str.split('-')[0][1:])
                    gv_days[ma_gv].add(day_num)
                except:
                    pass
        
        avg_teaching_days = sum(len(days) for days in gv_days.values()) / len(gv_days) if gv_days else 0
        
        return {
            'total_assignments': len(schedule_assignments),
            'total_teachers': len(gv_days),
            'avg_teaching_days_per_teacher': round(avg_teaching_days, 2),
            'teacher_workload_distribution': {
                gv: len(days) for gv, days in list(gv_days.items())[:10]
            }
        }
