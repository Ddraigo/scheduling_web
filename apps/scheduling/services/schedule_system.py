"""
Hệ thống sắp xếp lịch học tích hợp (REFACTORED Phase 2)
Uses: ScheduleGeneratorLLM, DataAccessLayer, LLM Services
"""

import json
import logging
import re
from datetime import datetime
from typing import Dict, List
from tabulate import tabulate

from .schedule_generator_llm import ScheduleGeneratorLLM
from .data_access_layer import DataAccessLayer
from .llm_service import LLMDataProcessor, LLMPromptBuilder
from ..utils.helpers import json_serial

logger = logging.getLogger(__name__)


class ScheduleSystem:
    """
    REFACTORED Phase 2: Hệ thống sắp xếp lịch học tích hợp
    
    Architecture:
    - ScheduleGeneratorLLM: Main scheduling engine using LLM
    - DataAccessLayer: Centralized data queries (replaces raw SQL)
    - LLMService: LLM integration (replaces ScheduleAI)
    - ScheduleValidator: Validates and scores schedules
    """
    
    def __init__(self):
        """Initialize with new architecture components"""
        self.generator = ScheduleGeneratorLLM()
        self.dal = DataAccessLayer()
        self.data_processor = LLMDataProcessor()
        self.prompt_builder = LLMPromptBuilder()
        self.current_data = {}
        
    def initialize(self):
        """Khởi tạo hệ thống"""
        logger.info("✅ Schedule System initialized with new architecture")
        logger.info("   - ScheduleGeneratorLLM: Main engine")
        logger.info("   - DataAccessLayer: Data queries")
        logger.info("   - LLM Service: Gemini API integration")
        return True
    
    def load_database_context(self, semester_code: str = None):
        """
        Tải ngữ cảnh từ database sử dụng DAL
        
        Args:
            semester_code: Mã học kỳ (VD: 2025-2026_HK1)
            
        Returns:
            Dict chứa dữ liệu từ DAL
        """
        logger.info(f"📊 Đang tải dữ liệu từ database cho {semester_code}...")
        
        if not semester_code:
            semester_code = "2025-2026_HK1"
        
        # Sử dụng DAL để lấy dữ liệu
        self.current_data = DataAccessLayer.get_schedule_data_for_llm(semester_code)
        
        logger.info(f"✅ Dữ liệu đã tải:")
        logger.info(f"   - Đợt xếp: {len(self.current_data.get('dot_xep_list', []))}")
        logger.info(f"   - Phòng học: {len(self.current_data.get('all_rooms', []))}")
        logger.info(f"   - Slot thời gian: {len(self.current_data.get('all_timeslots', []))}")
        
        return self.current_data
    
    def create_schedule(self, semester_code: str) -> Dict:
        """
        Tạo lịch học tối ưu cho một học kỳ
        
        Args:
            semester_code: Mã học kỳ (VD: 2025-2026_HK1)
            
        Returns:
            Dict chứa kết quả lịch học
        """
        logger.info(f"🎯 Tạo lịch tối ưu cho {semester_code}...")
        
        try:
            # Sử dụng ScheduleGeneratorLLM để tạo lịch
            result = self.generator.create_schedule_llm(semester_code)
            logger.info(f"✅ Lịch được tạo thành công")
            return {
                'success': True,
                'semester_code': semester_code,
                'result': result
            }
        except Exception as e:
            logger.error(f"❌ Lỗi tạo lịch: {e}")
            return {
                'success': False,
                'error': str(e),
                'semester_code': semester_code
            }
    
    def analyze_schedule_request(self, user_request: str) -> str:
        """
        REFACTORED Phase 2: Phân tích yêu cầu sắp xếp lịch
        Sử dụng LLMService components thay vì raw SQL queries
        
        Args:
            user_request: Yêu cầu từ người dùng
            
        Returns:
            Kết quả phân tích hoặc lịch được tạo
        """
        # Extract semester code nếu có
        semester_match = re.search(
            r'(20\d{2}[-_]20\d{2}[^a-zA-Z]*HK[12]|20\d{2}[-_]20\d{2})', 
            user_request
        )
        semester_code = semester_match.group(1) if semester_match else "2025-2026_HK1"
        
        # Kiểm tra xem có phải yêu cầu tạo lịch không
        create_schedule_keywords = [
            'tạo thời khóa biểu', 'tạo lịch', 'lập lịch', 'sắp xếp lịch', 'tối ưu lịch',
            'xếp lịch tối ưu', 'tự động xếp', 'generate schedule', 'create schedule',
            'sắp lịch', 'xếp lịch', 'tạo tkb'
        ]
        
        user_lower = user_request.lower()
        is_create_schedule = any(keyword in user_lower for keyword in create_schedule_keywords)
        
        if is_create_schedule:
            logger.info(f"🎯 Nhận diện: TẠO LỊCH cho {semester_code}")
            result = self.create_schedule(semester_code)
            return json.dumps(result, ensure_ascii=False, indent=2, default=json_serial)
        
        # Cho các yêu cầu khác, sử dụng LLMDataProcessor + Prompt Builder
        logger.info(f"📝 Xử lý yêu cầu thông thường: {user_request[:50]}...")
        try:
            # Simply return the request for now - can be enhanced later
            # with actual prompt building if needed
            return f"Yêu cầu: {user_request}\n⚠️ Tính năng xử lý yêu cầu tổng quát đang được phát triển"
        except Exception as e:
            logger.error(f"❌ Lỗi xử lý yêu cầu: {e}")
            return f"❌ Không thể xử lý yêu cầu: {str(e)}"
        return result
    
    def cleanup(self):
        """Dọn dẹp tài nguyên"""
        self.db.disconnect()
