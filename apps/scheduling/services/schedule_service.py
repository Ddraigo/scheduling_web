"""
DEPRECATED SHIM: schedule_service.py
This is a backward compatibility wrapper for views.py and management commands

TODO Phase 2: Refactor views.py to use ScheduleGeneratorLLM directly
"""

import logging
from .schedule_generator_llm import ScheduleGeneratorLLM

logger = logging.getLogger(__name__)


class ScheduleService:
    """
    DEPRECATED: This is a shim class for backward compatibility.
    
    It wraps ScheduleGeneratorLLM to maintain API compatibility with views.py
    and management commands during the Phase 1 → Phase 2 transition.
    
    TODO: Refactor views.py to use ScheduleGeneratorLLM directly in Phase 2
    """
    
    def __init__(self):
        """Initialize with LLM generator"""
        self.generator = ScheduleGeneratorLLM()
        logger.warning("⚠️ ScheduleService is DEPRECATED. Use ScheduleGeneratorLLM directly.")
    
    def generate_schedule(self, ma_dot: str, use_ai: bool = True) -> dict:
        """
        Generate schedule (shim for backward compatibility)
        
        Args:
            ma_dot: Scheduling period code (e.g., '2025-2026_HK1')
            use_ai: Ignored (LLM is always used now). Kept for API compatibility.
            
        Returns:
            Dict with schedule data {
                'success': bool,
                'schedule': [...],
                'metrics': {...},
                ...
            }
        """
        if not use_ai:
            logger.warning("⚠️ use_ai=False ignored. Using LLM (GA algorithm not supported anymore).")
        
        return self.generator.create_schedule_llm(ma_dot=ma_dot)
