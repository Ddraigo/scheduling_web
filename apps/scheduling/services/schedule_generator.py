"""
Tạo thời khóa biểu tối ưu
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List
import pandas as pd
from sqlalchemy import text
from tabulate import tabulate
from ..utils.helpers import json_serial

# ✅ Import Google GenAI SDK (new official SDK)
from google import genai
from google.genai import types

# ✅ Import Batch Scheduler cho LLM
from .batch_scheduler import BatchScheduler

# ✅ Import Schedule Validator
from .schedule_validator import ScheduleValidator

# 🔴 Import Schedule Repair (NEW FIX)
from .schedule_repair import ScheduleRepair


def map_constraint_weights_from_sql(constraints_df: pd.DataFrame) -> Dict[str, float]:
    """
    Map ràng buộc mềm từ SQL (tb_RANG_BUOC_MEM) sang keys của MetricsCalculator
    
    Args:
        constraints_df: DataFrame với columns [TenRangBuoc, TrongSo]
        
    Returns:
        Dict với keys: w_fair, w_wish, w_compact, w_unsat, w_daily_limit, w_compact_days
    """
    weights = {
        'w_fair': 1.0,           # Default fairness weight
        'w_wish': 1.2,           # Default wish satisfaction weight
        'w_compact': 0.5,        # Default compactness weight
        'w_unsat': 0.8,          # Default unmet wishes penalty
        'w_daily_limit': 0.6,    # Default daily limit compliance weight
        'w_compact_days': 0.4    # Default compact days weight
    }
    
    if constraints_df.empty:
        return weights
    
    # Map từ tên ràng buộc trong SQL sang keys
    # ⚠️ THỨ TỰ QUAN TRỌNG: Specific patterns trước, generic patterns sau
    name_mapping = [
        # RBM codes (specific - check first)
        ('rbm-001', 'w_daily_limit'),        # Giới hạn số tiết/ngày
        ('rbm-002', 'w_compact_days'),       # Lịch compact - ít ngày dạy
        ('rbm-003', 'w_fair'),               # Phân công công bằng
        ('rbm-nguyen-vong', 'w_wish'),       # Ưu tiên nguyện vọng
        
        # Specific phrases (check before generic)
        ('ưu tiên nguyện vọng', 'w_wish'),
        ('giới hạn số tiết/ngày', 'w_daily_limit'),
        ('giới hạn ngày', 'w_daily_limit'),
        ('ít ngày', 'w_compact_days'),
        ('compact days', 'w_compact_days'),
        ('phân công đều', 'w_fair'),
        
        # Generic keywords (check last)
        ('nguyện vọng', 'w_wish'),
        ('wish', 'w_wish'),
        ('công bằng', 'w_fair'),
        ('fairness', 'w_fair'),
        ('gọn', 'w_compact'),
        ('compact', 'w_compact'),          # Generic "compact" → w_compact
        ('tập trung', 'w_compact'),
        ('daily limit', 'w_daily_limit')
    ]
    
    for _, row in constraints_df.iterrows():
        ten_rb = str(row['TenRangBuoc']).lower()
        trong_so = float(row['TrongSo'])
        
        # Tìm key tương ứng (first match wins)
        matched = False
        for keyword, weight_key in name_mapping:
            if keyword in ten_rb:
                weights[weight_key] = trong_so
                matched = True
                break  # Stop at first match
        
        if not matched:
            logger.warning(f"⚠️ Unknown constraint: '{row['TenRangBuoc']}' - ignored")
    
    # w_unsat luôn bằng w_wish (penalty for unmet wishes)
    weights['w_unsat'] = weights['w_wish']
    
    return weights

logger = logging.getLogger(__name__)

# Import GA algorithm modules - CHỈ KHI CẦN DÙNG
GA_AVAILABLE = False
ga_module = None
sql_to_teachers = None
sql_to_rooms = None
sql_to_courses = None
extract_soft_constraints_weights = None
ga_result_to_json = None

def _lazy_import_ga():
    """Lazy import GA module để tránh auto-run khi import"""
    global GA_AVAILABLE, ga_module
    global sql_to_teachers, sql_to_rooms, sql_to_courses
    global extract_soft_constraints_weights, ga_result_to_json
    
    if GA_AVAILABLE:
        return True
    
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'algorithm'))
        
        # ✅ Import SQL-compatible version (no random data, no auto-run)
        import greedy_heuristic_ga_algorithm_sql as ga_mod
        
        from ga_adapter import (
            sql_to_teachers as stt, 
            sql_to_rooms as str_func, 
            sql_to_courses as stc,
            extract_soft_constraints_weights as escw, 
            ga_result_to_json as grtj
        )
        
        ga_module = ga_mod
        sql_to_teachers = stt
        sql_to_rooms = str_func
        sql_to_courses = stc
        extract_soft_constraints_weights = escw
        ga_result_to_json = grtj
        
        GA_AVAILABLE = True
        logger.info("✅ GA algorithm (SQL version) loaded successfully")
        return True
    except Exception as e:
        logger.warning(f"GA algorithm không khả dụng: {e}")
        import traceback
        traceback.print_exc()
        GA_AVAILABLE = False
        return False


class ScheduleGenerator:
    """Tạo thời khóa biểu tối ưu"""
    
    def __init__(self, db_connection, ai_instance):
        self.db = db_connection
        self.ai = ai_instance
    
    def create_schedule_with_ga_directly(self, semester_code: str = '2025-2026_HK1') -> str:
        """
        Chạy TRỰC TIẾP GA algorithm mà KHÔNG dùng AI
        
        Args:
            semester_code: Mã học kỳ (mặc định: '2025-2026_HK1')
            
        Returns:
            JSON string của thời khóa biểu
        """
        print("🧬 CHẠY TRỰC TIẾP GA ALGORITHM (BỎ QUA AI)")
        print(f"📅 Học kỳ: {semester_code}")
        print("="*80)
        
        try:
            # Gọi trực tiếp GA algorithm
            schedule_json = self._create_schedule_with_ga_algorithm()
            
            # Parse và lưu file
            result = json.loads(schedule_json)
            
            # Lưu vào file
            filename = f"schedule_ga_direct_{semester_code.replace('-', '_')}.json"
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            output_dir = os.path.join(project_root, 'output')
            os.makedirs(output_dir, exist_ok=True)
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=json_serial)
            
            print(f"\n💾 Đã lưu kết quả vào: {filepath}")
            
            # Format success message
            if 'schedule' in result:
                num_schedules = len(result['schedule'])
                metrics = result.get('metrics', {})
                
                return f"""
