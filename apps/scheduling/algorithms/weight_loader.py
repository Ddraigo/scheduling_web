"""
Utility module for loading soft constraint weights dynamically from database.
Provides fallback mechanism to hardcoded defaults if database is unavailable.

"""

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


# DEFAULT WEIGHTS - Fallback mechanism (MUST NOT be removed)
# These are used when database is unavailable or empty
DEFAULT_WEIGHTS = {
    'MIN_WORKING_DAYS': 1.0,
    'LECTURE_CONSECUTIVENESS': 1.5,
    'ROOM_STABILITY': 1.0,
    'TEACHER_LECTURE_CONSOLIDATION': 1.8,
    'TEACHER_PREFERENCE': 2.0,
    'TEACHER_WORKING_DAYS': 2.5,
    'ROOM_CAPACITY': 1.0,
}


# Mapping từ ma_rang_buoc trong DB → key trong code
# Admin có thể thêm/sửa/xóa ràng buộc trong DB, mapping này đảm bảo đúng trọng số được load
CONSTRAINT_MAPPING = {

    # Format mới (RBM-xxx) - tương thích với database hiện tại
    'RBM-001': 'TEACHER_WORKING_DAYS',        # Giới hạn số ngày làm việc tối thiểu của giảng viên
    'RBM-002': 'MIN_WORKING_DAYS',            # Giới hạn số ngày làm việc tối thiểu
    'RBM-003': 'LECTURE_CONSECUTIVENESS',     # Các tiết lý thuyết nên liên tiếp trong một buổi
    'RBM-004': 'ROOM_STABILITY',              # Ưu tiên lớp học cố định trong cả học kỳ
    'RBM-005': 'TEACHER_LECTURE_CONSOLIDATION', # Tập trung các tiết của GV vào ít ngày
    'RBM-006': 'TEACHER_PREFERENCE',          # Tôn trọng nguyện vọng giảng viên
}


