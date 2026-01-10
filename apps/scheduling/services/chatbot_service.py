"""
Chatbot Service - Tương tác hỏi đáp về lịch học và dữ liệu database
Sử dụng Google Gemini API
"""

import os
import re
import json
import time
import random
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from google import genai
from google.genai import types
from django.db.models import Q, Count, Avg, Sum

from .data_access_layer import (
    DataAccessLayer, 
    get_giang_vien_info_dict, 
    get_lop_info_dict
)
from .llm_service import LLMDataProcessor
from .chatbot_prompts import SYSTEM_INSTRUCTION, QUERY_SPEC_INSTRUCTION

logger = logging.getLogger(__name__)

# ====================================================================
# CONSTANTS CHO INTERACTIONS API
# ====================================================================

# Model constants
PRIMARY_MODEL = "gemini-2.5-pro"  # Model chính - ổn định
FALLBACK_MODEL = "gemini-2.5-flash"  # Model backup - nhẹ hơn

# Thinking levels cho các tác vụ khác nhau
THINKING_LEVEL_MINIMAL = "minimal"  # Không cần suy nghĩ, giảm độ trễ
THINKING_LEVEL_LOW = "low"  # Suy luận đơn giản, tiết kiệm chi phí
THINKING_LEVEL_MEDIUM = "medium"  # Tư duy cân bằng
THINKING_LEVEL_HIGH = "high"  # Tối đa chiều sâu suy luận


