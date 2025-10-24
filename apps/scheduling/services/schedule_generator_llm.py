"""
Schedule Generator - LLM Only Version
Chỉ dùng LLM thuần (bỏ GA), dùng DAL + LLM Service
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List

from google import genai
from google.genai import types

from ..utils.helpers import json_serial
from ..models import TimeSlot
from .data_access_layer import DataAccessLayer
from .llm_service import LLMDataProcessor, LLMPromptBuilder
from .schedule_validator import ScheduleValidator
from .schedule_ai import ScheduleAI

logger = logging.getLogger(__name__)


class ScheduleGeneratorLLM:
    """
    Tạo thời khóa biểu tối ưu dùng LLM
    
    Luồng:
    1. Lấy dữ liệu từ DAL (tối ưu hóa query)
    2. Xử lý dữ liệu bằng LLM Service
    3. Gọi LLM tạo lịch
    4. Validate & lưu JSON
    """
    
    def __init__(self, ai_instance=None):
        """
        Khởi tạo
        
        Args:
            ai_instance: Instance AI (Google Genai hoặc tương tự). Nếu None, dùng ScheduleAI()
        """
        # Sử dụng ScheduleAI nếu không có ai_instance
        if ai_instance is None:
            from .schedule_ai import ScheduleAI
            self.ai = ScheduleAI()
        else:
            self.ai = ai_instance
        
        self.validator = ScheduleValidator()
        self.processor = LLMDataProcessor()
        self.builder = LLMPromptBuilder()
        
    def create_schedule_llm(self, semester_code: str) -> str:
        """
        Tạo thời khóa biểu dùng LLM
        
        Args:
            semester_code: Mã đợt xếp (VD: 2024-2025_HK1)
            
        Returns:
            JSON string của thời khóa biểu
        """
        logger.info(f"🤖 Bắt đầu tạo lịch dùng LLM cho: {semester_code}")
        
        try:
            # Bước 1: Lấy dữ liệu từ DAL
            logger.info("📊 Bước 1: Lấy dữ liệu từ database...")
            schedule_data = self._fetch_schedule_data(semester_code)
            
            if not schedule_data.get('dot_xep_list') or len(schedule_data.get('dot_xep_list', [])) == 0:
                return f"❌ Không tìm thấy đợt xếp cho {semester_code}"
            
            # Bước 2: Xử lý dữ liệu chuẩn bị cho LLM
            logger.info("🔄 Bước 2: Xử lý dữ liệu...")
            processed_data = self._prepare_data_for_llm(schedule_data, semester_code)
            
            # Bước 3: Phát hiện xung đột hiện tại
            logger.info("🔍 Bước 3: Phát hiện xung đột...")
            conflicts = self._detect_conflicts(schedule_data, semester_code)
            
            # Bước 4: Xây dựng prompt cho LLM
            logger.info("📝 Bước 4: Xây dựng prompt...")
            prompt = self._build_llm_prompt(processed_data, conflicts)
            
            # Bước 5: Gọi LLM
            logger.info("🧠 Bước 5: Gọi LLM tạo lịch...")
            schedule_json = self._call_llm_for_schedule(prompt, processed_data)
            
            # Bước 6: Validate & lưu
            logger.info("✅ Bước 6: Validate & lưu lịch...")
            result = self._validate_and_save_schedule(
                schedule_json,
                semester_code,
                processed_data
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Lỗi tạo lịch: {e}", exc_info=True)
            return f"❌ Lỗi: {str(e)}"
    
    def _fetch_schedule_data(self, semester_code: str) -> dict:
        """
        Lấy dữ liệu từ DAL
        
        Returns:
            Dict chứa tất cả dữ liệu cần thiết
        """
        return DataAccessLayer.get_schedule_data_for_llm(semester_code)
    
    def _prepare_data_for_llm(self, schedule_data: dict, semester_code: str) -> dict:
        """
        ⭐ TỐI ƯU TOKEN: Chỉ gửi dữ liệu THẬT SỰ CẦN THIẾT cho LLM
        
        Dữ liệu CẦN:
        - ma_lop, so_sv, so_ca_tuan, loai_phong, thiet_bi_yeu_cau (để so sánh phòng)
        - ma_gv (để LLM biết ai dạy)
        - ma_phong, suc_chua, thiet_bi (để LLM xếp phòng hợp lý)
        - slot (bitmask compact T1-C1, T2-C2, etc)
        - preferences (để ưu tiên giảng viên)
        - constraints (mo_ta + trong_so để LLM hiểu)
        
        Dữ liệu KHÔNG CẦN:
        - ten_mon_hoc, nhom, to (thông tin bổ sung)
        - he_dao_tao, ngon_ngu (không ảnh hưởng scheduling)
        - gio_bat_dau, gio_ket_thuc (LLM chỉ cần slot ID)
        """
        logger.info(f"Preparing data for LLM, semester_code={semester_code}")
        logger.info(f"Schedule data keys: {schedule_data.keys()}")
        logger.info(f"Dot xep list: {schedule_data.get('dot_xep_list', [])}")
        
        prepared = {
            'semester_code': semester_code,
            'dot_xep_list': [],
            'rooms_by_type': {
                'LT': [],  # Phòng lý thuyết
                'TH': []   # Phòng thực hành
            },
            'timeslots': [],
            'slot_mapping': {},  # Map slot_id -> bitmask (cho việc ánh xạ lại)
            'stats': {
                'total_classes': 0,
                'total_schedules_needed': 0,
                'total_rooms': 0,
                'total_timeslots': 0,
            }
        }
        
        # 🔴 TỐI ƯU: Chỉ lấy phòng theo loại + thiết bị
        rooms_by_type = {'LT': [], 'TH': []}
        for p in schedule_data['all_rooms']:
            # Chuẩn hóa loại phòng: "Lý thuyết" → LT, "Thực hành" → TH
            raw_loai = p.loai_phong if p.loai_phong else ''
            room_type = 'TH' if 'Thực hành' in raw_loai or 'TH' in raw_loai or 'hành' in raw_loai else 'LT'
            room_obj = {
                'ma_phong': p.ma_phong,
                'suc_chua': p.suc_chua,
                'thiet_bi': p.thiet_bi if hasattr(p, 'thiet_bi') else '',
                'loai_phong': room_type,  # Thêm loai_phong để validator kiểm tra HC-05 & HC-06
            }
            rooms_by_type[room_type].append(room_obj)
        prepared['rooms_by_type'] = rooms_by_type
        prepared['stats']['total_rooms'] = len(schedule_data['all_rooms'])
        logger.info(f"Total rooms: LT={len(rooms_by_type['LT'])}, TH={len(rooms_by_type['TH'])}")
        
        # 🔴 TỐI ƯU: Slot bitmask compact (T2-C1, T3-C2, ...)
        # Format: TimeSlotID -> bitmask (ví dụ: "1001001" = điểm danh ngày)
        slot_counter = 0
        for ts in schedule_data['all_timeslots']:
            slot_id = ts.time_slot_id
            # Format compact: T{thu}-C{ca}
            # Ví dụ: T2-C1 (Thứ 2, Tiết 1)
            slot_compact = f"T{ts.thu}-C{ts.ca.ma_khung_gio}"
            prepared['timeslots'].append({
                'id': slot_compact,
                'original_id': slot_id,  # Giữ ID gốc để map lại
            })
            prepared['slot_mapping'][slot_compact] = slot_id
            slot_counter += 1
        
        prepared['stats']['total_timeslots'] = len(prepared['timeslots'])
        logger.info(f"Total timeslots: {len(prepared['timeslots'])}")
        
        # 🔴 TỐI ƯU: Xử lý từng đợt xếp - CHỈ GỬI DỮ LIỆU THIẾT YẾU
        for dot in schedule_data['dot_xep_list']:
            dot_data = schedule_data['all_dot_data'].get(dot.ma_dot, {})
            logger.info(f"Processing dot: {dot.ma_dot}, dot_data keys: {dot_data.keys()}")
            
            phan_cong_list = dot_data.get('phan_cong', [])
            logger.info(f"Phan cong count for {dot.ma_dot}: {len(phan_cong_list)}")
            
            dot_info = {
                'ma_dot': dot.ma_dot,
                'hoc_ky': dot.ma_du_kien_dt.get_hoc_ky_display() if hasattr(dot.ma_du_kien_dt, 'get_hoc_ky_display') else '',
                'phan_cong': self._format_phan_cong_compact(phan_cong_list),
                'constraints': self._format_constraints_compact(dot_data.get('constraints', [])),
                'preferences': self._format_preferences_compact(dot_data.get('preferences', [])),
            }
            
            logger.info(f"Formatted phan cong: {len(dot_info['phan_cong'])} items")
            
            prepared['dot_xep_list'].append(dot_info)
            prepared['stats']['total_classes'] += len(dot_info['phan_cong'])
            prepared['stats']['total_schedules_needed'] += sum(
                pc.get('so_ca_tuan', 0) for pc in dot_info['phan_cong']
            )
        
        logger.info(f"Prepared data stats: {prepared['stats']}")
        return prepared
    
    @staticmethod
    def _format_phan_cong_compact(phan_cong_list) -> list:
        """
        🔴 TỐI ƯU: Format phân công - CHỈ VỚI DỮ LIỆU THIẾT YẾU
        Loại bỏ: ten_mon_hoc, nhom, to, he_dao_tao, ngon_ngu
        Giữ: thiet_bi_yeu_cau (để so sánh với phòng)
        
        ⭐ FIX HC-05: Xác định loai_phong từ MonHoc theo SQL logic:
        - Nếu so_tiet_th = 0 → LT
        - Nếu so_tiet_lt = 0 AND so_tiet_th > 0 → TH
        - Nếu so_tiet_lt > 0 AND so_tiet_th > 0 AND to_mh = 0 → LT
        - Else → TH
        """
        result = []
        for pc in phan_cong_list:
            # Lấy ma_lop
            ma_lop_obj = pc.ma_lop if hasattr(pc, 'ma_lop') else None
            ma_lop = ma_lop_obj.ma_lop if ma_lop_obj and hasattr(ma_lop_obj, 'ma_lop') else pc.get('ma_lop')
            
            # Xác định loại phòng dựa vào SQL logic
            loai_phong = 'LT'  # Mặc định LT
            if ma_lop_obj and hasattr(ma_lop_obj, 'ma_mon_hoc') and ma_lop_obj.ma_mon_hoc:
                mon_hoc = ma_lop_obj.ma_mon_hoc
                so_tiet_th = mon_hoc.so_tiet_th if hasattr(mon_hoc, 'so_tiet_th') else 0
                so_tiet_lt = mon_hoc.so_tiet_lt if hasattr(mon_hoc, 'so_tiet_lt') else 0
                to_mh = ma_lop_obj.to_mh if hasattr(ma_lop_obj, 'to_mh') else None
                
                # Apply SQL logic
                if so_tiet_th == 0:
                    loai_phong = 'LT'
                elif so_tiet_lt == 0 and so_tiet_th > 0:
                    loai_phong = 'TH'
                elif so_tiet_lt > 0 and so_tiet_th > 0 and to_mh == 0:
                    loai_phong = 'LT'
                else:
                    loai_phong = 'TH'
            
            result.append({
                'ma_lop': ma_lop,
                'so_sv': ma_lop_obj.so_luong_sv if ma_lop_obj and hasattr(ma_lop_obj, 'so_luong_sv') else pc.get('so_sv', 0),
                'so_ca_tuan': ma_lop_obj.so_ca_tuan if ma_lop_obj and hasattr(ma_lop_obj, 'so_ca_tuan') else pc.get('so_ca_tuan', 1),
                'loai_phong': loai_phong,
                'thiet_bi_yeu_cau': ma_lop_obj.thiet_bi_yeu_cau if ma_lop_obj and hasattr(ma_lop_obj, 'thiet_bi_yeu_cau') else '',
                'ma_gv': pc.ma_gv.ma_gv if hasattr(pc, 'ma_gv') and pc.ma_gv and hasattr(pc.ma_gv, 'ma_gv') else pc.get('ma_gv'),
            })
        return result
    
    @staticmethod
    def _format_constraints_compact(constraints_list) -> dict:
        """
        🔴 TỐI ƯU: Format ràng buộc - CHỈ MÔ TẢ & TRỌNG SỐ
        LLM cần mô tả để hiểu mục đích ràng buộc
        Loại bỏ: tên (không cần), ma (có thể query sau)
        
        Input: List of RangBuocMem objects (normalized from DAL)
        """
        result = {}
        for rb in constraints_list:
            # RangBuocMem has: ma_rang_buoc, ten_rang_buoc, mo_ta, trong_so
            constraint_id = rb.ma_rang_buoc if isinstance(rb, dict) else rb.ma_rang_buoc
            constraint_desc = rb.get('mo_ta') if isinstance(rb, dict) else rb.mo_ta
            constraint_weight = rb.get('trong_so', 1) if isinstance(rb, dict) else rb.trong_so
            
            # Format: ID -> {mo_ta, trong_so}
            result[constraint_id] = {
                'mo_ta': constraint_desc,
                'trong_so': constraint_weight
            }
        return result
    
    @staticmethod
    def _format_preferences_compact(preferences_list) -> list:
        """
        🔴 TỐI ƯU: Format nguyên vọng - CHỈ MÃ GV & SLOT (bitmask)
        Loại bỏ: ten_gv, thu, ca
        """
        result = []
        for nv in preferences_list:
            if hasattr(nv, 'ma_gv') and hasattr(nv, 'time_slot_id'):
                result.append({
                    'gv': nv.ma_gv.ma_gv,
                    'slot': nv.time_slot_id,
                })
            else:
                result.append({
                    'gv': nv.get('ma_gv', nv.get('gv')),
                    'slot': nv.get('time_slot_id', nv.get('slot')),
                })
        return result
    
    def _detect_conflicts(self, schedule_data: dict, semester_code: str) -> dict:
        """
        Phát hiện xung đột hiện tại
        ⭐ Simplified: Xóa processor call không cần thiết
        Validation được làm bởi schedule_validator sau
        """
        # Placeholder - validation thực tế được làm bởi ScheduleValidator
        return {
            'phong_trung': [],
            'giang_vien_trung': [],
            'lop_chua_xep': []
        }
    
    def _build_llm_prompt(self, processed_data: dict, conflicts: dict) -> str:
        """
        🔴 TỐI ƯU: Sử dụng ScheduleAI utilities để format context
        Chỉ gửi DATA COMPACT thôi, KHÔNG gửi instruction (dùng instruction từ schedule_ai.py)
        
        Cấu trúc:
        1. Use format_schedule_context_for_ai() từ ScheduleAI để format thông tin
        2. Thêm constraints nếu có
        3. Append JSON data compact
        """
        # 1. Format context dữ liệu bằng ScheduleAI utilities
        context_part = self.ai.format_schedule_context_for_ai(processed_data)
        
        # 2. Thêm stats mở rộng
        stats = processed_data['stats']
        extended_context = f"""SCHEDULING CONTEXT:

