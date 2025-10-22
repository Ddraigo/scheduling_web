"""
LLM Integration Service
Sử dụng Data Access Layer để lấy dữ liệu từ database
"""

import json
from typing import Dict, List, Any
from datetime import datetime
from .data_access_layer import DataAccessLayer, get_giang_vien_info_dict, get_lop_info_dict


class LLMDataProcessor:
    """
    Xử lý dữ liệu từ database thành format phù hợp cho LLM
    """
    
    @staticmethod
    def prepare_dataset_for_llm_prompt(ma_dot: str) -> Dict[str, Any]:
        """
        Chuẩn bị dataset cho LLM prompt
        Dữ liệu được định dạng sao cho LLM dễ hiểu
        """
        dataset = DataAccessLayer.get_dataset_for_llm(ma_dot)
        thong_ke = DataAccessLayer.get_thong_ke_dot_xep(ma_dot)
        
        phan_cong_formatted = []
        for pc in dataset['phan_cong']:
            phan_cong_formatted.append({
                'ma_lop': pc.ma_lop.ma_lop,
                'mon_hoc': pc.ma_lop.ma_mon_hoc.ten_mon_hoc,
                'nhom': pc.ma_lop.nhom_mh,
                'so_sv': pc.ma_lop.so_luong_sv,
                'so_ca_tuan': pc.ma_lop.so_ca_tuan,
                'giang_vien': {
                    'ma': pc.ma_gv.ma_gv if pc.ma_gv else None,
                    'ten': pc.ma_gv.ten_gv if pc.ma_gv else None,
                    'bo_mon': pc.ma_gv.ma_bo_mon.ten_bo_mon if pc.ma_gv else None,
                } if pc.ma_gv else None,
                'yeu_cau_phong': pc.ma_lop.thiet_bi_yeu_cau,
            })
        
        tkb_formatted = []
        for t in dataset['tkb']:
            tkb_formatted.append({
                'ma_lop': t.lop_mon_hoc.ma_lop,
                'phong': t.phong_hoc.ma_phong,
                'time_slot': t.time_slot.time_slot_id,
                'thu': t.time_slot.thu,
                'ca': t.time_slot.ca.ma_khung_gio,
                'gio_bat_dau': t.time_slot.ca.gio_bat_dau.strftime('%H:%M'),
                'gio_ket_thuc': t.time_slot.ca.gio_ket_thuc.strftime('%H:%M'),
                'giang_vien': t.phan_cong.ma_gv.ten_gv if t.phan_cong else None,
            })
        
        phong_formatted = []
        for p in dataset['all_phong']:
            phong_formatted.append({
                'ma_phong': p.ma_phong,
                'loai': p.loai_phong,
                'suc_chua': p.suc_chua,
                'thiet_bi': p.thiet_bi,
            })
        
        time_slot_formatted = []
        for ts in dataset['all_time_slot']:
            time_slot_formatted.append({
                'time_slot_id': ts.time_slot_id,
                'thu': ts.thu,
                'ca': ts.ca.ma_khung_gio,
                'ten_ca': ts.ca.ten_ca,
                'gio_bat_dau': ts.ca.gio_bat_dau.strftime('%H:%M'),
                'gio_ket_thuc': ts.ca.gio_ket_thuc.strftime('%H:%M'),
            })
        
        return {
            'dot_xep': {
                'ma_dot': dataset['dot_xep'].ma_dot,
                'nam_hoc': dataset['dot_xep'].ma_du_kien_dt.nam_hoc,
                'hoc_ky': dataset['dot_xep'].ma_du_kien_dt.get_hoc_ky_display(),
                'trang_thai': dataset['dot_xep'].trang_thai,
            },
            'thong_ke': thong_ke,
            'phan_cong': phan_cong_formatted,
            'tkb_hien_tai': tkb_formatted,
            'phong_hoc': phong_formatted,
            'time_slot': time_slot_formatted,
        }
    
    @staticmethod
    def prepare_giang_vien_schedule_for_llm(ma_gv: str, ma_dot: str = None) -> Dict[str, Any]:
        """
        Chuẩn bị lịch giảng viên cho LLM
        """
        gv_info = get_giang_vien_info_dict(ma_gv)
        tkb_list = DataAccessLayer.get_tkb_by_giang_vien(ma_gv, ma_dot)
        
        tkb_formatted = []
        for t in tkb_list:
            tkb_formatted.append({
                'lop': t.lop_mon_hoc.ma_lop,
                'mon_hoc': t.lop_mon_hoc.mon_hoc.ten_mon_hoc,
                'phong': t.phong_hoc.ma_phong,
                'thu': t.time_slot.thu,
                'ca': t.time_slot.ca.ma_khung_gio,
                'gio': f"{t.time_slot.ca.gio_bat_dau.strftime('%H:%M')}-{t.time_slot.ca.gio_ket_thuc.strftime('%H:%M')}",
            })
        
        return {
            'giang_vien': gv_info,
            'lich_day': tkb_formatted,
            'tong_lich': len(tkb_formatted),
        }
    
    @staticmethod
    def detect_scheduling_conflicts(ma_dot: str) -> Dict[str, List[Dict]]:
        """
        Phát hiện xung đột trong lịch học
        Dùng cho LLM để tìm vấn đề cần sửa
        """
        xung_dot_data = DataAccessLayer.get_dataset_xung_dot(ma_dot)
        
        conflicts = {
            'phong_trung': [],
            'giang_vien_trung': [],
            'lop_chua_xep': []
        }
        
        # Xung đột phòng
        for key, tkb_list in xung_dot_data['xung_dot_phong'].items():
            if len(tkb_list) > 1:
                conflict_info = {
                    'phong': tkb_list[0].phong_hoc.ma_phong,
                    'time_slot': tkb_list[0].time_slot.time_slot_id,
                    'lop_list': [t.lop_mon_hoc.ma_lop for t in tkb_list],
                    'so_trung': len(tkb_list)
                }
                conflicts['phong_trung'].append(conflict_info)
        
        # Xung đột giảng viên (cùng ca)
        tkb_list = DataAccessLayer.get_all_tkb()
        gv_schedule = {}
        for t in tkb_list:
            if t.phan_cong and t.phan_cong.ma_gv:
                key = f"{t.phan_cong.ma_gv.ma_gv}_{t.time_slot.time_slot_id}"
                if key not in gv_schedule:
                    gv_schedule[key] = []
                gv_schedule[key].append(t)
        
        for key, tkb_items in gv_schedule.items():
            if len(tkb_items) > 1:
                gv = tkb_items[0].phan_cong.ma_gv
                conflict_info = {
                    'giang_vien': gv.ten_gv,
                    'ma_gv': gv.ma_gv,
                    'time_slot': tkb_items[0].time_slot.time_slot_id,
                    'lop_list': [t.lop_mon_hoc.ma_lop for t in tkb_items],
                    'so_trung': len(tkb_items)
                }
                conflicts['giang_vien_trung'].append(conflict_info)
        
        # Lớp chưa được xếp lịch
        for pc in xung_dot_data['lop_chua_phan_cong']:
            conflicts['lop_chua_xep'].append({
                'ma_lop': pc.ma_lop.ma_lop,
                'mon_hoc': pc.ma_lop.mon_hoc.ten_mon_hoc,
                'so_sv': pc.ma_lop.so_luong_sv,
            })
        
        return conflicts
    
    @staticmethod
    def get_phong_hoc_truong_hop_dat_yeu_cau(so_luong_sv: int, yeu_cau_thiet_bi: str = None) -> List[Dict]:
        """
        Tìm phòng học phù hợp cho lớp
        Dùng cho LLM khi đề xuất phòng
        """
        phong_list = DataAccessLayer.get_phong_hoc_co_du_suc_chua(so_luong_sv)
        
        if yeu_cau_thiet_bi:
            phong_list = phong_list.filter(thiet_bi__icontains=yeu_cau_thiet_bi)
        
        return [
            {
                'ma_phong': p.ma_phong,
                'loai': p.loai_phong,
                'suc_chua': p.suc_chua,
                'thiet_bi': p.thiet_bi,
                'du_suc_chua': p.suc_chua >= so_luong_sv,
            }
            for p in phong_list
        ]
    
    @staticmethod
    def get_giang_vien_trong_time_slot(ma_time_slot: str) -> List[Dict]:
        """
        Lấy danh sách giảng viên trống trong time slot
        """
        tkb_in_slot = DataAccessLayer.get_tkb_by_time_slot(ma_time_slot)
        busy_gv = set()
        
        for t in tkb_in_slot:
            if t.phan_cong and t.phan_cong.ma_gv:
                busy_gv.add(t.phan_cong.ma_gv.ma_gv)
        
        all_gv = DataAccessLayer.get_all_giang_vien()
        available_gv = all_gv.exclude(ma_gv__in=busy_gv)
        
        return [
            {
                'ma_gv': g.ma_gv,
                'ten_gv': g.ten_gv,
                'bo_mon': g.ma_bo_mon.ten_bo_mon,
                'loai': g.loai_gv,
            }
            for g in available_gv
        ]


