"""
LLM AI cho sắp xếp lịch học
"""

import os
import re
import logging
import json
from google import genai
from google.genai import types
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class TokenCounter:
    """Utility class để đếm tokens và thống kê sử dụng"""
    
    def __init__(self):
        self.usage_history: List[Dict[str, Any]] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
    
    def log_usage(self, prompt_len: int, context_len: int, max_output: int, response_len: int = 0, 
                  timestamp: str = None, model: str = "gemini-2.5-flash"):
        """
        Log thống kê token usage
        
        Args:
            prompt_len: Độ dài text của system instruction + user prompt (chars)
            context_len: Độ dài dữ liệu context (chars)
            max_output: Max output tokens được request
            response_len: Độ dài response nhận được (chars)
            timestamp: Thời gian request
            model: Model name
        """
        # Ước tính token count (Google Gemini: ~1 token/4 chars cho text)
        estimated_input_tokens = (prompt_len + context_len) // 4
        estimated_output_tokens = response_len // 4 if response_len > 0 else max_output // 4
        
        usage_entry = {
            'timestamp': timestamp or datetime.now().isoformat(),
            'model': model,
            'prompt_chars': prompt_len,
            'context_chars': context_len,
            'response_chars': response_len,
            'estimated_input_tokens': estimated_input_tokens,
            'estimated_output_tokens': estimated_output_tokens,
            'max_output_tokens': max_output,
            'total_estimated_tokens': estimated_input_tokens + estimated_output_tokens
        }
        
        self.usage_history.append(usage_entry)
        self.total_input_tokens += estimated_input_tokens
        self.total_output_tokens += estimated_output_tokens
        
        return usage_entry
    
    def get_summary(self) -> Dict[str, Any]:
        """Lấy thống kê tổng hợp"""
        return {
            'total_requests': len(self.usage_history),
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_tokens': self.total_input_tokens + self.total_output_tokens,
            'average_input_tokens': self.total_input_tokens // max(1, len(self.usage_history)),
            'average_output_tokens': self.total_output_tokens // max(1, len(self.usage_history)),
            'usage_history': self.usage_history
        }
    
    def export_report(self, filepath: str = None) -> str:
        """Export thống kê ra markdown file"""
        summary = self.get_summary()
        
        report = f"""# 📊 LLM Token Usage Report
Generated: {datetime.now().isoformat()}

## Summary Statistics
- **Total Requests**: {summary['total_requests']}
- **Total Input Tokens**: {summary['total_input_tokens']:,}
- **Total Output Tokens**: {summary['total_output_tokens']:,}
- **Total Tokens**: {summary['total_tokens']:,}
- **Average Input Tokens/Request**: {summary['average_input_tokens']:,}
- **Average Output Tokens/Request**: {summary['average_output_tokens']:,}

## Detailed Usage History
| # | Timestamp | Model | Input (chars) | Context (chars) | Response (chars) | Est. Input Tokens | Est. Output Tokens | Total Est. Tokens |
|---|-----------|-------|---------------|-----------------|------------------|-------------------|-------------------|-------------------|
"""
        for i, usage in enumerate(summary['usage_history'], 1):
            report += f"| {i} | {usage['timestamp']} | {usage['model']} | {usage['prompt_chars']:,} | {usage['context_chars']:,} | {usage['response_chars']:,} | {usage['estimated_input_tokens']:,} | {usage['estimated_output_tokens']:,} | {usage['total_estimated_tokens']:,} |\n"
        
        report += f"\n## Token Estimation Notes\n- Using approximation: 1 token ≈ 4 characters (Gemini)\n- Actual token counts may vary\n- View Gemini API console for accurate counts\n"
        
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"📊 Token usage report exported to {filepath}")
        
        return report


