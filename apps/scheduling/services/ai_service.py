"""
AI Service for Scheduling System using Google Gemini
Migrated from src/ai/schedule_ai.py
"""

import os
import re
from google import genai
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class SchedulingAIService:
    """AI Service for scheduling using Google Gemini"""
    
    def __init__(self):
        """Initialize Gemini AI client"""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = os.getenv("AI_MODEL_NAME", "gemini-2.0-flash-exp")
        
        # System instructions
        self.sql_system_instruction = self._get_sql_system_instruction()
        self.schedule_system_instruction = self._get_schedule_system_instruction()
    
    def _get_sql_system_instruction(self) -> str:
        """Get system instruction for SQL query generation"""
        return """Bạn là một chuyên gia về sắp xếp thời khóa biểu cho trường đại học với khả năng đọc và phân tích dữ liệu từ CSDL_TKB (Cơ sở dữ liệu Thời Khóa Biểu). 

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
    
    def _get_schedule_system_instruction(self) -> str:
        """Get system instruction for schedule generation"""
        return """Assign classes to rooms + timeslots.

INPUT:
- classes: [{id, teacher, course, students, sessions, type: "LT"/"TH", credits, preferred_teachers, preferred_days}]
- rooms: {LT: [...], TH: [...]}
- timeslots: [...]
- teacher_constraints: {teacher_id: {max_slots_per_week, max_slots_per_day, busy_slots, wishes}}
- soft_constraints: [{name, description, weight}] (from tb_RANG_BUOC_MEM or tb_RANG_BUOC_TRONG_DOT)

🔴 CRITICAL OUTPUT COUNT RULE:
- EACH class appears EXACTLY `sessions` times in output
- If class has sessions=1 → create 1 assignment
- If class has sessions=2 → create 2 assignments (different slots)
- TOTAL output count MUST = sum of all sessions
- Example: 216 classes, each sessions=2 → output 432 assignments
- DO NOT create more or fewer assignments than required

🔴 CRITICAL DISTRIBUTION RULES:
- DISTRIBUTE classes EVENLY across ALL weekdays (Monday-Friday)
- Target: ~30-40 classes per day MAXIMUM
- DO NOT concentrate 70%+ classes on a single day
- Use ALL available timeslots (35 total: 7 days × 5 slots)
- Balance across Thu2, Thu3, Thu4, Thu5, Thu6 (Mon-Fri)

HARD CONSTRAINTS (MUST satisfy - violation = infeasible):
HC-01 ⭐ CRITICAL - Teacher Conflicts:
- One teacher CANNOT teach 2+ classes in same timeslot
- BEFORE assigning a slot, CHECK if that teacher already teaches at that time
- If conflict detected, IMMEDIATELY choose a DIFFERENT slot
- Track: teacher_schedule = {teacher_id: [assigned_slots]}

HC-02 ⭐ CRITICAL - Room Conflicts:
- One room CANNOT host 2+ classes at same timeslot
- BEFORE assigning a slot, CHECK if that room already used at that time
- If conflict detected, IMMEDIATELY choose a DIFFERENT slot
- Track: room_schedule = {room_id: [assigned_slots]}

HC-03 - Room Capacity:
- Room capacity >= class size (students count)

HC-04 - Room Features:
- Room must have required equipment (projector, lab tools, etc.)

HC-05 ⭐ CRITICAL - Lab Room Matching:
- Lab/Practice classes (To_MH > 0) MUST use practice rooms ("Thực hành")
- Lab/Practice classes CANNOT use theory rooms
- HOW TO IDENTIFY: Check To_MH field (Tổ Môn Học)
  * To_MH = 0 or NULL → Theory class (Lớp lý thuyết chung)
  * To_MH > 0 → Practice group (Tổ thực hành)

HC-06 ⭐ CRITICAL - Theory Room Matching:
- Theory classes (To_MH = 0 or NULL) MUST use theory rooms ("Lý thuyết")
- Theory classes SHOULD NOT use lab rooms (waste resources)
- IMPORTANT: A class with SoTietTH>0 but To_MH=0 is STILL a theory class!
  * Example: "Công nghệ phần mềm" has SoTietTH=30 but To_MH=0
  * This is a combined theory+practice class taught as ONE SESSION
  * It requires THEORY room (large capacity for full class)
  * Practice groups (To_MH=1,2,3...) are separate smaller sessions
- Exception: If no theory room available, can temporarily use lab room

HC-07 - Teacher Weekly Limit:
- Teacher max slots/week limit (if specified)
- NEVER schedule any teacher on a Sunday.

HC-08 - Teacher Daily Limit:
- Teacher max slots/day limit (if specified)

HC-09 - Preferred Courses:
- Respect teacher's preferred courses (if constraint enabled)

HC-10 - Preferred Days:
- Respect teacher's preferred teaching days (if constraint enabled)

HC-11 - Busy Slots:
- Do NOT schedule during teacher's busy slots (meetings, commitments)

HC-12 - Fixed Timeslots:
- Some courses require specific timeslots (e.g., homeroom at Monday morning)

HC-13 - Session-based Slot Assignment ⭐ CRITICAL:
- IMPORTANT: `sessions` (SoCaTuan) field is THE ONLY factor determining number of schedule entries
- Each class MUST have EXACTLY `sessions` number of assignments - NO MORE, NO LESS
- DO NOT confuse with SoTiet (periods per session) - that's different!
- DO NOT multiply sessions by any other factor

