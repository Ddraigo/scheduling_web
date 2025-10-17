"""
Schedule Validator - Validation và metrics cho thời khóa biểu
Migrated from src/scheduling/schedule_validator.py
"""

import logging
from typing import Dict, List, Optional
from collections import defaultdict

from ..validators.constraint_checker import validate_all_constraints, ConstraintViolation
from ..validators.metrics_calculator import MetricsCalculator

logger = logging.getLogger(__name__)


class ScheduleValidator:
    """Validate và tính metrics cho thời khóa biểu"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset tất cả counters"""
        self.teacher_slots = defaultdict(set)
        self.room_slots = defaultdict(set)
        self.teacher_loads = defaultdict(int)
        self.teacher_day_slots = defaultdict(lambda: defaultdict(int))
        self.teacher_week_slots = defaultdict(int)
        self.violations = []
        
    def validate_schedule(
        self, 
        schedule_data: Dict,
        classes_data: List[Dict],
        rooms_data: Dict[str, List[str]],
        assignments_data: Optional[List[Dict]] = None,
        preferences_data: Optional[List[Dict]] = None,
        constraints_weights: Optional[Dict[str, float]] = None
    ) -> Dict:
        """
        Validate toàn bộ lịch và tính metrics
        
        Args:
            schedule_data: {"schedule": [...]}
            classes_data: Danh sách lớp học
            rooms_data: {"LT": [...], "TH": [...]}
            assignments_data: Phân công GV dạy lớp
            preferences_data: Nguyện vọng giảng viên
            constraints_weights: Trọng số ràng buộc mềm
            
        Returns:
            Dict chứa kết quả validation và metrics
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
        
        # 1. Validate constraints
        constraint_results = validate_all_constraints(
            schedules,
            classes_data,
            rooms_data,
            assignments_data or []
        )
        
        # 2. Calculate metrics
        assignments_map = {}
        if assignments_data:
            for a in assignments_data:
                malop = a.get('MaLop')
                magv = a.get('MaGV')
                if malop and magv:
                    assignments_map[malop] = magv
        
        metrics = MetricsCalculator.calculate_overall_metrics(
            schedules,
            total_classes=len(classes_data),
            total_rooms=len(rooms_data.get('LT', [])) + len(rooms_data.get('TH', [])),
            assignments_map=assignments_map
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
            if isinstance(v, dict):
                errors.append(f"{v['constraint_code']}: {v['message']} (Class: {v['class_id']})")
            else:
                errors.append(f"{v.constraint_code}: {v.message} (Class: {v.class_id})")
        
        return {
            "feasible": constraint_results['feasible'],
            "total_violations": constraint_results['total_violations'],
            "errors": errors,
            "metrics": metrics,
            "violations_by_type": constraint_results['violations_by_type'],
            "violations_by_class": constraint_results['violations_by_class'],
            "soft_violations": len(soft_violations),
            "soft_violations_by_type": dict(soft_violation_stats),
            "quality_score": self._calculate_quality_score(
                constraint_results,
                metrics,
                len(soft_violations)
            )
        }
    
    def _check_preferences(
        self,
        schedules: List[Dict],
        assignments_data: List[Dict],
        preferences_data: List[Dict]
    ) -> List[ConstraintViolation]:
        """Kiểm tra nguyện vọng giảng viên"""
        violations = []
        
        if not preferences_data:
            return violations
        
        # Build preferences map
        preferences_map = defaultdict(set)
        for pref in preferences_data:
            ma_gv = pref.get('MaGV')
            time_slot = pref.get('TimeSlotID')
            if ma_gv and time_slot:
                preferences_map[ma_gv].add(time_slot)
        
        # Build assignments map
        assignments_map = {}
        for a in assignments_data:
            malop = a.get('MaLop')
            magv = a.get('MaGV')
            if malop and magv:
                assignments_map[malop] = magv
        
        # Check violations
        for sched in schedules:
            class_id = sched.get('class')
            slot = sched.get('slot')
            teacher = assignments_map.get(class_id)
            
            if teacher and teacher in preferences_map:
                if slot not in preferences_map[teacher]:
                    violations.append(ConstraintViolation(
                        constraint_code='SC-WISH',
                        message=f"Không đáp ứng nguyện vọng giảng viên",
                        class_id=class_id,
                        severity='warning',
                        details={'teacher': teacher, 'slot': slot}
                    ))
        
        return violations
    
    def _calculate_quality_score(
        self,
        constraint_results: Dict,
        metrics: Dict,
        soft_violations: int
    ) -> float:
        """
        Tính điểm chất lượng tổng thể (0-100)
        
        Returns:
            Quality score từ 0 đến 100
        """
        # Base score from constraint satisfaction
        if constraint_results['total_violations'] > 0:
            constraint_score = max(0, 100 - constraint_results['total_violations'] * 2)
        else:
            constraint_score = 100
        
        # Distribution score
        distribution = metrics.get('distribution', {})
        balance_score = distribution.get('balance_score', 0)
        distribution_score = max(0, 100 - balance_score * 5)
        
        # Room utilization score
        room_util = metrics.get('room_utilization', {})
        util_rate = room_util.get('utilization_rate', 0)
        util_score = util_rate if util_rate <= 100 else max(0, 200 - util_rate)
        
        # Teacher load balance score
        teacher_load = metrics.get('teacher_load', {})
        load_balance = teacher_load.get('load_balance', 0)
        load_score = max(0, 100 - load_balance * 3)
        
        # Soft constraint penalty
        soft_penalty = min(50, soft_violations * 0.5)
        
        # Weighted average
        final_score = (
            constraint_score * 0.5 +
            distribution_score * 0.2 +
            util_score * 0.1 +
            load_score * 0.2
        ) - soft_penalty
        
        return max(0, min(100, final_score))
    
    def validate_schedule_django(self, ma_dot: str) -> Dict:
        """
        Validate schedule sử dụng Django ORM
        
        Args:
            ma_dot: Mã đợt xếp lịch
            
        Returns:
            Validation results
        """
        from ..models import ThoiKhoaBieu, PhanCong, LopMonHoc, PhongHoc
        
        try:
            # Get schedules from database
            tkb_list = ThoiKhoaBieu.objects.filter(
                dot_xep__ma_dot=ma_dot
            ).select_related(
                'lop_mon_hoc', 'phong_hoc', 'time_slot', 'phan_cong'
            )
            
            if not tkb_list.exists():
                return {
                    'feasible': False,
                    'errors': ['No schedules found for this period']
                }
            
            # Convert to dict format
            schedules = []
            for tkb in tkb_list:
                schedules.append({
                    'class': tkb.lop_mon_hoc.ma_lop,
                    'room': tkb.phong_hoc.ma_phong,
                    'slot': tkb.time_slot.ma_time_slot,
                })
            
            # Get classes data
            classes_data = []
            for lop in LopMonHoc.objects.filter(
                tkb_list__dot_xep__ma_dot=ma_dot
            ).distinct():
                classes_data.append({
                    'id': lop.ma_lop,
                    'type': lop.loai_lop or 'LT',
                    'size': lop.si_so,
                })
            
            # Get rooms data
            rooms_data = {
                'LT': list(PhongHoc.objects.filter(loai_phong='LT').values_list('ma_phong', flat=True)),
                'TH': list(PhongHoc.objects.filter(loai_phong='TH').values_list('ma_phong', flat=True)),
                'room_capacities': {
                    r.ma_phong: r.suc_chua
                    for r in PhongHoc.objects.all()
                }
            }
            
            # Get assignments
            assignments_data = []
            for pc in PhanCong.objects.filter(dot_xep__ma_dot=ma_dot):
                assignments_data.append({
                    'MaLop': pc.lop_mon_hoc.ma_lop,
                    'MaGV': pc.giang_vien.ma_gv,
                })
            
            # Validate
            return self.validate_schedule(
                {'schedule': schedules},
                classes_data,
                rooms_data,
                assignments_data
            )
        
        except Exception as e:
            logger.error(f"Error validating schedule: {e}")
            return {
                'feasible': False,
                'errors': [str(e)]
            }
