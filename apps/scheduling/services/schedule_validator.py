"""
Module validation và metrics cho thời khóa biểu
Kiểm tra hard constraints và tính toán soft constraints metrics
REFACTORED Phase 2: Sử dụng shared validation library + new data structures
"""

import logging
from typing import Dict, List, Tuple, Set
from collections import defaultdict
import math

try:
    from src.validation.constraint_checker import validate_all_constraints, ConstraintViolation
    from src.validation.metrics_calculator import MetricsCalculator
except ImportError:
    # Fallback: provide basic validation if shared libraries not available
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ Shared validation libraries not found, using basic validation")
    
    class ConstraintViolation:
        def __init__(self, constraint_code, message, class_id, details=None):
            self.constraint_code = constraint_code
            self.message = message
            self.class_id = class_id
            self.details = details or {}

logger = logging.getLogger(__name__)


class ScheduleValidator:
    """
    REFACTORED Phase 2: Validate và tính metrics cho thời khóa biểu
    
    Công việc:
    1. Kiểm tra hard constraints (xung đột thời gian, phòng học, giảng viên)
    2. Tính toán soft constraints metrics (nguyện vọng giảng viên, tối ưu hóa)
    3. Format kết quả validation cho LLM và frontend
    
    Data flow:
    - Input: schedule_data từ ScheduleGeneratorLLM
    - Process: validate_all_constraints() + calculate_all_metrics()
    - Output: Dict chứa feasibility score, violations, metrics
    """
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset tất cả counters"""
        self.teacher_slots = defaultdict(set)  # {teacher: {(day, slot), ...}}
        self.room_slots = defaultdict(set)      # {room: {(day, slot), ...}}
        self.teacher_loads = defaultdict(int)    # {teacher: count}
        self.teacher_day_slots = defaultdict(lambda: defaultdict(int))  # {teacher: {day: count}}
        self.teacher_week_slots = defaultdict(int)  # {teacher: total_slots}
        self.violations = []
        
    def validate_schedule(
        self, 
        schedule_data: Dict,
        classes_data: List[Dict],
        rooms_data: Dict[str, List[str]],
        assignments_data: List[Dict] = None,
        preferences_data: List[Dict] = None,
        constraints_weights: Dict[str, float] = None
    ) -> Dict:
        """
        Validate toàn bộ lịch và tính metrics
        REFACTORED Phase 2: Sử dụng shared validation library
        
        Args:
            schedule_data: {"schedule": [...]} từ LLM
            classes_data: Danh sách lớp học
            rooms_data: {"LT": [...], "TH": [...]}
            assignments_data: Phân công GV dạy lớp từ DataAccessLayer
            preferences_data: Nguyện vọng giảng viên từ DataAccessLayer
            constraints_weights: Trọng số ràng buộc mềm
            
        Returns:
            Dict chứa:
            - feasible: boolean
            - errors: list of hard constraint violations
            - metrics: dict of optimization metrics
            - violations_by_type: dict thống kê vi phạm
            - soft_violations_by_type: dict vi phạm mềm
            
        Example:
            ```python
            validator = ScheduleValidator()
            result = validator.validate_schedule(
                schedule_data=llm_result,
                classes_data=dal.get_all_lop_mon_hoc(),
                rooms_data={'LT': [...], 'TH': [...]},
                assignments_data=dal.get_phan_cong_all(),
                preferences_data=dal.get_nguyen_vong_all()
            )
            ```
        """
        self.reset()
        
        schedules = schedule_data.get('schedule', [])
        
        if not schedules:
            return {
                "feasible": False,
                "errors": ["No schedules found"],
                "metrics": {},
                "violations_by_type": {},
                "soft_violations_by_type": {}
            }
        
        # 1. Validate constraints using SHARED library
        constraint_results = validate_all_constraints(
            schedules,
            classes_data,
            rooms_data,
            assignments_data or []
        )
        
        # 2. Calculate metrics using SHARED library
        metrics = MetricsCalculator.calculate_all_metrics(
            schedules,
            classes_data,
            assignments_data or [],
            preferences_data or [],
            constraints_weights or {}
        )
        
        # 3. Check soft constraints (preferences)
        soft_violations = self._check_preferences(
            schedules,
            assignments_data or [],
            preferences_data or []
        )
        
        # Count soft violations by type
        soft_violation_stats = defaultdict(int)
        for v in soft_violations:
            soft_violation_stats[v.constraint_code] += 1
        
        # 4. Format output
        errors = []
        for v in constraint_results['violations'][:20]:
            errors.append(f"{v.constraint_code}: {v.message}")
        
        return {
            "feasible": constraint_results['feasible'],
            "errors": errors,
            "total_violations": constraint_results['total_violations'],
            "total_soft_violations": len(soft_violations),
            "hard_violated_classes": constraint_results['violated_classes_count'],
            "soft_violated_classes": len({v.class_id for v in soft_violations}),
            "ok_classes": len(classes_data) - constraint_results['violated_classes_count'],
            "violations_by_type": constraint_results['violations_by_type'],
            "soft_violations_by_type": dict(soft_violation_stats),
            "violations_details": [
                {'constraint': v.constraint_code, 'message': v.message, 'class': v.class_id}
                for v in constraint_results['violations'][:20]
            ],
            "soft_violations_details": [
                {'constraint': v.constraint_code, 'message': v.message, 'class': v.class_id}
                for v in soft_violations[:20]
            ],
            "metrics": metrics,
            "all_assigned": len(schedules) == sum(
                c.get('sessions', c.get('SoCaTuan', 1)) for c in classes_data
            )
        }
    
    def _check_preferences(
        self,
        schedules: List[Dict],
        assignments_data: List[Dict],
        preferences_data: List[Dict]
    ) -> List[ConstraintViolation]:
        """
        Check soft constraints (teacher preferences)
        
        Supports 2 formats:
        1. {'MaGV': 'GV001', 'Thu': 2, 'Ca': 1}
        2. {'MaGV': 'GV001', 'TimeSlotID': 'Thu2-Ca1'}
        
        Returns:
            List of soft constraint violations
        """
        violations = []
        
        if not preferences_data:
            return violations
        
        assignments_map = {a['MaLop']: a['MaGV'] for a in assignments_data if 'MaLop' in a and 'MaGV' in a}
        prefs_map = defaultdict(set)
        
        for pref in preferences_data:
            teacher = pref.get('MaGV')
            if not teacher:
                continue
            
            # Format 1: Thu, Ca fields
            if 'Thu' in pref and 'Ca' in pref:
                day = pref.get('Thu')
                slot = pref.get('Ca')
                if day is not None and slot is not None:
                    prefs_map[teacher].add((day, slot))
            
            # Format 2: TimeSlotID field (Thu2-Ca1)
            elif 'TimeSlotID' in pref:
                slot_str = pref.get('TimeSlotID')
                if slot_str:
                    day, slot = self._parse_timeslot(slot_str)
                    prefs_map[teacher].add((day, slot))
        
        for idx, sched in enumerate(schedules):
            class_id = sched.get('class')
            slot_str = sched.get('slot')
            
            teacher = assignments_map.get(class_id)
            if not teacher:
                continue
            
            day, slot_num = self._parse_timeslot(slot_str)
            
            if (day, slot_num) not in prefs_map.get(teacher, set()):
                violations.append(ConstraintViolation(
                    constraint_code='PREF-01',
                    message=f'Teacher {teacher} teaches class {class_id} outside preferred slot',
                    class_id=class_id,
                    details={'teacher': teacher, 'slot': slot_str}
                ))
        
        return violations
    
    def _parse_timeslot(self, slot_str: str) -> tuple[int, int]:
        """
        Parse TimeSlotID thành (day, slot)
        Format: "Thu2-Ca1" → (0, 0), "Thu3-Ca2" → (1, 1), ...
        """
        try:
            parts = slot_str.split('-')
            day_part = parts[0]
            slot_part = parts[1]
            
            day_num = int(''.join(filter(str.isdigit, day_part)))
            day = day_num - 2
            
            slot_num = int(''.join(filter(str.isdigit, slot_part)))
            slot = slot_num - 1
            
            return (day, slot)
        except:
            logger.warning(f"Cannot parse timeslot: {slot_str}, using (0, 0)")
            return (0, 0)