📊 THỐNG KÊ:
- Tổng lớp: {stats['total_classes']}
- Tiết cần xếp: {stats['total_schedules_needed']}
- Phòng: {stats['total_rooms']}
- Time slot: {stats['total_timeslots']}

{context_part}

� CONSTRAINTS APPLIED:
"""
        
        # 3. Thêm constraints nếu có
        for dot_info in processed_data['dot_xep_list']:
            if dot_info.get('constraints'):
                for const_id, const_info in dot_info['constraints'].items():
                    extended_context += f"- {const_id}: {const_info.get('mo_ta', '')}\n"
        
        # 4. Data JSON (compact)
        data_str = json.dumps({
            'classes': [pc for dot in processed_data['dot_xep_list'] for pc in dot['phan_cong']],
            'rooms': processed_data['rooms_by_type'],
            'timeslots': processed_data['timeslots'],
            'constraints': {dot['ma_dot']: dot['constraints'] for dot in processed_data['dot_xep_list']},
            'preferences_count': len([p for dot in processed_data['dot_xep_list'] for p in dot['preferences']]),
        }, ensure_ascii=False, indent=2)
        
        total_size = len(extended_context) + len(data_str)
        logger.info(f"📊 LLM Prompt size: {len(extended_context)} (context) + {len(data_str)} (data) = {total_size} chars")
        
        return extended_context + "\n\nDATA:\n" + data_str
    
    def _call_llm_for_schedule(self, prompt: str, processed_data: dict) -> dict:
        """
        🔴 OPTIMIZED: Gọi ScheduleAI.generate_schedule_json() để tạo lịch
        
        Sử dụng dụng centralized AI interface thay vì gọi Gemini trực tiếp
        - AI instance sử dụng schedule_system_instruction từ ScheduleAI
        - Prompt chỉ chứa dữ liệu, instruction được handle bởi ScheduleAI
        
        Returns:
            Dict optimized như schedule_2025_2026_HK1.json
            {
                "schedule": [
                    {"class": "LOP-001", "room": "A101", "slot": "Thu2-Ca1"},
                    ...
                ],
                "validation": {...},
                "metrics": {...},
                "errors": [...]
            }
        """
        try:
            # Gọi ScheduleAI với prompt đã được build từ _build_llm_prompt
            logger.info("🧠 Gọi ScheduleAI.generate_schedule_json()...")
            
            if isinstance(self.ai, ScheduleAI):
                # Nếu là ScheduleAI, dùng generate_schedule_json
                llm_response = self.ai.generate_schedule_json(prompt)
            else:
                # Fallback cho các instance khác
                logger.warning("⚠️ AI instance không phải ScheduleAI, sử dụng mock response")
                return self._generate_mock_schedule_optimized(processed_data)
            
            # 🔴 MAP SLOT LẠI: T2-C1 → Thu2-Ca1
            return self._parse_and_map_llm_response(llm_response, processed_data)
            
        except Exception as e:
            logger.error(f"❌ Lỗi gọi LLM: {e}", exc_info=True)
            return {
                'schedule': [],
                'validation': {'feasible': False, 'all_assigned': False, 'total_violations': 0},
                'metrics': {'fitness': 0},
                'errors': [f"LLM error: {str(e)}"]
            }
    
    def _parse_and_map_llm_response(self, llm_response: dict, processed_data: dict) -> dict:
        """
        🔴 TỐI ƯU: Parse LLM response & map slot lại
        
        Quy trình:
        1. LLM trả về schedule với slot compact (T2-C1)
        2. Map lại: T2-C1 → Thu2-Ca1 (original ID)
        3. Format optimized (chỉ class, room, slot)
        4. Validate & generate errors
        5. Return format giống schedule_2025_2026_HK1.json
        """
        slot_mapping = processed_data.get('slot_mapping', {})
        
        schedule = []
        violations = []
        mapped_count = 0
        failed_map_count = 0
        
        # 🔴 MAP SLOT & FORMAT
        for entry in llm_response.get('schedule', []):
            try:
                # Lấy slot từ LLM
                compact_slot = entry.get('slot')
                
                # Thử map: T2-C1 → Thu2-Ca1
                original_slot = slot_mapping.get(compact_slot)
                
                # Nếu không map được, kiểm tra xem có phải đã là ID thật không
                if not original_slot:
                    # LLM có thể trả về slot ID thực tế (Thu2-Ca1) thay vì compact format
                    # Kiểm tra xem slot này có tồn tại trong DB không
                    if TimeSlot.objects.filter(time_slot_id=compact_slot).exists():
                        original_slot = compact_slot
                    else:
                        violations.append(f"⚠️ Slot không tồn tại: {compact_slot}")
                        failed_map_count += 1
                        continue
                
                # Format optimized (compact)
                schedule.append({
                    'class': entry.get('class'),
                    'room': entry.get('room'),
                    'slot': original_slot  # ← ĐÃ MAP LẠI
                })
                mapped_count += 1
                
            except Exception as e:
                violations.append(f"❌ Lỗi map slot: {str(e)}")
                failed_map_count += 1
        
        # Collect thêm violations từ LLM response
        if 'violations' in llm_response:
            violations.extend(llm_response['violations'])
        
        logger.info(f"📊 Map slot: {mapped_count} thành công, {failed_map_count} lỗi")
        
        # Chuẩn bị phan_cong dict cho validator
        phan_cong_dict = {}
        for dot_info in processed_data.get('dot_xep_list', []):
            for cls in dot_info.get('phan_cong', []):
                ma_lop = cls.get('ma_lop')
                if ma_lop:
                    phan_cong_dict[ma_lop] = {
                        'ma_gv': cls.get('ma_gv'),
                        'ma_dot': dot_info.get('ma_dot'),
                        'so_sv': cls.get('so_sv', 0),
                        'so_ca_tuan': cls.get('so_ca_tuan', 1),  # Số ca/tuần (1, 2, 3, ...)
                        'class_type': cls.get('loai_phong', 'LT'),  # TH hoặc LT
                        'thiet_bi_yeu_cau': cls.get('thiet_bi_yeu_cau', '')  # Thiết bị yêu cầu cho HC-04
                    }
        
        validation_result = self.validator.validate_schedule_compact(
            schedule_assignments=schedule,
            prepared_data=processed_data,
            phan_cong_dict=phan_cong_dict
        )
        
        # Metrics từ LLM
        metrics = llm_response.get('metrics', {
            'fitness': 0,
            'wish_satisfaction': 0,
            'room_efficiency': 0,
            'total_schedules': len(schedule)
        })
        metrics['total_schedules'] = len(schedule)
        
        # Format optimized như schedule_2025_2026_HK1.json
        result = {
            'schedule': schedule,
            'validation': validation_result,
            'metrics': metrics,
            'errors': violations if violations else []
        }
        
        return result
    
    def _generate_mock_schedule_optimized(self, processed_data: dict) -> dict:
        """
        🔴 OPTIMIZED: Tạo mock schedule (format như schedule_2025_2026_HK1.json)
        
        Returns:
            {
                "schedule": [{"class": "LOP-001", "room": "A101", "slot": "Thu2-Ca1"}],
                "validation": {...},
                "metrics": {...},
                "errors": []
            }
        """
        schedule = []
        timeslots = processed_data.get('timeslots', [])
        slot_idx = 0
        
        # Duyệt từng đợt & phân công
        for dot_info in processed_data['dot_xep_list']:
            rooms_lt = processed_data['rooms_by_type'].get('LT', [])
            rooms_th = processed_data['rooms_by_type'].get('TH', [])
            all_rooms = rooms_lt + rooms_th
            room_idx = 0
            
            for pc in dot_info['phan_cong']:
                if pc['so_ca_tuan'] and all_rooms:
                    # Tạo lịch cho số ca trong tuần
                    for ca_idx in range(min(pc['so_ca_tuan'], len(timeslots))):
                        # Lấy slot (với map lại)
                        ts = timeslots[slot_idx % len(timeslots)]
                        original_slot = ts.get('original_id', ts.get('id', 'Thu2-Ca1'))
                        
                        # Format optimized
                        schedule.append({
                            'class': pc['ma_lop'],
                            'room': all_rooms[room_idx % len(all_rooms)]['ma_phong'],
                            'slot': original_slot  # ← ORIGINAL ID (not compact)
                        })
                        
                        slot_idx += 1
                        room_idx += 1
        
        # Chuẩn bị phan_cong dict cho validator
        phan_cong_dict = {}
        for dot_info in processed_data.get('dot_xep_list', []):
            for cls in dot_info.get('phan_cong', []):
                ma_lop = cls.get('ma_lop')
                if ma_lop:
                    phan_cong_dict[ma_lop] = {
                        'ma_gv': cls.get('ma_gv'),
                        'ma_dot': dot_info.get('ma_dot'),
                        'so_sv': cls.get('so_sv', 0),
                        'so_ca_tuan': cls.get('so_ca_tuan', 1),  # Số ca/tuần (1, 2, 3, ...)
                        'class_type': cls.get('loai_phong', 'LT'),  # TH hoặc LT
                        'thiet_bi_yeu_cau': cls.get('thiet_bi_yeu_cau', '')  # Thiết bị yêu cầu cho HC-04
                    }
        
        validation_result = self.validator.validate_schedule_compact(
            schedule_assignments=schedule,
            prepared_data=processed_data,
            phan_cong_dict=phan_cong_dict
        )
        
        # Format giống schedule_2025_2026_HK1.json
        result = {
            'metrics': {
                'fitness': 0,
                'wish_satisfaction': 0,
                'room_efficiency': 0.85,
                'total_schedules': len(schedule)
            },
            'schedule': schedule,
            'validation': validation_result,
            'errors': []
        }
        
        logger.info(f"✅ Generated mock schedule: {len(schedule)} schedules")
        return result
    
    def _validate_and_save_schedule(
        self,
        schedule_result: dict,
        semester_code: str,
        processed_data: dict
    ) -> str:
        """
        🔴 OPTIMIZED: Validate schedule & lưu vào file (format giống schedule_2025_2026_HK1.json)
        
        Input: 
            schedule_result: {
                'schedule': [{class, room, slot (original ID)}, ...],
                'validation': {...},
                'metrics': {...},
                'errors': [...]
            }
        """
        try:
            # schedule_result đã là dict, không cần parse JSON
            
            # Lưu file
            filename = f"schedule_llm_{semester_code.replace('-', '_').replace('_', '-')}.json"
            output_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'output')
            os.makedirs(output_dir, exist_ok=True)
            
            filepath = os.path.join(output_dir, filename)
            
            # 🔴 Format output giống schedule_2025_2026_HK1.json
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(schedule_result, f, ensure_ascii=False, indent=2, default=json_serial)
            
            logger.info(f"💾 Đã lưu lịch vào: {filepath}")
            
            # Format thông báo
            num_schedules = len(schedule_result.get('schedule', []))
            metrics = schedule_result.get('metrics', {})
            validation = schedule_result.get('validation', {})
            errors = schedule_result.get('errors', [])
            
            message = f"""
✅ TẠO LỊCH THÀNH CÔNG
─────────────────────────────────────────
📊 Kết quả:
  • Tổng lịch: {num_schedules}
  • Fitness: {metrics.get('fitness', 0):.2f}
  • Wish satisfaction: {metrics.get('wish_satisfaction', 0):.1%}
  • Room efficiency: {metrics.get('room_efficiency', 0):.1%}

🔍 Validation:
  • Feasible: {validation.get('feasible', False)}
  • All assigned: {validation.get('all_assigned', False)}
  • Total violations: {validation.get('total_violations', 0)}

{'❌ Violations:' if errors else '✅ No violations'}
{chr(10).join(['  ' + str(e) for e in errors[:5]])}{'...' if len(errors) > 5 else ''}

📁 File: {filepath}
"""
            return message
            
        except Exception as e:
            logger.error(f"❌ Lỗi lưu lịch: {e}", exc_info=True)
            return f"❌ Lỗi: {str(e)}"
            
            