class WeightLoader:
    """
    Load soft constraint weights dynamically from database with fallback to defaults.
    
    Design Principles:
    1. Database-first: Try to load from tb_RANG_BUOC_MEM + tb_RANG_BUOC_TRONG_DOT
    2. Failsafe: Always fallback to DEFAULT_WEIGHTS if DB fails
    3. Dot-specific: Load weights per MaDot (scheduling period)
    4. Never crash: Handle all edge cases gracefully
    
    Usage:
        weights = WeightLoader.load_weights(ma_dot='DOT-2024-HK1')
        penalty = violation_count * weights['TEACHER_PREFERENCE']
    """
    
    @staticmethod
    def load_weights(ma_dot: Optional[str] = None) -> Dict[str, float]:
        """
        Load soft constraint weights for a specific scheduling period.
        
        Args:
            ma_dot: Scheduling period code (e.g., 'DOT-2024-HK1')
                   If None, loads all default constraints from tb_RANG_BUOC_MEM
        
        Returns:
            Dict mapping constraint names to weights, e.g.:
            {
                'MIN_WORKING_DAYS': 1.0,
                'TEACHER_PREFERENCE': 2.5,
                ...
            }
        
        Logic Flow (3-tier priority):
            1. If ma_dot is provided:
               - Try to load from tb_RANG_BUOC_TRONG_DOT.TrongSo (dot-specific overrides)
               - Nếu ràng buộc có trong đợt → dùng TrongSo từ RangBuocTrongDot
               - If empty/not found, fallback to step 2
            2. Try to load from tb_RANG_BUOC_MEM.TrongSo (global defaults)
               - Nếu không có trong đợt → dùng TrongSo từ RangBuocMem
            3. If database fails or is empty, use DEFAULT_WEIGHTS (hardcoded)
        """
        try:
            # Import models inside method to avoid circular dependency
            from apps.scheduling.models import RangBuocMem, RangBuocTrongDot
            
            weights = {}
            
            # Step 1: Load dot-specific constraints first (highest priority)
            if ma_dot:
                dot_constraints = WeightLoader._load_from_dot(ma_dot, RangBuocTrongDot, RangBuocMem)
                if dot_constraints:
                    logger.info(f"Loaded {len(dot_constraints)} dot-specific weights for {ma_dot}")
                    weights.update(dot_constraints)  # Add all dot-specific weights
                else:
                    logger.info(f"No dot-specific constraints found for {ma_dot}")
            
            # Step 2: Load global constraints for missing keys (fallback)
            global_constraints = WeightLoader._load_from_global(RangBuocMem)
            if global_constraints:
                added_count = 0
                for key, value in global_constraints.items():
                    if key not in weights:  # Chỉ thêm nếu chưa có từ dot-specific
                        weights[key] = value
                        added_count += 1
                if added_count > 0:
                    logger.info(f"Added {added_count} global weights from RangBuocMem")
            
            # Step 3: Merge với DEFAULT_WEIGHTS (hardcoded) cho các key còn thiếu
            final_weights = DEFAULT_WEIGHTS.copy()
            final_weights.update(weights)  # Override defaults với DB values
            
            # Log any constraints using default values (hardcoded)
            missing_keys = set(DEFAULT_WEIGHTS.keys()) - set(weights.keys())
            if missing_keys:
                logger.warning(
                    f"Using hardcoded default weights for missing constraints: {missing_keys}"
                )
            
            return final_weights
            
        except Exception as e:
            # Database error or models not available - use defaults
            logger.error(
                f"Failed to load weights from database: {e}. Using DEFAULT_WEIGHTS."
            )
            return DEFAULT_WEIGHTS.copy()
    
    @staticmethod
    def _load_from_dot(ma_dot: str, RangBuocTrongDot, RangBuocMem) -> Dict[str, float]:
        """
        Load weights from tb_RANG_BUOC_TRONG_DOT for a specific scheduling period.
        Ưu tiên trọng số từ TrongSo trong RangBuocTrongDot (override cho đợt cụ thể).
        
        Returns:
            Dict of weights, or empty dict if no constraints found
        """
        try:
            # Get all constraints assigned to this dot
            dot_constraints = RangBuocTrongDot.objects.filter(
                ma_dot=ma_dot
            ).select_related('ma_rang_buoc')
            
            if not dot_constraints.exists():
                return {}
            
            weights = {}
            for dot_rb in dot_constraints:
                rang_buoc = dot_rb.ma_rang_buoc
                ma_rb = rang_buoc.ma_rang_buoc
                
                # Map database code to internal key
                if ma_rb in CONSTRAINT_MAPPING:
                    key = CONSTRAINT_MAPPING[ma_rb]
                    # Ưu tiên dùng trong_so từ RangBuocTrongDot (override cho đợt)
                    weights[key] = float(dot_rb.trong_so)
                    logger.debug(f"Loaded dot-specific weight: {key} = {dot_rb.trong_so}")
                else:
                    logger.warning(
                        f"Unknown constraint code '{ma_rb}' in database. Skipping."
                    )
            
            return weights
            
        except Exception as e:
            logger.error(f"Error loading dot-specific weights: {e}")
            return {}
    
    @staticmethod
    def _load_from_global(RangBuocMem) -> Dict[str, float]:
        """
        Load weights from tb_RANG_BUOC_MEM (global default constraints).
        
        Returns:
            Dict of weights, or empty dict if table is empty
        """
        try:
            all_constraints = RangBuocMem.objects.all()
            
            if not all_constraints.exists():
                return {}
            
            weights = {}
            for rang_buoc in all_constraints:
                ma_rb = rang_buoc.ma_rang_buoc
                
                # Map database code to internal key
                if ma_rb in CONSTRAINT_MAPPING:
                    key = CONSTRAINT_MAPPING[ma_rb]
                    weights[key] = float(rang_buoc.trong_so)
                else:
                    logger.warning(
                        f"Unknown constraint code '{ma_rb}' in database. Skipping."
                    )
            
            return weights
            
        except Exception as e:
            logger.error(f"Error loading global weights: {e}")
            return {}
    
    @staticmethod
    def get_weight(constraint_name: str, ma_dot: Optional[str] = None) -> float:
        """
        Convenience method to get a single weight value.
        
        Args:
            constraint_name: One of the keys in DEFAULT_WEIGHTS
            ma_dot: Optional scheduling period code
        
        Returns:
            Weight value (float), guaranteed to never fail
        
        Example:
            weight = WeightLoader.get_weight('TEACHER_PREFERENCE', 'DOT-2024-HK1')
        """
        weights = WeightLoader.load_weights(ma_dot)
        return weights.get(constraint_name, DEFAULT_WEIGHTS.get(constraint_name, 1.0))


# Convenience functions for backward compatibility
def load_weights_for_dot(ma_dot: str) -> Dict[str, float]:
    """
    Load weights for a specific scheduling period.
    Convenience function wrapping WeightLoader.load_weights()
    """
    return WeightLoader.load_weights(ma_dot)


def get_default_weights() -> Dict[str, float]:
    """
    Get the hardcoded default weights.
    Useful for testing or when you explicitly want defaults.
    """
    return DEFAULT_WEIGHTS.copy()
