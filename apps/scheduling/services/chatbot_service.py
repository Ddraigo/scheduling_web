"""
Chatbot Service - Tương tác hỏi đáp về lịch học và dữ liệu database
Sử dụng Google Gemini API
"""

import os
import re
import json
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from google import genai
from google.genai import types

from .data_access_layer import (
    DataAccessLayer, 
    get_giang_vien_info_dict, 
    get_lop_info_dict
)

logger = logging.getLogger(__name__)


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
        """Khởi tạo chatbot với Google Gemini API"""
        api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("Cần cấu hình GEMINI_API_KEY hoặc GOOGLE_API_KEY")
        
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-pro"
        
        # System instruction cho chatbot
        self.system_instruction = """Bạn là trợ lý thông minh cho hệ thống quản lý thời khóa biểu đại học.

Nhiệm vụ của bạn:
1. Trả lời các câu hỏi về giảng viên, môn học, phòng học, lịch dạy
2. Giúp tra cứu thông tin từ database đã được cung cấp
3. Gợi ý phòng phù hợp khi người dùng hỏi về xếp lịch
4. Trả lời bằng tiếng Việt, ngắn gọn và chính xác

Quy tắc quan trọng:
- Phòng LT (Lý thuyết): Dùng cho môn lý thuyết, có bàn ghế thường
- Phòng TH (Thực hành): Dùng cho môn thực hành, có máy tính/thiết bị
- Khi gợi ý phòng, PHẢI kiểm tra:
  + Loại phòng phù hợp (LT/TH)
  + Sức chứa đủ cho số sinh viên
  + Phòng trống trong time slot được hỏi

Format trả lời:
- Sử dụng emoji phù hợp để dễ đọc
- Dùng bullet points khi liệt kê
- Khi không tìm thấy thông tin, nói rõ ràng"""

        # Conversation history
        self.conversation_history: List[Dict[str, str]] = []
        
    def _build_context_from_database(self, ma_dot: str = None) -> str:
        """
        Xây dựng context từ database để cung cấp cho LLM
        
        Args:
            ma_dot: Mã đợt xếp (optional). Nếu None, dùng đợt đang hoạt động
        """
        context_parts = []
        
        try:
            from ..models import (
                Khoa, BoMon, GVDayMon, GiangVien, MonHoc, LopMonHoc,
                PhanCong, ThoiKhoaBieu, NguyenVong, NgayNghiDot, RangBuocMem, DotXep
            )
            
            # 0. Thống kê theo Khoa và Bộ môn
            all_khoa = Khoa.objects.all().prefetch_related('bo_mon_list__giang_vien_list')
            context_parts.append("🏛️ THỐNG KÊ GIẢNG VIÊN THEO KHOA VÀ BỘ MÔN:")
            for khoa in all_khoa:
                bo_mon_list = khoa.bo_mon_list.all()
                total_gv_khoa = sum(bm.giang_vien_list.count() for bm in bo_mon_list)
                context_parts.append(f"\n📌 {khoa.ten_khoa} ({khoa.ma_khoa}): {total_gv_khoa} giảng viên")
                for bm in bo_mon_list:
                    gv_count = bm.giang_vien_list.count()
                    gv_names = [gv.ten_gv for gv in bm.giang_vien_list.all()[:5]]
                    gv_str = ", ".join(gv_names) if gv_names else "Chưa có"
                    if gv_count > 5:
                        gv_str += f"... (+{gv_count - 5} GV khác)"
                    context_parts.append(f"  └─ {bm.ten_bo_mon}: {gv_count} GV ({gv_str})")
            
            # 1. Lấy thông tin giảng viên chi tiết với Khoa/Bộ môn
            giang_vien_total = GiangVien.objects.count()
            giang_vien_list = GiangVien.objects.select_related('ma_bo_mon', 'ma_bo_mon__ma_khoa').all()[:50]
            gv_summary = []
            for gv in giang_vien_list:
                try:
                    gv_day_mon = GVDayMon.objects.filter(ma_gv=gv.ma_gv).select_related('ma_mon_hoc')
                    mon_day = [m.ma_mon_hoc.ten_mon_hoc for m in gv_day_mon]
                    khoa_name = gv.ma_bo_mon.ma_khoa.ten_khoa if gv.ma_bo_mon and gv.ma_bo_mon.ma_khoa else "N/A"
                    bm_name = gv.ma_bo_mon.ten_bo_mon if gv.ma_bo_mon else "N/A"
                    gv_summary.append(f"- {gv.ten_gv} ({gv.ma_gv}) | Khoa: {khoa_name} | BM: {bm_name} | Dạy: {', '.join(mon_day[:3]) if mon_day else 'chưa phân công'}")
                except Exception:
                    gv_summary.append(f"- {gv.ten_gv} ({gv.ma_gv})")
            
            context_parts.append(f"\n📚 DANH SÁCH GIẢNG VIÊN CHI TIẾT (Tổng: {giang_vien_total}, hiển thị {min(30, len(gv_summary))}):")
            context_parts.append("\n".join(gv_summary[:30]))
            
            # 2. Danh sách môn học
            mon_hoc_total = MonHoc.objects.count()
            mon_hoc_list = MonHoc.objects.all()[:50]
            context_parts.append(f"\n📖 DANH SÁCH MÔN HỌC (Tổng: {mon_hoc_total}, hiển thị {len(mon_hoc_list)}):")
            for mh in mon_hoc_list:
                context_parts.append(f"- {mh.ten_mon_hoc} ({mh.ma_mon_hoc}): {mh.so_tin_chi or 0} TC, LT: {mh.so_tiet_lt or 0} tiết, TH: {mh.so_tiet_th or 0} tiết")
            
            # 3. Lấy thông tin phòng học
            phong_list = DataAccessLayer.get_all_phong_hoc()
            phong_lt = [p for p in phong_list if 'thuyết' in (p.loai_phong or '').lower() or 'lt' in (p.loai_phong or '').lower()]
            phong_th = [p for p in phong_list if 'hành' in (p.loai_phong or '').lower() or 'th' in (p.loai_phong or '').lower()]
            
            context_parts.append(f"\n🏫 PHÒNG HỌC (Tổng: {len(phong_list)} phòng):")
            context_parts.append(f"- Phòng Lý thuyết (LT): {len(phong_lt)} phòng")
            for p in phong_lt[:10]:
                context_parts.append(f"  + {p.ma_phong}: Sức chứa {p.suc_chua} SV")
            if len(phong_lt) > 10:
                context_parts.append(f"  + ... và {len(phong_lt) - 10} phòng LT khác")
            context_parts.append(f"- Phòng Thực hành (TH): {len(phong_th)} phòng")
            for p in phong_th[:10]:
                context_parts.append(f"  + {p.ma_phong}: Sức chứa {p.suc_chua} SV, Thiết bị: {p.thiet_bi or 'N/A'}")
            if len(phong_th) > 10:
                context_parts.append(f"  + ... và {len(phong_th) - 10} phòng TH khác")
            
            # 4. Lấy time slots
            timeslots = DataAccessLayer.get_all_time_slot()
            context_parts.append(f"\n⏰ KHUNG THỜI GIAN (Tổng: {len(timeslots)} time slots):")
            ts_by_day = {}
            for ts in timeslots:
                day = ts.thu
                if day not in ts_by_day:
                    ts_by_day[day] = []
                ts_by_day[day].append(f"Ca {ts.ca.ma_khung_gio} ({ts.ca.gio_bat_dau.strftime('%H:%M')}-{ts.ca.gio_ket_thuc.strftime('%H:%M')})")
            
            for day in sorted(ts_by_day.keys()):
                context_parts.append(f"- Thứ {day}: {', '.join(ts_by_day[day])}")
            
            # 5. Danh sách đợt xếp lịch
            dot_xep_total = DotXep.objects.count()
            dot_xep_list = DotXep.objects.all()[:10]
            context_parts.append(f"\n📅 DANH SÁCH ĐỢT XẾP LỊCH (Tổng: {dot_xep_total}):")
            for dx in dot_xep_list:
                context_parts.append(f"- {dx.ten_dot} ({dx.ma_dot}): Trạng thái {dx.trang_thai}")
            
            # 6. Nếu có mã đợt, lấy thêm thông tin chi tiết
            if ma_dot:
                try:
                    # Thống kê cơ bản
                    thong_ke = DataAccessLayer.get_thong_ke_dot_xep(ma_dot)
                    context_parts.append(f"\n📊 THỐNG KÊ ĐỢT XẾP {ma_dot}:")
                    context_parts.append(f"- Tổng lớp: {thong_ke['tong_lop']}")
                    context_parts.append(f"- Lớp đã xếp: {thong_ke['lop_da_xep']}")
                    context_parts.append(f"- Tỷ lệ: {thong_ke['tyle_xep_xong']:.1f}%")
                    
                    # Danh sách lớp môn học trong đợt
                    phan_cong_total = PhanCong.objects.filter(ma_dot=ma_dot).count()
                    phan_cong_list = PhanCong.objects.filter(ma_dot=ma_dot).select_related('ma_lop', 'ma_lop__ma_mon_hoc', 'ma_gv')[:50]
                    context_parts.append(f"\n📋 DANH SÁCH LỚP MÔN HỌC TRONG ĐỢT (Tổng: {phan_cong_total} lớp, hiển thị {len(phan_cong_list)}):")
                    for pc in phan_cong_list[:30]:
                        gv_name = pc.ma_gv.ten_gv if pc.ma_gv else "Chưa phân công GV"
                        lop = pc.ma_lop
                        context_parts.append(f"- {lop.ma_lop}: {lop.ma_mon_hoc.ten_mon_hoc} | SV: {lop.so_luong_sv or 0} | GV: {gv_name} | Tuần {pc.tuan_bd}-{pc.tuan_kt}")
                    
                    # Thời khóa biểu đã xếp
                    tkb_total = ThoiKhoaBieu.objects.filter(ma_dot=ma_dot).count()
                    tkb_list = ThoiKhoaBieu.objects.filter(ma_dot=ma_dot).select_related('ma_lop', 'ma_phong', 'time_slot_id', 'time_slot_id__ca')[:50]
                    context_parts.append(f"\n🗓️ THỜI KHÓA BIỂU ĐÃ XẾP (Tổng: {tkb_total} buổi, hiển thị {len(tkb_list)}):")
                    for tkb in tkb_list[:30]:
                        ts = tkb.time_slot_id
                        thu_str = 'CN' if ts.thu == 8 else f'T{ts.thu}'
                        phong = tkb.ma_phong.ma_phong if tkb.ma_phong else "Chưa xếp phòng"
                        context_parts.append(f"- {tkb.ma_lop.ma_lop}: {thu_str} Ca{ts.ca.ma_khung_gio} | Phòng: {phong} | Tuần: {tkb.tuan_hoc[:10]}...")
                    
                    # Nguyện vọng GV trong đợt - LẤY TẤT CẢ
                    nguyen_vong_total = NguyenVong.objects.filter(ma_dot=ma_dot).count()
                    nguyen_vong_list = NguyenVong.objects.filter(ma_dot=ma_dot).select_related('ma_gv', 'time_slot_id', 'time_slot_id__ca')
                    if nguyen_vong_total > 0:
                        context_parts.append(f"\n💬 NGUYỆN VỌNG GV TRONG ĐỢT (Tổng: {nguyen_vong_total} nguyện vọng):")
                        # Group theo GV
                        nv_by_gv = {}
                        for nv in nguyen_vong_list:
                            gv_key = f"{nv.ma_gv.ten_gv} ({nv.ma_gv.ma_gv})"
                            if gv_key not in nv_by_gv:
                                nv_by_gv[gv_key] = []
                            ts = nv.time_slot_id
                            thu_str = 'CN' if ts.thu == 8 else f'Thứ {ts.thu}'
                            nv_by_gv[gv_key].append(f"{thu_str}-Ca{ts.ca.ma_khung_gio}")
                        
                        context_parts.append(f"| STT | Giảng viên | Số NV | Nguyện vọng thời gian |")
                        context_parts.append(f"|-----|------------|-------|----------------------|")
                        for idx, (gv, slots) in enumerate(sorted(nv_by_gv.items()), 1):
                            slots_str = ", ".join(sorted(set(slots)))
                            context_parts.append(f"| {idx} | {gv} | {len(slots)} | {slots_str} |")
                    
                    # Ngày nghỉ trong đợt
                    ngay_nghi_list = NgayNghiDot.objects.filter(ma_dot=ma_dot)
                    if ngay_nghi_list.exists():
                        context_parts.append(f"\n🏖️ NGÀY NGHỈ TRONG ĐỢT:")
                        for nn in ngay_nghi_list:
                            context_parts.append(f"- {nn.ten_ngay_nghi or 'Nghỉ'}: {nn.ngay_bd} ({nn.so_ngay_nghi} ngày)")
                    
                except Exception as e:
                    logger.warning(f"Không lấy được thông tin đợt {ma_dot}: {e}")
            
            # 7. Ràng buộc mềm
            rang_buoc_list = RangBuocMem.objects.all()[:10]
            if rang_buoc_list.exists():
                context_parts.append("\n⚠️ CÁC RÀNG BUỘC MỀM:")
                for rb in rang_buoc_list:
                    context_parts.append(f"- {rb.ten_rang_buoc}: Trọng số {rb.trong_so}")
            
        except Exception as e:
            logger.error(f"Lỗi build context: {e}")
            context_parts.append(f"[Lỗi lấy dữ liệu: {e}]")
        
        return "\n".join(context_parts)
    
    def _extract_query_intent(self, message: str) -> Dict[str, Any]:
        """
        Phân tích ý định từ câu hỏi người dùng
        
        Returns:
            Dict với các key: intent, entities (giảng viên, phòng, thời gian, môn học)
        """
        message_lower = message.lower()
        
        intent = {
            'type': 'general',
            'entities': {
                'giang_vien': None,
                'mon_hoc': None,
                'phong': None,
                'thu': None,
                'ca': None,
                'loai_phong': None
            }
        }
        
        # Detect intent type
        if any(kw in message_lower for kw in ['giảng viên', 'gv', 'thầy', 'cô', 'giáo viên']):
            intent['type'] = 'giang_vien_info'
        elif any(kw in message_lower for kw in ['phòng trống', 'phòng nào', 'gợi ý phòng', 'xếp vào']):
            intent['type'] = 'room_suggestion'
        elif any(kw in message_lower for kw in ['lịch', 'thời khóa biểu', 'tkb']):
            intent['type'] = 'schedule_query'
        elif any(kw in message_lower for kw in ['môn', 'học phần']):
            intent['type'] = 'mon_hoc_info'
        
        # Extract day of week
        day_mapping = {
            'thứ 2': 2, 'thứ hai': 2, 't2': 2,
            'thứ 3': 3, 'thứ ba': 3, 't3': 3,
            'thứ 4': 4, 'thứ tư': 4, 't4': 4,
            'thứ 5': 5, 'thứ năm': 5, 't5': 5,
            'thứ 6': 6, 'thứ sáu': 6, 't6': 6,
            'thứ 7': 7, 'thứ bảy': 7, 't7': 7,
        }
        for pattern, day in day_mapping.items():
            if pattern in message_lower:
                intent['entities']['thu'] = day
                break
        
        # Extract ca (period)
        ca_match = re.search(r'ca\s*(\d+)', message_lower)
        if ca_match:
            intent['entities']['ca'] = int(ca_match.group(1))
        
        # Detect room type
        if any(kw in message_lower for kw in ['thực hành', 'th', 'máy tính']):
            intent['entities']['loai_phong'] = 'TH'
        elif any(kw in message_lower for kw in ['lý thuyết', 'lt']):
            intent['entities']['loai_phong'] = 'LT'
        
        return intent
    
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
        Tìm thông tin giảng viên theo tên hoặc mã
        """
        try:
            all_gv = DataAccessLayer.get_all_giang_vien()
            
            # Tìm theo mã hoặc tên (case insensitive)
            search_lower = search_term.lower()
            for gv in all_gv:
                if search_lower in gv.ma_gv.lower() or search_lower in gv.ten_gv.lower():
                    return get_giang_vien_info_dict(gv.ma_gv)
            
            return None
        except Exception as e:
            logger.error(f"Lỗi get_teacher_info: {e}")
            return None
    
    def _process_with_tools(self, message: str, intent: Dict, ma_dot: str = None) -> str:
        """
        Xử lý câu hỏi với các tools (functions) nội bộ
        Trả về thông tin bổ sung để đưa vào context cho LLM
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
        
        # Teacher info - search for teacher name in message
        if intent['type'] == 'giang_vien_info':
            # Try to extract teacher name/code from message
            # Simple approach: look for words after "giảng viên", "thầy", "cô"
            patterns = [
                r'giảng viên\s+(\w+)',
                r'thầy\s+(\w+)',
                r'cô\s+(\w+)',
                r'gv\s+(\w+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, message.lower())
                if match:
                    search_term = match.group(1)
                    gv_info = self._get_teacher_info(search_term)
                    if gv_info:
                        additional_context.append(f"\n👤 THÔNG TIN GIẢNG VIÊN {gv_info['ten_gv']}:")
                        additional_context.append(f"- Mã GV: {gv_info['ma_gv']}")
                        additional_context.append(f"- Bộ môn: {gv_info['bo_mon']['ten']}")
                        additional_context.append(f"- Loại: {gv_info['loai_gv']}")
                        if gv_info['mon_hoc_co_the_day']:
                            mon_list = [m['ten'] for m in gv_info['mon_hoc_co_the_day'][:5]]
                            additional_context.append(f"- Môn dạy: {', '.join(mon_list)}")
                    break
        
        return "\n".join(additional_context)
    
    def chat(self, message: str, ma_dot: str = None) -> Dict[str, Any]:
        """
        Xử lý tin nhắn từ người dùng
        
        Args:
            message: Câu hỏi/tin nhắn từ người dùng
            ma_dot: Mã đợt xếp hiện tại (optional)
            
        Returns:
            Dict với response và metadata
        """
        try:
            # 1. Phân tích intent
            intent = self._extract_query_intent(message)
            logger.info(f"Intent detected: {intent['type']}")
            
            # 2. Lấy thông tin từ database dựa trên intent
            tool_context = self._process_with_tools(message, intent, ma_dot)
            
            # 3. Xây dựng context tổng hợp
            db_context = self._build_context_from_database(ma_dot)
            
            # 4. Tạo prompt đầy đủ
            full_context = f"""
{db_context}

{tool_context}

---
Câu hỏi của người dùng: {message}
"""
            
            # 5. Gọi Gemini API với retry cho rate limit và overload
            max_retries = 3
            retry_delay = 2  # seconds
            response = None
            models_to_try = [self.model, "gemini-2.5-flash", "gemini-2.0-flash", ]
            
            for model_idx, current_model in enumerate(models_to_try):
                for attempt in range(max_retries):
                    try:
                        response = self.client.models.generate_content(
                            model=current_model,
                            contents=full_context,
                            config=types.GenerateContentConfig(
                                system_instruction=self.system_instruction,
                                temperature=0.7,
                                max_output_tokens=8192,
                            )
                        )
                        break  # Success, exit retry loop
                    except Exception as api_err:
                        error_str = str(api_err)
                        # Handle rate limit (429) and overload (503)
                        if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str or '503' in error_str or 'UNAVAILABLE' in error_str:
                            if attempt < max_retries - 1:
                                logger.warning(f"API error with {current_model}, retrying in {retry_delay}s... (attempt {attempt + 1})")
                                time.sleep(retry_delay)
                                retry_delay *= 2  # Exponential backoff
                            else:
                                logger.warning(f"Model {current_model} failed, trying next model...")
                                break  # Try next model
                        else:
                            raise api_err
                
                if response:
                    break  # Got response, exit model loop
                retry_delay = 2  # Reset delay for next model
            
            if not response:
                return {
                    'success': False,
                    'response': "⏳ Tất cả các model AI đang quá tải. Vui lòng thử lại sau 1-2 phút.",
                    'error': 'all_models_unavailable'
                }
            
            # 6. Lưu vào history
            self.conversation_history.append({
                'role': 'user',
                'content': message,
                'timestamp': datetime.now().isoformat()
            })
            
            # Extract text from response properly (handling thought_signature parts)
            response_text = ""
            try:
                if response.candidates and len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    if candidate.content and candidate.content.parts:
                        text_parts = []
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                text_parts.append(part.text)
                        response_text = "".join(text_parts)
                
                if not response_text and response.text:
                    response_text = response.text
            except Exception as text_err:
                logger.warning(f"Error extracting text: {text_err}")
                response_text = response.text if hasattr(response, 'text') and response.text else ""
            
            if not response_text:
                response_text = "Xin lỗi, tôi không thể xử lý câu hỏi này."
            
            self.conversation_history.append({
                'role': 'assistant', 
                'content': response_text,
                'timestamp': datetime.now().isoformat()
            })
            
            return {
                'success': True,
                'response': response_text,
                'intent': intent,
                'metadata': {
                    'model': self.model,
                    'timestamp': datetime.now().isoformat()
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
    
    def clear_history(self):
        """Xóa lịch sử hội thoại"""
        self.conversation_history = []


# Singleton instance
_chatbot_instance = None

def get_chatbot() -> ScheduleChatbot:
    """Lấy singleton instance của chatbot"""
    global _chatbot_instance
    if _chatbot_instance is None:
        _chatbot_instance = ScheduleChatbot()
    return _chatbot_instance