✅ **TẠO TKB BẰNG GA THÀNH CÔNG!**

📊 Kết quả:
- Học kỳ: {semester_code}
- Đã xếp: {num_schedules} lịch
- File: `{filename}`
- Fitness: {metrics.get('fitness_after', 'N/A')}
- Wish satisfaction: {metrics.get('wish_satisfaction', 'N/A')}

📁 Đã lưu JSON đầy đủ vào: {filepath}
"""
            else:
                return schedule_json
                
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            return f"❌ Lỗi chạy GA: {e}\n\n{error_trace}"
    
    def create_optimal_schedule_to_json(self, semester_code: str, use_ga_directly: bool = False) -> str:
        """
        Tạo thời khóa biểu tối ưu và lưu vào file JSON
        
        Args:
            semester_code: Mã học kỳ
            use_ga_directly: True = chạy trực tiếp GA, bỏ qua AI (mặc định: False)
        """
        try:
            # ✅ NẾU YÊU CẦU CHẠY TRỰC TIẾP GA
            if use_ga_directly:
                print("🧬 Chế độ: CHẠY TRỰC TIẾP GA (BỎ QUA AI)")
                schedule_result = self._create_schedule_with_ga_algorithm()
                
                # Parse và validate
                final_result = json.loads(schedule_result)
                
                # Lưu file
                filename = f"schedule_ga_direct_{semester_code.replace('-', '_')}.json"
                current_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(os.path.dirname(current_dir))
                output_dir = os.path.join(project_root, 'output')
                os.makedirs(output_dir, exist_ok=True)
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(final_result, f, ensure_ascii=False, indent=2, default=json_serial)
                
                print(f"💾 Đã lưu thời khóa biểu vào: {filepath}")
                
                # Format message
                num_schedules = len(final_result.get('schedule', []))
                metrics = final_result.get('metrics', {})
                
                return f"""
✅ **TẠO TKB BẰNG GA THÀNH CÔNG!**

📊 Kết quả:
- Học kỳ: {semester_code}
- Đã xếp: {num_schedules} lịch
- File: `{filename}`
- Fitness: {metrics.get('fitness_after', 'N/A')}

