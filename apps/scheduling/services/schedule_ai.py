"""
LLM AI cho sắp xếp lịch học
"""

import os
import re
from google import genai
from google.genai import types
from typing import List


class ScheduleAI:
    """LLM AI cho sắp xếp lịch học"""
    
    def __init__(self):
        # Khởi tạo client theo tài liệu chính thức
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
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

        # System instruction cho schedule generation (compact, English)
        self.schedule_system_instruction = """Assign classes to rooms + timeslots.

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

HC-03 ⭐ CRITICAL - Room Capacity:
- Room capacity MUST be >= class size (students count)
- Example: 80-student class → needs room with capacity >= 80
- Check: context['room_capacity'][room_id] >= class['students']
- DO NOT assign 80-student class to 45-capacity room

HC-04 ⭐ CRITICAL - Room Equipment:
- Room MUST have ALL required equipment from class
- Example: Class needs "Máy chiếu, Micro" → room MUST have both
- Check: context['room_equipment'][room_id] contains all items from class['equipment_required']
- Equipment matching is case-insensitive and flexible (substring match)
- DO NOT assign class to room missing required equipment

HC-05 ⭐ CRITICAL - Room Type Matching (LT vs TH):
- RULE: If class.type == "LT" → room MUST be in rooms['LT']
- RULE: If class.type == "TH" → room MUST be in rooms['TH']
- DO NOT ASSIGN: TH class to LT room (this is HC-05 violation)
- DO NOT ASSIGN: LT class to TH room
- Use context['room_type'][room_id] to verify room type

HC-06 - Theory Room Priority:
- Large classes (full cohorts) should use theory rooms
- Small practice groups use practice rooms
- Check class.type field in input

HC-07 - Teacher Weekly Limit:
- Teacher max slots/week limit (if specified)
- NEVER schedule any teacher on Sunday.

HC-08 - Teacher Daily Limit:
- Teacher max slots/day limit (if specified)

HC-09 - Preferred Courses:
- Respect teacher's preferred courses (if constraint enabled)

HC-10 ⭐⭐ TEACHER PREFERENCE (NguyenVong) = SEMI-HARD CONSTRAINT:
- Satisfy teacher preferences BEFORE soft constraints
- Try best effort to schedule at preferred slots (from tb_NGUYEN_VONG)
- Only violate IF conflict with HC-01 to HC-09 (hard constraints)
- NEVER violate preference just to improve soft constraint score
- Violation only = necessary compromise for hard constraint conflict (NOT a penalty)

HC-11 - Busy Slots:
- Do NOT schedule during teacher's busy slots

HC-12 - Fixed Timeslots:
- Some courses require specific timeslots

HC-13 - Session-based Slot Assignment ⭐ CRITICAL:
- Each class MUST have EXACTLY `sessions` number of assignments
- sessions=1 → 1 assignment
- sessions=2 → 2 assignments

SOFT CONSTRAINTS (SHOULD satisfy - weighted score penalty):
- Defined in context['soft_constraints'] with weight values
- ONLY optimize AFTER all hard constraints + teacher preferences are satisfied
- Violation = weight × count
- Example: "Minimize Sunday classes" weight=0.5, violate 10 times → -5 points
- Priority order: Hard Constraints > Teacher Preferences > Soft Constraints

**NEW CONTEXT FIELDS (for better scheduling):**

🔴 room_capacity: {"C201": 80, "F711": 45, ...}
   Use: Check if room_capacity[room_id] >= class['students']

🔴 room_type: {"C201": "LT", "Lab-01": "TH", ...}
   Use: Verify room type matches class type

🔴 class_capacity_requirements: {"LOP-00000001": 80, ...}
   Use: Know which classes need large rooms

🔴 teacher_preferences: [
     {"teacher": "GV003", "preferred_slots": ["Thu2-Ca1", "Thu2-Ca2", ...], "total_preferences": 10}
   ]
   Use: Try to honor teacher wishes when possible

**VERIFICATION CHECKLIST:**
Before returning schedule:
- ✅ Each class appears exactly `sessions` times
- ✅ No teacher teaches 2+ classes in same slot (HC-01)
- ✅ No room hosts 2+ classes in same slot (HC-02)
- ✅ All rooms have capacity >= class size (HC-03)
- ✅ All rooms have required equipment (HC-04)
- ✅ All LT classes use LT rooms, all TH use TH rooms (HC-05/HC-06)
- ✅ Teacher preferences honored when possible (HC-10)
- ✅ Total output count = sum(sessions for all classes)

OUTPUT FORMAT:
{"schedule": [{"class": "LOP-xxx", "room": "Dxxx", "slot": "ThuX-CaY"}]}

🔴 CRITICAL - CLASS ID FORMATTING:
- COPY class IDs EXACTLY as provided in input
- DO NOT remove leading zeros (e.g., LOP-00000012 → LOP-0000012 is WRONG)
- DO NOT reformat or "simplify" IDs
- Use EXACT string from input classes[i].id field

IMPORTANT:
- Each schedule item has 3 fields: class, room, slot (NO teacher field)
- NO explanations, NO comments - Pure JSON only"""
    
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
        config = types.GenerateContentConfig(
            temperature=0.5,  # Cao hơn một chút để linh hoạt trong scheduling
            top_p=0.95,
            top_k=40,
            max_output_tokens=100000,  # Tăng cao để chứa 216 schedules
            response_mime_type="application/json",  # Yêu cầu trả về JSON
            system_instruction=self.schedule_system_instruction
        )
        
        response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=context_prompt,
            config=config
        )
        
        # DEBUG: Log response details
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🔍 AI raw response length: {len(response.text)} chars")
        logger.info(f"🔍 AI response preview: {response.text[:500]}...")
        
        # Khi response_mime_type='application/json', response.text đã là JSON string
        import json
        parsed = json.loads(response.text)
        logger.info(f"🔍 Parsed JSON keys: {list(parsed.keys())}")
        if 'schedule' in parsed:
            logger.info(f"🔍 Schedule array length: {len(parsed['schedule'])}")
            # Log sample assignments
            if parsed['schedule']:
                logger.info(f"🔍 Sample assignments: {parsed['schedule'][:3]}")
        
        return parsed
    
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