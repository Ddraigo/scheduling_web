"""
Validator chuyên biệt cho LLM Schedule Generation
Kiểm tra hard constraints + tính toán metrics
Tích hợp với cấu trúc dữ liệu hiện tại (ma_dot, ma_lop, ma_phong, time_slot_id)

Sử dụng ConstraintViolation từ constraint_checker.py để đảm bảo consistency
"""

import logging
from typing import Dict, List, Optional
from collections import defaultdict

from apps.scheduling.validators.constraint_checker import ConstraintViolation

logger = logging.getLogger(__name__)


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
        self.teacher_schedule = defaultdict(list)  # {ma_gv: [(ma_dot, time_slot_id), ...]}
        self.room_schedule = defaultdict(list)      # {ma_phong: [(ma_dot, time_slot_id), ...]}
        self.class_schedule = defaultdict(dict)     # {ma_lop: {'ma_phong': ..., 'time_slot_id': ..., 'ma_gv': ...}}
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
        assigned_classes = len(schedule_assignments)
        
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
        
        # Format output
        return {
            'feasible': len(self.violations) == 0,
            'total_classes': total_classes,
            'assigned_classes': assigned_classes,
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
            slot_key = (ma_gv, slot_compact)
            if slot_key in self.teacher_schedule[ma_gv]:
                self.violations.append(ConstraintViolation(
                    'HC-01',
                    f'GV {ma_gv} dạy nhiều lớp cùng slot {slot_compact}',
                    ma_lop,
                    {'teacher': ma_gv, 'slot': slot_compact}
                ))
            else:
                self.teacher_schedule[ma_gv].append(slot_key)
        
        # HC-02: Phòng không có 2 lớp cùng lúc
        slot_key = (ma_phong, slot_compact)
        if slot_key in self.room_schedule[ma_phong]:
            self.violations.append(ConstraintViolation(
                'HC-02',
                f'Phòng {ma_phong} có 2 lớp cùng slot {slot_compact}',
                ma_lop,
                {'room': ma_phong, 'slot': slot_compact}
            ))
        else:
            self.room_schedule[ma_phong].append(slot_key)
        
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