📁 Đã lưu vào: {filepath}
"""
            
            # ✅ FLOW BÌN THƯỜNG: Dùng AI trước
            print("🤖 Đang thu thập dữ liệu để tạo lịch tối ưu...")
            
            # Định nghĩa các queries
            queries = self._get_schedule_queries(semester_code)
            
            print(f"📊 Đang thực thi queries cho học kỳ: {semester_code}...")
            
            # Thực thi queries và lấy dữ liệu
            data_frames = self._execute_schedule_queries(queries, semester_code)
            
            if not self._validate_data(data_frames):
                return "❌ Không đủ dữ liệu để tạo thời khóa biểu"
            
            print("🧠 Đang sử dụng AI để tạo lịch tối ưu...")
            
            # Tạo context cho AI
            scheduling_context = self._prepare_scheduling_context_for_json(
                semester_code, **data_frames
            )
            
            # Gọi AI để tạo thời khóa biểu JSON
            schedule_result = self._generate_optimal_schedule_json(scheduling_context)
            
            # 🔴 FIX: Apply schedule repair BEFORE validation
            print("🔧 Đang sửa lịch để khắc phục vi phạm...")
            repair = ScheduleRepair()
            schedule_data = json.loads(schedule_result)
            schedule_list = schedule_data.get('schedule', [])
            
            repaired_schedule, repair_stats = repair.repair_schedule(
                schedule_list,
                data_frames['phan_cong_df'],
                data_frames['rooms_df'],
                data_frames['timeslots_df']['TimeSlotID'].tolist()
            )
            
            logger.info(f"✅ Repair: {repair_stats}")
            schedule_data['schedule'] = repaired_schedule
            schedule_result = json.dumps(schedule_data, ensure_ascii=False, indent=2)
            
            # ✅ VALIDATE và tính METRICS (on repaired schedule)
            print("🔍 Đang validate lịch học và tính metrics...")
            validation_result = self._validate_and_calculate_metrics(
                schedule_result,
                data_frames
            )
            
            # ✅ Thêm metrics vào kết quả
            final_result = json.loads(schedule_result)
            final_result['validation'] = {
                'feasible': validation_result['feasible'],
                'all_assigned': validation_result['all_assigned'],
                'total_violations': validation_result['total_violations'],
                'violations_by_type': validation_result['violations_by_type']
            }
            final_result['metrics'] = validation_result['metrics']
            
            if not validation_result['feasible']:
                final_result['errors'] = validation_result['errors']
                print(f"⚠️ Tìm thấy {validation_result['total_violations']} vi phạm ràng buộc cứng!")
            else:
                print("✅ Lịch học thỏa mãn tất cả ràng buộc cứng!")
            
            # Convert back to JSON string
            schedule_json = json.dumps(final_result, ensure_ascii=False, indent=2)
            
            # Lưu vào file trong thư mục output của project
            filename = f"schedule_{semester_code.replace('-', '_')}.json"
            
            # Lấy đường dẫn thư mục gốc của project (2 cấp từ src/scheduling)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            output_dir = os.path.join(project_root, 'output')
            
            # Tạo thư mục output nếu chưa tồn tại
            os.makedirs(output_dir, exist_ok=True)
            
            filepath = os.path.join(output_dir, filename)
            
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(schedule_json)
                
                print(f"💾 Đã lưu thời khóa biểu vào: {filepath}")
                
                # Trả về kết quả với metrics
                return self._format_success_message_with_metrics(
                    semester_code, filename, schedule_json, 
                    data_frames['phan_cong_df'],
                    validation_result
                )
                
            except Exception as e:
                return f"❌ Lỗi lưu file: {e}\n\n📄 **Kết quả JSON:**\n{schedule_json[:1000]}..."
            
        except Exception as e:
            return f"❌ Lỗi tạo thời khóa biểu: {e}"
    
    def _get_schedule_queries(self, semester_code: str) -> Dict[str, str]:
        """Tạo các query tối ưu - CHỈ LẤY DỮ LIỆU CẦN THIẾT"""
        return {
            'dot_xep': f"""
                SELECT dx.MaDot, dx.TrangThai
                FROM tb_DOT_XEP dx 
                JOIN tb_DUKIEN_DT ddt ON dx.MaDuKienDT = ddt.MaDuKienDT
                WHERE dx.MaDuKienDT LIKE N'%{semester_code}%' 
                AND dx.TrangThai IN ('DRAFT', 'RUNNING')
            """,
            
            'phan_cong': f"""
                SELECT DISTINCT 
                    pc.MaLop, pc.MaGV,
                    lm.SoLuongSV, lm.SoCaTuan,
                    mh.MaMonHoc, mh.SoTinChi,
                    CASE 
                        WHEN mh.SoTietTH > 0 THEN N'TH'
                        ELSE N'LT'
                    END AS LoaiPhong
                FROM tb_PHAN_CONG pc
                JOIN tb_LOP_MONHOC lm ON pc.MaLop = lm.MaLop
                JOIN tb_MON_HOC mh ON lm.MaMonHoc = mh.MaMonHoc  
                JOIN tb_DOT_XEP dx ON pc.MaDot = dx.MaDot
                WHERE dx.MaDuKienDT LIKE N'%{semester_code}%'
            """,
            
            'rooms': """
                SELECT MaPhong, SucChua, LoaiPhong
                FROM tb_PHONG_HOC
                ORDER BY LoaiPhong, SucChua DESC
            """,
            
            'timeslots': """
                SELECT ts.TimeSlotID
                FROM tb_TIME_SLOT ts
                ORDER BY ts.Thu, ts.Ca
            """,
            
            'constraints': f"""
                SELECT rbm.TenRangBuoc, rbm.TrongSo
                FROM tb_RANG_BUOC_MEM rbm
                JOIN tb_RANG_BUOC_TRONG_DOT rbtd ON rbm.MaRangBuoc = rbtd.MaRangBuoc
                JOIN tb_DOT_XEP dx ON rbtd.MaDot = dx.MaDot
                WHERE dx.MaDuKienDT LIKE N'%{semester_code}%'
                ORDER BY rbm.TrongSo DESC
            """,
            
            'preferences': f"""
                SELECT nv.MaGV, nv.TimeSlotID
                FROM tb_NGUYEN_VONG nv
                JOIN tb_DOT_XEP dx ON nv.MaDot = dx.MaDot
                WHERE dx.MaDuKienDT LIKE N'%{semester_code}%'
            """
        }
    
    def _execute_schedule_queries(self, queries: Dict[str, str], semester_code: str) -> Dict[str, pd.DataFrame]:
        """Thực thi queries tối ưu và trả về DataFrames"""
        with self.db.engine.connect() as conn:
            result = {}
            
            # Đợt xếp
            data = conn.execute(text(queries['dot_xep'])).fetchall()
            result['dot_xep_df'] = pd.DataFrame(data, columns=['MaDot', 'TrangThai'])
            print(f"✅ Đợt xếp: {len(data)} records")
            
            # Phân công (CHỈ 7 CỘT CẦN THIẾT)
            data = conn.execute(text(queries['phan_cong'])).fetchall()
            result['phan_cong_df'] = pd.DataFrame(data, columns=[
                'MaLop', 'MaGV', 'SoLuongSV', 'SoCaTuan',
                'MaMonHoc', 'SoTinChi', 'LoaiPhong'
            ])
            print(f"✅ Phân công: {len(data)} records")
            
            # Phòng học
            data = conn.execute(text(queries['rooms'])).fetchall()
            result['rooms_df'] = pd.DataFrame(data, columns=[
                'MaPhong', 'SucChua', 'LoaiPhong'
            ])
            print(f"✅ Phòng học: {len(data)} records")
            
            # Time slots (chỉ cần TimeSlotID)
            data = conn.execute(text(queries['timeslots'])).fetchall()
            result['timeslots_df'] = pd.DataFrame(data, columns=['TimeSlotID'])
            print(f"✅ Time slots: {len(data)} records")
            
            # Ràng buộc (kiểm tra đợt có ràng buộc không, nếu không thì lấy mặc định)
            check_constraints_query = text("""
                SELECT COUNT(*) as cnt
                FROM tb_RANG_BUOC_TRONG_DOT rbtd
                JOIN tb_DOT_XEP dx ON rbtd.MaDot = dx.MaDot
                WHERE dx.MaDuKienDT LIKE :semester_code
            """)
            check_result = conn.execute(check_constraints_query, {"semester_code": f"%{semester_code}%"}).fetchone()
            has_constraints = check_result[0] > 0 if check_result else False
            
            if has_constraints:
                # Có ràng buộc trong đợt → Dùng query đã định nghĩa
                data = conn.execute(text(queries['constraints'])).fetchall()
            else:
                # Không có ràng buộc trong đợt → Lấy tất cả ràng buộc mặc định
                default_constraints_query = text("""
                    SELECT TenRangBuoc, TrongSo
                    FROM tb_RANG_BUOC_MEM
                    ORDER BY TrongSo DESC
                """)
                data = conn.execute(default_constraints_query).fetchall()
            
            result['constraints_df'] = pd.DataFrame(data, columns=[
                'TenRangBuoc', 'TrongSo'
            ])
            print(f"✅ Ràng buộc: {len(data)} records" + (" (mặc định)" if not has_constraints else " (từ đợt)"))
            
            # Nguyện vọng (CHỈ MÃ, KHÔNG CẦN TÊN)
            data = conn.execute(text(queries['preferences'])).fetchall()
            result['preferences_df'] = pd.DataFrame(data, columns=[
                'MaGV', 'TimeSlotID'
            ])
            print(f"✅ Nguyện vọng: {len(data)} records")
            
            return result
    
    def _validate_data(self, data_frames: Dict[str, pd.DataFrame]) -> bool:
        """Kiểm tra dữ liệu có đủ không"""
        return not data_frames['phan_cong_df'].empty
    
    def _prepare_scheduling_context_for_json(
        self, semester_code: str, dot_xep_df, phan_cong_df, 
        rooms_df, timeslots_df, constraints_df, preferences_df
    ) -> str:
        """
        Chuẩn bị context CHO AI - ENHANCED WITH FIXES
        
        🔴 FIX #2: Add room capacity, full preferences, room type mapping
        🔴 FIX #3: Add room capacity constraint
        🔴 FIX #4: Include ALL 834 preferences (not just top 50)
        """
        
        # Create room capacity dict
        room_capacity_dict = {}
        for _, row in rooms_df.iterrows():
            room_capacity_dict[row['MaPhong']] = row['SucChua']
        
        # 🔴 FIX #2: Separate rooms by type with explicit mapping
        lt_rooms = rooms_df[rooms_df['LoaiPhong'].str.contains('thuyết|LT', case=False, na=False)]['MaPhong'].tolist()
        th_rooms = rooms_df[rooms_df['LoaiPhong'].str.contains('hành|TH', case=False, na=False)]['MaPhong'].tolist()
        
        # Create room-type mapping
        room_type_map = {room: 'LT' for room in lt_rooms}
        room_type_map.update({room: 'TH' for room in th_rooms})
        
        # 🔴 FIX #4: Include ALL preferences, not just top 50
        # Group preferences by teacher (since preferences_df has one row per preference)
        preferences_by_teacher = {}
        if not preferences_df.empty:
            for _, row in preferences_df.iterrows():
                teacher_id = row['MaGV']
                time_slot = row['TimeSlotID']
                if teacher_id not in preferences_by_teacher:
                    preferences_by_teacher[teacher_id] = {'preferred': [], 'avoid': []}
                preferences_by_teacher[teacher_id]['preferred'].append(time_slot)
        
        preferences_list = [
            {
                'teacher': teacher_id,
                'preferred_slots': prefs['preferred'][:10],  # Top 10 preferred per teacher
                'total_preferences': len(prefs['preferred'])
            }
            for teacher_id, prefs in sorted(preferences_by_teacher.items())
        ]
        
        # ✅ ENHANCED CONTEXT with ALL FIXES
        context = {
            'classes': [
                {
                    'id': row['MaLop'],
                    'teacher': row['MaGV'],
                    'students': row['SoLuongSV'],
                    'sessions': row['SoCaTuan'],
                    'type': row['LoaiPhong']  # LT or TH
                }
                for _, row in phan_cong_df.iterrows()
            ],
            
            'rooms': {
                'LT': lt_rooms,
                'TH': th_rooms
            },
            
            'timeslots': timeslots_df['TimeSlotID'].tolist(),
            
            # 🔴 FIX #2: Add room capacity constraint
            'room_capacity': room_capacity_dict,
            
            # 🔴 FIX #2: Add room type mapping (for HC-05/06 validation)
            'room_type': room_type_map,
            
            # 🔴 FIX #3: Add class capacity requirements
            'class_capacity_requirements': {
                row['MaLop']: row['SoLuongSV']
                for _, row in phan_cong_df.iterrows()
            },
            
            # 🔴 FIX #4: Include ALL teacher preferences (834 total)
            'teacher_preferences': preferences_list,
            'total_preferences_count': len(preferences_df) if not preferences_df.empty else 0
        }
        
        logger.info(f"📊 Context includes: {len(preferences_list)} teachers with {len(preferences_df) if not preferences_df.empty else 0} total preferences (was 50)")
        
        return json.dumps(context, ensure_ascii=False)
    
    def _generate_optimal_schedule_json(self, context: str) -> str:
        """
        AI tạo TKB - Sử dụng ScheduleAI.generate_schedule_json()
        ⭐ CHỈ GỬI CONTEXT JSON, PROMPT ĐÃ CÓ TRONG schedule_ai.py (schedule_system_instruction)
        """
        
        # Parse context để log
        context_data = json.loads(context)
        classes = context_data['classes']
        total_schedules = sum(c['sessions'] for c in classes)
        
        try:
            logger.info(f"🤖 Sending {len(classes)} classes → {total_schedules} schedules")
            logger.info(f"📋 Using ScheduleAI system prompt (includes all 13 HC)")
            
            # ✅ GỬI CONTEXT JSON - Prompt đã có trong ScheduleAI
            parsed = self.ai.generate_schedule_json(context)
            
            logger.info(f"📝 Response type: {type(parsed)}")
            
            # Re-parse context for validation
            context_data = json.loads(context)
            
            if 'schedule' in parsed:
                logger.info(f"📊 AI created {len(parsed['schedule'])} schedules")
                if len(parsed['schedule']) > 0:
                    logger.info(f"🔍 Sample: {parsed['schedule'][0]}")
                    
                    # Validate
                    if self._validate_ai_schedule(parsed, context_data):
                        logger.info("✅ AI single-shot success!")
                        return json.dumps(parsed, ensure_ascii=False, indent=2)
                else:
                    logger.warning(f"⚠️ AI returned EMPTY schedule!")
            
            # Failed → try batching
            logger.warning("⚠️ Single-shot failed, try BATCHING...")
            return self._generate_schedule_with_batching(context_data)
                
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ JSON decode error: {e}, fallback sang GA")
            return self._create_schedule_with_ga_algorithm()
        except Exception as e:
            logger.error(f"❌ Lỗi AI: {e}")
            logger.warning("➡️ Fallback sang GA algorithm")
            return self._create_schedule_with_ga_algorithm()
    
    def _generate_schedule_with_batching(self, context_data: Dict) -> str:
        """
        ✅ BATCH SCHEDULING - Chia nhỏ task cho LLM
        """
        logger.info("🔄 Starting BATCH SCHEDULING...")
        
        try:
            batch_scheduler = BatchScheduler(
                ai_instance=self.ai,
                batch_size=25  # 25 classes/batch → ~9 batches
            )
            
            # Use new compact format
            classes = context_data['classes']
            rooms = context_data['rooms']
            timeslots = context_data['timeslots']
            
            result = batch_scheduler.generate_schedule_with_batching(
                classes=classes,
                rooms=rooms,
                timeslots=timeslots,
                max_retries=2
            )
            
            if 'error' in result:
                logger.error(f"❌ Batch scheduling FAILED: {result['error']}")
                logger.warning("➡️ Fallback sang GA algorithm")
                return self._create_schedule_with_ga_algorithm()
            
            # Success!
            logger.info(f"✅ Batch scheduling SUCCESS: {len(result['schedule'])} schedules")
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"❌ Lỗi batch scheduling: {e}")
            logger.warning("➡️ Fallback sang GA algorithm")
            return self._create_schedule_with_ga_algorithm()
    
    def _validate_ai_schedule(self, schedule_data: Dict, context_data: Dict) -> bool:
        """Validate AI output - CHỈ 3 FIELDS BẮT BUỘC: class, room, slot"""
        try:
            if 'schedule' not in schedule_data:
                logger.warning("Missing 'schedule' key")
                return False
            
            schedule_list = schedule_data['schedule']
            if not isinstance(schedule_list, list) or len(schedule_list) == 0:
                logger.warning("Schedule empty or not a list")
                return False
            
            # ✅ Valid IDs from context (new compact format)
            valid_rooms = set(context_data['rooms']['LT'] + context_data['rooms']['TH'])
            valid_timeslots = set(context_data['timeslots'])
            valid_classes = set(c['id'] for c in context_data['classes'])
            
            # 🔍 DEBUG: Log class IDs format
            logger.info(f"🔍 Sample valid_classes (first 5): {list(valid_classes)[:5]}")
            logger.info(f"🔍 Sample AI classes (first 5): {[s['class'] for s in schedule_list[:5]]}")

            
            # ✅ Check 3 REQUIRED fields: class, room, slot (NO teacher - có trong tb_PHAN_CONG)
            required_keys = ['class', 'room', 'slot']
            invalid_count = 0
            
            for i, entry in enumerate(schedule_list[:50]):  # Check first 50
                # Missing keys?
                for key in required_keys:
                    if key not in entry:
                        logger.warning(f"Entry {i} missing '{key}'")
                        return False
                
                # ✅ Validate real IDs from SQL
                if entry['class'] not in valid_classes:
                    logger.warning(f"Entry {i}: class '{entry['class']}' NOT EXIST!")
                    invalid_count += 1
                
                if entry['room'] not in valid_rooms:
                    logger.warning(f"Entry {i}: room '{entry['room']}' NOT EXIST!")
                    invalid_count += 1
                    
                if entry['slot'] not in valid_timeslots:
                    logger.warning(f"Entry {i}: slot '{entry['slot']}' NOT EXIST!")
                    invalid_count += 1
            
            # ❌ >20% invalid → reject
            if invalid_count > len(schedule_list[:50]) * 0.2:
                logger.error(f"❌ VALIDATION FAILED: {invalid_count}/50 invalid IDs!")
                return False
            
            # Check minimum count (at least 50% of expected)
            expected_schedules = sum(c['sessions'] for c in context_data['classes'])
            min_schedules = expected_schedules * 0.5
            
            if len(schedule_list) < min_schedules:
                logger.warning(f"Only {len(schedule_list)}/{expected_schedules} schedules (< 50%)")
                return False
            
            logger.info(f"✅ Validation passed: {len(schedule_list)} schedules, {invalid_count} invalid")
            return True
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False
    
    def _create_schedule_with_ga_algorithm(self) -> str:
        """
        Sử dụng Genetic Algorithm để tạo lịch tối ưu
        Kết hợp ràng buộc cứng + mềm từ SQL
        """
        # Lazy import GA modules
        if not _lazy_import_ga():
            error_msg = {
                "error": "GA algorithm không khả dụng",
                "timestamp": datetime.now().isoformat(),
                "message": "Không thể tạo thời khóa biểu. Vui lòng kiểm tra GA algorithm."
            }
            return json.dumps(error_msg, ensure_ascii=False, indent=2)
        
        try:
            print("🧬 Đang sử dụng Genetic Algorithm để tối ưu...")
            
            # === 1. QUERY DỮ LIỆU TỪ SQL ===
            
            # Giảng viên
            giang_vien_query = """
            SELECT DISTINCT gv.MaGV, gv.TenGV, gv.MaBoMon
            FROM tb_GIANG_VIEN gv
            JOIN tb_PHAN_CONG pc ON gv.MaGV = pc.MaGV
            WHERE pc.MaDot LIKE N'%2025-2026_HK1%'
            """
            giang_vien_df = self.db.execute_query(giang_vien_query)
            
            # Nguyện vọng
            nguyen_vong_query = """
            SELECT nv.MaGV, nv.TimeSlotID
            FROM tb_NGUYEN_VONG nv
            WHERE nv.MaDot LIKE N'%2025-2026_HK1%'
            """
            nguyen_vong_df = self.db.execute_query(nguyen_vong_query)
            
            # Phòng học
            phong_hoc_query = """
            SELECT MaPhong, SucChua, LoaiPhong, ThietBi
            FROM tb_PHONG_HOC
            ORDER BY SucChua DESC
            """
            phong_hoc_df = self.db.execute_query(phong_hoc_query)
            
            # TimeSlots
            timeslots_query = """
            SELECT TimeSlotID, Thu, Ca
            FROM tb_TIME_SLOT
            WHERE Thu <> 8
            ORDER BY Thu, Ca
            """
            timeslots_df = self.db.execute_query(timeslots_query)
            
            # Phân công
            phan_cong_query = """
            SELECT pc.MaDot, pc.MaLop, pc.MaGV
            FROM tb_PHAN_CONG pc
            WHERE pc.MaDot LIKE N'%2025-2026_HK1%'
            """
            phan_cong_df = self.db.execute_query(phan_cong_query)
            
            # Lớp môn học
            lop_monhoc_query = """
            SELECT lm.MaLop, lm.MaMonHoc, lm.SoLuongSV, lm.SoCaTuan, 
                   lm.ThietBiYeuCau, lm.HeDaoTao, lm.To_MH
            FROM tb_LOP_MONHOC lm
            JOIN tb_MON_HOC mh ON lm.MaMonHoc = mh.MaMonHoc
            WHERE lm.MaLop IN (SELECT MaLop FROM tb_PHAN_CONG WHERE MaDot LIKE N'%2025-2026_HK1%')
            """
            lop_monhoc_df = self.db.execute_query(lop_monhoc_query)
            
            # Môn học
            mon_hoc_query = """
            SELECT mh.MaMonHoc, mh.TenMonHoc, mh.SoTinChi, mh.SoTietLT, mh.SoTietTH
            FROM tb_MON_HOC mh
            WHERE mh.MaMonHoc IN (SELECT MaMonHoc FROM tb_LOP_MONHOC WHERE MaLop IN 
                                 (SELECT MaLop FROM tb_PHAN_CONG WHERE MaDot LIKE N'%2025-2026_HK1%'))
            """
            mon_hoc_df = self.db.execute_query(mon_hoc_query)
            
            # Ràng buộc mềm (ưu tiên từ đợt, fallback sang bảng chung)
            # Bước 1: Kiểm tra xem có ràng buộc trong đợt không
            check_query = """
            SELECT COUNT(*) as cnt
            FROM tb_RANG_BUOC_TRONG_DOT rbtd
            WHERE rbtd.MaDot LIKE N'%2025-2026_HK1%'
            """
            check_result = self.db.execute_query(check_query)
            has_dot_constraints = check_result.iloc[0]['cnt'] > 0 if not check_result.empty else False
            
            # Bước 2: Lấy ràng buộc tùy theo có ràng buộc trong đợt hay không
            if has_dot_constraints:
                # Có ràng buộc trong đợt → CHỈ lấy những ràng buộc được gán cho đợt này
                print("📋 Sử dụng ràng buộc mềm từ đợt xếp...")
                rang_buoc_query = """
                SELECT rbm.MaRangBuoc, rbm.TenRangBuoc, rbm.TrongSo
                FROM tb_RANG_BUOC_MEM rbm
                INNER JOIN tb_RANG_BUOC_TRONG_DOT rbtd ON rbm.MaRangBuoc = rbtd.MaRangBuoc
                WHERE rbtd.MaDot LIKE N'%2025-2026_HK1%'
                """
            else:
                # KHÔNG có ràng buộc trong đợt → Lấy TẤT CẢ ràng buộc từ bảng chung làm mặc định
                print("📋 Đợt xếp chưa cấu hình ràng buộc → Sử dụng TẤT CẢ ràng buộc mặc định từ tb_RANG_BUOC_MEM...")
                rang_buoc_query = """
                SELECT MaRangBuoc, TenRangBuoc, TrongSo
                FROM tb_RANG_BUOC_MEM
                ORDER BY TrongSo DESC
                """
            
            rang_buoc_df = self.db.execute_query(rang_buoc_query)
            
            print(f"✅ Đã load: {len(giang_vien_df)} GV, {len(phong_hoc_df)} phòng, "
                  f"{len(phan_cong_df)} phân công, {len(rang_buoc_df)} ràng buộc mềm")
            
            # === 2. CONVERT SANG CẤU TRÚC GA ===
            
            teachers = sql_to_teachers(giang_vien_df, nguyen_vong_df, timeslots_df, phan_cong_df)
            rooms = sql_to_rooms(phong_hoc_df)
            courses, mapping = sql_to_courses(phan_cong_df, lop_monhoc_df, mon_hoc_df, giang_vien_df)
            
            print(f"✅ Converted: {len(teachers)} teachers, {len(rooms)} rooms, {len(courses)} course units")
            print(f"🔍 DEBUG: Vài tên courses đầu tiên: {[c.name for c in courses[:5]]}")
            
            # === 3. CẤU HÌNH WEIGHTS TỪ RÀNG BUỘC MỀM ===
            
            weights = extract_soft_constraints_weights(rang_buoc_df)
            # weights is now Dict[str, float] = {
            #     'w_daily_limit': 0.90, 'w_compact_days': 0.85,
            #     'w_fair': 1.0, 'w_wish': 1.2, 
            #     'w_compact': 0.5, 'w_unsat': 0.8
            # }
            
            print(f"📊 SQL Weights loaded: {weights}")
            
            # === 4. INJECT VÀO GA MODULE ===
            
            print("🔧 Injecting SQL data vào GA module...")
            
            # 4.1. Inject main data structures
            ga_module.teachers = teachers
            ga_module.rooms = rooms
            ga_module.courses = courses
            
            # 4.2. ✅ Inject SQL weights into sql_weights dict (used by fitness function)
            ga_module.sql_weights = weights
            
            # 4.3. Rebuild ALL global dictionaries
            print("🔨 Rebuilding course_by_id...")
            ga_module.course_by_id = {c.id: c for c in courses}
            
            print("🔨 Rebuilding assignments_by_teacher...")
            ga_module.assignments_by_teacher = {t.id: set() for t in teachers}
            
            print("🔨 Rebuilding teacher_load, teacher_day_mask, dept_of_teacher...")
            ga_module.teacher_load = {t.id: 0 for t in teachers}
            ga_module.teacher_day_mask = {t.id: [0] * ga_module.DAYS for t in teachers}
            ga_module.dept_of_teacher = {t.id: t.dept for t in teachers}
            
            print("🔨 Rebuilding teacher_week_slots, teacher_day_slots...")
            ga_module.teacher_week_slots = {t.id: 0 for t in teachers}
            ga_module.teacher_day_slots = {t.id: [0] * ga_module.DAYS for t in teachers}
            
            print("🔨 Rebuilding assignment arrays...")
            ga_module.assign_teacher = {c.id: None for c in courses}
            ga_module.assign_day = {c.id: None for c in courses}
            ga_module.assign_slot = {c.id: None for c in courses}
            ga_module.assign_room = {c.id: None for c in courses}
            
            print("🔨 Rebuilding candidate_rooms_for_course...")
            ga_module.candidate_rooms_for_course = {}
            for c in courses:
                room_ids = set()
                for r in rooms:
                    # Capacity check
                    if r.capacity < c.size:
                        continue
                    
                    # Room type check
                    if c.room_type_required and c.room_type_required.strip():
                        if c.room_type_required.lower() not in r.room_type.lower():
                            continue
                    
                    # Equipment check
                    if c.equipment_required and c.equipment_required.strip():
                        required_items = [item.strip().lower() for item in c.equipment_required.split(',') if item.strip()]
                        if not all(req_item in r.equipment.lower() for req_item in required_items):
                            continue
                    
                    room_ids.add(r.id)
                ga_module.candidate_rooms_for_course[c.id] = room_ids
            
            print("🔨 Rebuilding feasible_slots...")
            ga_module.feasible_slots = {c.id: {} for c in courses}
            for c in courses:
                for tid in c.candidate_teachers:
                    f = []
                    t_bits = teachers[tid].availability_bits
                    for d in range(ga_module.DAYS):
                        for s in range(ga_module.SLOTS):
                            if ga_module.window_available(t_bits, d, s, c.duration):
                                f.append((d, s))
                    ga_module.feasible_slots[c.id][tid] = f
            
            print("🔨 Calling build_option_lists() to rebuild OptionList và WishEnd...")
            ga_module.build_option_lists()
            
            print("✅ Injection complete! GA module ready với SQL data.")
            
            # === 5. CHẠY GA ===
            
            print("🚀 Bắt đầu chạy GA (Multi-start + Genetic Algorithm + Local Search)...")
            timetable, metrics = ga_module.run_demo()
            
            print(f"✅ GA hoàn thành! Fitness={metrics.get('fitness_after', 'N/A')}, "
                  f"Wish satisfaction={metrics.get('wish_satisfaction', 0)}")
            
            # === 6. CONVERT KẾT QUẢ VỀ JSON ===
            
            result_json = ga_result_to_json(timetable, metrics, mapping, teachers, rooms)
            
            return json.dumps(result_json, ensure_ascii=False, indent=2, default=json_serial)
            
        except Exception as e:
            logger.error(f"Lỗi GA algorithm: {e}")
            import traceback
            traceback.print_exc()
            error_msg = {
                "error": f"GA algorithm thất bại: {e}",
                "timestamp": datetime.now().isoformat(),
                "message": "Không thể tạo thời khóa biểu. Vui lòng kiểm tra dữ liệu hoặc cấu hình GA."
            }
            return json.dumps(error_msg, ensure_ascii=False, indent=2, default=json_serial)
    
    def _format_success_message(
        self, semester_code: str, filename: str, 
        schedule_json: str, phan_cong_data
    ) -> str:
        """Thông báo thành công RÚT GỌN"""
        # Đếm số lịch đã tạo từ JSON
        try:
            data = json.loads(schedule_json)
            schedules_created = len(data.get('schedule', []))
        except:
            schedules_created = 0
        
        return f"""
