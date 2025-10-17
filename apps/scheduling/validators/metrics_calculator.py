"""
Shared metrics calculation
⭐ ĐỒNG BỘ HOÀN TOÀN VỚI greedy_heuristic_ga_algorithm_sql.py
"""

import math
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """
    Tính toán metrics cho soft constraints
    ⭐ Logic dùng chung cho GA và Validator
    """
    
    @staticmethod
    def fairness_teacher_load_std(teacher_week_slots: Dict[str, int]) -> Tuple[float, float]:
        """
        Tính độ lệch chuẩn phân công GV
        
        Returns:
            (fairness_std, fairness_score)
        """
        loads = list(teacher_week_slots.values())
        if not loads:
            return (0.0, 1.0)
        
        mean_load = sum(loads) / len(loads)
        variance = sum((x - mean_load) ** 2 for x in loads) / len(loads)
        std = math.sqrt(variance)
        
        # Fairness score: càng std nhỏ càng tốt
        fairness_score = 1.0 / (1.0 + std)
        
        return (std, fairness_score)
    
    @staticmethod
    def wish_satisfaction_score(
        schedules: List[Dict],
        assignments_map: Dict[str, str],
        preferences_map: Dict[str, Set[str]]
    ) -> Tuple[int, int, float]:
        """
        Tính tỷ lệ nguyện vọng được đáp ứng
        ⭐ Count wishes across ALL teachers (not just scheduled)
        
        Returns:
            (wish_count, total_wishes, satisfaction_ratio)
        """
        # Count wishes across ALL teachers (not just scheduled)
        total_wishes = sum(len(slots) for slots in preferences_map.values())
        
        if total_wishes == 0:
            return (0, 0, 1.0)
        
        # Count satisfied wishes
        wish_count = 0
        for sched in schedules:
            class_id = sched.get('class')
            slot = sched.get('slot')
            teacher = assignments_map.get(class_id)
            
            if teacher and teacher in preferences_map:
                if slot in preferences_map[teacher]:
                    wish_count += 1
        
        satisfaction_ratio = wish_count / total_wishes
        return (wish_count, total_wishes, satisfaction_ratio)
    
    @staticmethod
    def compactness_penalty(teacher_day_slots: Dict[str, Dict[int, int]]) -> float:
        """
        Tính penalty cho lịch không compact
        Penalty càng thấp càng tốt (lịch compact)
        
        Returns:
            compactness_penalty (lower is better)
        """
        penalty = 0.0
        
        for teacher, day_slots in teacher_day_slots.items():
            # Số ngày dạy
            days_teaching = len([d for d, count in day_slots.items() if count > 0])
            
            # Penalty nếu dạy ít tiết nhưng nhiều ngày
            total_slots = sum(day_slots.values())
            if days_teaching > 0 and total_slots > 0:
                avg_slots_per_day = total_slots / days_teaching
                # Penalty nếu avg < 2 (lịch rải rác)
                if avg_slots_per_day < 2:
                    penalty += (2 - avg_slots_per_day) * days_teaching
        
        return penalty
    
    @staticmethod
    def daily_limit_compliance(
        teacher_day_slots: Dict[str, Dict[int, int]],
        max_daily_slots: int = 5
    ) -> Tuple[int, int]:
        """
        RBM-001: Kiểm tra giới hạn số tiết/ngày
        
        Returns:
            (compliant_count, violation_count)
        """
        compliant = 0
        violations = 0
        
        for teacher, day_slots in teacher_day_slots.items():
            for day, count in day_slots.items():
                if count > 0:
                    if count <= max_daily_slots:
                        compliant += 1
                    else:
                        violations += 1
        
        return (compliant, violations)
    
    @staticmethod
    def compact_days_score(teacher_day_slots: Dict[str, Dict[int, int]]) -> float:
        """
        RBM-002: Điểm thưởng cho lịch compact (ít ngày, nhiều tiết/ngày)
        Score càng cao càng tốt
        
        Returns:
            compact_days_score (higher is better)
        """
        score = 0.0
        
        for teacher, day_slots in teacher_day_slots.items():
            days_teaching = len([d for d, count in day_slots.items() if count > 0])
            total_slots = sum(day_slots.values())
            
            if days_teaching > 0 and total_slots > 0:
                # Thưởng nếu dạy ít ngày nhưng nhiều tiết/ngày
                avg_slots_per_day = total_slots / days_teaching
                # Score tăng nếu avg >= 2
                if avg_slots_per_day >= 2:
                    score += avg_slots_per_day * (6 - days_teaching)  # Ít ngày = điểm cao
        
        return score
    
    @staticmethod
    def parse_timeslot(slot_str: str) -> Tuple[int, int]:
        """
        Parse TimeSlotID thành (day, slot)
        Format: "Thu2-Ca1" → (0, 0), "Thu3-Ca2" → (1, 1), ...
        Thu2=Mon=0, Thu3=Tue=1, ..., Thu7=Sat=5, Thu8=Sun=6
        """
        try:
            parts = slot_str.split('-')
            if len(parts) != 2:
                return (0, 0)
            
            day_part = parts[0]  # "Thu2"
            slot_part = parts[1]  # "Ca1"
            
            # Extract day number (Thu2 → 2)
            day_num_str = ''.join(filter(str.isdigit, day_part))
            if not day_num_str:
                return (0, 0)
            day_num = int(day_num_str)
            day = day_num - 2  # Thu2=0, Thu3=1, ..., Thu7=5, Thu8=6
            
            # Extract slot number (Ca1 → 1)
            slot_num_str = ''.join(filter(str.isdigit, slot_part))
            if not slot_num_str:
                return (0, 0)
            slot_num = int(slot_num_str)
            slot = slot_num - 1  # Ca1=0, Ca2=1, ...
            
            return (day, slot)
        except Exception as e:
            logger.warning(f"Cannot parse timeslot: {slot_str}, using (0, 0). Error: {e}")
            return (0, 0)
    
    @staticmethod
    def calculate_all_metrics(
        schedules: List[Dict],
        classes_data: List[Dict],
        assignments_data: List[Dict],
        preferences_data: List[Dict],
        weights: Dict[str, float] = None
    ) -> Dict:
        """
        Tính TẤT CẢ metrics
        ⭐ Function dùng chung cho tất cả validation
        
        Args:
            schedules: [{'class': 'LOP-xxx', 'slot': 'Thu2-Ca1', 'room': 'P101'}, ...]
            classes_data: [{'id': 'LOP-xxx', 'type': 'LT', ...}, ...]
            assignments_data: [{'MaLop': 'LOP-xxx', 'MaGV': 'GV001'}, ...]
            preferences_data: [{'MaGV': 'GV001', 'TimeSlotID': 'Thu2-Ca1'}, ...]
            weights: {'w_fair': 1.0, 'w_wish': 1.2, ...}
            
        Returns:
            Dict chứa tất cả metrics
        """
        # Build maps
        assignments_map = {}
        for a in assignments_data:
            malop = a.get('MaLop')
            magv = a.get('MaGV')
            if malop and magv:
                assignments_map[malop] = magv
        
        preferences_map = defaultdict(set)
        for pref in preferences_data:
            teacher = pref.get('teacher') or pref.get('MaGV')
            slot = pref.get('slots') or pref.get('TimeSlotID')
            if teacher and slot:
                if isinstance(slot, list):
                    preferences_map[teacher].update(slot)
                else:
                    preferences_map[teacher].add(slot)
        
        # Build teacher tracking
        teacher_week_slots = defaultdict(int)
        teacher_day_slots = defaultdict(lambda: defaultdict(int))
        
        for sched in schedules:
            class_id = sched.get('class')
            slot_str = sched.get('slot')
            teacher = assignments_map.get(class_id)
            
            if teacher and slot_str:
                teacher_week_slots[teacher] += 1
                
                # Parse day from slot
                day, slot_num = MetricsCalculator.parse_timeslot(slot_str)
                teacher_day_slots[teacher][day] += 1
        
        # Calculate metrics
        fairness_std, fairness_score = MetricsCalculator.fairness_teacher_load_std(teacher_week_slots)
        
        wish_count, total_wishes, wish_satisfaction = MetricsCalculator.wish_satisfaction_score(
            schedules, assignments_map, preferences_map
        )
        
        compactness = MetricsCalculator.compactness_penalty(teacher_day_slots)
        
        daily_compliant, daily_violations = MetricsCalculator.daily_limit_compliance(teacher_day_slots)
        
        compact_days = MetricsCalculator.compact_days_score(teacher_day_slots)
        
        # Default weights (từ SQL nếu có)
        if weights is None:
            weights = {
                'w_fair': 1.0,
                'w_wish': 1.2,
                'w_compact': 0.5,
                'w_unsat': 0.8,
                'w_daily_limit': 0.6,
                'w_compact_days': 0.4
            }
        
        # Calculate fitness (REWARDS - PENALTIES)
        # Formula: fairness + wish_satisfaction - compactness_penalty + daily_compliance + compact_days - unmet_wishes
        total_daily = daily_compliant + daily_violations
        daily_compliance_ratio = daily_compliant / max(total_daily, 1) if total_daily > 0 else 1.0
        
        fitness = (
            weights.get('w_fair', 1.0) * fairness_score +
            weights.get('w_wish', 1.2) * wish_satisfaction -
            weights.get('w_compact', 0.5) * compactness +
            weights.get('w_daily_limit', 0.6) * daily_compliance_ratio +
            weights.get('w_compact_days', 0.4) * compact_days -
            weights.get('w_unsat', 0.8) * (total_wishes - wish_count)
        )
        
        return {
            'fitness': fitness,
            'fairness_std': fairness_std,
            'fairness_score': fairness_score,
            'wish_satisfaction': wish_satisfaction,
            'wish_count': wish_count,
            'total_wishes': total_wishes,
            'unmet_wishes': total_wishes - wish_count,
            'compactness_penalty': compactness,
            'daily_compliant': daily_compliant,
            'daily_violations': daily_violations,
            'compact_days_score': compact_days,
            'teacher_loads': dict(teacher_week_slots)
        }
