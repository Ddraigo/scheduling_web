"""
Custom Model Managers
Giúp gọi custom query trực tiếp từ model mà không cần import DAL
Ví dụ: GiangVien.objects.get_by_bo_mon('BM-001-001')
"""

from django.db import models


class GiangVienManager(models.Manager):
    """Custom manager cho GiangVien model"""
    
    def get_by_bo_mon(self, ma_bo_mon):
        """Lấy tất cả GV theo bộ môn"""
        return self.filter(ma_bo_mon=ma_bo_mon)
    
    def with_full_info(self):
        """Lấy GV kèm toàn bộ thông tin liên quan"""
        return self.select_related('ma_bo_mon__ma_khoa')
    
    def co_the_day_mon(self, ma_mon_hoc):
        """Lấy tất cả GV có thể dạy môn học"""
        return self.filter(
            giangvien_day_mon__ma_mon_hoc=ma_mon_hoc
        ).distinct()
    
    def dang_day_trong_dot(self, ma_dot):
        """Lấy tất cả GV đang dạy trong đợt xếp"""
        return self.filter(
            phan_cong__ma_dot=ma_dot
        ).distinct()


class MonHocManager(models.Manager):
    """Custom manager cho MonHoc model"""
    
    def with_giang_vien(self):
        """Lấy môn kèm giảng viên có thể dạy"""
        return self.prefetch_related('mon_hoc_day_by')
    
    def co_tiet_thuc_hanh(self):
        """Lấy những môn có tiết thực hành"""
        return self.filter(so_tiet_th__gt=0)
    
    def chi_ly_thuyet(self):
        """Lấy những môn chỉ có lý thuyết"""
        return self.filter(so_tiet_th__isnull=True)


class LopMonHocManager(models.Manager):
    """Custom manager cho LopMonHoc model"""
    
    def with_phan_cong(self):
        """Lấy lớp kèm phân công"""
        return self.select_related(
            'ma_mon_hoc'
        ).prefetch_related('phan_cong_lop')
    
    def theo_mon_hoc(self, ma_mon_hoc):
        """Lấy tất cả lớp theo môn"""
        return self.filter(ma_mon_hoc=ma_mon_hoc)
    
    def chua_phan_cong_trong_dot(self, ma_dot):
        """Lấy những lớp chưa được phân công trong đợt"""
        return self.filter(
            phan_cong__ma_dot=ma_dot,
            phan_cong__ma_gv__isnull=True
        )


class PhongHocManager(models.Manager):
    """Custom manager cho PhongHoc model"""
    
    def co_du_suc_chua(self, so_luong):
        """Lấy phòng đủ sức chứa"""
        return self.filter(suc_chua__gte=so_luong)
    
    def theo_loai(self, loai_phong):
        """Lấy phòng theo loại"""
        return self.filter(loai_phong=loai_phong)
    
    def theo_thiet_bi(self, thiet_bi):
        """Lấy phòng có thiết bị cụ thể"""
        return self.filter(thiet_bi__icontains=thiet_bi)
    
    def trong_trong_time_slot(self, ma_time_slot, ma_dot=None):
        """Lấy phòng trống trong time slot"""
        from ..models import ThoiKhoaBieu
        
        occupied = ThoiKhoaBieu.objects.filter(
            time_slot__time_slot_id=ma_time_slot
        )
        if ma_dot:
            occupied = occupied.filter(dot_xep__ma_dot=ma_dot)
        
        occupied_rooms = occupied.values_list('phong_hoc__ma_phong', flat=True)
        return self.exclude(ma_phong__in=occupied_rooms)


class TimeSlotManager(models.Manager):
    """Custom manager cho TimeSlot model"""
    
    def theo_thu(self, thu):
        """Lấy time slot theo thứ"""
        return self.filter(thu=thu).order_by('ca__ma_khung_gio')
    
    def with_khung_gio(self):
        """Lấy time slot kèm khung giờ"""
        return self.select_related('ca').order_by('thu', 'ca__ma_khung_gio')
    
    def toan_bo_tuan(self):
        """Lấy tất cả time slot trong tuần (từ thứ 2 đến CN)"""
        return self.order_by('thu', 'ca__ma_khung_gio')