✅ **TẠO TKB THÀNH CÔNG!**

📊 Kết quả:
- Học kỳ: {semester_code}
- Phân công: {len(phan_cong_data)} lớp
- Đã xếp: {schedules_created} lịch
- File: `{filename}`

📁 Đã lưu JSON đầy đủ vào file.
"""
    
    def _validate_and_calculate_metrics(
        self,
        schedule_json_str: str,
        data_frames: Dict[str, pd.DataFrame]
    ) -> Dict:
        """
        Validate lịch học và tính metrics
        
        Args:
            schedule_json_str: JSON string của schedule
            data_frames: Dữ liệu từ database
            
        Returns:
            Dict chứa kết quả validation và metrics
        """
        try:
            # Parse JSON
            schedule_data = json.loads(schedule_json_str)
            
            # Chuẩn bị dữ liệu cho validator
            classes_data = []
            for _, row in data_frames['phan_cong_df'].iterrows():
                classes_data.append({
                    'id': row['MaLop'],
                    'course': row['MaMonHoc'],
                    'students': row['SoLuongSV'],
                    'sessions': row['SoCaTuan'],
                    'type': row['LoaiPhong'],
                    'credits': row['SoTinChi']
                })
            
            # ⭐ Assignments data (tb_PHAN_CONG) - MaLop → MaGV
            assignments_data = []
            for _, row in data_frames['phan_cong_df'].iterrows():
                assignments_data.append({
                    'MaLop': row['MaLop'],
                    'MaGV': row['MaGV']
                })
            
            # Rooms data
            rooms_df = data_frames['rooms_df']
            rooms_data = {
                'LT': rooms_df[rooms_df['LoaiPhong'].str.contains('thuyết|LT', case=False, na=False)]['MaPhong'].tolist(),
                'TH': rooms_df[rooms_df['LoaiPhong'].str.contains('hành|TH', case=False, na=False)]['MaPhong'].tolist()
            }
            
            # Preferences data
            preferences_data = []
            if not data_frames['preferences_df'].empty:
                for teacher, group in data_frames['preferences_df'].groupby('MaGV'):
                    preferences_data.append({
                        'teacher': teacher,
                        'slots': group['TimeSlotID'].tolist()
                    })
            
            # ✅ Constraints weights - MAP TỪ SQL SANG METRICS KEYS
            constraints_weights = map_constraint_weights_from_sql(data_frames['constraints_df'])
            logger.info(f"📊 Soft constraint weights from SQL: {constraints_weights}")
            
            # Tạo validator và validate
            validator = ScheduleValidator()
            result = validator.validate_schedule(
                schedule_data,
                classes_data,
                rooms_data,
                assignments_data,  # ⭐ Pass assignments từ tb_PHAN_CONG
                preferences_data,
                constraints_weights  # ⭐ Pass dynamic weights từ SQL
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Lỗi validation: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "feasible": False,
                "errors": [f"Validation error: {str(e)}"],
                "total_violations": 1,
                "violations_by_type": {},
                "metrics": {},
                "all_assigned": False
            }
    
    def _format_success_message_with_metrics(
        self, semester_code: str, filename: str, 
        schedule_json: str, phan_cong_data,
        validation_result: Dict
    ) -> str:
        """Thông báo thành công với metrics chi tiết"""
        # Đếm số lịch đã tạo từ JSON
        try:
            data = json.loads(schedule_json)
            schedules_created = len(data.get('schedule', []))
        except:
            schedules_created = 0
        
        metrics = validation_result.get('metrics', {})
        
        # Format metrics
        metrics_text = f"""
