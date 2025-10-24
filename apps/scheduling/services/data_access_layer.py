"""
Data Access Layer (DAL) - Lấy dữ liệu từ database cho LLM và các hàm khác
Tập trung hóa tất cả các truy vấn, dễ tái sử dụng, dễ bảo trì
"""

from django.db.models import Prefetch, Count, Q
from datetime import datetime, timedelta
import logging
from ..models import (
    Khoa, BoMon, GiangVien, MonHoc, PhongHoc, LopMonHoc,
    DotXep, PhanCong, TimeSlot, ThoiKhoaBieu, DuKienDT,
    RangBuocMem, KhungTG, NguyenVong, GVDayMon, RangBuocTrongDot
)

logger = logging.getLogger(__name__)


class DataAccessLayer:
    """
    Lớp truy cập dữ liệu tập trung.
    Mọi hàm lấy dữ liệu phức tạp nên đặt ở đây để tái sử dụng
    """
    
    # ======================== KHOA ========================
    
    @staticmethod
    def get_all_khoa():
        """Lấy tất cả khoa"""
        return Khoa.objects.all()
    
    @staticmethod
    def get_khoa_by_id(ma_khoa):
        """Lấy khoa theo mã"""
        return Khoa.objects.get(ma_khoa=ma_khoa)
    
    @staticmethod
    def get_khoa_with_bo_mon():
        """Lấy tất cả khoa kèm theo bộ môn (optimize query)"""
        return Khoa.objects.prefetch_related('bo_mon_list').all()
    
    # ======================== BỘ MÔN ========================
    
    @staticmethod
    def get_all_bo_mon():
        """Lấy tất cả bộ môn"""
        return BoMon.objects.select_related('ma_khoa').all()
    
    @staticmethod
    def get_bo_mon_by_khoa(ma_khoa):
        """Lấy tất cả bộ môn theo khoa"""
        return BoMon.objects.filter(ma_khoa=ma_khoa)
    
    # ======================== GIẢNG VIÊN ========================
    
    @staticmethod
    def get_all_giang_vien():
        """Lấy tất cả giảng viên"""
        return GiangVien.objects.select_related('ma_bo_mon__ma_khoa').all()
    
    @staticmethod
    def get_giang_vien_by_bo_mon(ma_bo_mon):
        """Lấy tất cả giảng viên theo bộ môn"""
        return GiangVien.objects.filter(ma_bo_mon=ma_bo_mon)
    
    @staticmethod
    def get_giang_vien_by_id(ma_gv):
        """Lấy giảng viên theo mã"""
        return GiangVien.objects.select_related('ma_bo_mon').get(ma_gv=ma_gv)
    
    @staticmethod
    def get_giang_vien_co_the_day_mon(ma_mon_hoc):
        """Lấy tất cả giảng viên có thể dạy môn học"""
        return GiangVien.objects.filter(
            giangvien_day_mon__ma_mon_hoc=ma_mon_hoc
        ).distinct()
    
    @staticmethod
    def get_giang_vien_thong_tin_day(ma_gv):
        """
        Lấy thông tin giảng viên + môn họ có thể dạy + lịch dạy
        """
        gv = GiangVien.objects.select_related('ma_bo_mon').get(ma_gv=ma_gv)
        return {
            'giang_vien': gv,
            'mon_hoc_co_the_day': GVDayMon.objects.filter(
                ma_gv=ma_gv
            ).select_related('ma_mon_hoc'),
            'lich_day_hien_tai': ThoiKhoaBieu.objects.filter(
                phan_cong__ma_gv=ma_gv,
                ma_dot__trang_thai__in=['RUNNING', 'PUBLISHED']
            ).select_related('time_slot_id', 'ma_lop', 'ma_phong')
        }
    
    # ======================== MÔN HỌC ========================
    
    @staticmethod
    def get_all_mon_hoc():
        """Lấy tất cả môn học"""
        return MonHoc.objects.all()
    
    @staticmethod
    def get_mon_hoc_by_id(ma_mon_hoc):
        """Lấy môn học theo mã"""
        return MonHoc.objects.get(ma_mon_hoc=ma_mon_hoc)
    
    @staticmethod
    def get_mon_hoc_with_giang_vien(ma_mon_hoc):
        """Lấy môn học + danh sách giảng viên có thể dạy"""
        mon = MonHoc.objects.get(ma_mon_hoc=ma_mon_hoc)
        giang_vien_list = GVDayMon.objects.filter(
            ma_mon_hoc=ma_mon_hoc
        ).select_related('ma_gv')
        return {'mon_hoc': mon, 'giang_vien_list': giang_vien_list}
    
    # ======================== LỚP MÔN HỌC ========================
    
    @staticmethod
    def get_all_lop_mon_hoc():
        """Lấy tất cả lớp môn học"""
        return LopMonHoc.objects.select_related('ma_mon_hoc').all()
    
    @staticmethod
    def get_lop_by_mon_hoc(ma_mon_hoc):
        """Lấy tất cả lớp theo môn học"""
        return LopMonHoc.objects.filter(ma_mon_hoc=ma_mon_hoc)
    
    @staticmethod
    def get_lop_with_phan_cong(ma_lop):
        """Lấy lớp + phân công giảng viên"""
        lop = LopMonHoc.objects.select_related('ma_mon_hoc').get(ma_lop=ma_lop)
        phan_cong = PhanCong.objects.filter(ma_lop=ma_lop).select_related('ma_gv')
        return {'lop': lop, 'phan_cong_list': phan_cong}
    
    # ======================== PHÒNG HỌC ========================
    
    @staticmethod
    def get_all_phong_hoc():
        """Lấy tất cả phòng học"""
        return PhongHoc.objects.all()
    
    @staticmethod
    def get_phong_hoc_theo_loai(loai_phong):
        """Lấy phòng học theo loại"""
        return PhongHoc.objects.filter(loai_phong=loai_phong)
    
    @staticmethod
    def get_phong_hoc_co_du_suc_chua(so_luong_toi_thieu):
        """Lấy phòng học có đủ sức chứa"""
        return PhongHoc.objects.filter(suc_chua__gte=so_luong_toi_thieu)
    
    @staticmethod
    def get_phong_hoc_trống_time_slot(ma_time_slot, ma_dot=None):
        """Lấy phòng trống trong time slot cụ thể"""
        occupied = ThoiKhoaBieu.objects.filter(
            time_slot_id=ma_time_slot
        )
        if ma_dot:
            occupied = occupied.filter(ma_dot__ma_dot=ma_dot)
        
        occupied_rooms = occupied.values_list('ma_phong__ma_phong', flat=True)
        return PhongHoc.objects.exclude(ma_phong__in=occupied_rooms)
    
    # ======================== TIME SLOT / KHUNG GIỜ ========================
    
    @staticmethod
    def get_all_time_slot():
        """Lấy tất cả time slot"""
        return TimeSlot.objects.select_related('ca').order_by('thu', 'ca__ma_khung_gio')
    
    @staticmethod
    def get_time_slot_by_thu(thu):
        """Lấy time slot theo thứ"""
        return TimeSlot.objects.filter(thu=thu).order_by('ca__ma_khung_gio')
    
    @staticmethod
    def get_khung_gio_all():
        """Lấy tất cả khung giờ"""
        return KhungTG.objects.all()
    
    # ======================== ĐỢT XẾP / SCHEDULE ROUND ========================
    
    @staticmethod
    def get_all_dot_xep():
        """Lấy tất cả đợt xếp"""
        return DotXep.objects.select_related('ma_du_kien_dt').all()
    
    @staticmethod
    def get_dot_xep_by_id(ma_dot):
        """Lấy đợt xếp theo mã"""
        return DotXep.objects.select_related('ma_du_kien_dt').get(ma_dot=ma_dot)
    
    @staticmethod
    def get_dot_xep_dang_hoat_dong():
        """Lấy đợt xếp đang hoạt động (RUNNING)"""
        return DotXep.objects.filter(trang_thai='RUNNING')
    
    @staticmethod
    def get_dot_xep_with_lop_mon_hoc(ma_dot):
        """Lấy đợt xếp + danh sách lớp cần xếp"""
        dot = DotXep.objects.get(ma_dot=ma_dot)
        lop_list = PhanCong.objects.filter(
            ma_dot=ma_dot
        ).select_related('ma_lop__ma_mon_hoc', 'ma_gv')
        return {'dot_xep': dot, 'lop_list': lop_list}
    
    # ======================== PHÂN CÔNG GIẢNG VIÊN ========================
    
    @staticmethod
    def get_phan_cong_by_dot(ma_dot):
        """Lấy tất cả phân công trong đợt xếp"""
        return PhanCong.objects.filter(
            ma_dot=ma_dot
        ).select_related('ma_lop__ma_mon_hoc', 'ma_gv')
    
    @staticmethod
    def get_phan_cong_giang_vien(ma_gv, ma_dot=None):
        """Lấy phân công của giảng viên"""
        query = PhanCong.objects.filter(ma_gv=ma_gv).select_related('ma_lop', 'ma_dot')
        if ma_dot:
            query = query.filter(ma_dot=ma_dot)
        return query
    
    # ======================== THỜI KHOÁ BIỂU ========================
    
    @staticmethod
    def get_all_tkb():
        """Lấy tất cả lịch học"""
        return ThoiKhoaBieu.objects.select_related(
            'ma_lop', 'ma_phong', 'time_slot_id', 'ma_dot'
        ).all()
    
    @staticmethod
    def get_tkb_by_giang_vien(ma_gv, ma_dot=None):
        """Lấy lịch học của giảng viên"""
        query = ThoiKhoaBieu.objects.filter(
            phan_cong__ma_gv=ma_gv
        ).select_related('ma_lop', 'ma_phong', 'time_slot_id', 'ma_dot')
        if ma_dot:
            query = query.filter(ma_dot__ma_dot=ma_dot)
        return query
    
    @staticmethod
    def get_tkb_by_lop(ma_lop, ma_dot=None):
        """Lấy lịch học của lớp"""
        query = ThoiKhoaBieu.objects.filter(
            ma_lop__ma_lop=ma_lop
        ).select_related('ma_phong', 'time_slot_id')
        if ma_dot:
            query = query.filter(ma_dot__ma_dot=ma_dot)
        return query
    
    @staticmethod
    def get_tkb_by_phong(ma_phong, ma_dot=None):
        """Lấy lịch học theo phòng"""
        query = ThoiKhoaBieu.objects.filter(
            ma_phong__ma_phong=ma_phong
        ).select_related('ma_lop', 'time_slot_id')
        if ma_dot:
            query = query.filter(ma_dot__ma_dot=ma_dot)
        return query
    
    @staticmethod
    def get_tkb_by_time_slot(ma_time_slot, ma_dot=None):
        """Lấy tất cả lịch trong time slot"""
        query = ThoiKhoaBieu.objects.filter(
            time_slot_id=ma_time_slot
        ).select_related('ma_lop', 'ma_phong')
        if ma_dot:
            query = query.filter(ma_dot__ma_dot=ma_dot)
        return query
    
    # ======================== NGUYÊN VỌNG GV ========================
    
    @staticmethod
    def get_nguyen_vong_giang_vien(ma_gv, ma_dot=None):
        """Lấy nguyên vọng time slot của giảng viên"""
        query = NguyenVong.objects.filter(
            ma_gv=ma_gv
        ).select_related('ma_dot', 'time_slot_id')
        if ma_dot:
            query = query.filter(ma_dot=ma_dot)
        return query
    
    # ======================== DỮ LIỆU HỖ TRỢ LLM ========================
    
    @staticmethod
    def get_dataset_for_llm(ma_dot):
        """
        Lấy toàn bộ dataset cần thiết cho LLM
        Tối ưu hóa query để tránh N+1 problem
        """
        dot = DotXep.objects.select_related('ma_du_kien_dt').get(ma_dot=ma_dot)
        
        phan_cong_list = PhanCong.objects.filter(
            ma_dot=ma_dot
        ).select_related(
            'ma_lop__ma_mon_hoc',
            'ma_gv__ma_bo_mon',
            'ma_dot'
        )
        
        tkb_list = ThoiKhoaBieu.objects.filter(
            ma_dot__ma_dot=ma_dot
        ).select_related(
            'ma_lop__ma_mon_hoc',
            'ma_phong',
            'time_slot_id__ca'
        )
        
        return {
            'dot_xep': dot,
            'phan_cong': phan_cong_list,
            'tkb': tkb_list,
            'all_phong': PhongHoc.objects.all(),
            'all_time_slot': TimeSlot.objects.select_related('ca').order_by('thu', 'ca'),
            'all_khung_gio': KhungTG.objects.all(),
        }
    
    @staticmethod
    def get_dataset_xung_dot(ma_dot):
        """
        Lấy dữ liệu xung đột: phòng trống, giảng viên trống, lớp chưa xếp
        Dùng cho LLM phát hiện vấn đề
        """
        dot = DotXep.objects.get(ma_dot=ma_dot)
        
        # Lớp chưa được phân công
        lop_chua_phan_cong = PhanCong.objects.filter(
            ma_dot=ma_dot,
            ma_gv__isnull=True
        ).select_related('ma_lop__ma_mon_hoc')
        
        # Xung đột phòng (cùng phòng, cùng time slot)
        tkb_list = ThoiKhoaBieu.objects.filter(
            ma_dot=dot
        ).select_related('ma_phong', 'time_slot_id')
        
        xung_dot_phong = {}
        for tkb in tkb_list:
            key = f"{tkb.ma_phong.ma_phong}_{tkb.time_slot_id}"
            if key not in xung_dot_phong:
                xung_dot_phong[key] = []
            xung_dot_phong[key].append(tkb)
        
        return {
            'dot_xep': dot,
            'lop_chua_phan_cong': lop_chua_phan_cong,
            'xung_dot_phong': {k: v for k, v in xung_dot_phong.items() if len(v) > 1}
        }
    
    @staticmethod
    def get_thong_ke_dot_xep(ma_dot):
        """
        Thống kê cho đợt xếp: số lớp, số GV, số phòng, số ca, % xếp xong
        """
        phan_cong = PhanCong.objects.filter(ma_dot=ma_dot)
        tkb = ThoiKhoaBieu.objects.filter(ma_dot__ma_dot=ma_dot)
        
        total_lop = phan_cong.count()
        lop_da_xep = tkb.values('ma_lop').distinct().count()
        
        return {
            'tong_lop': total_lop,
            'lop_da_xep': lop_da_xep,
            'tyle_xep_xong': (lop_da_xep / total_lop * 100) if total_lop > 0 else 0,
            'tong_giang_vien': phan_cong.values('ma_gv').distinct().count(),
            'tong_phong_su_dung': tkb.values('ma_phong').distinct().count(),
            'tong_time_slot_su_dung': tkb.values('time_slot_id').distinct().count(),
            'tong_lich': tkb.count(),
        }
    
    # ======================== FOR SCHEDULE GENERATOR ========================
    
    @staticmethod
    def get_dot_xep_by_semester(semester_code: str):
        """
        Lấy tất cả đợt xếp theo kỳ học (semester code)
        semester_code là primary key của DuKienDT (VD: "2025-2026_HK1")
        """
        try:
            dot_list = DotXep.objects.filter(
                ma_du_kien_dt_id=semester_code
            ).select_related('ma_du_kien_dt')
            return list(dot_list)
        except Exception as e:
            logger.error(f"Error getting DotXep by semester {semester_code}: {e}")
            return []
    
    @staticmethod
    def get_phan_cong_with_mon_for_dot(ma_dot: str):
        """
        Lấy phân công + thông tin môn học cho đợt xếp
        Chuẩn bị dữ liệu cho LLM
        """
        return PhanCong.objects.filter(
            ma_dot=ma_dot
        ).select_related(
            'ma_lop__ma_mon_hoc',
            'ma_gv__ma_bo_mon',
            'ma_dot__ma_du_kien_dt'
        )
    
    @staticmethod
    @staticmethod
    def get_nguyen_vong_for_dot(ma_dot: str):
        """
        Lấy các nguyên vọng time slot cho đợt xếp
        """
        return NguyenVong.objects.filter(
            ma_dot=ma_dot
        ).select_related('ma_gv', 'time_slot_id')
    
    @staticmethod
    def get_rang_buoc_for_dot(ma_dot: str):
        """
        Lấy các ràng buộc mềm cho đợt xếp:
        1. Nếu đợt có RangBuocTrongDot → lấy những ràng buộc đó
        2. Nếu không có → lấy tất cả RangBuocMem (mặc định)
        
        Returns: List of RangBuocMem objects (normalized)
        """
        # Check if period has custom soft constraints
        has_custom = RangBuocTrongDot.objects.filter(ma_dot=ma_dot).exists()
        
        if has_custom:
            # Get RangBuocMem objects from the junction table
            return RangBuocMem.objects.filter(
                rangbuoctrongdot__ma_dot=ma_dot
            ).distinct()
        else:
            # Get default constraints
            return RangBuocMem.objects.all()
    
    @staticmethod
    def get_schedule_data_for_llm(semester_code: str) -> dict:
        """
        Lấy TOÀN BỘ dữ liệu cần thiết cho LLM tạo lịch
        Tối ưu hóa query, tránh N+1 problem
        
        Returns:
            {
                'dot_xep_list': [...],
                'phan_cong_list': [...],
                'rooms': [...],
                'timeslots': [...],
                'constraints': [...],
                'preferences': [...]
            }
        """
        # Lấy đợt xếp
        dot_list = DataAccessLayer.get_dot_xep_by_semester(semester_code)
        
        result = {
            'dot_xep_list': dot_list,
            'all_dot_data': {}
        }
        
        # Với mỗi đợt, lấy đầy đủ dữ liệu
        for dot in dot_list:
            ma_dot = dot.ma_dot
            
            result['all_dot_data'][ma_dot] = {
                'phan_cong': DataAccessLayer.get_phan_cong_with_mon_for_dot(ma_dot),
                'constraints': DataAccessLayer.get_rang_buoc_for_dot(ma_dot),
                'preferences': DataAccessLayer.get_nguyen_vong_for_dot(ma_dot),
                'tkb_hien_tai': DataAccessLayer.get_tkb_by_dot(ma_dot),
            }
        
        # Lấy dữ liệu chung (không phụ thuộc đợt)
        result['all_rooms'] = DataAccessLayer.get_all_phong_hoc()
        result['all_timeslots'] = DataAccessLayer.get_all_time_slot()
        result['all_khung_gio'] = DataAccessLayer.get_khung_gio_all()
        
        return result
    
    @staticmethod
    def get_tkb_by_dot(ma_dot: str):
        """
        Lấy tất cả lịch hiện tại của đợt xếp
        """
        return ThoiKhoaBieu.objects.filter(
            ma_dot__ma_dot=ma_dot
        ).select_related(
            'ma_lop__ma_mon_hoc',
            'ma_phong',
            'time_slot_id__ca'
        )