class ScheduleAI:
    """LLM AI cho sắp xếp lịch học"""
    
    def __init__(self):
        # Khởi tạo client theo tài liệu chính thức
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.token_counter = TokenCounter()
        
        # System instruction cho SQL query generation
        self.sql_system_instruction = """Bạn là một chuyên gia về sắp xếp thời khóa biểu cho trường đại học với khả năng đọc và phân tích dữ liệu từ CSDL_TKB (Cơ sở dữ liệu Thời Khóa Biểu). 

**QUAN TRỌNG**: 
1. Bạn CHỈ được đưa ra SQL queries. KHÔNG được tự suy đoán kết quả. 
2. Hệ thống sẽ tự động thực thi queries và trả về kết quả thực tế từ database.
3. Luôn sử dụng DISTINCT để tránh duplicate records.
4. Khi tìm kiếm tên môn học, sử dụng LIKE với % để tìm kiếm gần đúng.

==== CẤU TRÚC DATABASE THỰC TẾ ====
- tb_KHOA: Quản lý khoa (MaKhoa VARCHAR(12), TenKhoa NVARCHAR(200))
- tb_BO_MON: Bộ môn thuộc khoa (MaBoMon VARCHAR(12), MaKhoa VARCHAR(12), TenBoMon NVARCHAR(200))
- tb_GIANG_VIEN: Giảng viên thuộc bộ môn (MaGV VARCHAR(12), MaBoMon VARCHAR(12), TenGV NVARCHAR(200), LoaiGV NVARCHAR(100), GhiChu NVARCHAR(300), Email VARCHAR(200))
- tb_DUKIEN_DT: Dự kiến đào tạo theo học kỳ (MaDuKienDT VARCHAR(15), NamHoc VARCHAR(9), HocKy TINYINT, NgayBD SMALLDATETIME, NgayKT SMALLDATETIME, MoTaHocKy NVARCHAR(100))
- tb_MON_HOC: Môn học (MaMonHoc VARCHAR(10), TenMonHoc NVARCHAR(200), SoTinChi TINYINT, SoTietLT TINYINT, SoTietTH TINYINT, SoTuan TINYINT DEFAULT 15)
- tb_GV_DAY_MON: Giảng viên đủ điều kiện dạy môn (MaMonHoc VARCHAR(10), MaGV VARCHAR(12))
- tb_KHUNG_TG: Khung thời gian các ca (MaKhungGio TINYINT, TenCa NVARCHAR(50), GioBatDau TIME, GioKetThuc TIME, SoTiet TINYINT DEFAULT 3)
- tb_TIME_SLOT: Slot thời gian (TimeSlotID VARCHAR(10), Thu TINYINT 2-8, Ca TINYINT 1-5) - Thu từ 2-8 (T2-CN), Ca từ 1-5
- tb_PHONG_HOC: Phòng học (MaPhong VARCHAR(12), LoaiPhong NVARCHAR(100), SucChua SMALLINT, ThietBi NVARCHAR(400), GhiChu NVARCHAR(200))
- tb_RANG_BUOC_MEM: Ràng buộc mềm có trọng số (MaRangBuoc VARCHAR(15), TenRangBuoc NVARCHAR(200), MoTa NVARCHAR(500), TrongSo FLOAT)
- tb_LOP_MONHOC: Lớp môn học cụ thể (MaLop VARCHAR(12), MaMonHoc VARCHAR(10), Nhom_MH TINYINT, To_MH TINYINT, SoLuongSV SMALLINT, HeDaoTao NVARCHAR(200), NgonNgu NVARCHAR(50), ThietBiYeuCau NVARCHAR(400), SoCaTuan TINYINT DEFAULT 1)
- tb_DOT_XEP: Đợt xếp thời khóa biểu (MaDot VARCHAR(20), MaDuKienDT VARCHAR(15), TenDot NVARCHAR(200), TrangThai VARCHAR(20): DRAFT/RUNNING/LOCKED/PUBLISHED, NgayTao DATETIME2, NgayKhoa DATETIME2)
- tb_PHAN_CONG: Phân công giảng viên dạy lớp (MaDot VARCHAR(20), MaLop VARCHAR(12), MaGV VARCHAR(12))
- tb_RANG_BUOC_TRONG_DOT: Áp dụng ràng buộc mềm trong đợt (MaDot VARCHAR(20), MaRangBuoc VARCHAR(15))
- tb_NGUYEN_VONG: Nguyện vọng giảng viên (MaGV VARCHAR(12), MaDot VARCHAR(20), TimeSlotID VARCHAR(10))
- tb_TKB: Thời khóa biểu chính thức (MaTKB VARCHAR(15), MaDot VARCHAR(20), MaLop VARCHAR(12), MaPhong VARCHAR(12), TimeSlotID VARCHAR(10), TuanHoc VARCHAR(64), NgayBD SMALLDATETIME, NgayKT SMALLDATETIME)

==== HƯỚNG DẪN TRẢ LỜI ====
1. Phân tích yêu cầu của người dùng
2. Đưa ra SQL query chính xác và hoàn chỉnh
3. Giải thích ngắn gọn logic của query
4. KHÔNG tự suy đoán kết quả - để hệ thống thực thi

**Định dạng trả lời:**
```sql
[SQL_QUERY_HERE]
```

**Giải thích:** [Mô tả ngắn gọn logic]

**Lưu ý:** Hệ thống sẽ tự động thực thi query và hiển thị kết quả thực tế."""

        # System instruction cho schedule generation (hybrid optimized)
        self.schedule_system_instruction = """Task: Generate Class Schedule (JSON Output)
OUTPUT (JSON Only): {"schedule": [{"class": "...", "room": "...", "slot": "..."}]}

CRITICAL FORMATTING RULES
JSON Only: Output ONLY the JSON object. No explanations.
CLASS ID: Must be an EXACT COPY of the class.id (e.g., LOP-00000012).
SLOT FORMAT: Must STRICTLY adhere to T[2-7]-C[1-5] (e.g., T2-C1, T7-C5). T8 (Sunday) is NOT allowed.
COUNT: Total assignments in schedule MUST equal SUM(class.sessions).

INPUTS & CONTEXT
Inputs: classes (with sessions, type, students, equipment_required), rooms (LT/TH), teacher_constraints, soft_constraints.
Context: room_capacity[], room_type[], room_equipment[], teacher_preferences[].

SCHEDULING PRIORITIES (Strict Order)
PRIORITY 1: HARD CONSTRAINTS (MANDATORY)
Violation = Invalid Schedule.

HC-01 (Teacher Conflict): One teacher, one slot.
HC-02 (Room Conflict): One room, one slot.
HC-03 (Room Type): class.type ("LT"/"TH") MUST match room_type.
HC-04 (Capacity): room_capacity[room_id] MUST be >= class.students.
HC-05 (Equipment): room_equipment[room_id] MUST contain ALL class.equipment_required.
HC-06 (Teacher Busy): DO NOT schedule during teacher.busy_slots.
HC-07 (Teacher Limits): Respect max_slots_per_day and max_slots_per_week.
HC-08 (Session Rules - CRITICAL):
A class must have EXACTLY sessions assignments.
If sessions=2: MUST be a consecutive pair on the same day (e.g., T3-C1 & T3-C2, or T4-C3 & T4-C4).
If sessions=3: MUST be a consecutive trio on the same day (e.g., T5-C1, T5-C2, T5-C3).

Consecutive Rule: Valid groups are (C1,C2) and (C3,C4).
FORBIDDEN: Do not schedule across lunch (e.g., T2-C2 & T2-C3 is INVALID).

PRIORITY 2: TEACHER PREFERENCES (Semi-Hard)
Maximize assignments to teacher_preferences.preferred_slots.
ONLY violate if it conflicts with Priority 1 (Hard Constraints).
DO NOT violate preference to optimize Priority 3 or 4.

PRIORITY 3: TEACHER COMPACTNESS (Optimize for Teacher)
Goal: Minimize the number of days each teacher must come to campus.
Rule: Try to group all classes for a single teacher into the fewest days possible.
(Example: If a teacher has 3 classes, scheduling them on T2 and T3 is better than on T2, T4, and T5).
This is secondary to P1 (Hard Constraints) and P2 (Preferences).

PRIORITY 4: SCHOOL DISTRIBUTION & SOFT CONSTRAINTS (Low)
School Distribution: Spread the total school schedule load EVENLY across T2-T7 (Mon-Sat). Avoid concentrating >70% of all classes on 1-2 days. (This balances the school's resources).
Soft Constraints: After all above rules are met, optimize to minimize penalties based on soft_constraints weights (e.g., "Minimize Saturday")."""

    def generate_sql_query(self, user_prompt: str) -> str:
        """
        Tạo SQL query từ user prompt - Sử dụng cho chat/query
        Trả về text/plain
        """
        config = types.GenerateContentConfig(
            temperature=0,
            top_p=0.95,
            top_k=64,
            max_output_tokens=8192,
            response_mime_type="text/plain",
            system_instruction=self.sql_system_instruction
        )
        
        response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_prompt,
            config=config
        )
        
        return response.text
    
    def generate_schedule_json(self, context_prompt: str) -> dict:
        """
        Tạo thời khóa biểu từ context - Sử dụng cho auto-scheduling
        Trả về application/json
        
        Args:
            context_prompt: Full context string chứa:
                - Classes info (ma_lop, so_sv, so_ca_tuan, etc)
                - Rooms info (ma_phong, loai_phong, suc_chua)
                - TimeSlots info (time_slot_id, T2-C1, etc)
                - Teacher assignments (ma_gv)
                - Constraints & preferences
        
        Returns:
            Dict với format: {"schedule": [{"class": "ma_lop", "room": "ma_phong", "slot": "T2-C1"}, ...]}
        """
        # 📊 Log token usage stats TRƯỚC request
        prompt_len = len(self.schedule_system_instruction)
        context_len = len(context_prompt)
        max_output_tokens = 50000  
        
        logger.info(f"📊 === TOKEN STATS (BEFORE REQUEST) ===")
        logger.info(f"   System Instruction: {prompt_len:,} chars (est. {prompt_len//4:,} tokens)")
        logger.info(f"   User Context: {context_len:,} chars (est. {context_len//4:,} tokens)")
        logger.info(f"   Combined Input: {prompt_len + context_len:,} chars (est. {(prompt_len + context_len)//4:,} tokens)")
        logger.info(f"   Max Output Tokens Requested: {max_output_tokens:,}")
        logger.warning(f"⚠️  IMPORTANT: If response is still truncated, consider reducing context size or max_output_tokens")
        
        config = types.GenerateContentConfig(
            temperature=0.5,  # Cao hơn một chút để linh hoạt trong scheduling
            top_p=0.95,
            top_k=40,
            max_output_tokens=max_output_tokens,  # Tăng cao để chứa 216 schedules
            response_mime_type="application/json",  # Yêu cầu trả về JSON
            system_instruction=self.schedule_system_instruction
        )
        
        response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=context_prompt,
            config=config
        )
        
        # 🔴 CHECK: response.text is None?
        if response.text is None:
            logger.error(f"❌ CRITICAL: response.text is None!")
            logger.error(f"   Response object: {response}")
            logger.error(f"   Response candidates: {getattr(response, 'candidates', 'N/A')}")
            
            # Get finish_reason to understand why response is empty
            finish_reason = None
            try:
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    finish_reason = getattr(candidate, 'finish_reason', None)
                    finish_message = getattr(candidate, 'finish_message', None)
                    content = getattr(candidate, 'content', None)
                    
                    logger.error(f"   Candidates count: {len(response.candidates)}")
                    logger.error(f"   Finish reason: {finish_reason}")
                    logger.error(f"   Finish message: {finish_message}")
                    logger.error(f"   Content: {content}")
                    
                    if content:
                        logger.error(f"   Content parts: {getattr(content, 'parts', [])}")
            except Exception as e:
                logger.warning(f"   Could not extract candidate info: {e}")
            
            # Return error response with finish reason
            error_msg = f'LLM response.text is None'
            if finish_reason:
                error_msg += f' (finish_reason: {finish_reason})'
            
            fallback = {
                'schedule': [],
                'validation': {'errors': []},
                'metrics': {},
                'errors': [error_msg]
            }
            logger.warning(f"⚠️ Using fallback response due to None text")
            return fallback
            
        # 🔴 CHECK: response.text is empty string?
        if not response.text or response.text.strip() == '':
            logger.error(f"❌ CRITICAL: response.text is empty!")
            fallback = {
                'schedule': [],
                'validation': {'errors': []},
                'metrics': {},
                'errors': ['LLM response.text is empty']
            }
            logger.warning(f"⚠️ Using fallback response due to empty text")
            return fallback
            
        
        # �📊 Log token usage stats SAU khi nhận response
        response_len = len(response.text)
        usage_entry = self.token_counter.log_usage(
            prompt_len=prompt_len,
            context_len=context_len,
            max_output=max_output_tokens,
            response_len=response_len,
            model='gemini-2.5-flash'
        )
        
        logger.info(f"� === TOKEN STATS (AFTER RESPONSE) ===")
        logger.info(f"   Response Length: {response_len:,} chars (est. {response_len//4:,} tokens)")
        logger.info(f"   Total Input (Estimated): {usage_entry['estimated_input_tokens']:,} tokens")
        logger.info(f"   Total Output (Estimated): {usage_entry['estimated_output_tokens']:,} tokens")
        logger.info(f"   Total (Estimated): {usage_entry['total_estimated_tokens']:,} tokens")
        
        logger.info(f"🔍 AI raw response length: {len(response.text)} chars")
        logger.info(f"🔍 AI response preview (first 500 chars): {response.text[:500]}...")
        logger.info(f"🔍 AI response suffix (last 200 chars): ...{response.text[-200:]}")
        
        # Check if response looks truncated (ends with incomplete JSON)
        if response.text.strip().endswith(',') or response.text.strip().endswith('[') or response.text.strip().endswith('{'):
            logger.warning(f"⚠️ TRUNCATED: Response ends with incomplete character!")
            logger.info(f"   Last 300 chars: {response.text[-300:]}")
            
            # Check finish_reason to confirm truncation
            try:
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    finish_reason = getattr(candidate, 'finish_reason', None)
                    logger.error(f"❌ Response was truncated! finish_reason: {finish_reason}")
                    logger.error(f"   Response length: {len(response.text)} chars (max was: 20000 tokens ≈ 80000 chars)")
            except Exception as e:
                logger.debug(f"Could not check finish_reason: {e}")
        
        # Try to parse JSON - nếu không thành công, try to extract JSON từ response
        try:
            parsed = json.loads(response.text)
            logger.info(f"✅ Parsed JSON successfully. Keys: {list(parsed.keys())}")
            return parsed
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Failed to parse JSON directly at position {e.pos}: {e.msg}")
            logger.info(f"🔍 Response text around error (±100 chars): ...{response.text[max(0, e.pos-100):e.pos+100]}...")
            logger.info(f"🔍 Response length: {len(response.text)} chars")
            logger.info(f"🔍 Trying to extract JSON from response...")
            
            # Try to find JSON block in response - be more aggressive
            import re
            
            # Strategy: Try to find the main JSON object by looking for key patterns
            # 1. Try to find {"schedule": [...] as the main object start
            # 2. Try to balance braces to find valid JSON
            
            extracted_json = None
            
            # Method 1: Look for JSON starting with "schedule" key
            schedule_match = re.search(r'\{\s*"schedule"\s*:', response.text)
            if schedule_match:
                start_pos = schedule_match.start()
                logger.info(f"🔍 Found 'schedule' key at position {start_pos}")
                
                # Try to extract from this position by counting braces
                brace_count = 0
                in_string = False
                escape_next = False
                end_pos = start_pos
                
                for i in range(start_pos, len(response.text)):
                    char = response.text[i]
                    
                    if escape_next:
                        escape_next = False
                        continue
                    
                    if char == '\\':
                        escape_next = True
                        continue
                    
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue
                    
                    if not in_string:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos = i + 1
                                break
                
                if brace_count == 0:
                    json_str = response.text[start_pos:end_pos]
                    logger.info(f"🔍 Extracted JSON by brace matching ({len(json_str)} chars)")
                    
                    try:
                        # Try to fix common JSON issues before parsing
                        # 1. Fix unterminated strings by finding incomplete quotes
                        json_str = re.sub(r',\s*}', '}', json_str)
                        json_str = re.sub(r',\s*]', ']', json_str)
                        
                        parsed = json.loads(json_str)
                        logger.info(f"✅ Successfully extracted JSON via brace matching")
                        return parsed
                    except json.JSONDecodeError as e2:
                        logger.warning(f"⚠️ Brace matching extraction failed: {e2}")
                        extracted_json = None
            
            # Method 2: Try regex patterns if Method 1 failed
            if not extracted_json:
                patterns = [
                    (r'\{\s*"schedule"[\s\S]*\}(?=\s*(?:,|}|]|$))', 'schedule key pattern'),
                    (r'\{[^{}]*"schedule"[^{}]*\}', 'nested pattern'),
                ]
                
                for pattern, desc in patterns:
                    try:
                        json_match = re.search(pattern, response.text)
                        if json_match:
                            json_str = json_match.group(0)
                            logger.info(f"🔍 Found potential JSON via {desc} ({len(json_str)} chars)")
                            
                            # Try to fix common JSON issues
                            json_str = re.sub(r',\s*}', '}', json_str)
                            json_str = re.sub(r',\s*]', ']', json_str)
                            
                            parsed = json.loads(json_str)
                            logger.info(f"✅ Successfully extracted JSON via {desc}")
                            return parsed
                    except json.JSONDecodeError as e2:
                        logger.warning(f"⚠️ {desc} extraction failed: {e2}")
                        continue
            
            logger.error(f"❌ No valid JSON found in response after multiple extraction attempts")
            # Fallback: create empty schedule structure
            logger.warning(f"⚠️ Creating fallback schedule structure")
            fallback = {
                'schedule': [],
                'validation': {'errors': []},
                'metrics': {},
                'errors': [f'Failed to parse LLM response - Invalid JSON at position {e.pos}']
            }
            logger.info(f"🔍 Using fallback response with {len(fallback['errors'])} errors")
            return fallback
    
    def _extract_sql_from_response(self, response_text: str) -> List[str]:
        """Trích xuất các SQL queries từ response của AI"""
        # Tìm tất cả SQL queries trong code blocks
        sql_pattern = r'```sql\s*(.*?)\s*```'
        matches = re.findall(sql_pattern, response_text, re.DOTALL | re.IGNORECASE)
        
        # Làm sạch và lọc các queries
        queries = []
        for match in matches:
            query = match.strip()
            
            # Chỉ làm sạch cơ bản, không sửa nhiều để tránh làm hỏng SQL
            # 1. Loại bỏ comments
            query = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
            query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
            
            # 2. Xử lý tiếng Việt - thêm N prefix cho Unicode strings
            query = self._fix_vietnamese_strings(query)
            
            # 3. Chỉ chuẩn hóa whitespace cơ bản - thay nhiều space/tab/newline thành 1 space
            query = re.sub(r'\s+', ' ', query).strip()
            
            # 4. Đảm bảo kết thúc bằng dấu ;
            if query and not query.endswith(';'):
                query = query + ';'
            
            if query and len(query) > 15:  # Bỏ qua queries quá ngắn
                queries.append(query)
                
        return queries
    
    def _fix_vietnamese_strings(self, query: str) -> str:
        """Thêm N prefix cho các chuỗi tiếng Việt trong SQL"""
        # Tìm tất cả chuỗi trong dấu nháy đơn
        def replace_vietnamese_string(match):
            string_content = match.group(1)
            
            # Kiểm tra xem chuỗi có chứa ký tự tiếng Việt không
            vietnamese_chars = 'àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđĐÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴ'
            
            if any(char in vietnamese_chars for char in string_content):
                # Kiểm tra xem đã có N prefix chưa
                full_match = match.group(0)
                if not full_match.startswith('N\'') and not full_match.startswith('n\''):
                    return f"N'{string_content}'"
                    
            return match.group(0)
        
        # Tìm và thay thế các chuỗi trong dấu nháy đơn (không có N prefix)
        # Pattern này tìm: 'string_content' nhưng không có N hoặc n đứng trước
        pattern = r"(?<!N)(?<!n)'([^']*?)'"
        query = re.sub(pattern, replace_vietnamese_string, query)
        
        return query

    def get_soft_constraints_prompt(self, ma_dot: str = None) -> str:
        """
        Tạo SQL query để lấy ràng buộc mềm cho đợt xếp lịch.
        Ưu tiên: tb_RANG_BUOC_TRONG_DOT > tb_RANG_BUOC_MEM (mặc định)
        
        Args:
            ma_dot: Mã đợt xếp lịch. Nếu None, chỉ lấy ràng buộc mặc định
            
        Returns:
            SQL query string để lấy danh sách ràng buộc mềm
        """
        if ma_dot:
            query = f"""
            -- Lấy ràng buộc mềm cho đợt {ma_dot}
            SELECT 
                rb.MaRangBuoc,
                rb.TenRangBuoc,
                rb.MoTa,
                rb.TrongSo
            FROM tb_RANG_BUOC_MEM rb
            INNER JOIN tb_RANG_BUOC_TRONG_DOT rbtd 
                ON rb.MaRangBuoc = rbtd.MaRangBuoc
            WHERE rbtd.MaDot = N'{ma_dot}'
            ORDER BY rb.TrongSo DESC;
            """
        else:
            query = """
            -- Lấy tất cả ràng buộc mềm mặc định
            SELECT 
                MaRangBuoc,
                TenRangBuoc,
                MoTa,
                TrongSo
            FROM tb_RANG_BUOC_MEM
            ORDER BY TrongSo DESC;
            """
        
        return query.strip()
    
    def format_constraints_for_ai(self, constraints_data: List[dict]) -> str:
        """
        Format dữ liệu ràng buộc mềm từ SQL thành chuỗi cho AI context
        
        Args:
            constraints_data: List of dicts with keys: MaRangBuoc, TenRangBuoc, MoTa, TrongSo
            
        Returns:
            Formatted string for AI prompt
        """
        if not constraints_data:
            return "No soft constraints specified - use default optimization."
        
        lines = ["SOFT CONSTRAINTS (from database):"]
        for idx, c in enumerate(constraints_data, 1):
            lines.append(
                f"{idx}. {c['TenRangBuoc']} (weight={c['TrongSo']:.2f}): {c['MoTa']}"
            )
        
        return "\n".join(lines)
    
    def format_schedule_context_for_ai(self, prepared_data: dict) -> str:
        """
        Format dữ liệu scheduling từ prepare_data_for_llm() thành context cho LLM
        
        Args:
            prepared_data: Dict từ schedule_generator_llm._prepare_data_for_llm()
                Chứa: rooms_by_type, timeslots, dot_xep_list, slot_mapping, etc
        
        Returns:
            Full context string để đưa vào LLM prompt
        """
        lines = []
        
        # 1. Rooms format
        rooms_lt = prepared_data.get('rooms_by_type', {}).get('LT', [])
        rooms_th = prepared_data.get('rooms_by_type', {}).get('TH', [])
        
        lines.append("🏫 PHÒNG HỌC (Rooms):")
        lines.append(f"  LT (Lý Thuyết - Theory): {len(rooms_lt)} phòng")
        for room in rooms_lt[:5]:
            lines.append(f"    - {room['ma_phong']} (capacity: {room['suc_chua']})")
        if len(rooms_lt) > 5:
            lines.append(f"    ... and {len(rooms_lt) - 5} more")
        
        lines.append(f"  TH (Thực Hành - Practice): {len(rooms_th)} phòng")
        for room in rooms_th[:5]:
            lines.append(f"    - {room['ma_phong']} (capacity: {room['suc_chua']})")
        if len(rooms_th) > 5:
            lines.append(f"    ... and {len(rooms_th) - 5} more")
        
        # 2. TimeSlots format
        timeslots = prepared_data.get('timeslots', [])
        lines.append(f"\n⏰ TIME SLOTS: {len(timeslots)} slots")
        lines.append("  Format: T{day}-C{slot}")
        lines.append("  Days: T2-T7 (Monday-Saturday)")
        lines.append("  Slots: C1-C5 (periods)")
        for ts in timeslots[:10]:
            lines.append(f"    - {ts['id']}")
        if len(timeslots) > 10:
            lines.append(f"  ... and {len(timeslots) - 10} more")
        
        # 3. Classes & Teachers format
        total_classes = 0
        total_gv = set()
        total_sessions = 0
        
        for dot_info in prepared_data.get('dot_xep_list', []):
            classes = dot_info.get('phan_cong', [])  # FIX: Dùng 'phan_cong' thay vì 'classes'
            total_classes += len(classes)
            for cls in classes:
                total_gv.add(cls.get('ma_gv'))
                total_sessions += cls.get('so_ca_tuan', 1)
        
        lines.append(f"\n👥 CLASSES & TEACHERS:")
        lines.append(f"  Total classes: {total_classes}")
        lines.append(f"  Total sessions to assign: {total_sessions}")
        lines.append(f"  Total teachers: {len(total_gv)}")
        
        # 4. Stats
        stats = prepared_data.get('stats', {})
        lines.append(f"\n📊 STATS:")
        lines.append(f"  Total rooms: {stats.get('total_rooms', 0)}")
        lines.append(f"  Total timeslots: {stats.get('total_timeslots', 0)}")
        
        # 5. Room Type & Capacity mapping for HC-05 & HC-04 validation
        lines.append(f"\n🏷️ ROOM DETAILS (for constraint checking):")
        lines.append("  room_type: {")
        for room_type in ['LT', 'TH']:
            for room in prepared_data.get('rooms_by_type', {}).get(room_type, [])[:3]:
                lines.append(f'    "{room["ma_phong"]}": "{room_type}",')
        lines.append("    ... (all rooms)")
        lines.append("  }")
        
        lines.append("  room_capacity: {")
        for room_type in ['LT', 'TH']:
            for room in prepared_data.get('rooms_by_type', {}).get(room_type, [])[:3]:
                lines.append(f'    "{room["ma_phong"]}": {room["suc_chua"]},')
        lines.append("    ... (all rooms)")
        lines.append("  }")
        
        lines.append("  room_equipment: {")
        for room_type in ['LT', 'TH']:
            for room in prepared_data.get('rooms_by_type', {}).get(room_type, [])[:3]:
                equipment = room.get('thiet_bi', 'N/A')
                lines.append(f'    "{room["ma_phong"]}": "{equipment}",')
        lines.append("    ... (all rooms)")
        lines.append("  }")
        
        # 6. Class types for HC-05 validation
        lines.append(f"\n📚 CLASS TYPES (LT vs TH):")
        lt_count = 0
        th_count = 0
        for dot_info in prepared_data.get('dot_xep_list', []):
            for cls in dot_info.get('phan_cong', []):
                class_type = cls.get('loai_phong', 'LT')
                if class_type == 'TH':
                    th_count += 1
                else:
                    lt_count += 1
        lines.append(f"  LT classes: {lt_count}")
        lines.append(f"  TH classes: {th_count}")
        lines.append("  ⚠️ CRITICAL: TH classes MUST use TH rooms, LT classes MUST use LT rooms!")
        
        # 7. Teacher preferences (nguyện vọng GV)
        total_prefs = 0
        teacher_with_prefs = set()
        for dot_info in prepared_data.get('dot_xep_list', []):
            prefs = dot_info.get('preferences', [])
            total_prefs += len(prefs)
            for pref in prefs:
                teacher_with_prefs.add(pref.get('ma_gv'))
        
        if total_prefs > 0:
            lines.append(f"\n💚 TEACHER PREFERENCES:")
            lines.append(f"  Teachers with preferences: {len(teacher_with_prefs)}")
            lines.append(f"  Total preferred slots: {total_prefs}")
            lines.append("  Try to honor these when possible (soft constraint)")
        
        return "\n".join(lines)
    
    def export_token_report(self, filepath: str = None) -> str:
        """
        Export thống kê token usage ra markdown file
        
        Args:
            filepath: Đường dẫn file output (nếu None, sẽ lưu vào output/token_usage_report.md)
        
        Returns:
            Nội dung report dưới dạng string
        """
        if filepath is None:
            filepath = os.path.join(os.path.dirname(__file__), '../../output/token_usage_report.md')
        
        # Tạo thư mục nếu chưa tồn tại
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        report = self.token_counter.export_report(filepath)
        logger.info(f"📊 Token usage report exported to {filepath}")
        return report
    
    def get_token_summary(self) -> Dict[str, Any]:
        """Lấy thống kê token tóm tắt"""
        return self.token_counter.get_summary()