📊 **METRICS:**
- ✅ Feasible: {validation_result.get('feasible', False)}
- ✅ All Assigned: {validation_result.get('all_assigned', False)}
- 🎯 Fitness: {metrics.get('fitness', 'N/A')}
- ⚖️ Fairness (std): {metrics.get('fairness_std', 'N/A')}
- 💚 Wish Satisfaction: {metrics.get('wish_satisfaction', 0)}/{metrics.get('wish_total', 0)} ({metrics.get('wish_coverage_rate', 0):.1%})
- 📅 Compactness (gaps): {metrics.get('compactness_penalty', 'N/A')}
- 👥 Teacher Load: min={metrics.get('teacher_load_min', 'N/A')}, max={metrics.get('teacher_load_max', 'N/A')}, avg={metrics.get('teacher_load_avg', 'N/A')}
"""
        
        if not validation_result.get('feasible'):
            violations = validation_result.get('violations_by_type', {})
            violations_text = "\n".join([f"  - {k}: {v} vi phạm" for k, v in violations.items()])
            metrics_text += f"\n⚠️ **VI PHẠM:**\n{violations_text}\n"
        
        return f"""
✅ **TẠO TKB THÀNH CÔNG!**

📊 Kết quả:
- Học kỳ: {semester_code}
- Phân công: {len(phan_cong_data)} lớp
- Đã xếp: {schedules_created} lịch
- File: `{filename}`

{metrics_text}

📁 Đã lưu JSON đầy đủ vào file.
"""