# ======================== HELPER FUNCTIONS ========================

def get_giang_vien_info_dict(ma_gv):
    """Lấy thông tin giảng viên dưới dạng dict (dùng cho JSON API)"""
    gv = DataAccessLayer.get_giang_vien_by_id(ma_gv)
    thong_tin = DataAccessLayer.get_giang_vien_thong_tin_day(ma_gv)
    
    return {
        'ma_gv': gv.ma_gv,
        'ten_gv': gv.ten_gv,
        'loai_gv': gv.loai_gv,
        'email': gv.email,
        'bo_mon': {
            'ma': gv.ma_bo_mon.ma_bo_mon,
            'ten': gv.ma_bo_mon.ten_bo_mon,
        },
        'mon_hoc_co_the_day': [
            {'ma': m.ma_mon_hoc.ma_mon_hoc, 'ten': m.ma_mon_hoc.ten_mon_hoc}
            for m in thong_tin['mon_hoc_co_the_day']
        ],
        'so_mon_co_the_day': thong_tin['mon_hoc_co_the_day'].count(),
        'lich_day_hien_tai': [
            {
                'lop': t.lop_mon_hoc.ma_lop,
                'mon': t.lop_mon_hoc.mon_hoc.ten_mon_hoc,
                'phong': t.phong_hoc.ma_phong,
                'time_slot': t.time_slot.time_slot_id,
            }
            for t in thong_tin['lich_day_hien_tai']
        ]
    }


def get_lop_info_dict(ma_lop):
    """Lấy thông tin lớp dưới dạng dict"""
    lop_info = DataAccessLayer.get_lop_with_phan_cong(ma_lop)
    lop = lop_info['lop']
    phan_cong_list = lop_info['phan_cong_list']
    
    return {
        'ma_lop': lop.ma_lop,
        'mon_hoc': lop.ma_mon_hoc.ten_mon_hoc,
        'nhom': lop.nhom_mh,
        'to': lop.to_mh,
        'so_sv': lop.so_luong_sv,
        'he_dao_tao': lop.he_dao_tao,
        'ngon_ngu': lop.ngon_ngu,
        'so_ca_tuan': lop.so_ca_tuan,
        'phan_cong_giang_vien': [
            {'ma_gv': pc.ma_gv.ma_gv, 'ten_gv': pc.ma_gv.ten_gv}
            for pc in phan_cong_list
        ]
    }