class DotXepManager(models.Manager):
    """Custom manager cho DotXep model"""
    
    def dang_hoat_dong(self):
        """Lấy đợt xếp đang hoạt động"""
        return self.filter(trang_thai__in=['RUNNING', 'PUBLISHED'])
    
    def with_khoang_gio(self):
        """Lấy đợt kèm dự kiến đào tạo"""
        return self.select_related('ma_du_kien_dt')
    
    def theo_nam_hoc_hoc_ky(self, nam_hoc, hoc_ky):
        """Lấy đợt theo năm học và học kỳ"""
        return self.filter(
            ma_du_kien_dt__nam_hoc=nam_hoc,
            ma_du_kien_dt__hoc_ky=hoc_ky
        )


class ThoiKhoaBieuManager(models.Manager):
    """Custom manager cho ThoiKhoaBieu model"""
    
    def with_full_info(self):
        """Lấy TKB kèm toàn bộ thông tin liên quan"""
        return self.select_related(
            'lop_mon_hoc__ma_mon_hoc',
            'phong_hoc',
            'time_slot__ca',
            'phan_cong__ma_gv',
            'dot_xep'
        )
    
    def cua_giang_vien(self, ma_gv, ma_dot=None):
        """Lấy lịch dạy của giảng viên"""
        query = self.filter(
            phan_cong__ma_gv=ma_gv
        ).with_full_info()
        if ma_dot:
            query = query.filter(dot_xep__ma_dot=ma_dot)
        return query
    
    def cua_lop(self, ma_lop, ma_dot=None):
        """Lấy lịch học của lớp"""
        query = self.filter(
            lop_mon_hoc__ma_lop=ma_lop
        ).with_full_info()
        if ma_dot:
            query = query.filter(dot_xep__ma_dot=ma_dot)
        return query
    
    def cua_phong(self, ma_phong, ma_dot=None):
        """Lấy lịch của phòng"""
        query = self.filter(
            phong_hoc__ma_phong=ma_phong
        ).with_full_info()
        if ma_dot:
            query = query.filter(dot_xep__ma_dot=ma_dot)
        return query
    
    def trong_time_slot(self, ma_time_slot, ma_dot=None):
        """Lấy tất cả lịch trong time slot"""
        query = self.filter(
            time_slot__time_slot_id=ma_time_slot
        ).with_full_info()
        if ma_dot:
            query = query.filter(dot_xep__ma_dot=ma_dot)
        return query


class PhanCongManager(models.Manager):
    """Custom manager cho PhanCong model"""
    
    def trong_dot(self, ma_dot):
        """Lấy tất cả phân công trong đợt"""
        return self.filter(
            ma_dot=ma_dot
        ).select_related('ma_lop__ma_mon_hoc', 'ma_gv')
    
    def cua_giang_vien(self, ma_gv, ma_dot=None):
        """Lấy phân công của giảng viên"""
        query = self.filter(ma_gv=ma_gv).select_related('ma_lop', 'ma_dot')
        if ma_dot:
            query = query.filter(ma_dot=ma_dot)
        return query
    
    def chua_phan_cong(self, ma_dot):
        """Lấy phân công chưa có giảng viên"""
        return self.filter(
            ma_dot=ma_dot,
            ma_gv__isnull=True
        ).select_related('ma_lop__ma_mon_hoc')


# ======================== CÁC TRUY VẤN SỬ DỤNG CUSTOM MANAGERS ========================

"""
Ví dụ cách dùng các custom managers:

# 1. Lấy GV theo bộ môn
gv_list = GiangVien.objects.get_by_bo_mon('BM-001-001')

# 2. Lấy GV có thể dạy môn
gv_co_the_day = GiangVien.objects.co_the_day_mon('502045')

# 3. Lấy phòng đủ sức chứa
phong = PhongHoc.objects.co_du_suc_chua(40)

# 4. Lấy phòng trống trong ca
phong_trong = PhongHoc.objects.trong_trong_time_slot('Thu2-Ca1')

# 5. Lấy lịch GV
lich_gv = ThoiKhoaBieu.objects.cua_giang_vien('GV001', 'DOT1_2025-2026_HK1')

# 6. Lấy lịch lớp
lich_lop = ThoiKhoaBieu.objects.cua_lop('LOP-001', 'DOT1_2025-2026_HK1')

# 7. Lấy phân công chưa phân công GV
phan_cong = PhanCong.objects.chua_phan_cong('DOT1_2025-2026_HK1')

# 8. Lấy time slot trong tuần
time_slot_list = TimeSlot.objects.with_khung_gio()

# 9. Lấy đợt đang hoạt động
dot_dang_hoat_dong = DotXep.objects.dang_hoat_dong()

# 10. Lấy lớp theo môn
lop_list = LopMonHoc.objects.theo_mon_hoc('502045')
"""