class ScheduleChatbot:
    """
    Chatbot hỏi đáp về lịch học và dữ liệu trường học
    
    Các khả năng:
    - Tra cứu thông tin giảng viên (dạy môn gì, lịch dạy)
    - Tra cứu phòng trống theo thời gian
    - Tra cứu lịch học của lớp/môn
    - Tư vấn xếp lịch (gợi ý phòng phù hợp)
    """
    
    def __init__(self):
        """Khởi tạo chatbot với Google Gemini Interactions API
        
        Sử dụng Interactions API (Beta) với các cải tiến:
        - Stateful conversations với previous_interaction_id
        - Rate limiting với exponential backoff
        - Thinking level configuration
        - Multiple API keys rotation để tránh rate limit
        """
        # === MULTIPLE API KEYS SUPPORT ===
        # Hỗ trợ nhiều API keys: GEMINI_API_KEYS=key1,key2,key3
        # Hoặc fallback về GEMINI_API_KEY/GOOGLE_API_KEY (có thể có dấu phẩy)
        api_keys_str = os.environ.get('GEMINI_API_KEYS')
        
        if not api_keys_str:
            # Fallback: Check GEMINI_API_KEY or GOOGLE_API_KEY
            api_keys_str = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        
        if api_keys_str:
            # Parse keys (split by comma)
            self.api_keys = [k.strip() for k in api_keys_str.split(',') if k.strip()]
            if not self.api_keys:
                raise ValueError("API keys string is empty")
            self.current_key_index = 0
        else:
            raise ValueError("Cần cấu hình GEMINI_API_KEYS hoặc GEMINI_API_KEY")
        
        # Key rotation tracking
        self.key_stats = {}  # {key_index: {'uses': 0, 'failures': 0, 'last_used': timestamp}}
        self.key_cooldowns = {}  # {key_index: cooldown_until_timestamp}
        self.key_invalid = set()  # Set of invalid key indices (API_KEY_INVALID)
        
        # Initialize first client
        self.client = genai.Client(api_key=self.api_keys[self.current_key_index])
        self.model = FALLBACK_MODEL # Model chính - nhanh và ổn định
        
        logger.info(f"🔑 Initialized chatbot with {len(self.api_keys)} API key(s)")
        
        # Interactions API: Lưu interaction_id để tiếp tục cuộc trò chuyện
        self._last_interaction_id: Optional[str] = None
        self._use_stateful_mode = True  # Bật chế độ stateful (default)
        self._store_interactions = True  # Không lưu trữ trên server (tiết kiệm quota)
        
        # System instruction cho chatbot (giữ riêng để giảm độ dài file)
        self.system_instruction = SYSTEM_INSTRUCTION

        # Conversation history (local backup for stateless fallback)
        self.conversation_history: List[Dict[str, str]] = []
        
        # Cache cho đợt xếp hiện tại
        self._cached_dot_xep = None
        self._cache_time = None
        
        # === GLOBAL RATE LIMITING ===
        # Giới hạn tổng số requests cho chatbot (không phân biệt key)
        self._request_limit_per_minute = 3  # Max 3 requests/minute (giảm 429)
        self._request_window_seconds = 60  # Time window
        self._request_timestamps = []  # List of request timestamps
        
        # Rate limiting với exponential backoff (per-key basis)
        self._last_api_call = None
        self._min_delay_between_calls = 2.5  # seconds - base delay (tăng để giảm 429)
        self._max_delay_between_calls = 15.0  # seconds - max delay
        self._current_delay = self._min_delay_between_calls  # adaptive delay
        self._consecutive_rate_limits = 0  # đếm số lần bị rate limit liên tiếp
        self._rate_limit_reset_time = None  # thời điểm reset quota
        self._key_cooldown_duration = 60  # seconds - cooldown time per key after 429
        
        # Database schema để AI sinh query
        self.db_schema = self._build_db_schema()
    
    def _build_db_schema(self) -> str:
        """
        Xây dựng schema database ĐẦY ĐỦ để AI hiểu cấu trúc dữ liệu
        Dựa trên csdl_tkb.sql thực tế
        """
        return """
DATABASE SCHEMA - HỆ THỐNG QUẢN LÝ THỜI KHÓA BIỂU ĐẠI HỌC

=== BẢNG MASTER DATA (không phụ thuộc đợt xếp) ===

1. Khoa (tb_KHOA → model: Khoa)
   - ma_khoa: VARCHAR(12) PK (VD: "K-001", "CNTT")
   - ten_khoa: NVARCHAR(200) (VD: "Công nghệ thông tin", "Quản trị kinh doanh")
   
2. BoMon (tb_BO_MON → model: BoMon)
   - ma_bo_mon: VARCHAR(12) PK (VD: "BM-001-001" = BM-MaKhoa-số thứ tự)
   - ma_khoa: FK → Khoa
   - ten_bo_mon: NVARCHAR(200)
   
3. GiangVien (tb_GIANG_VIEN → model: GiangVien)
   - ma_gv: VARCHAR(12) PK (VD: "GV001", "GV123")
   - ma_bo_mon: FK → BoMon
   - ten_gv: NVARCHAR(200)
   - loai_gv: NVARCHAR(100) ("co_huu", "thinh_giang")
   - email: VARCHAR(200)
   
4. MonHoc (tb_MON_HOC → model: MonHoc)
   - ma_mon_hoc: VARCHAR(10) PK (VD: "MH-0000001", "INT1001")
   - ten_mon_hoc: NVARCHAR(200)
   - so_tin_chi: TINYINT
   - so_tiet_lt: TINYINT (số tiết lý thuyết)
   - so_tiet_th: TINYINT (số tiết thực hành)
   - so_tuan: TINYINT DEFAULT 15
   
5. GVDayMon (tb_GV_DAY_MON → model: GVDayMon)
   - id: INT PK AUTO
   - ma_mon_hoc: FK → MonHoc
   - ma_gv: FK → GiangVien
   - UNIQUE(ma_mon_hoc, ma_gv)
   → Quan hệ N-N: GV nào có thể dạy môn nào
   
6. PhongHoc (tb_PHONG_HOC → model: PhongHoc)
   - ma_phong: VARCHAR(12) PK (VD: "A101", "B001", "LAB01")
   - loai_phong: NVARCHAR(100) ("Lý thuyết"/"LT", "Thực hành"/"TH")
   - suc_chua: SMALLINT
   - thiet_bi: NVARCHAR(400)
   
7. KhungGio (tb_KHUNG_TG → model: KhungTG)
   - ma_khung_gio: TINYINT PK (1, 2, 3, 4, 5)
   - ten_ca: NVARCHAR(50) ("Ca 1", "Ca 2"...)
   - gio_bat_dau: TIME
   - gio_ket_thuc: TIME
   - so_tiet: TINYINT DEFAULT 3
   
8. TimeSlot (tb_TIME_SLOT → model: TimeSlot)
   - time_slot_id: VARCHAR(10) PK (VD: "Thu2-Ca1", "Thu5-Ca3")
   - thu: TINYINT (2-8, trong đó 8=Chủ nhật)
   - ca: FK → KhungGio
   - UNIQUE(thu, ca)

9. DuKienDT (tb_DUKIEN_DT → model: DuKienDT) - Kế hoạch đào tạo theo kỳ
   - ma_du_kien_dt: VARCHAR(15) PK (VD: "2025-2026_HK1")
   - nam_hoc: VARCHAR(9) (VD: "2025-2026")
   - hoc_ky: TINYINT (1=HK1, 2=HK2, 3=HK Hè)
   - ngay_bd: DATETIME (ngày bắt đầu kỳ)
   - ngay_kt: DATETIME (ngày kết thúc kỳ)
   - mo_ta_hoc_ky: NVARCHAR(100)

10. RangBuocMem (tb_RANG_BUOC_MEM → model: RangBuocMem) - Ràng buộc mềm
    - ma_rang_buoc: VARCHAR(15) PK (VD: "RBM-001")
    - ten_rang_buoc: NVARCHAR(200)
    - mo_ta: NVARCHAR(500)
    - trong_so: FLOAT (trọng số ưu tiên)

=== BẢNG TRANSACTION DATA (phụ thuộc đợt xếp) ===

11. DotXep (tb_DOT_XEP → model: DotXep) - Đợt xếp lịch
    - ma_dot: VARCHAR(12) PK (VD: "DOT2025-01")
    - ten_dot: NVARCHAR(200)
    - nam_hoc: VARCHAR(9)
    - hoc_ky: TINYINT
    - trang_thai: NVARCHAR(20) ("DRAFT", "RUNNING", "LOCKED", "PUBLISHED")
    - ngay_bat_dau: DATE
    - ngay_ket_thuc: DATE

12. LopMonHoc (tb_LOP_MON_HOC → model: LopMonHoc)
    - ma_lop: VARCHAR(15) PK (VD: "INT1001-N1")
    - ma_mon_hoc: FK → MonHoc
    - nhom_mh: TINYINT (nhóm lý thuyết)
    - to_mh: TINYINT (tổ thực hành - NULL nếu lớp lý thuyết)
    - ma_du_kien_dt: FK → DuKienDT
    - ma_dot: FK → DotXep (đợt xếp đang thuộc)
    - so_luong_sv: SMALLINT
    - he_dao_tao: NVARCHAR(200) ("Đại học", "Cao đẳng")
    - ngon_ngu: NVARCHAR(50)
    - thiet_bi_yeu_cau: NVARCHAR(400)
    - so_ca_tuan: TINYINT DEFAULT 1 (số ca/tuần cần xếp)
    - UNIQUE(ma_mon_hoc, nhom_mh, to_mh)
   
13. PhanCong (tb_PHAN_CONG → model: PhanCong) - Phân công GV dạy lớp
    - id: INT PK AUTO
    - ma_dot: FK → DotXep
    - ma_lop: FK → LopMonHoc
    - ma_gv: FK → GiangVien (NULL nếu chưa phân công)
    - tuan_bd: TINYINT (tuần bắt đầu 1-15)
    - tuan_kt: TINYINT (tuần kết thúc 1-15)
    - UNIQUE(ma_dot, ma_lop)
   
14. NguyenVong (tb_NGUYEN_VONG → model: NguyenVong) - GV đăng ký slot muốn dạy
    - id: INT PK AUTO
    - ma_gv: FK → GiangVien
    - ma_dot: FK → DotXep
    - time_slot_id: FK → TimeSlot
    - UNIQUE(ma_gv, ma_dot, time_slot_id)

15. RangBuocTrongDot (tb_RANG_BUOC_TRONG_DOT → model: RangBuocTrongDot)
    - id: INT PK AUTO
    - ma_dot: FK → DotXep
    - ma_rang_buoc: FK → RangBuocMem
    - trong_so: FLOAT (trọng số riêng cho đợt này)
    - UNIQUE(ma_dot, ma_rang_buoc)

16. NgayNghiDot (tb_NGAY_NGHI_DOT → model: NgayNghiDot) - Ngày nghỉ trong đợt
    - id: INT PK AUTO
    - ma_dot: FK → DotXep
    - ngay_bd: DATE (ngày bắt đầu nghỉ)
    - so_ngay_nghi: INT
    - tuan_bd: INT (tuần bắt đầu)
    - tuan_kt: INT (tuần kết thúc)
    - ten_ngay_nghi: NVARCHAR(100)
    - ghi_chu: NVARCHAR(200)
   
17. ThoiKhoaBieu (tb_TKB → model: ThoiKhoaBieu) - Kết quả xếp lịch
    - ma_tkb: VARCHAR(15) PK
    - ma_dot: FK → DotXep
    - ma_lop: FK → LopMonHoc
    - ma_phong: FK → PhongHoc (NULL nếu chưa xếp phòng)
    - time_slot_id: FK → TimeSlot
    - tuan_hoc: VARCHAR(64) (pattern tuần: "1111111000000000")
    - ngay_bd: DATE
    - ngay_kt: DATE
    - ngay_tao: DATETIME2
    - UNIQUE(ma_dot, ma_lop, ma_phong, time_slot_id)

=== RELATIONSHIPS (QUAN HỆ) ===
- GiangVien.ma_bo_mon → BoMon → Khoa (GV thuộc BM, BM thuộc Khoa)
- GVDayMon: GiangVien ↔ MonHoc (N-N: GV dạy được môn nào)
- LopMonHoc.ma_mon_hoc → MonHoc (Lớp của môn nào)
- PhanCong: GiangVien ↔ LopMonHoc trong DotXep (GV dạy lớp nào trong đợt)
- NguyenVong: GiangVien ↔ TimeSlot trong DotXep (GV muốn dạy slot nào)
- ThoiKhoaBieu: LopMonHoc ↔ PhongHoc ↔ TimeSlot trong DotXep

=== DJANGO ORM FIELD MAPPING ===
- Truy vấn khoa của GV: giangvien.ma_bo_mon.ma_khoa.ten_khoa
- Truy vấn môn GV dạy: GVDayMon.filter(ma_gv=...).select_related('ma_mon_hoc')
- Truy vấn GV trong khoa: GiangVien.filter(ma_bo_mon__ma_khoa__ten_khoa__icontains=...)
- Truy vấn lịch GV: ThoiKhoaBieu + PhanCong join trên ma_lop
- Truy vấn phòng trống: PhongHoc.exclude(ma_phong__in=ThoiKhoaBieu.filter(time_slot_id=...).values('ma_phong'))

=== GHI CHÚ QUAN TRỌNG ===
- Khoa CNTT = "Công nghệ thông tin" (tìm với icontains)
- Trạng thái đợt: DRAFT → RUNNING → LOCKED → PUBLISHED
- TuanHoc pattern: "1" = có học, "0" = nghỉ (VD: "111111100000000" = học 7 tuần đầu)
- TimeSlot format: "Thu2-Ca1" = Thứ 2, Ca 1
"""

    # ====================================================================
    # MULTIPLE API KEYS MANAGEMENT
    # ====================================================================
    
    def _check_global_rate_limit(self) -> Tuple[bool, float, int]:
        """
        Kiểm tra giới hạn tổng số requests/minute (5 requests/phút).
        
        Returns:
            Tuple[can_proceed, wait_time, current_count]
            - can_proceed: True nếu còn quota
            - wait_time: Thời gian cần chờ nếu hết quota (seconds)
            - current_count: Số requests trong window hiện tại
        """
        current_time = time.time()
        window_start = current_time - self._request_window_seconds
        
        # Clean up old timestamps outside window
        self._request_timestamps = [
            ts for ts in self._request_timestamps 
            if ts > window_start
        ]
        
        current_count = len(self._request_timestamps)
        
        # Check if exceeded limit
        if current_count >= self._request_limit_per_minute:
            # Calculate wait time until oldest request expires
            if self._request_timestamps:
                oldest_timestamp = self._request_timestamps[0]
                wait_time = (oldest_timestamp + self._request_window_seconds) - current_time
                wait_time = max(0, wait_time)
            else:
                wait_time = 0
            
            logger.warning(f"⚠️ Global rate limit: {current_count}/{self._request_limit_per_minute} requests in last 60s")
            return False, wait_time, current_count
        
        return True, 0, current_count
    
    def _record_request(self):
        """Ghi nhận một request mới vào tracking."""
        self._request_timestamps.append(time.time())
    
    def _get_next_available_key(self) -> Optional[int]:
        """
        Tìm API key tiếp theo có thể sử dụng (không trong cooldown và không invalid).
        
        Returns:
            Index của key khả dụng, hoặc None nếu tất cả đang cooldown/invalid
        """
        current_time = time.time()
        
        # Nếu chỉ có 1 key, return luôn (trừ khi invalid)
        if len(self.api_keys) == 1:
            return 0 if 0 not in self.key_invalid else None
        
        # Tìm key không trong cooldown và không invalid
        for i in range(len(self.api_keys)):
            next_idx = (self.current_key_index + i) % len(self.api_keys)
            
            # Skip invalid keys
            if next_idx in self.key_invalid:
                logger.debug(f"Key {next_idx} is marked invalid, skipping")
                continue
            
            # Check cooldown
            if next_idx in self.key_cooldowns:
                cooldown_until = self.key_cooldowns[next_idx]
                if current_time < cooldown_until:
                    wait_time = cooldown_until - current_time
                    logger.debug(f"Key {next_idx} in cooldown for {wait_time:.1f}s more")
                    continue
                else:
                    # Cooldown ended, remove it
                    del self.key_cooldowns[next_idx]
            
            # Key available
            return next_idx
        
        # All keys in cooldown or invalid
        return None
    
    def _rotate_to_next_key(self) -> bool:
        """
        Chuyển sang API key tiếp theo.
        
        Returns:
            True nếu rotate thành công, False nếu không còn key khả dụng
        """
        next_idx = self._get_next_available_key()
        
        if next_idx is None:
            logger.warning("⚠️ All API keys are in cooldown")
            return False
        
        if next_idx != self.current_key_index:
            logger.info(f"🔄 Rotating from key {self.current_key_index} → key {next_idx}")
            self.current_key_index = next_idx
            # Recreate client with new key
            self.client = genai.Client(api_key=self.api_keys[self.current_key_index])
        
        return True
    
    def _mark_key_cooldown(self, key_index: int, duration: float = None):
        """Đánh dấu một key vào trạng thái cooldown."""
        if duration is None:
            duration = self._key_cooldown_duration
        
        cooldown_until = time.time() + duration
        self.key_cooldowns[key_index] = cooldown_until
        logger.info(f"❄️ Key {key_index} in cooldown for {duration:.1f}s")
    
    def _track_key_usage(self, key_index: int, success: bool):
        """Track usage statistics cho một key."""
        if key_index not in self.key_stats:
            self.key_stats[key_index] = {'uses': 0, 'failures': 0, 'last_used': None}
        
        stats = self.key_stats[key_index]
        stats['uses'] += 1
        stats['last_used'] = time.time()
        
        if not success:
            stats['failures'] += 1
    
    def get_key_usage_stats(self) -> Dict[int, Dict[str, Any]]:
        """Lấy thống kê sử dụng của tất cả API keys."""
        stats = self.key_stats.copy()
        
        # Add invalid status to stats
        for key_idx in range(len(self.api_keys)):
            if key_idx not in stats:
                stats[key_idx] = {'uses': 0, 'failures': 0, 'last_used': None}
            stats[key_idx]['invalid'] = key_idx in self.key_invalid
            stats[key_idx]['in_cooldown'] = key_idx in self.key_cooldowns
        
        return stats
    
    def get_keys_health(self) -> Dict[str, Any]:
        """Lấy trạng thái health của tất cả keys."""
        total_keys = len(self.api_keys)
        invalid_count = len(self.key_invalid)
        cooldown_count = len(self.key_cooldowns)
        available_count = total_keys - invalid_count
        
        return {
            'total_keys': total_keys,
            'available': available_count,
            'invalid': invalid_count,
            'in_cooldown': cooldown_count,
            'current_key': self.current_key_index,
            'health_percentage': (available_count / total_keys * 100) if total_keys > 0 else 0
        }

    # ====================================================================
    # INTERACTIONS API HELPER METHODS (Beta)
    # ====================================================================
    
    def _check_rate_limit_status(self) -> Tuple[bool, float]:
        """
        Kiểm tra trạng thái rate limit và tính delay cần thiết.
        
        Returns:
            Tuple[can_proceed, wait_time]
            - can_proceed: True nếu có thể gọi API
            - wait_time: Thời gian cần chờ (seconds)
        """
        current_time = time.time()
        
        # Nếu đang trong thời gian chờ reset
        if self._rate_limit_reset_time and current_time < self._rate_limit_reset_time:
            wait_time = self._rate_limit_reset_time - current_time
            logger.info(f"Rate limit active, need to wait {wait_time:.1f}s")
            return False, wait_time
        
        # Tính delay dựa trên số lần rate limit liên tiếp (exponential backoff)
        if self._consecutive_rate_limits > 0:
            # Exponential backoff: 2^n * base_delay
            backoff_delay = min(
                (2 ** self._consecutive_rate_limits) * self._min_delay_between_calls,
                self._max_delay_between_calls
            )
            self._current_delay = backoff_delay
        else:
            self._current_delay = self._min_delay_between_calls
        
        # Kiểm tra delay từ lần gọi trước
        if self._last_api_call:
            elapsed = current_time - self._last_api_call
            if elapsed < self._current_delay:
                wait_time = self._current_delay - elapsed
                return False, wait_time
        
        return True, 0
    
    def _apply_rate_limit_delay(self):
        """Áp dụng delay trước khi gọi API (nếu cần)."""
        can_proceed, wait_time = self._check_rate_limit_status()
        if not can_proceed and wait_time > 0:
            logger.info(f"Applying rate limit delay: {wait_time:.1f}s")
            time.sleep(wait_time)
    
    def _handle_rate_limit_error(self, error: Exception) -> bool:
        """
        Xử lý lỗi rate limit và API key invalid từ API với key rotation.
        
        Args:
            error: Exception từ API
            
        Returns:
            True nếu nên retry (đã rotate key), False nếu nên dùng fallback
        """
        error_str = str(error)
        
        # Kiểm tra lỗi config (response_mime_type không support) - KHÔNG đánh dấu invalid
        is_config_error = "no such field" in error_str or "invalid JSON" in error_str
        
        if is_config_error:
            logger.warning(f"⚠️ Config error (not key issue): {error_str[:150]}")
            # Đây là lỗi code, không phải lỗi key - không retry
            return False
        
        # Kiểm tra API key invalid (400 error với API_KEY_INVALID)
        is_invalid_key = "API_KEY_INVALID" in error_str or "API key not valid" in error_str
        
        if is_invalid_key:
            logger.error(f"❌ Key {self.current_key_index} is INVALID: {error_str[:200]}")
            
            # Mark current key as invalid permanently
            self.key_invalid.add(self.current_key_index)
            self._track_key_usage(self.current_key_index, success=False)
            
            # Try rotate to another key
            if len(self.api_keys) > 1:
                if self._rotate_to_next_key():
                    logger.info(f"✅ Rotated to key {self.current_key_index} after invalid key")
                    return True  # Retry with new key
                else:
                    logger.error("❌ All API keys are invalid or unavailable")
                    return False  # Use fallback
            else:
                # Only one key and it's invalid
                logger.error("❌ Single API key is invalid, cannot proceed")
                return False
        
        # Kiểm tra các loại rate limit errors
        is_rate_limit = any(code in error_str for code in ['429', 'RESOURCE_EXHAUSTED', 'quota', 'rate_limit'])
        
        if is_rate_limit:
            # Track failure cho current key
            self._track_key_usage(self.current_key_index, success=False)
            
            # Mark current key as cooldown
            self._mark_key_cooldown(self.current_key_index)
            
            # Try rotate to next key
            if len(self.api_keys) > 1:
                if self._rotate_to_next_key():
                    logger.info(f"✅ Rotated to key {self.current_key_index}, will retry")
                    self._consecutive_rate_limits = 0  # Reset counter after rotation
                    return True  # Retry with new key (limited by MAX_RETRIES)
                else:
                    logger.warning("⚠️ All keys exhausted, will use fallback")
                    self._consecutive_rate_limits += 1
                    return False  # Use fallback
            else:
                # Single key - exponential backoff
                self._consecutive_rate_limits += 1
                
                if self._consecutive_rate_limits >= 3:
                    # Sau 3 lần liên tiếp, chờ lâu hơn (có thể quota hết)
                    self._rate_limit_reset_time = time.time() + 60.0  # Chờ 1 phút
                    logger.warning(f"Multiple rate limits ({self._consecutive_rate_limits}x), setting 60s cooldown")
                    return False  # Dùng fallback ngay
                else:
                    # Exponential backoff
                    backoff = min((2 ** self._consecutive_rate_limits) * self._min_delay_between_calls, 30)
                    self._rate_limit_reset_time = time.time() + backoff
                    logger.warning(f"Rate limited ({self._consecutive_rate_limits}x), backoff {backoff:.1f}s")
                    return self._consecutive_rate_limits < 2  # Retry nếu < 2 lần
        
        return False  # Không phải rate limit error
    
    def _reset_rate_limit_tracking(self):
        """Reset tracking khi API call thành công."""
        self._consecutive_rate_limits = 0
        self._current_delay = self._min_delay_between_calls
        self._rate_limit_reset_time = None
    
    def _call_interactions_api(
        self, 
        prompt: str, 
        model: str = None,
        thinking_level: str = THINKING_LEVEL_LOW,
        use_stateful: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 8096,
        response_mime_type: str = "text/plain",  # Ignored in Interactions API, for fallback only
        _retry_count: int = 0  # Internal: track retry attempts
    ) -> Tuple[Optional[str], Optional[str], Optional[Exception]]:
        """
        Gọi Interactions API với rate limiting và error handling.
        
        Theo tài liệu mới:
        - Sử dụng client.interactions.create() thay vì models.generate_content()
        - Hỗ trợ stateful mode với previous_interaction_id
        - Sử dụng thinking_level thay vì thinking_config
        - Global rate limit: 5 requests/minute
        - Max retry: 1 lần (tránh burn hết tất cả keys)
        - NOTE: response_mime_type NOT supported in Interactions API Beta
        
        Args:
            prompt: Nội dung câu hỏi/prompt
            model: Model để sử dụng (default: PRIMARY_MODEL)
            thinking_level: Mức độ suy luận ("minimal", "low", "medium", "high")
            use_stateful: Sử dụng stateful mode với previous_interaction_id
            temperature: Nhiệt độ sampling
            max_tokens: Số token tối đa output
            response_mime_type: IGNORED - Chỉ dùng cho fallback generate_content
            _retry_count: INTERNAL - số lần đã retry
            
        Returns:
            Tuple[response_text, interaction_id, error]
        """
        MAX_RETRIES = 1  # Chỉ retry 1 lần để tránh burn hết keys
        
        if model is None:
            model = self.model
        
        # === CHECK GLOBAL RATE LIMIT (5 requests/minute) ===
        can_proceed, wait_time, current_count = self._check_global_rate_limit()
        if not can_proceed:
            logger.warning(f"🚫 Rate limit exceeded: {current_count}/5 requests/minute. Wait {wait_time:.1f}s")
            error_msg = f"Rate limit: {current_count}/5 requests/minute. Please wait {wait_time:.0f} seconds."
            return None, None, Exception(error_msg)
        
        # Apply per-key rate limiting
        self._apply_rate_limit_delay()
        
        # Record this request
        self._record_request()
        
        try:
            # Thử sử dụng Interactions API mới
            try:
                interaction_params = {
                    "model": model,
                    "input": prompt,
                    "store": self._store_interactions,  # Không lưu trên server để tiết kiệm quota
                }
                
                # Thêm generation_config với thinking_level
                generation_config = {
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                    # NOTE: response_mime_type NOT supported in Interactions API
                }
                
                # Chỉ thêm thinking_level cho Flash models
                if "flash" in model.lower() and thinking_level:
                    generation_config["thinking_level"] = thinking_level
                
                interaction_params["generation_config"] = generation_config
                
                # Sử dụng previous_interaction_id nếu stateful mode
                if use_stateful and self._use_stateful_mode and self._last_interaction_id:
                    interaction_params["previous_interaction_id"] = self._last_interaction_id
                
                # Gọi Interactions API
                interaction = self.client.interactions.create(**interaction_params)
                
                self._last_api_call = time.time()
                self._reset_rate_limit_tracking()
                
                # Track successful usage
                self._track_key_usage(self.current_key_index, success=True)
                
                # Extract response text
                response_text = ""
                if interaction.outputs:
                    # Lấy output cuối cùng (text output)
                    for output in interaction.outputs:
                        if hasattr(output, 'text') and output.text:
                            response_text = output.text
                            break
                        elif hasattr(output, 'type') and output.type == "text":
                            response_text = getattr(output, 'text', '')
                            break
                
                # Lưu interaction_id cho stateful mode
                new_interaction_id = interaction.id if hasattr(interaction, 'id') else None
                if use_stateful and new_interaction_id:
                    self._last_interaction_id = new_interaction_id
                
                logger.info(f"✅ API success [key {self.current_key_index}], model={model}")
                return response_text, new_interaction_id, None
                
            except AttributeError as attr_err:
                # Interactions API chưa available trong SDK version này
                # Fallback về generate_content API cũ
                logger.info(f"Interactions API not available: {attr_err}. Using generate_content fallback.")
                return self._call_generate_content_fallback(
                    prompt, model, thinking_level, temperature, max_tokens, response_mime_type
                )
                
        except Exception as e:
            error_str = str(e)
            logger.warning(f"API call failed: {error_str}")
            
            # Check if exceeded max retries
            if _retry_count >= MAX_RETRIES:
                logger.warning(f"⚠️ Max retries ({MAX_RETRIES}) reached, using fallback")
                return None, None, e
            
            # Handle rate limit
            should_retry = self._handle_rate_limit_error(e)
            if should_retry:
                # Retry với delay
                logger.info(f"Retrying after rate limit (attempt {_retry_count + 1}/{MAX_RETRIES})...")
                time.sleep(self._current_delay)
                return self._call_interactions_api(
                    prompt, model, thinking_level, use_stateful, temperature, max_tokens, 
                    response_mime_type, _retry_count + 1
                )
            
            return None, None, e
    
    def _call_generate_content_fallback(
        self,
        prompt: str,
        model: str,
        thinking_level: str,
        temperature: float,
        max_tokens: int,
        response_mime_type: str = "text/plain"
    ) -> Tuple[Optional[str], Optional[str], Optional[Exception]]:
        """
        Fallback sử dụng generate_content API cũ nếu Interactions API không available.
        API này hỗ trợ response_mime_type.
        """
        try:
            # Build config
            config_params = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "response_mime_type": response_mime_type,  # Supported in generate_content
            }
            
            # Thêm thinking_config cho models hỗ trợ
            if "flash" in model.lower() or "2.5" in model:
                thinking_budget = 0 if thinking_level == THINKING_LEVEL_MINIMAL else 1024
                config_params["thinking_config"] = types.ThinkingConfig(
                    thinking_budget=thinking_budget
                )
            
            response = self.client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(**config_params)
            )
            
            self._last_api_call = time.time()
            self._reset_rate_limit_tracking()
            
            # Extract response text
            response_text = ""
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_text += part.text
            
            if not response_text and hasattr(response, 'text'):
                response_text = response.text
            
            logger.info(f"generate_content fallback success, model={model}")
            return response_text, None, None
            
        except Exception as e:
            logger.warning(f"generate_content fallback failed: {e}")
            return None, None, e

    def reset_conversation(self):
        """Reset conversation state (clear history và interaction_id)."""
        self.conversation_history = []
        self._last_interaction_id = None
        logger.info("Conversation reset")
    
    # Alias for backward compatibility
    clear_history = reset_conversation
    
    def _generate_query_with_ai(self, message: str, ma_dot: str = None, feedback: str = None) -> Dict[str, Any]:
        """
        AI sinh câu truy vấn dựa trên câu hỏi tự nhiên
        
        Flow: Câu hỏi → AI sinh query spec → Hệ thống parse & thực thi
        
        Args:
            message: Câu hỏi từ người dùng
            ma_dot: Mã đợt xếp hiện tại
            feedback: Feedback từ lần query trước (nếu có) để AI tự sửa
        
        Returns:
            Dict với query_spec để hệ thống thực thi
        """
        # Thêm feedback section nếu có (để AI tự sửa query)
        feedback_section = ""
        if feedback:
            feedback_section = f"""
=== FEEDBACK TỪ LẦN TRƯỚC ===
{feedback}

HÃY PHÂN TÍCH FEEDBACK VÀ SỬA LẠI QUERY SPECIFICATION CHO ĐÚNG!
"""
        
        # Dùng replace để tránh KeyError do dấu ngoặc nhọn trong JSON template
        query_prompt = f"{self.db_schema}\n\n" + QUERY_SPEC_INSTRUCTION
        query_prompt = query_prompt.replace("{question}", message)
        query_prompt = query_prompt.replace("{ma_dot}", ma_dot or "(không có - chỉ query master data)")
        query_prompt = query_prompt.replace("{feedback_section}", feedback_section)
        
        # Sinh query_spec dùng model nhẹ trước để tiết kiệm quota
        model_used = FALLBACK_MODEL
        response_text, _, error = self._call_generate_content_fallback(
            prompt=query_prompt,
            model=model_used,
            thinking_level=THINKING_LEVEL_MINIMAL,
            temperature=0.1,
            max_tokens=900,
            response_mime_type="application/json"
        )

        # Nếu model nhẹ cũng hết quota/lỗi, thử model chính
        if error or not response_text:
            error_str = str(error) if error else "empty response"
            if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str or not response_text:
                logger.warning(f"Fallback model unavailable ({error_str}), trying primary model")
                model_used = PRIMARY_MODEL
                response_text, _, error = self._call_generate_content_fallback(
                    prompt=query_prompt,
                    model=model_used,
                    thinking_level=THINKING_LEVEL_MINIMAL,
                    temperature=0.1,
                    max_tokens=900,
                    response_mime_type="application/json"
                )

        if error:
            error_str = str(error)
            # Kiểm tra nếu là lỗi rate limit
            if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
                logger.warning("Rate limited, falling back to keyword query")
                return {'success': False, 'error': 'Rate limited', 'use_fallback': True}
            logger.warning(f"AI query generation failed: {error}")
            return {'success': False, 'error': error_str}
        
        if not response_text:
            return {'success': False, 'error': 'Empty response from AI'}
        
        # Clean and parse JSON
        response_text = response_text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.startswith('```'):
            response_text = response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Find JSON object
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                query_spec = json.loads(json_match.group(0))
                logger.info(f"AI generated query spec: {query_spec.get('explanation', '')}")
                return {
                    'success': True,
                    'query_spec': query_spec,
                    'raw_response': response_text,
                    'model_used': model_used
                }
            except json.JSONDecodeError as je:
                # JSON không hoàn chỉnh - thử sửa
                logger.warning(f"JSON parse error: {je}. Trying to fix incomplete JSON...")
                # Thử thêm closing braces
                json_text = json_match.group(0)
                open_braces = json_text.count('{') - json_text.count('}')
                if open_braces > 0:
                    json_text += '}' * open_braces
                    try:
                        query_spec = json.loads(json_text)
                        logger.info(f"Fixed JSON successfully: {query_spec.get('explanation', '')}")
                        return {
                            'success': True,
                            'query_spec': query_spec,
                            'raw_response': response_text,
                            'model_used': PRIMARY_MODEL
                        }
                    except:
                        pass
                logger.warning(f"Cannot parse JSON from AI response: {response_text[:300]}")
                return {'success': False, 'error': f'Cannot parse JSON: {str(je)}'}
        else:
            logger.warning(f"Cannot parse JSON from AI response: {response_text[:200]}")
            return {'success': False, 'error': 'Cannot parse JSON'}
    
    def _execute_ai_generated_query(self, query_spec: Dict, ma_dot: str = None) -> Dict[str, Any]:
        """
        Thực thi query specification do AI sinh ra
        An toàn: Chỉ cho phép ORM queries, không raw SQL
        """
        result = {
            'success': False,
            'query_description': query_spec.get('explanation', ''),
            'data': [],
            'summary': ''
        }
        
        try:
            from ..models import (
                Khoa, BoMon, GiangVien, MonHoc, LopMonHoc,
                PhanCong, ThoiKhoaBieu, NguyenVong, GVDayMon, PhongHoc, DotXep, TimeSlot
            )
            
            # Map table names to models
            table_map = {
                'Khoa': Khoa, 'khoa': Khoa,
                'BoMon': BoMon, 'bo_mon': BoMon,
                'GiangVien': GiangVien, 'giang_vien': GiangVien,
                'MonHoc': MonHoc, 'mon_hoc': MonHoc,
                'LopMonHoc': LopMonHoc, 'lop_mon_hoc': LopMonHoc,
                'PhanCong': PhanCong, 'phan_cong': PhanCong,
                'ThoiKhoaBieu': ThoiKhoaBieu, 'tkb': ThoiKhoaBieu,
                'NguyenVong': NguyenVong, 'nguyen_vong': NguyenVong,
                'GVDayMon': GVDayMon, 'gv_day_mon': GVDayMon,
                'PhongHoc': PhongHoc, 'phong_hoc': PhongHoc,
                'DotXep': DotXep, 'dot_xep': DotXep,
                'TimeSlot': TimeSlot, 'time_slot': TimeSlot,
            }
            
            # Get primary table
            tables = query_spec.get('tables', [])
            if not tables:
                return result
            
            primary_table = tables[0]
            model = table_map.get(primary_table)
            if not model:
                logger.warning(f"Unknown table: {primary_table}")
                return result
            
            # Build queryset
            queryset = model.objects.all()
            
            # Apply joins (select_related/prefetch_related) with allowlist
            joins = query_spec.get('joins', [])
            allowed_joins = {
                'GiangVien': {'ma_bo_mon', 'ma_bo_mon__ma_khoa'},
                'BoMon': {'ma_khoa'},
                'LopMonHoc': {'ma_mon_hoc', 'phan_cong_list', 'tkb_list'},
                'PhanCong': {'ma_lop', 'ma_lop__ma_mon_hoc', 'ma_gv'},
                'ThoiKhoaBieu': {'ma_lop', 'ma_lop__ma_mon_hoc', 'ma_lop__phan_cong_list', 'ma_phong', 'time_slot_id', 'time_slot_id__ca'},
                'NguyenVong': {'ma_gv', 'time_slot_id'},
                'GVDayMon': {'ma_gv', 'ma_mon_hoc'},
                'DotXep': {'ma_du_kien_dt'},
                'PhongHoc': set(),
                'MonHoc': set(),
                'Khoa': set(),
                'TimeSlot': {'ca'},
            }
            join_aliases = {
                'phancong': 'phan_cong_list',
                'phan_cong': 'phan_cong_list',
                'ma_lop__phancong': 'ma_lop__phan_cong_list',
                'ma_lop__phan_cong': 'ma_lop__phan_cong_list',
            }

            if joins:
                allowed_for_model = allowed_joins.get(model.__name__, set())
                for j in joins:
                    normalized_join = join_aliases.get(j, j)

                    # Skip if not in allowlist
                    if allowed_for_model and normalized_join not in allowed_for_model:
                        logger.warning(f"Join '{normalized_join}' not allowed for {model.__name__}, skipping")
                        continue

                    # Reverse relations should use prefetch_related
                    if normalized_join.endswith('_list'):
                        try:
                            queryset = queryset.prefetch_related(normalized_join)
                        except Exception as e:
                            logger.warning(f"Join '{normalized_join}' skipped (unsupported path): {e}")
                        continue

                    # Try select_related, fallback prefetch; if both fail, skip
                    try:
                        queryset = queryset.select_related(normalized_join)
                        continue
                    except Exception as e:
                        logger.debug(f"select_related failed for '{normalized_join}': {e}")
                    try:
                        queryset = queryset.prefetch_related(normalized_join)
                    except Exception as e:
                        logger.warning(f"Join '{normalized_join}' skipped (unsupported path): {e}")
            
            # Apply filters - WHITELIST approach
            filters = query_spec.get('filters', {})
            allowed_lookups = ['exact', 'iexact', 'contains', 'icontains', 'gt', 'gte', 'lt', 'lte', 'in', 'startswith', 'endswith']

            # Allowlist fields per model
            allowed_filter_fields = {
                'GiangVien': {'ma_gv', 'ten_gv', 'loai_gv', 'ma_bo_mon__ma_khoa__ten_khoa', 'ma_bo_mon__ten_bo_mon'},
                'BoMon': {'ma_bo_mon', 'ten_bo_mon', 'ma_khoa__ten_khoa'},
                'MonHoc': {'ma_mon_hoc', 'ten_mon_hoc', 'so_tin_chi', 'so_tiet_lt', 'so_tiet_th'},
                'LopMonHoc': {'ma_lop', 'ma_mon_hoc__ten_mon_hoc', 'ma_mon_hoc__ma_mon_hoc'},
                'PhanCong': {'ma_gv__ten_gv', 'ma_lop__ma_mon_hoc__ten_mon_hoc', 'ma_dot__ma_dot'},
                'ThoiKhoaBieu': {
                    'ma_lop__ma_mon_hoc__ten_mon_hoc',
                    'ma_phong__ma_phong',
                    'time_slot_id__thu',
                    'time_slot_id__ca__ma_khung_gio',
                    'ma_dot__ma_dot',
                    'ma_lop__phan_cong_list__ma_gv__ten_gv',
                },
                'NguyenVong': {'ma_gv__ten_gv', 'ma_dot__ma_dot', 'time_slot_id__thu', 'time_slot_id__ca__ma_khung_gio'},
                'GVDayMon': {'ma_gv__ten_gv', 'ma_mon_hoc__ten_mon_hoc'},
                'PhongHoc': {'ma_phong', 'loai_phong', 'suc_chua'},
                'DotXep': {'ma_dot', 'ten_dot', 'trang_thai'},
                'TimeSlot': {'thu', 'ca__ma_khung_gio'},
            }

            safe_filters = {}
            allowed_fields = allowed_filter_fields.get(model.__name__, set())
            for key, value in filters.items():
                # Parse lookup type
                parts = key.split('__')
                lookup = parts[-1] if len(parts) > 1 and parts[-1] in allowed_lookups else None

                # Validate: only allow field traversal, no code injection
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*(__[a-zA-Z_][a-zA-Z0-9_]*)*$', key):
                    logger.warning(f"Invalid filter key rejected: {key}")
                    continue

                # Enforce allowlist
                base_field = key if lookup is None else '__'.join(parts[:-1])
                if allowed_fields and base_field not in allowed_fields:
                    logger.warning(f"Filter '{key}' not allowed for {model.__name__}, skipping")
                    continue

                # Sanitize value
                if isinstance(value, str):
                    value = value.replace(';', '').replace('--', '')

                # Try applying individually to catch unsupported traversal early
                try:
                    queryset.filter(**{key: value})
                    safe_filters[key] = value
                except Exception as e:
                    logger.warning(f"Skipping unsupported filter '{key}': {e}")
                    continue

            if safe_filters:
                try:
                    queryset = queryset.filter(**safe_filters)
                except Exception as e:
                    logger.warning(f"Filter application failed, using partial filters: {e}")
                    # Try one-by-one to salvage workable filters
                    qs_temp = queryset
                    for k, v in safe_filters.items():
                        try:
                            qs_temp = qs_temp.filter(**{k: v})
                        except Exception:
                            logger.warning(f"Filter '{k}' still invalid after salvage, skipping")
                            continue
                    queryset = qs_temp
            
            # Apply dot_xep filter if needed
            if query_spec.get('needs_dot_xep') and ma_dot:
                if hasattr(model, 'ma_dot'):
                    queryset = queryset.filter(ma_dot=ma_dot)
            
            # Order by
            order_by = query_spec.get('order_by', [])
            if order_by:
                valid_orders = [o for o in order_by if re.match(r'^-?[a-zA-Z_][a-zA-Z0-9_]*(__[a-zA-Z_][a-zA-Z0-9_]*)*$', o)]
                if valid_orders:
                    queryset = queryset.order_by(*valid_orders)
            
            # Limit
            limit = min(query_spec.get('limit', 100), 300)  # Max 300 records
            
            # Execute query based on type
            query_type = query_spec.get('query_type', 'SELECT')
            
            if query_type == 'COUNT':
                count = queryset.count()
                result['data'] = [{'count': count}]
                result['summary'] = f"Kết quả: {count}"
                result['success'] = True
                
            elif query_type == 'AGGREGATE':
                aggregations = query_spec.get('aggregations', {})
                agg_result = {}
                if aggregations.get('count'):
                    agg_result['count'] = queryset.count()
                if aggregations.get('sum_field'):
                    agg_result['sum'] = queryset.aggregate(Sum(aggregations['sum_field']))
                if aggregations.get('avg_field'):
                    agg_result['avg'] = queryset.aggregate(Avg(aggregations['avg_field']))
                result['data'] = [agg_result]
                result['summary'] = f"Kết quả thống kê: {agg_result}"
                result['success'] = True
                
            else:  # SELECT
                # Get select fields
                select_fields = query_spec.get('select_fields', [])
                
                data = []
                for obj in queryset[:limit]:
                    item = {}
                    
                    # If specific fields requested
                    if select_fields:
                        for field in select_fields:
                            try:
                                # Handle nested fields like ma_mon_hoc__ten_mon_hoc
                                parts = field.split('__')
                                value = obj
                                for part in parts:
                                    value = getattr(value, part, None)
                                    if value is None:
                                        break
                                item[field] = str(value) if value else None
                            except Exception:
                                item[field] = None
                    else:
                        # Default: get all fields based on model type
                        item = self._model_to_dict(obj)
                    
                    data.append(item)
                
                result['data'] = data
                result['summary'] = f"Tìm thấy {len(data)} kết quả"
                result['success'] = True
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing AI query: {e}")
            result['summary'] = f"Lỗi thực thi: {str(e)}"
            return result
    
    def _model_to_dict(self, obj) -> Dict:
        """Convert model object to dict với các field thường dùng"""
        data = {}
        model_name = obj.__class__.__name__
        
        if model_name == 'GiangVien':
            data = {
                'ma_gv': obj.ma_gv,
                'ten_gv': obj.ten_gv,
                'loai_gv': getattr(obj, 'loai_gv', ''),
                'khoa': obj.ma_bo_mon.ma_khoa.ten_khoa if obj.ma_bo_mon and obj.ma_bo_mon.ma_khoa else 'N/A',
                'bo_mon': obj.ma_bo_mon.ten_bo_mon if obj.ma_bo_mon else 'N/A'
            }
        elif model_name == 'MonHoc':
            data = {
                'ma_mon': obj.ma_mon_hoc,
                'ten_mon': obj.ten_mon_hoc,
                'so_tin_chi': obj.so_tin_chi or 0,
                'so_tiet_lt': obj.so_tiet_lt or 0,
                'so_tiet_th': obj.so_tiet_th or 0
            }
        elif model_name == 'Khoa':
            data = {
                'ma_khoa': obj.ma_khoa,
                'ten_khoa': obj.ten_khoa
            }
        elif model_name == 'BoMon':
            data = {
                'ma_bo_mon': obj.ma_bo_mon,
                'ten_bo_mon': obj.ten_bo_mon,
                'khoa': obj.ma_khoa.ten_khoa if obj.ma_khoa else 'N/A'
            }
        elif model_name == 'PhongHoc':
            data = {
                'ma_phong': obj.ma_phong,
                'loai_phong': obj.loai_phong or 'N/A',
                'suc_chua': obj.suc_chua or 0,
                'thiet_bi': obj.thiet_bi or ''
            }
        elif model_name == 'GVDayMon':
            data = {
                'giang_vien': obj.ma_gv.ten_gv if obj.ma_gv else 'N/A',
                'mon_hoc': obj.ma_mon_hoc.ten_mon_hoc if obj.ma_mon_hoc else 'N/A'
            }
        elif model_name == 'LopMonHoc':
            data = {
                'ma_lop': obj.ma_lop,
                'mon_hoc': obj.ma_mon_hoc.ten_mon_hoc if obj.ma_mon_hoc else 'N/A',
                'so_sv': obj.so_luong_sv or 0,
                'he': obj.he_dao_tao or ''
            }
        elif model_name == 'DotXep':
            data = {
                'ma_dot': obj.ma_dot,
                'ten_dot': obj.ten_dot,
                'trang_thai': obj.trang_thai
            }
        else:
            # Generic: get all simple fields
            for field in obj._meta.fields:
                try:
                    value = getattr(obj, field.name)
                    if value is not None and not callable(value):
                        data[field.name] = str(value) if not isinstance(value, (int, float, bool)) else value
                except Exception:
                    pass
        
        return data
    
    def _get_active_dot_xep(self, show_notice: bool = True) -> Tuple[Optional[str], str]:
        """
        Tự động lấy mã đợt xếp phù hợp nhất - ưu tiên đợt CÓ DỮ LIỆU TKB
        
        Thứ tự ưu tiên:
        1. Đợt đang hoạt động (RUNNING/PUBLISHED) có TKB
        2. Đợt mới nhất có TKB
        3. Nếu không có đợt nào có TKB → thông báo
        
        Args:
            show_notice: Luôn hiện thông báo đợt đang dùng (mặc định True)
        
        Returns:
            Tuple[ma_dot, thong_bao]: (mã đợt, thông báo cho người dùng)
        """
        try:
            from django.utils import timezone
            from ..models import ThoiKhoaBieu, DotXep
            
            # Cache 5 phút - nhưng vẫn trả về thông báo nếu show_notice=True
            if self._cached_dot_xep and self._cache_time:
                if (timezone.now() - self._cache_time).seconds < 300:
                    if show_notice:
                        # Lấy thông tin đợt để hiển thị
                        try:
                            dot = DotXep.objects.get(ma_dot=self._cached_dot_xep)
                            so_tkb = ThoiKhoaBieu.objects.filter(ma_dot=self._cached_dot_xep).count()
                            return self._cached_dot_xep, f"📅 Đang sử dụng: **{dot.ten_dot}** - {so_tkb} lịch"
                        except:
                            return self._cached_dot_xep, f"📅 Đang sử dụng đợt: {self._cached_dot_xep}"
                    return self._cached_dot_xep, ""
            
            # Lấy danh sách các đợt CÓ TKB (có lịch đã xếp)
            dots_co_tkb = ThoiKhoaBieu.objects.values('ma_dot').distinct()
            ma_dots_co_tkb = [d['ma_dot'] for d in dots_co_tkb]
            
            if not ma_dots_co_tkb:
                return None, "⚠️ Chưa có đợt xếp nào có thời khóa biểu. Vui lòng xếp lịch trước."
            
            # Ưu tiên 1: Đợt đang hoạt động có TKB
            dot_hoat_dong = DotXep.objects.filter(
                ma_dot__in=ma_dots_co_tkb,
                trang_thai__in=['RUNNING', 'PUBLISHED']
            ).order_by('-ngay_tao').first()
            
            if dot_hoat_dong:
                # Đếm số TKB
                so_tkb = ThoiKhoaBieu.objects.filter(ma_dot=dot_hoat_dong.ma_dot).count()
                self._cached_dot_xep = dot_hoat_dong.ma_dot
                self._cache_time = timezone.now()
                return dot_hoat_dong.ma_dot, f"📅 Tự động chọn đợt đang hoạt động: **{dot_hoat_dong.ten_dot}** - {so_tkb} lịch"
            
            # Ưu tiên 2: Đợt mới nhất có TKB
            dot_moi_nhat = DotXep.objects.filter(
                ma_dot__in=ma_dots_co_tkb
            ).order_by('-ngay_tao').first()
            
            if dot_moi_nhat:
                so_tkb = ThoiKhoaBieu.objects.filter(ma_dot=dot_moi_nhat.ma_dot).count()
                self._cached_dot_xep = dot_moi_nhat.ma_dot
                self._cache_time = timezone.now()
                
                # Liệt kê các đợt khác có TKB
                other_dots = DotXep.objects.filter(
                    ma_dot__in=ma_dots_co_tkb
                ).exclude(ma_dot=dot_moi_nhat.ma_dot).order_by('-ngay_tao')[:3]
                
                msg = f"📅 Tự động chọn đợt mới nhất có lịch: **{dot_moi_nhat.ten_dot}** - {so_tkb} lịch\n"
                if other_dots.exists():
                    other_list = ", ".join([f"{d.ten_dot}" for d in other_dots])
                    msg += f"💡 Đợt khác: {other_list}\n"
                    msg += "   → Muốn tra đợt khác? Hãy nói rõ tên đợt."
                return dot_moi_nhat.ma_dot, msg
            
            return None, "⚠️ Không tìm thấy đợt xếp có thời khóa biểu."
            
        except Exception as e:
            logger.warning(f"Không lấy được đợt xếp: {e}")
            return None, f"⚠️ Lỗi khi tìm đợt xếp: {str(e)}"
        

    
    def _get_available_rooms(self, thu: int, ca: int, loai_phong: str = None, 
                            so_sv_toi_thieu: int = 0, ma_dot: str = None) -> List[Dict]:
        """
        Lấy danh sách phòng trống theo thời gian
        
        Args:
            thu: Thứ trong tuần (2-7)
            ca: Ca học (1, 2, 3, ...)
            loai_phong: 'LT' hoặc 'TH' (optional)
            so_sv_toi_thieu: Sức chứa tối thiểu
            ma_dot: Mã đợt xếp để kiểm tra phòng đã dùng
        """
        try:
            # Tìm time slot
            timeslots = DataAccessLayer.get_all_time_slot()
            target_ts = None
            for ts in timeslots:
                if ts.thu == thu and ts.ca.ma_khung_gio == f"Ca{ca}":
                    target_ts = ts
                    break
            
            if not target_ts:
                return []
            
            # Lấy phòng trống trong time slot này
            available_rooms = DataAccessLayer.get_available_rooms_in_timeslot(
                target_ts.time_slot_id, ma_dot
            )
            
            # Filter theo loại phòng và sức chứa
            result = []
            for room in available_rooms:
                # Check loại phòng
                room_type = room.loai_phong or ''
                is_lt = 'thuyết' in room_type.lower() or 'lt' in room_type.lower()
                is_th = 'hành' in room_type.lower() or 'th' in room_type.lower()
                
                if loai_phong:
                    if loai_phong == 'LT' and not is_lt:
                        continue
                    if loai_phong == 'TH' and not is_th:
                        continue
                
                # Check sức chứa
                if room.suc_chua < so_sv_toi_thieu:
                    continue
                
                result.append({
                    'ma_phong': room.ma_phong,
                    'loai_phong': 'LT' if is_lt else ('TH' if is_th else 'Khác'),
                    'suc_chua': room.suc_chua,
                    'thiet_bi': room.thiet_bi or ''
                })
            
            # Sort by capacity
            result.sort(key=lambda x: x['suc_chua'])
            return result
            
        except Exception as e:
            logger.error(f"Lỗi get_available_rooms: {e}")
            return []
    
    def _get_teacher_info(self, search_term: str) -> Optional[Dict]:
        """
        Tìm thông tin giảng viên - TÁI SỬ DỤNG từ DAL
        """
        try:
            all_gv = DataAccessLayer.get_all_giang_vien()
            search_lower = search_term.lower()
            
            for gv in all_gv:
                if search_lower in gv.ma_gv.lower() or search_lower in gv.ten_gv.lower():
                    # Sử dụng helper từ DAL
                    return get_giang_vien_info_dict(gv.ma_gv)
            return None
        except Exception as e:
            logger.error(f"Lỗi get_teacher_info: {e}")
            return None
    
    def _get_thong_ke(self, ma_dot: str) -> Optional[Dict]:
        """
        Lấy thống kê đợt xếp - TÁI SỬ DỤNG từ DAL
        """
        try:
            return DataAccessLayer.get_thong_ke_dot_xep(ma_dot)
        except Exception as e:
            logger.error(f"Lỗi get_thong_ke: {e}")
            return None
    
    def _detect_conflicts(self, ma_dot: str) -> Optional[Dict]:
        """
        Phát hiện xung đột - TÁI SỬ DỤNG từ LLMDataProcessor
        """
        try:
            return LLMDataProcessor.detect_scheduling_conflicts(ma_dot)
        except Exception as e:
            logger.error(f"Lỗi detect_conflicts: {e}")
            return None

    def _suggest_schedule_change(self, ma_gv: str, current_slot: str = None, 
                                  ma_dot: str = None) -> Dict[str, Any]:
        """
        GỢI Ý đổi lịch cho giảng viên - CHỈ ĐỌC, KHÔNG TÁC ĐỘNG DATABASE
        
        Args:
            ma_gv: Mã hoặc tên giảng viên
            current_slot: Slot hiện tại muốn đổi (VD: "Thu2-Ca1"), None = tìm tất cả
            ma_dot: Mã đợt xếp
            
        Returns:
            Dict với danh sách gợi ý và lý do
        """
        from ..models import (
            GiangVien, ThoiKhoaBieu, NguyenVong, PhanCong, 
            PhongHoc, TimeSlot, LopMonHoc
        )
        
        result = {
            'success': False,
            'giang_vien': None,
            'lich_hien_tai': [],
            'goi_y': [],
            'message': ''
        }
        
        try:
            # 1. Tìm giảng viên
            gv = None
            search_lower = ma_gv.lower()
            for g in GiangVien.objects.select_related('ma_bo_mon'):
                if search_lower in g.ma_gv.lower() or search_lower in g.ten_gv.lower():
                    gv = g
                    break
            
            if not gv:
                result['message'] = f"Không tìm thấy giảng viên '{ma_gv}'"
                return result
            
            result['giang_vien'] = {
                'ma_gv': gv.ma_gv,
                'ten_gv': gv.ten_gv,
                'bo_mon': gv.ma_bo_mon.ten_bo_mon if gv.ma_bo_mon else 'N/A'
            }
            
            # 2. Lấy lịch hiện tại của GV trong đợt
            lich_query = ThoiKhoaBieu.objects.filter(
                ma_dot=ma_dot
            ).select_related(
                'ma_lop', 'ma_lop__ma_mon_hoc', 'ma_phong', 'time_slot_id'
            )
            
            # Lọc theo GV thông qua PhanCong
            phan_cong_lop = PhanCong.objects.filter(
                ma_dot=ma_dot, ma_gv=gv
            ).values_list('ma_lop__ma_lop', flat=True)
            
            lich_gv = lich_query.filter(ma_lop__ma_lop__in=phan_cong_lop)
            
            for tkb in lich_gv:
                ts = tkb.time_slot_id
                thu_str = f"Thứ {ts.thu}" if ts.thu != 8 else "CN"
                ca_str = f"Ca {ts.ca.ma_khung_gio}" if ts.ca else ""
                
                result['lich_hien_tai'].append({
                    'ma_tkb': tkb.ma_tkb,
                    'slot': ts.time_slot_id,
                    'thu': ts.thu,
                    'ca': ts.ca.ma_khung_gio if ts.ca else None,
                    'thu_ca_str': f"{thu_str} {ca_str}",
                    'lop': tkb.ma_lop.ma_lop,
                    'mon': tkb.ma_lop.ma_mon_hoc.ten_mon_hoc if tkb.ma_lop.ma_mon_hoc else 'N/A',
                    'phong': tkb.ma_phong.ma_phong if tkb.ma_phong else 'Chưa xếp'
                })
            
            if not result['lich_hien_tai']:
                result['message'] = f"GV {gv.ten_gv} chưa có lịch dạy trong đợt này"
                result['success'] = True
                return result
            
            # 3. Lấy nguyện vọng của GV
            nguyen_vong = NguyenVong.objects.filter(
                ma_gv=gv, ma_dot=ma_dot
            ).values_list('time_slot_id__time_slot_id', flat=True)
            nguyen_vong_set = set(nguyen_vong)
            
            # 4. Tìm tất cả slot trong hệ thống
            all_slots = TimeSlot.objects.select_related('ca').order_by('thu', 'ca__ma_khung_gio')
            
            # 5. Tìm các slot GV đang bận (để loại trừ)
            slot_ban = set(l['slot'] for l in result['lich_hien_tai'])
            
            # 6. Tìm slot trống (không có TKB nào của GV)
            for slot in all_slots:
                if slot.time_slot_id in slot_ban:
                    continue  # GV đã có lịch slot này
                
                thu_str = f"Thứ {slot.thu}" if slot.thu != 8 else "CN"
                ca_str = f"Ca {slot.ca.ma_khung_gio}" if slot.ca else ""
                
                # Kiểm tra phòng trống trong slot này
                phong_trong = DataAccessLayer.get_available_rooms_in_timeslot(
                    slot.time_slot_id, ma_dot
                )
                
                if not phong_trong.exists():
                    continue  # Không có phòng trống
                
                # Tính điểm gợi ý
                score = 0
                reasons = []
                
                # Ưu tiên slot trong nguyện vọng
                if slot.time_slot_id in nguyen_vong_set:
                    score += 50
                    reasons.append("✅ Đúng nguyện vọng GV")
                else:
                    reasons.append("⚠️ Không trong nguyện vọng")
                
                # Ưu tiên nhiều phòng trống (dễ chọn)
                so_phong = phong_trong.count()
                score += min(so_phong * 2, 20)
                reasons.append(f"🏫 {so_phong} phòng trống")
                
                # Ưu tiên slot liền kề với lịch hiện tại (tiện di chuyển)
                for lich in result['lich_hien_tai']:
                    if lich['thu'] == slot.thu:
                        if slot.ca and lich['ca']:
                            ca_diff = abs(int(slot.ca.ma_khung_gio) - int(lich['ca']))
                            if ca_diff == 1:
                                score += 10
                                reasons.append("📍 Liền kề lịch hiện tại")
                                break
                
                # Lấy danh sách phòng phù hợp
                phong_list = [
                    {'ma_phong': p.ma_phong, 'loai': p.loai_phong, 'suc_chua': p.suc_chua}
                    for p in phong_trong[:5]
                ]
                
                result['goi_y'].append({
                    'slot': slot.time_slot_id,
                    'thu_ca_str': f"{thu_str} {ca_str}",
                    'thu': slot.thu,
                    'ca': slot.ca.ma_khung_gio if slot.ca else None,
                    'score': score,
                    'reasons': reasons,
                    'phong_goi_y': phong_list,
                    'trong_nguyen_vong': slot.time_slot_id in nguyen_vong_set
                })
            
            # Sắp xếp theo điểm giảm dần
            result['goi_y'].sort(key=lambda x: x['score'], reverse=True)
            
            # Giới hạn top 10
            result['goi_y'] = result['goi_y'][:10]
            
            result['success'] = True
            result['message'] = f"Tìm thấy {len(result['goi_y'])} slot có thể đổi cho GV {gv.ten_gv}"
            
        except Exception as e:
            logger.error(f"Lỗi suggest_schedule_change: {e}")
            result['message'] = f"Lỗi: {str(e)}"
        
        return result

    def _is_followup_request(self, message: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Kiểm tra xem tin nhắn có phải là yêu cầu follow-up không.
        VD: "Thể hiện bằng bảng", "Chi tiết hơn", "Giải thích thêm"
        
        Returns:
            Tuple[is_followup, format_type, last_data]
            - is_followup: True nếu là yêu cầu follow-up
            - format_type: 'table', 'list', 'detail', 'explain', 'summary'
            - last_data: Dữ liệu từ response trước (nếu có)
        """
        msg_lower = message.lower().strip()
        
        # Các pattern yêu cầu format lại
        format_patterns = {
            'table': ['bảng', 'table', 'dạng bảng', 'theo bảng', 'thể hiện bằng bảng', 'hiển thị bảng'],
            'list': ['danh sách', 'list', 'liệt kê', 'liệt kê ra', 'kể ra'],
            'detail': ['chi tiết', 'detail', 'cụ thể', 'rõ hơn', 'chi tiết hơn', 'cụ thể hơn'],
            'explain': ['giải thích', 'explain', 'tại sao', 'vì sao', 'như thế nào'],
            'summary': ['tóm tắt', 'summary', 'ngắn gọn', 'tổng quan']
        }
        
        # Kiểm tra xem có phải yêu cầu format không
        detected_format = None
        for fmt, keywords in format_patterns.items():
            for kw in keywords:
                if kw in msg_lower:
                    detected_format = fmt
                    break
            if detected_format:
                break
        
        if not detected_format:
            return False, '', None
        
        # Kiểm tra độ ngắn của tin nhắn (yêu cầu follow-up thường ngắn)
        # VD: "Thể hiện bằng bảng" (4 từ), "Chi tiết hơn" (2 từ)
        word_count = len(msg_lower.split())
        if word_count > 8:  # Nếu câu dài, có thể là câu hỏi mới có chứa keyword
            return False, '', None
        
        # Lấy dữ liệu từ conversation history
        last_data = None
        if len(self.conversation_history) >= 2:
            # Tìm response cuối cùng của assistant
            for i in range(len(self.conversation_history) - 1, -1, -1):
                if self.conversation_history[i].get('role') == 'assistant':
                    last_data = {
                        'response': self.conversation_history[i].get('content', ''),
                        'timestamp': self.conversation_history[i].get('timestamp', '')
                    }
                    # Cũng lấy câu hỏi gốc
                    if i > 0 and self.conversation_history[i-1].get('role') == 'user':
                        last_data['original_question'] = self.conversation_history[i-1].get('content', '')
                    break
        
        if last_data:
            return True, detected_format, last_data
        
        return False, detected_format, None
    
    def _format_as_table(self, data: List[Dict], title: str = '') -> str:
        """
        Format dữ liệu thành bảng Markdown.
        """
        if not data:
            return "Không có dữ liệu để hiển thị bảng."
        
        lines = []
        if title:
            lines.append(f"**{title}**\n")
        
        # Lấy headers từ keys của item đầu tiên
        headers = list(data[0].keys())
        
        # Header row
        header_row = "| " + " | ".join(str(h).replace('_', ' ').title() for h in headers) + " |"
        separator = "|" + "|".join(["---"] * len(headers)) + "|"
        
        lines.append(header_row)
        lines.append(separator)
        
        # Data rows
        for item in data:
            row = "| " + " | ".join(str(item.get(h, 'N/A')) for h in headers) + " |"
            lines.append(row)
        
        return "\n".join(lines)
    
    def _get_conversation_context(self, limit: int = 4) -> str:
        """
        Lấy ngữ cảnh từ conversation history.
        
        Args:
            limit: Số lượng tin nhắn gần nhất cần lấy
            
        Returns:
            String chứa conversation history
        """
        if not self.conversation_history:
            return ""
        
        recent = self.conversation_history[-limit:]
        lines = ["\n=== LỊCH SỬ HỘI THOẠI GẦN ĐÂY ==="]
        
        for msg in recent:
            role = "👤 Người dùng" if msg['role'] == 'user' else "🤖 Trợ lý"
            content = msg.get('content', '')[:500]  # Giới hạn 500 ký tự mỗi tin
            if len(msg.get('content', '')) > 500:
                content += "..."
            lines.append(f"{role}: {content}")
        
        lines.append("=" * 40)
        return "\n".join(lines)

    def _simple_keyword_query(self, message: str) -> Dict[str, Any]:
        """
        Query đơn giản dựa trên keyword - KHÔNG CẦN AI.
        Xử lý các câu hỏi phổ biến về số lượng/danh sách.
        
        Cải tiến:
        - Trích xuất số lượng từ câu hỏi (VD: "5 phòng", "10 giảng viên")
        - Hỗ trợ "gần đây", "mới nhất" (sắp xếp theo ID giảm dần)
        
        Returns:
            Dict với success, data, intent_type, query_type
        """
        from ..models import Khoa, BoMon, GiangVien, MonHoc, PhongHoc, DotXep
        
        msg_lower = message.lower()
        result = {'success': False, 'data': [], 'summary': '', 'intent_type': 'general', 'query_type': 'SELECT'}
        
        # === HELPER: Trích xuất số lượng từ câu hỏi ===
        def extract_limit(text: str, default: int = 20) -> int:
            """Trích xuất số lượng từ câu hỏi. VD: '5 phòng', 'top 10'"""
            # Pattern: số + từ khóa hoặc "top/first số"
            patterns = [
                r'(\d+)\s*(?:phòng|giảng viên|gv|môn|khoa|bộ môn|đợt)',
                r'(?:top|first|đầu tiên|liệt kê)\s*(\d+)',
                r'(\d+)\s*(?:cái|người|kết quả|record)',
            ]
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    num = int(match.group(1))
                    return min(num, 100)  # Max 100
            return default
        
        # === HELPER: Kiểm tra yêu cầu sắp xếp "gần đây" ===
        def wants_recent(text: str) -> bool:
            """Kiểm tra xem user có muốn dữ liệu gần đây/mới nhất không"""
            recent_keywords = ['gần đây', 'mới nhất', 'mới thêm', 'cuối cùng', 'recent', 'latest', 'newest']
            return any(kw in text for kw in recent_keywords)
        
        # Trích xuất limit và recent flag
        limit = extract_limit(msg_lower)
        order_recent = wants_recent(msg_lower)
        
        try:
            # === KHOA ===
            if any(kw in msg_lower for kw in ['khoa', 'faculty']):
                if any(kw in msg_lower for kw in ['bao nhiêu', 'mấy', 'số lượng', 'tổng', 'count', 'đếm']):
                    count = Khoa.objects.count()
                    result = {
                        'success': True,
                        'data': [{'count': count}],
                        'summary': f'Hệ thống có {count} khoa',
                        'intent_type': 'khoa_info',
                        'query_type': 'COUNT'
                    }
                elif any(kw in msg_lower for kw in ['danh sách', 'liệt kê', 'list', 'có những', 'gồm những']) or limit < 20:
                    # Sử dụng limit từ câu hỏi, sắp xếp theo ID giảm dần nếu "gần đây"
                    queryset = Khoa.objects.all()
                    if order_recent:
                        queryset = queryset.order_by('-ma_khoa')
                    khoas = queryset[:limit]
                    data = [{'ma_khoa': k.ma_khoa, 'ten_khoa': k.ten_khoa} for k in khoas]
                    recent_note = " (mới nhất)" if order_recent else ""
                    result = {
                        'success': True,
                        'data': data,
                        'summary': f'Danh sách {len(data)} khoa{recent_note}',
                        'intent_type': 'khoa_info',
                        'query_type': 'SELECT'
                    }
                else:
                    # Mặc định: đếm khoa
                    count = Khoa.objects.count()
                    result = {
                        'success': True,
                        'data': [{'count': count}],
                        'summary': f'Hệ thống có {count} khoa',
                        'intent_type': 'khoa_info',
                        'query_type': 'COUNT'
                    }
            
            # === BỘ MÔN ===
            elif any(kw in msg_lower for kw in ['bộ môn', 'bo mon', 'department']):
                if any(kw in msg_lower for kw in ['bao nhiêu', 'mấy', 'số lượng', 'tổng', 'count']):
                    count = BoMon.objects.count()
                    result = {
                        'success': True,
                        'data': [{'count': count}],
                        'summary': f'Hệ thống có {count} bộ môn',
                        'intent_type': 'bo_mon_info',
                        'query_type': 'COUNT'
                    }
                else:
                    queryset = BoMon.objects.select_related('ma_khoa')
                    if order_recent:
                        queryset = queryset.order_by('-ma_bo_mon')
                    bomons = queryset[:limit]
                    data = [{'ma_bo_mon': b.ma_bo_mon, 'ten_bo_mon': b.ten_bo_mon, 'khoa': b.ma_khoa.ten_khoa if b.ma_khoa else 'N/A'} for b in bomons]
                    recent_note = " (mới nhất)" if order_recent else ""
                    result = {
                        'success': True,
                        'data': data,
                        'summary': f'Danh sách {len(data)} bộ môn{recent_note}',
                        'intent_type': 'bo_mon_info',
                        'query_type': 'SELECT'
                    }
            
            # === GIẢNG VIÊN ===
            elif any(kw in msg_lower for kw in ['giảng viên', 'giáo viên', 'giang vien', 'gv', 'thầy', 'cô', 'teacher', 'lecturer']):
                if any(kw in msg_lower for kw in ['bao nhiêu', 'mấy', 'số lượng', 'tổng', 'count']):
                    count = GiangVien.objects.count()
                    result = {
                        'success': True,
                        'data': [{'count': count}],
                        'summary': f'Hệ thống có {count} giảng viên',
                        'intent_type': 'giang_vien_info',
                        'query_type': 'COUNT'
                    }
                else:
                    queryset = GiangVien.objects.select_related('ma_bo_mon', 'ma_bo_mon__ma_khoa')
                    if order_recent:
                        queryset = queryset.order_by('-ma_gv')
                    gvs = queryset[:limit]
                    data = [{'ma_gv': g.ma_gv, 'ten_gv': g.ten_gv, 'bo_mon': g.ma_bo_mon.ten_bo_mon if g.ma_bo_mon else 'N/A'} for g in gvs]
                    recent_note = " (mới nhất)" if order_recent else ""
                    result = {
                        'success': True,
                        'data': data,
                        'summary': f'Danh sách {len(data)} giảng viên{recent_note}',
                        'intent_type': 'giang_vien_info',
                        'query_type': 'SELECT'
                    }
            
            # === MÔN HỌC ===
            elif any(kw in msg_lower for kw in ['môn học', 'mon hoc', 'môn', 'subject', 'course']):
                if any(kw in msg_lower for kw in ['bao nhiêu', 'mấy', 'số lượng', 'tổng', 'count']):
                    count = MonHoc.objects.count()
                    result = {
                        'success': True,
                        'data': [{'count': count}],
                        'summary': f'Hệ thống có {count} môn học',
                        'intent_type': 'mon_hoc_info',
                        'query_type': 'COUNT'
                    }
                else:
                    queryset = MonHoc.objects.all()
                    if order_recent:
                        queryset = queryset.order_by('-ma_mon_hoc')
                    monhocs = queryset[:limit]
                    data = [{'ma_mon': m.ma_mon_hoc, 'ten_mon': m.ten_mon_hoc, 'so_tin_chi': m.so_tin_chi} for m in monhocs]
                    recent_note = " (mới nhất)" if order_recent else ""
                    result = {
                        'success': True,
                        'data': data,
                        'summary': f'Danh sách {len(data)} môn học{recent_note}',
                        'intent_type': 'mon_hoc_info',
                        'query_type': 'SELECT'
                    }
            
            # === PHÒNG HỌC ===
            elif any(kw in msg_lower for kw in ['phòng học', 'phong hoc', 'phòng', 'room']):
                if any(kw in msg_lower for kw in ['bao nhiêu', 'mấy', 'số lượng', 'tổng', 'count']):
                    count = PhongHoc.objects.count()
                    result = {
                        'success': True,
                        'data': [{'count': count}],
                        'summary': f'Hệ thống có {count} phòng học',
                        'intent_type': 'phong_hoc_info',
                        'query_type': 'COUNT'
                    }
                else:
                    queryset = PhongHoc.objects.all()
                    if order_recent:
                        queryset = queryset.order_by('-ma_phong')
                    phongs = queryset[:limit]
                    data = [{'ma_phong': p.ma_phong, 'loai_phong': p.loai_phong, 'suc_chua': p.suc_chua} for p in phongs]
                    recent_note = " (mới nhất)" if order_recent else ""
                    result = {
                        'success': True,
                        'data': data,
                        'summary': f'Danh sách {len(data)} phòng học{recent_note}',
                        'intent_type': 'phong_hoc_info',
                        'query_type': 'SELECT'
                    }
            
            # === ĐỢT XẾP ===
            elif any(kw in msg_lower for kw in ['đợt', 'dot', 'học kỳ', 'semester', 'thời khóa biểu', 'tkb']):
                if any(kw in msg_lower for kw in ['bao nhiêu', 'mấy', 'số lượng', 'tổng', 'count']):
                    count = DotXep.objects.count()
                    result = {
                        'success': True,
                        'data': [{'count': count}],
                        'summary': f'Hệ thống có {count} đợt xếp',
                        'intent_type': 'dot_xep_info',
                        'query_type': 'COUNT'
                    }
                else:
                    # Đợt xếp mặc định luôn sắp xếp theo ngày mới nhất
                    dots = DotXep.objects.all().order_by('-ngay_bd')[:limit]
                    data = [{'ma_dot': d.ma_dot, 'ten_dot': d.ten_dot, 'trang_thai': d.trang_thai} for d in dots]
                    result = {
                        'success': True,
                        'data': data,
                        'summary': f'Danh sách {len(data)} đợt xếp lịch (mới nhất)',
                        'intent_type': 'dot_xep_info',
                        'query_type': 'SELECT'
                    }
            
            # === PHÂN CÔNG ===
            elif any(kw in msg_lower for kw in ['phân công', 'phan cong', 'phancong', 'assignment']):
                from ..models import PhanCong
                if any(kw in msg_lower for kw in ['bao nhiêu', 'mấy', 'số lượng', 'tổng', 'count']):
                    count = PhanCong.objects.count()
                    result = {
                        'success': True,
                        'data': [{'count': count}],
                        'summary': f'Hệ thống có {count} phân công giảng dạy',
                        'intent_type': 'phan_cong_info',
                        'query_type': 'COUNT'
                    }
                else:
                    queryset = PhanCong.objects.select_related('ma_gv', 'ma_lop', 'ma_dot')
                    if order_recent:
                        queryset = queryset.order_by('-id')
                    phan_congs = queryset[:limit]
                    data = [{
                        'id': pc.id,
                        'giang_vien': pc.ma_gv.ten_gv if pc.ma_gv else 'Chưa phân công',
                        'lop': pc.ma_lop.ma_lop if pc.ma_lop else 'N/A',
                        'dot': pc.ma_dot.ten_dot if pc.ma_dot else 'N/A'
                    } for pc in phan_congs]
                    recent_note = " (mới nhất)" if order_recent else ""
                    result = {
                        'success': True,
                        'data': data,
                        'summary': f'Danh sách {len(data)} phân công{recent_note}',
                        'intent_type': 'phan_cong_info',
                        'query_type': 'SELECT'
                    }
            
            # === LỚP MÔN HỌC ===
            elif any(kw in msg_lower for kw in ['lớp môn', 'lop mon', 'lớp học', 'section', 'class']):
                from ..models import LopMonHoc
                if any(kw in msg_lower for kw in ['bao nhiêu', 'mấy', 'số lượng', 'tổng', 'count']):
                    count = LopMonHoc.objects.count()
                    result = {
                        'success': True,
                        'data': [{'count': count}],
                        'summary': f'Hệ thống có {count} lớp môn học',
                        'intent_type': 'lop_mon_hoc_info',
                        'query_type': 'COUNT'
                    }
                else:
                    queryset = LopMonHoc.objects.select_related('ma_mon_hoc')
                    if order_recent:
                        queryset = queryset.order_by('-ma_lop')
                    lops = queryset[:limit]
                    data = [{
                        'ma_lop': l.ma_lop,
                        'mon_hoc': l.ma_mon_hoc.ten_mon_hoc if l.ma_mon_hoc else 'N/A',
                        'so_sv': l.so_luong_sv or 0,
                        'nhom': l.nhom_mh
                    } for l in lops]
                    recent_note = " (mới nhất)" if order_recent else ""
                    result = {
                        'success': True,
                        'data': data,
                        'summary': f'Danh sách {len(data)} lớp môn học{recent_note}',
                        'intent_type': 'lop_mon_hoc_info',
                        'query_type': 'SELECT'
                    }
            
            # === THỜI KHÓA BIỂU ===
            elif any(kw in msg_lower for kw in ['thời khóa biểu', 'tkb', 'lịch học', 'schedule']):
                from ..models import ThoiKhoaBieu
                if any(kw in msg_lower for kw in ['bao nhiêu', 'mấy', 'số lượng', 'tổng', 'count']):
                    count = ThoiKhoaBieu.objects.count()
                    result = {
                        'success': True,
                        'data': [{'count': count}],
                        'summary': f'Hệ thống có {count} bản ghi thời khóa biểu',
                        'intent_type': 'tkb_info',
                        'query_type': 'COUNT'
                    }
                else:
                    queryset = ThoiKhoaBieu.objects.select_related('ma_lop', 'ma_phong', 'time_slot_id')
                    if order_recent:
                        queryset = queryset.order_by('-ngay_tao')
                    tkbs = queryset[:limit]
                    data = [{
                        'ma_tkb': t.ma_tkb,
                        'lop': t.ma_lop.ma_lop if t.ma_lop else 'N/A',
                        'phong': t.ma_phong.ma_phong if t.ma_phong else 'Chưa xếp',
                        'slot': t.time_slot_id.time_slot_id if t.time_slot_id else 'N/A'
                    } for t in tkbs]
                    recent_note = " (mới nhất)" if order_recent else ""
                    result = {
                        'success': True,
                        'data': data,
                        'summary': f'Danh sách {len(data)} thời khóa biểu{recent_note}',
                        'intent_type': 'tkb_info',
                        'query_type': 'SELECT'
                    }
            
            # === NGUYỆN VỌNG ===
            elif any(kw in msg_lower for kw in ['nguyện vọng', 'nguyen vong', 'đăng ký', 'preference']):
                from ..models import NguyenVong
                if any(kw in msg_lower for kw in ['bao nhiêu', 'mấy', 'số lượng', 'tổng', 'count']):
                    count = NguyenVong.objects.count()
                    result = {
                        'success': True,
                        'data': [{'count': count}],
                        'summary': f'Hệ thống có {count} nguyện vọng đăng ký',
                        'intent_type': 'nguyen_vong_info',
                        'query_type': 'COUNT'
                    }
                else:
                    queryset = NguyenVong.objects.select_related('ma_gv', 'time_slot_id')
                    nvs = queryset[:limit]
                    data = [{
                        'id': nv.id,
                        'giang_vien': nv.ma_gv.ten_gv if nv.ma_gv else 'N/A',
                        'slot': nv.time_slot_id.time_slot_id if nv.time_slot_id else 'N/A'
                    } for nv in nvs]
                    result = {
                        'success': True,
                        'data': data,
                        'summary': f'Danh sách {len(data)} nguyện vọng',
                        'intent_type': 'nguyen_vong_info',
                        'query_type': 'SELECT'
                    }
            
            # === CHÀO HỎI ===
            elif any(kw in msg_lower for kw in ['xin chào', 'hello', 'hi', 'chào', 'hey']):
                greetings = [
                    "Xin chào! 👋 Tôi có thể giúp gì cho bạn?",
                    "Chào bạn! 😊 Bạn cần hỗ trợ gì về thời khóa biểu?",
                    "Hello! 🎓 Tôi sẵn sàng hỗ trợ bạn tra cứu thông tin.",
                ]
                result = {
                    'success': True,
                    'data': [],
                    'summary': random.choice(greetings),
                    'intent_type': 'greeting',
                    'query_type': 'NONE'
                }
        
        except Exception as e:
            logger.error(f"Simple keyword query error: {e}")
            result = {'success': False, 'error': str(e)}
        
        return result

    def _generate_fallback_response(self, query_result: Dict, intent: Dict, ma_dot: str = None) -> str:
        """
        Sinh câu trả lời trực tiếp từ kết quả query khi AI không khả dụng.
        KHÔNG CẦN GỌI API - tiết kiệm tài nguyên.
        """
        intent_type = intent['type']
        query_type = intent.get('query_type')
        entities = intent.get('entities', {})
        
        lines = ["Chào bạn! 👋\n"]
        
        if not query_result.get('success'):
            lines.append("❌ Không thể thực hiện truy vấn. Vui lòng thử lại.")
            return "\n".join(lines)
        
        data = query_result.get('data', [])
        summary = query_result.get('summary', '')
        
        # === GIẢNG VIÊN ===
        if intent_type == 'giang_vien_info':
            if query_type == 'COUNT':
                count = data[0].get('count', 0) if data else 0
                khoa_filter = entities.get('khoa')
                if khoa_filter:
                    lines.append(f"📊 **Khoa {khoa_filter}** có **{count} giảng viên** 👨‍🏫")
                else:
                    lines.append(f"📊 Hệ thống có tổng cộng **{count} giảng viên** 👨‍🏫")
            else:
                lines.append(f"📋 {summary}\n")
                for gv in data[:10]:
                    mon_str = ", ".join(gv.get('mon_day', [])[:3]) or "Chưa phân công"
                    lines.append(f"- **{gv['ten_gv']}** ({gv['ma_gv']})")
                    lines.append(f"  Khoa: {gv['khoa']} | BM: {gv['bo_mon']} | Môn: {mon_str}")
                if len(data) > 10:
                    lines.append(f"... và {len(data) - 10} giảng viên khác")
        
        # === MÔN HỌC ===
        elif intent_type == 'mon_hoc_info':
            if query_type == 'COUNT':
                count = data[0].get('count', 0) if data else 0
                lines.append(f"📚 Hệ thống có **{count} môn học**")
            else:
                lines.append(f"📋 {summary}\n")
                for mon in data[:10]:
                    lines.append(f"- **{mon['ten_mon']}** ({mon['ma_mon']}): {mon['so_tin_chi']} TC")
        
        # === PHÒNG TRỐNG ===
        elif intent_type == 'room_suggestion':
            thu = entities.get('thu')
            ca = entities.get('ca')
            rooms = self._get_available_rooms(thu, ca, entities.get('loai_phong'), ma_dot=ma_dot) if thu and ca else []
            
            thu_str = f"Thứ {thu}" if thu else "?"
            ca_str = f"Ca {ca}" if ca else "?"
            
            if rooms:
                lines.append(f"🏫 **Phòng trống {thu_str}, {ca_str}:**\n")
                for r in rooms[:10]:
                    lines.append(f"- **{r['ma_phong']}**: {r['loai_phong']}, {r['suc_chua']} chỗ")
                lines.append(f"\n✅ Tìm thấy {len(rooms)} phòng trống")
            else:
                lines.append(f"❌ Không có phòng trống vào {thu_str}, {ca_str}")
        
        # === LỊCH DẠY / TKB ===
        elif intent_type == 'schedule_query':
            if data:
                lines.append(f"📅 {summary}\n")
                for tkb in data[:10]:
                    thu_str = f"Thứ {tkb['thu']}" if tkb['thu'] != 8 else "CN"
                    lines.append(f"- **{tkb['ma_lop']}**: {tkb['ten_mon']}")
                    lines.append(f"  {thu_str} {tkb['ca']} | Phòng: {tkb['phong']}")
            else:
                lines.append("❌ Không tìm thấy lịch dạy nào")
                if ma_dot:
                    lines.append(f"(Đợt xếp: {ma_dot})")
        
        # === NGUYỆN VỌNG ===
        elif intent_type == 'nguyen_vong_query':
            if data:
                lines.append(f"💬 {summary}\n")
                nv_by_gv = {}
                for nv in data:
                    gv = nv['giang_vien']
                    if gv not in nv_by_gv:
                        nv_by_gv[gv] = []
                    nv_by_gv[gv].append(f"Thứ {nv['thu']}-{nv['ca']}")
                for gv, slots in list(nv_by_gv.items())[:10]:
                    lines.append(f"- **{gv}**: {', '.join(slots)}")
            else:
                lines.append("❌ Không tìm thấy nguyện vọng nào")
        
        # === KHOA ===
        elif intent_type == 'khoa_info':
            if query_type == 'COUNT':
                count = data[0].get('count', 0) if data else 0
                lines.append(f"🏛️ Hệ thống có **{count} khoa**")
            else:
                lines.append(f"🏛️ {summary}\n")
                for k in data[:10]:
                    lines.append(f"- **{k.get('ten_khoa', 'N/A')}** ({k.get('ma_khoa', 'N/A')})")
        
        # === BỘ MÔN ===
        elif intent_type == 'bo_mon_info':
            if query_type == 'COUNT':
                count = data[0].get('count', 0) if data else 0
                lines.append(f"📚 Hệ thống có **{count} bộ môn**")
            else:
                lines.append(f"📚 {summary}\n")
                for bm in data[:10]:
                    lines.append(f"- **{bm.get('ten_bo_mon', 'N/A')}** | Khoa: {bm.get('khoa', 'N/A')}")
        
        # === PHÒNG HỌC ===
        elif intent_type == 'phong_hoc_info':
            if query_type == 'COUNT':
                count = data[0].get('count', 0) if data else 0
                lines.append(f"🏫 Hệ thống có **{count} phòng học**")
            else:
                lines.append(f"🏫 {summary}\n")
                for p in data[:10]:
                    lines.append(f"- **{p['ma_phong']}**: {p.get('loai_phong', 'N/A')}, {p.get('suc_chua', 'N/A')} chỗ")
        
        # === ĐỢT XẾP ===
        elif intent_type == 'dot_xep_info':
            if query_type == 'COUNT':
                count = data[0].get('count', 0) if data else 0
                lines.append(f"📅 Hệ thống có **{count} đợt xếp lịch**")
            else:
                lines.append(f"📅 {summary}\n")
                for d in data[:5]:
                    lines.append(f"- **{d.get('ten_dot', 'N/A')}** ({d.get('ma_dot', 'N/A')}): {d.get('trang_thai', 'N/A')}")
        
        # === PHÂN CÔNG ===
        elif intent_type == 'phan_cong_info':
            if query_type == 'COUNT':
                count = data[0].get('count', 0) if data else 0
                lines.append(f"📋 Hệ thống có **{count} phân công giảng dạy**")
            else:
                lines.append(f"📋 {summary}\n")
                for pc in data[:10]:
                    lines.append(f"- **{pc.get('giang_vien', 'N/A')}** → Lớp: {pc.get('lop', 'N/A')} | Đợt: {pc.get('dot', 'N/A')}")
        
        # === LỚP MÔN HỌC ===
        elif intent_type == 'lop_mon_hoc_info':
            if query_type == 'COUNT':
                count = data[0].get('count', 0) if data else 0
                lines.append(f"📚 Hệ thống có **{count} lớp môn học**")
            else:
                lines.append(f"📚 {summary}\n")
                for l in data[:10]:
                    lines.append(f"- **{l.get('ma_lop', 'N/A')}**: {l.get('mon_hoc', 'N/A')} | SV: {l.get('so_sv', 0)} | Nhóm: {l.get('nhom', 'N/A')}")
        
        # === THỜI KHÓA BIỂU ===
        elif intent_type == 'tkb_info':
            if query_type == 'COUNT':
                count = data[0].get('count', 0) if data else 0
                lines.append(f"📅 Hệ thống có **{count} bản ghi thời khóa biểu**")
            else:
                lines.append(f"📅 {summary}\n")
                for t in data[:10]:
                    lines.append(f"- **{t.get('ma_tkb', 'N/A')}**: Lớp {t.get('lop', 'N/A')} | Phòng: {t.get('phong', 'N/A')} | Slot: {t.get('slot', 'N/A')}")
        
        # === NGUYỆN VỌNG (fallback) ===
        elif intent_type == 'nguyen_vong_info':
            if query_type == 'COUNT':
                count = data[0].get('count', 0) if data else 0
                lines.append(f"💬 Hệ thống có **{count} nguyện vọng đăng ký**")
            else:
                lines.append(f"💬 {summary}\n")
                for nv in data[:10]:
                    lines.append(f"- **{nv.get('giang_vien', 'N/A')}** → Slot: {nv.get('slot', 'N/A')}")
        
        # === CHÀO HỎI ===
        elif intent_type == 'greeting':
            # Trả lời trực tiếp từ summary (đã random trong _simple_keyword_query)
            return summary if summary else "Xin chào! 👋 Tôi có thể giúp gì cho bạn?"
        
        # === THỐNG KÊ ===
        elif intent_type == 'thong_ke_query':
            if data:
                stats = data[0]
                lines.append("📊 **Thống kê tổng hợp:**\n")
                lines.append(f"- Giảng viên: **{stats.get('tong_giang_vien', 'N/A')}**")
                lines.append(f"- Môn học: **{stats.get('tong_mon_hoc', 'N/A')}**")
                lines.append(f"- Khoa: **{stats.get('tong_khoa', 'N/A')}** | Bộ môn: **{stats.get('tong_bo_mon', 'N/A')}**")
                if stats.get('dot_xep'):
                    lines.append(f"\n📅 Đợt {stats['dot_xep']}: {stats.get('lop_da_xep', 0)}/{stats.get('tong_lop', 0)} lớp ({stats.get('ty_le_xep', 0)}%)")
        
        # === GENERAL ===
        else:
            lines.append(f"ℹ️ {summary}")
            if data:
                lines.append(f"\nDữ liệu: {json.dumps(data[:3], ensure_ascii=False)}")
        
        return "\n".join(lines)
    
    def _process_with_tools(self, message: str, intent: Dict, ma_dot: str = None) -> str:
        """
        Xử lý câu hỏi với các tools (functions) nội bộ
        Trả về thông tin bổ sung để đưa vào context cho LLM
        TÁI SỬ DỤNG code từ DAL và LLMDataProcessor
        """
        additional_context = []
        
        # Room suggestion
        if intent['type'] == 'room_suggestion':
            thu = intent['entities'].get('thu')
            ca = intent['entities'].get('ca')
            loai_phong = intent['entities'].get('loai_phong')
            
            if thu and ca:
                rooms = self._get_available_rooms(thu, ca, loai_phong, ma_dot=ma_dot)
                if rooms:
                    additional_context.append(f"\n🔍 KẾT QUẢ TRA CỨU PHÒNG TRỐNG (Thứ {thu}, Ca {ca}):")
                    for r in rooms[:10]:
                        additional_context.append(
                            f"- {r['ma_phong']}: {r['loai_phong']}, {r['suc_chua']} chỗ"
                            + (f", TB: {r['thiet_bi']}" if r['thiet_bi'] else "")
                        )
                else:
                    additional_context.append(f"\n⚠️ Không có phòng {loai_phong or ''} trống vào Thứ {thu}, Ca {ca}")
        
        # Teacher info - sử dụng DAL
        if intent['type'] == 'giang_vien_info':
            patterns = [r'giảng viên\s+(\w+)', r'thầy\s+(\w+)', r'cô\s+(\w+)', r'gv\s+(\w+)']
            for pattern in patterns:
                match = re.search(pattern, message.lower())
                if match:
                    gv_info = self._get_teacher_info(match.group(1))
                    if gv_info:
                        additional_context.append(f"\n👤 THÔNG TIN GIẢNG VIÊN {gv_info['ten_gv']}:")
                        additional_context.append(f"- Mã GV: {gv_info['ma_gv']}")
                        additional_context.append(f"- Bộ môn: {gv_info['bo_mon']['ten']}")
                        additional_context.append(f"- Loại: {gv_info['loai_gv']}")
                        if gv_info.get('mon_hoc_co_the_day'):
                            mon_list = [m['ten'] for m in gv_info['mon_hoc_co_the_day'][:5]]
                            additional_context.append(f"- Môn dạy: {', '.join(mon_list)}")
                    break
        
        # Thống kê - sử dụng DAL
        if intent['type'] == 'thong_ke_query' and ma_dot:
            thong_ke = self._get_thong_ke(ma_dot)
            if thong_ke:
                additional_context.append(f"\n📊 THỐNG KÊ ĐỢT {ma_dot}:")
                additional_context.append(f"- Tổng lớp: {thong_ke.get('tong_lop', 0)}")
                additional_context.append(f"- Đã xếp: {thong_ke.get('lop_da_xep', 0)}")
                additional_context.append(f"- Tỷ lệ: {thong_ke.get('tyle_xep_xong', 0):.1f}%")
                additional_context.append(f"- Tổng GV: {thong_ke.get('tong_giang_vien', 0)}")
        
        # Xung đột - sử dụng LLMDataProcessor
        if 'xung đột' in message.lower() or 'conflict' in message.lower():
            if ma_dot:
                conflicts = self._detect_conflicts(ma_dot)
                if conflicts:
                    additional_context.append(f"\n⚠️ PHÁT HIỆN XUNG ĐỘT:")
                    additional_context.append(f"- Phòng trùng: {len(conflicts.get('phong_trung', []))} TH")
                    additional_context.append(f"- GV trùng: {len(conflicts.get('giang_vien_trung', []))} TH")
                    additional_context.append(f"- Lớp chưa xếp: {len(conflicts.get('lop_chua_xep', []))} lớp")
        
        # GỢI Ý ĐỔI LỊCH - CHỈ ĐỌC, KHÔNG TÁC ĐỘNG DATABASE
        doi_lich_keywords = ['đổi lịch', 'chuyển lịch', 'dời lịch', 'thay đổi lịch', 
                            'gợi ý lịch', 'slot khác', 'ca khác', 'đổi ca']
        if any(kw in message.lower() for kw in doi_lich_keywords):
            # Nếu chưa có ma_dot, tự động lấy đợt mới nhất
            current_ma_dot = ma_dot
            if not current_ma_dot:
                try:
                    from ..models import DotXep
                    dot_moi_nhat = DotXep.objects.order_by('-ngay_bat_dau').first()
                    if dot_moi_nhat:
                        current_ma_dot = dot_moi_nhat.ma_dot
                        additional_context.append(f"📅 Tự động chọn đợt: **{dot_moi_nhat.ten_dot}** ({current_ma_dot})")
                except Exception as e:
                    logger.warning(f"Không thể lấy đợt mới nhất: {e}")
            
            # Tìm tên GV trong câu hỏi
            gv_patterns = [
                r'(?:giảng viên|thầy|cô|gv)\s+([a-zA-ZÀ-ỹ\s]+?)(?:\s+từ|\s+sang|\s+đổi|\?|$)',
                r'đổi.*?(?:cho|của)\s+([a-zA-ZÀ-ỹ\s]+?)(?:\s+từ|\s+sang|\?|$)',
                r'lịch\s+(?:của\s+)?([a-zA-ZÀ-ỹ\s]+?)(?:\s+từ|\s+sang|\?|$)'
            ]
            gv_name = None
            for pattern in gv_patterns:
                match = re.search(pattern, message.lower())
                if match:
                    gv_name = match.group(1).strip()
                    break
            
            if gv_name and current_ma_dot:
                suggest_result = self._suggest_schedule_change(gv_name, ma_dot=current_ma_dot)
                
                if suggest_result['success']:
                    gv_info = suggest_result['giang_vien']
                    additional_context.append(f"\n🔄 GỢI Ý ĐỔI LỊCH CHO GV {gv_info['ten_gv']} (Mã: {gv_info['ma_gv']})")
                    additional_context.append(f"📍 Bộ môn: {gv_info['bo_mon']}")
                    
                    # Lịch hiện tại
                    if suggest_result['lich_hien_tai']:
                        additional_context.append(f"\n📅 LỊCH HIỆN TẠI ({len(suggest_result['lich_hien_tai'])} slot):")
                        for lich in suggest_result['lich_hien_tai'][:5]:
                            additional_context.append(
                                f"  • {lich['thu_ca_str']}: {lich['mon']} | Phòng: {lich['phong']}"
                            )
                    
                    # Gợi ý slot thay thế
                    if suggest_result['goi_y']:
                        additional_context.append(f"\n✨ GỢI Ý SLOT THAY THẾ (Top {len(suggest_result['goi_y'])}):")
                        for i, gy in enumerate(suggest_result['goi_y'][:5], 1):
                            nguyen_vong_icon = "💚" if gy['trong_nguyen_vong'] else "💛"
                            additional_context.append(
                                f"  {i}. {nguyen_vong_icon} {gy['thu_ca_str']} (điểm: {gy['score']})"
                            )
                            additional_context.append(f"     Lý do: {', '.join(gy['reasons'])}")
                            if gy['phong_goi_y']:
                                phong_str = ', '.join([p['ma_phong'] for p in gy['phong_goi_y'][:3]])
                                additional_context.append(f"     Phòng gợi ý: {phong_str}")
                        
                        additional_context.append("\n⚠️ LƯU Ý: Đây chỉ là GỢI Ý, không tự động thay đổi lịch.")
                        additional_context.append("   Vui lòng kiểm tra và xác nhận với bộ phận quản lý để thực hiện.")
                    else:
                        additional_context.append("\n❌ Không tìm thấy slot phù hợp để gợi ý đổi.")
                else:
                    additional_context.append(f"\n⚠️ {suggest_result['message']}")
            elif not gv_name:
                additional_context.append("\n❓ Vui lòng cho biết tên giảng viên cần đổi lịch.")
                additional_context.append("   VD: 'Gợi ý đổi lịch cho thầy Nguyễn Văn A'")
            elif not current_ma_dot:
                additional_context.append("\n⚠️ Không tìm thấy đợt xếp nào trong hệ thống.")
        
        return "\n".join(additional_context)
    
    def chat(self, message: str, ma_dot: str = None) -> Dict[str, Any]:
        """
        Xử lý tin nhắn từ người dùng với AI-generated query execution
        
        Flow chính:
        1. AI sinh câu truy vấn (query_spec) từ câu hỏi tự nhiên
        2. Hệ thống thực thi query an toàn (chỉ Django ORM, không raw SQL)
        3. Nếu query lỗi/trống → feedback cho AI và thử lại (max 2 lần)
        4. AI format câu trả lời từ kết quả
        
        Fallback: Nếu AI không khả dụng → rule-based extraction + system fallback response
        
        Args:
            message: Câu hỏi/tin nhắn từ người dùng
            ma_dot: Mã đợt xếp hiện tại (optional, sẽ tự động detect nếu cần)
            
        Returns:
            Dict với response và metadata
        """
        try:
            query_result = None
            intent = None
            ai_query_used = False
            dot_xep_notice = ""  # Thông báo về đợt xếp cho người dùng
            
            # ====================================================
            # BƯỚC 0: KIỂM TRA YÊU CẦU FOLLOW-UP (format lại, chi tiết...)
            # ====================================================
            is_followup, format_type, last_data = self._is_followup_request(message)
            
            if is_followup and last_data:
                logger.info(f"[Chat] Detected follow-up request: format={format_type}")
                
                # Tạo prompt để AI format lại dữ liệu cũ
                followup_prompt = f"""
YÊU CẦU FOLLOW-UP: {message}
LOẠI FORMAT: {format_type}

CÂU HỎI GỐC: {last_data.get('original_question', 'N/A')}

CÂU TRẢ LỜI TRƯỚC:
{last_data.get('response', '')}

NHIỆM VỤ:
- Người dùng muốn {format_type.upper()} lại thông tin trước đó
- Nếu format="table": Hiển thị dữ liệu dạng bảng Markdown với | header | header | và |---|---|
- Nếu format="list": Hiển thị dạng danh sách có đánh số
- Nếu format="detail": Mở rộng thông tin chi tiết hơn
- Nếu format="explain": Giải thích ý nghĩa dữ liệu
- Nếu format="summary": Tóm tắt ngắn gọn

HÃY FORMAT LẠI THÔNG TIN THEO YÊU CẦU. Trả lời bằng tiếng Việt.
"""
                # Gọi AI để format lại sử dụng Interactions API
                try:
                    response_text, interaction_id, error = self._call_interactions_api(
                        prompt=followup_prompt,
                        model=self.model,
                        thinking_level=THINKING_LEVEL_LOW,
                        use_stateful=True,  # Sử dụng stateful để giữ ngữ cảnh
                        temperature=0.7,
                        max_tokens=4096,
                        response_mime_type="text/plain"  # Text response cho user
                    )
                    
                    if response_text and not error:
                        # Lưu vào history
                        self.conversation_history.append({
                            'role': 'user',
                            'content': message,
                            'timestamp': datetime.now().isoformat()
                        })
                        self.conversation_history.append({
                            'role': 'assistant',
                            'content': response_text,
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        return {
                            'success': True,
                            'response': response_text,
                            'intent': {'type': 'followup_format', 'format': format_type},
                            'metadata': {
                                'model': self.model,
                                'timestamp': datetime.now().isoformat(),
                                'followup': True,
                                'interaction_id': interaction_id
                            }
                        }
                except Exception as e:
                    logger.warning(f"Follow-up AI failed: {e}, continuing with normal flow")
            
            # ====================================================
            # BƯỚC 1: AI SINH QUERY VỚI SELF-CORRECTION
            # ====================================================
            logger.info(f"[Chat] Bắt đầu xử lý: '{message}'")
            
            max_query_attempts = 3  # Tối đa 3 lần thử (1 lần đầu + 2 lần sửa)
            feedback = None  # Feedback cho AI để tự sửa query
            last_query_spec = None
            
            for attempt in range(max_query_attempts):
                # Thử dùng AI sinh query specification (có feedback nếu là lần retry)
                ai_query_result = self._generate_query_with_ai(message, ma_dot, feedback=feedback)
                
                if not ai_query_result.get('success'):
                    logger.warning(f"[Chat] AI query gen failed (attempt {attempt+1})")
                    break  # AI không khả dụng, thoát vòng lặp
                
                query_spec = ai_query_result['query_spec']
                last_query_spec = query_spec
                ai_query_used = True
                logger.info(f"[Chat] AI query spec (attempt {attempt+1}): {query_spec.get('explanation', '')}")
                
                # Xác định đợt xếp nếu cần
                if query_spec.get('needs_dot_xep') and not ma_dot:
                    ma_dot, dot_xep_notice = self._get_active_dot_xep()
                    logger.info(f"[Chat] AI query needs đợt xếp, auto-detected: {ma_dot}")
                elif not query_spec.get('needs_dot_xep'):
                    ma_dot = None  # AI biết không cần đợt
                    logger.info("[Chat] AI query: master data - không cần đợt xếp")
                
                # Thực thi query do AI sinh
                query_result = self._execute_ai_generated_query(query_spec, ma_dot)
                
                # Kiểm tra kết quả và quyết định có cần retry không
                if query_result.get('success'):
                    data = query_result.get('data', [])
                    
                    # Kiểm tra nếu kết quả có ý nghĩa
                    if data:
                        # Query thành công và có data - DONE
                        logger.info(f"[Chat] Query success with {len(data)} results")
                        break
                    else:
                        # Query thành công nhưng KHÔNG CÓ DATA
                        # Có thể query đúng nhưng data trống, hoặc query sai
                        if attempt < max_query_attempts - 1:
                            # Tạo feedback để AI thử lại với query khác
                            feedback = f"""
QUERY TRƯỚC ĐÃ THỰC THI NHƯNG TRẢ VỀ KẾT QUẢ TRỐNG (0 records).

Query spec đã dùng:
- Tables: {query_spec.get('tables')}
- Filters: {query_spec.get('filters')}
- Explanation: {query_spec.get('explanation')}

NGUYÊN NHÂN CÓ THỂ:
1. Filter quá chặt (ví dụ: tìm "Công nghệ thông tin" nhưng DB lưu "CNTT")
2. Bảng sai (ví dụ: dùng bảng GiangVien thay vì Khoa)
3. Field path sai (ví dụ: ten_khoa thay vì ma_khoa__ten_khoa)

GỢI Ý:
- Thử bỏ/nới lỏng filters
- Kiểm tra lại tên bảng/field
- Với câu hỏi đếm đơn giản, dùng query_type="COUNT" và không cần filter
"""
                            logger.info(f"[Chat] Empty result, retrying with feedback (attempt {attempt+1})")
                            continue
                        else:
                            # Hết lần retry - chấp nhận kết quả trống
                            logger.info("[Chat] Max retries reached, accepting empty result")
                            break
                else:
                    # Query THẤT BẠI (lỗi execution)
                    error_msg = query_result.get('error', 'Unknown error')
                    if attempt < max_query_attempts - 1:
                        # Tạo feedback về lỗi để AI sửa
                        feedback = f"""
QUERY TRƯỚC BỊ LỖI KHI THỰC THI!

Query spec đã dùng:
- Tables: {query_spec.get('tables')}  
- Filters: {query_spec.get('filters')}
- Joins: {query_spec.get('joins')}

LỖI: {error_msg}

NGUYÊN NHÂN CÓ THỂ:
1. Field không tồn tại trong model
2. Join path sai (VD: ma_bo_mon__ma_khoa thay vì bo_mon__khoa)
3. Tên bảng sai (VD: 'khoa' thay vì 'Khoa')

HÃY SỬA LẠI QUERY SPECIFICATION!
"""
                        logger.info(f"[Chat] Query error: {error_msg}, retrying with feedback")
                        continue
                    else:
                        # Hết lần retry
                        logger.warning(f"[Chat] Max retries reached, query still failing: {error_msg}")
                        break
            
            # Tạo intent từ query_spec cuối cùng
            if last_query_spec:
                intent = {
                    'type': last_query_spec.get('intent_type', 'general'),
                    'entities': last_query_spec.get('filters', {}),
                    'query_type': last_query_spec.get('query_type', 'SELECT')
                }
            
            # Nếu AI không khả dụng hoặc tất cả attempts đều fail
            if not ai_query_used or (query_result and not query_result.get('success')):
                # ====================================================
                # FALLBACK: AI không khả dụng - thử simple keyword query
                # ====================================================
                logger.info("[Chat] AI query failed, trying simple keyword fallback")
                
                # THỬ SIMPLE KEYWORD QUERY (không cần AI)
                simple_result = self._simple_keyword_query(message)
                
                if simple_result.get('success'):
                    logger.info(f"[Chat] Simple keyword query success: {simple_result.get('summary')}")
                    query_result = simple_result
                    intent = {
                        'type': simple_result.get('intent_type', 'general'),
                        'entities': {},
                        'query_type': simple_result.get('query_type', 'SELECT')
                    }
                else:
                    # Tạo intent cơ bản
                    if not intent:
                        intent = {'type': 'general', 'entities': {}, 'query_type': 'SELECT'}
                    if not query_result:
                        query_result = {
                            'success': False,
                            'message': 'Không thể phân tích câu hỏi'
                        }
            
            # ====================================================
            # BƯỚC 2: LẤY THÔNG TIN BỔ SUNG TỪ TOOLS
            # ====================================================
            tool_context = self._process_with_tools(message, intent, ma_dot) if intent else ""
            
            # ====================================================
            # BƯỚC 3: TẠO PROMPT CHO AI TRẢ LỜI
            # ====================================================
            dot_xep_info = f"ĐỢT XẾP ĐANG SỬ DỤNG: {ma_dot}" if ma_dot else "(Truy vấn dữ liệu master - không phụ thuộc đợt xếp)"
            query_method = "AI-generated query" if ai_query_used else "Rule-based query"
            
            # Thêm thông báo về đợt xếp nếu có
            dot_notice_section = ""
            if dot_xep_notice:
                dot_notice_section = f"\n{dot_xep_notice}\n"
            
            # Lấy conversation history để AI hiểu ngữ cảnh
            conversation_context = self._get_conversation_context(limit=4)
            
            full_context = f"""
CÂU HỎI HIỆN TẠI: {message}
{dot_xep_info}
PHƯƠNG PHÁP TRUY VẤN: {query_method}
{conversation_context}

{'='*60}
KẾT QUẢ TRUY VẤN TỪ DATABASE:
{'='*60}
"""
            
            if query_result and query_result.get('success'):
                full_context += f"\n📊 {query_result.get('query_description', 'Truy vấn dữ liệu')}\n"
                full_context += f"✅ {query_result.get('summary', '')}\n\n"
                
                # Format data
                if query_result.get('data'):
                    full_context += "DỮ LIỆU TRUY VẤN:\n"
                    full_context += json.dumps(query_result['data'], ensure_ascii=False, indent=2)
                    full_context += "\n"
            else:
                full_context += "⚠️ Không thực hiện được truy vấn tự động. Sử dụng thông tin tổng quát.\n\n"
            
            # Thêm tool context nếu có
            if tool_context:
                full_context += f"\n{'='*60}\nTHÔNG TIN BỔ SUNG:\n{'='*60}\n{tool_context}\n"
            
            # Hướng dẫn trả lời
            full_context += f"""

{'='*60}
HƯỚNG DẪN TRẢ LỜI:
{'='*60}
- Dựa vào "KẾT QUẢ TRUY VẤN" ở trên để trả lời chính xác
- Trả lời bằng tiếng Việt, tự nhiên và dễ hiểu
- Sử dụng emoji phù hợp
- Format rõ ràng với bullet points hoặc bảng
- Nếu data rỗng, nói rõ "không tìm thấy"
- Trả lời ngắn gọn, đủ ý
- QUAN TRỌNG: Nếu LỊCH SỬ HỘI THOẠI có dữ liệu liên quan, sử dụng ngữ cảnh đó
- Nếu người dùng yêu cầu "bảng", "chi tiết", "giải thích" → format lại dữ liệu từ câu trả lời trước
"""
            
            # ====================================================
            # BƯỚC 4: GỌI AI ĐỂ FORMAT CÂU TRẢ LỜI (sử dụng Interactions API)
            # ====================================================
            
            # Chuẩn bị prompt cho AI
            final_prompt = self.system_instruction + "\n\n" + full_context
            
            # Sử dụng Interactions API với stateful mode để giữ ngữ cảnh hội thoại
            response_text, interaction_id, error = self._call_interactions_api(
                prompt=final_prompt,
                model=self.model,
                thinking_level=THINKING_LEVEL_LOW,  # Suy luận nhẹ cho response formatting
                use_stateful=self._use_stateful_mode,  # Sử dụng stateful mode
                temperature=0.7,
                max_tokens=8192,
                response_mime_type="text/plain"  # Text response cho user
            )
            
            if error:
                error_str = str(error)
                
                # Kiểm tra nếu là lỗi global rate limit
                if "Rate limit:" in error_str and "requests/minute" in error_str:
                    logger.warning(f"Global rate limit hit: {error_str}")
                    
                    # Trả về thông báo cho user
                    rate_limit_msg = f"""⏱️ **Tạm thời quá tải**

Hệ thống đang xử lý nhiều yêu cầu đồng thời. Vui lòng đợi một chút rồi thử lại.

_(Giới hạn: 5 yêu cầu/phút để đảm bảo chất lượng phản hồi)_"""
                    
                    return {
                        'success': False,
                        'response': rate_limit_msg,
                        'intent': {'type': 'rate_limit'},
                        'metadata': {
                            'timestamp': datetime.now().isoformat(),
                            'rate_limited': True,
                            'error': error_str
                        }
                    }
            
            if error or not response_text:
                # === FALLBACK: Hệ thống tự trả lời khi AI không khả dụng ===
                logger.warning(f"AI unavailable ({error}), using system fallback response")
                fallback_response = self._generate_fallback_response(query_result, intent, ma_dot)
                
                # Thêm thông báo về đợt xếp đầu response
                final_fallback_response = (dot_notice_section + fallback_response) if dot_notice_section else fallback_response
                
                self.conversation_history.append({
                    'role': 'user',
                    'content': message,
                    'timestamp': datetime.now().isoformat()
                })
                self.conversation_history.append({
                    'role': 'assistant', 
                    'content': final_fallback_response,
                    'timestamp': datetime.now().isoformat()
                })
                
                return {
                    'success': True,
                    'response': final_fallback_response,
                    'intent': intent,
                    'metadata': {
                        'model': 'system_fallback',
                        'timestamp': datetime.now().isoformat(),
                        'note': 'AI không khả dụng, hệ thống tự sinh câu trả lời từ kết quả truy vấn'
                    }
                }
            
            # Lưu vào local history (backup cho stateless fallback)
            self.conversation_history.append({
                'role': 'user',
                'content': message,
                'timestamp': datetime.now().isoformat()
            })
            
            # Thêm thông báo về đợt xếp đầu response nếu có
            final_response = (dot_notice_section + response_text) if dot_notice_section else response_text
            
            self.conversation_history.append({
                'role': 'assistant', 
                'content': final_response,
                'timestamp': datetime.now().isoformat()
            })
            
            return {
                'success': True,
                'response': final_response,
                'intent': intent,
                'metadata': {
                    'model': self.model,
                    'timestamp': datetime.now().isoformat(),
                    'interaction_id': interaction_id,  # Lưu interaction_id cho debugging
                    'stateful_mode': self._use_stateful_mode
                }
            }
            
        except Exception as e:
            logger.error(f"Chatbot error: {e}")
            return {
                'success': False,
                'response': f"Đã xảy ra lỗi: {str(e)}",
                'error': str(e)
            }
    
    def get_conversation_history(self) -> List[Dict]:
        """Lấy lịch sử hội thoại"""
        return self.conversation_history


# Singleton instance
_chatbot_instance = None

def get_chatbot() -> ScheduleChatbot:
    """Lấy singleton instance của chatbot"""
    global _chatbot_instance
    if _chatbot_instance is None:
        _chatbot_instance = ScheduleChatbot()
    return _chatbot_instance