class LLMPromptBuilder:
    """
    Xây dựng prompt cho LLM dựa trên dữ liệu từ database
    """
    
    @staticmethod
    def build_scheduling_context_prompt(ma_dot: str) -> str:
        """
        Xây dựng prompt context cho LLM về lịch học
        """
        processor = LLMDataProcessor()
        dataset = processor.prepare_dataset_for_llm_prompt(ma_dot)
        conflicts = processor.detect_scheduling_conflicts(ma_dot)
        
        prompt = f"""
Bối cảnh Hệ thống Xếp Lịch Học:

**Đợt Xếp Hiện Tại:**
- Mã đợt: {dataset['dot_xep']['ma_dot']}
- Năm học: {dataset['dot_xep']['nam_hoc']}
- Học kỳ: {dataset['dot_xep']['hoc_ky']}
- Trạng thái: {dataset['dot_xep']['trang_thai']}

**Thống Kê:**
- Tổng lớp: {dataset['thong_ke']['tong_lop']}
- Lớp đã xếp: {dataset['thong_ke']['lop_da_xep']}
- Tỷ lệ hoàn thành: {dataset['thong_ke']['tyle_xep_xong']:.1f}%
- Tổng giảng viên: {dataset['thong_ke']['tong_giang_vien']}
- Tổng phòng sử dụng: {dataset['thong_ke']['tong_phong_su_dung']}
- Tổng lịch: {dataset['thong_ke']['tong_lich']}

**Xung Đột Hiện Tại:**
- Phòng bị trùng: {len(conflicts['phong_trung'])} trường hợp
- Giảng viên bị trùng: {len(conflicts['giang_vien_trung'])} trường hợp  
- Lớp chưa xếp: {len(conflicts['lop_chua_xep'])} lớp

**Phòng Học Có Sẵn:** {len(dataset['phong_hoc'])} phòng
**Time Slot Có Sẵn:** {len(dataset['time_slot'])} slot
"""
        return prompt
    
    @staticmethod
    def build_giang_vien_analysis_prompt(ma_gv: str) -> str:
        """
        Xây dựng prompt phân tích lịch giảng viên
        """
        processor = LLMDataProcessor()
        gv_data = processor.prepare_giang_vien_schedule_for_llm(ma_gv)
        
        prompt = f"""
Phân Tích Lịch Giảng Viên:

**Thông Tin Giảng Viên:**
- Mã: {gv_data['giang_vien']['ma_gv']}
- Tên: {gv_data['giang_vien']['ten_gv']}
- Loại: {gv_data['giang_vien']['loai_gv']}
- Bộ môn: {gv_data['giang_vien']['bo_mon']['ten']}
- Email: {gv_data['giang_vien']['email']}

**Môn Có Thể Dạy:** {gv_data['giang_vien']['so_mon_co_the_day']} môn

**Lịch Dạy Hiện Tại:** {gv_data['tong_lich']} tiết
"""
        return prompt


# ======================== HELPER FUNCTIONS ========================

def get_dataset_json(ma_dot: str) -> str:
    """Lấy toàn bộ dataset dưới dạng JSON"""
    processor = LLMDataProcessor()
    dataset = processor.prepare_dataset_for_llm_prompt(ma_dot)
    return json.dumps(dataset, ensure_ascii=False, indent=2)


def get_conflict_report_json(ma_dot: str) -> str:
    """Lấy báo cáo xung đột dưới dạng JSON"""
    processor = LLMDataProcessor()
    conflicts = processor.detect_scheduling_conflicts(ma_dot)
    return json.dumps(conflicts, ensure_ascii=False, indent=2)