**EXAMPLES:**
1. If class has sessions=1 (most common):
   * Create EXACTLY 1 assignment for that class
   * One entry in schedule array
   * Example: {"class": "LOP-00000001", "room": "B401", "slot": "Thu2-Ca1"}
   * Even if SoTiet=3 (3 periods), still only 1 schedule entry!

2. If class has sessions=2 (rare):
   * Create EXACTLY 2 assignments for that class
   * Two entries in schedule array
   * MUST use consecutive slot pairs: (Ca1-Ca2) or (Ca3-Ca4) ONLY
   * DO NOT use (Ca2-Ca3) - this is INVALID
   * Same day, same room, but 2 different consecutive slots
   * Example: LOP-00000001 with sessions=2 (SoCaTuan=2) → create 2 entries:
     {"class": "LOP-00000001", "room": "B401", "slot": "Thu2-Ca1"}
     {"class": "LOP-00000001", "room": "B401", "slot": "Thu2-Ca2"}

**VERIFICATION:**
- Count unique class IDs in your output
- Must equal total number of classes
- sessions=1 means "this class meets once per week"
- One meeting = one schedule entry

SOFT CONSTRAINTS (Optimize with weights from SQL):
- Apply from tb_RANG_BUOC_TRONG_DOT for current batch if exists
- Otherwise use default from tb_RANG_BUOC_MEM
- Each constraint has: name, description, weight
- Examples: fairness, wish_satisfaction, compactness, resource_efficiency, morning_priority

ALGORITHM SUGGESTION:
1. Count total assignments needed: sum of all sessions
2. Group classes by teacher
3. For each class:
   - If sessions=1: assign to 1 slot
   - If sessions=2: assign to 2 consecutive slots (Ca1-Ca2 or Ca3-Ca4)
4. Distribute across days (Mon-Fri) to avoid concentration
5. Track assignments: {teacher: {day: [slots]}, room: {day: [slots]}}
6. Before each assignment:
   - CHECK teacher availability at that slot
   - CHECK room availability at that slot
   - If conflict → try different day/slot
5. Prioritize spreading across weekdays to avoid concentration

OUTPUT FORMAT:
{"schedule": [{"class": "LOP-xxx", "room": "Dxxx", "slot": "ThuX-CaY"}]}

🔴 CRITICAL - CLASS ID FORMATTING:
- COPY class IDs EXACTLY as provided in input
- DO NOT remove leading zeros (e.g., LOP-00000012 → LOP-0000012 is WRONG)
- DO NOT reformat or "simplify" IDs
- Use EXACT string from input classes[i].id field
- Example: If input has "LOP-00000001", output MUST be "LOP-00000001" (8 digits after dash)

IMPORTANT:
- Each schedule item has 3 fields: class, room, slot
- DO NOT include "teacher" field (already in tb_PHAN_CONG database)
- NO explanations, NO comments
- Pure JSON only"""
    
    def generate_sql_query(self, user_request: str, db_context: str = "") -> str:
        """
        Generate SQL query from natural language request
        
        Args:
            user_request: Natural language request from user
            db_context: Database context information
            
        Returns:
            SQL query string or AI response
        """
        try:
            prompt = f"{db_context}\n\n{user_request}" if db_context else user_request
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    'system_instruction': self.sql_system_instruction,
                    'temperature': 0,
                }
            )
            
            return response.text if response else ""
        
        except Exception as e:
            logger.error(f"Error generating SQL query: {e}")
            return f"Error: {str(e)}"
    
    def extract_sql_from_response(self, ai_response: str) -> List[str]:
        """
        Extract SQL queries from AI response
        
        Args:
            ai_response: Full AI response text
            
        Returns:
            List of extracted SQL queries
        """
        # Pattern to match SQL code blocks
        pattern = r'```sql\s*(.*?)\s*```'
        matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
        
        if matches:
            return [match.strip() for match in matches if match.strip()]
        
        # Fallback: try to find SELECT/INSERT/UPDATE/DELETE statements
        sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH']
        lines = ai_response.split('\n')
        queries = []
        current_query = []
        
        for line in lines:
            stripped = line.strip()
            if any(stripped.upper().startswith(kw) for kw in sql_keywords):
                if current_query:
                    queries.append('\n'.join(current_query))
                current_query = [line]
            elif current_query:
                current_query.append(line)
        
        if current_query:
            queries.append('\n'.join(current_query))
        
        return queries
    
    def generate_schedule_with_ai(self, scheduling_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate optimal schedule using AI
        
        Args:
            scheduling_data: Dictionary containing:
                - classes: List of classes to schedule
                - rooms: Available rooms
                - timeslots: Available time slots
                - constraints: Hard and soft constraints
                
        Returns:
            Dictionary with schedule assignments
        """
        try:
            import json
            
            prompt = f"""Generate optimal schedule with this data:
            
{json.dumps(scheduling_data, ensure_ascii=False, indent=2)}

Return JSON format:
{{
  "assignments": [
    {{"class_id": "...", "room_id": "...", "timeslot_id": "...", "week": 1}},
    ...
  ],
  "metrics": {{
    "total_classes": ...,
    "constraints_satisfied": ...,
    "quality_score": ...
  }}
}}
"""
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    'system_instruction': self.schedule_system_instruction,
                    'temperature': 0.3,
                    'response_mime_type': 'application/json',
                }
            )
            
            if response and response.text:
                return json.loads(response.text)
            
            return {"error": "No response from AI"}
        
        except Exception as e:
            logger.error(f"Error generating schedule: {e}")
            return {"error": str(e)}
