"""
Django Models for Scheduling System
Chuyển đổi từ SQL Server schema sang Django ORM
UPDATED: Sync với csdl_tkb.sql thật
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError


class Khoa(models.Model):
    """Khoa - Faculty/Department - tb_KHOA"""
    ma_khoa = models.CharField(max_length=12, primary_key=True, db_column='MaKhoa', verbose_name="Mã khoa")
    ten_khoa = models.CharField(max_length=200, db_column='TenKhoa', verbose_name="Tên khoa")
    
    class Meta:
        db_table = 'tb_KHOA'
        verbose_name = "Khoa"
        verbose_name_plural = "Các Khoa"
        ordering = ['ma_khoa']
    
    def __str__(self):
        return f"{self.ma_khoa} - {self.ten_khoa}"


class BoMon(models.Model):
    """Bộ môn - Subject Department - tb_BO_MON"""
    ma_bo_mon = models.CharField(max_length=12, primary_key=True, db_column='MaBoMon', verbose_name="Mã bộ môn")
    ma_khoa = models.ForeignKey(Khoa, on_delete=models.CASCADE, db_column='MaKhoa', 
                                related_name='bo_mon_list', verbose_name="Khoa")
    ten_bo_mon = models.CharField(max_length=200, db_column='TenBoMon', verbose_name="Tên bộ môn")
    
    class Meta:
        db_table = 'tb_BO_MON'
        verbose_name = "Bộ môn"
        verbose_name_plural = "Các Bộ môn"
        ordering = ['ma_bo_mon']
        unique_together = [['ma_khoa', 'ten_bo_mon']]  # UQ_BM_Ten_Trong_Khoa
    
    def __str__(self):
        return f"{self.ma_bo_mon} - {self.ten_bo_mon}"


class GiangVien(models.Model):
    """Giảng viên - Teacher/Lecturer - tb_GIANG_VIEN"""
    ma_gv = models.CharField(max_length=12, primary_key=True, db_column='MaGV', verbose_name="Mã giảng viên")
    ma_bo_mon = models.ForeignKey(BoMon, on_delete=models.CASCADE, db_column='MaBoMon',
                                  related_name='giang_vien_list', verbose_name="Bộ môn")
    ten_gv = models.CharField(max_length=200, db_column='TenGV', verbose_name="Tên giảng viên")
    loai_gv = models.CharField(max_length=100, null=True, blank=True, db_column='LoaiGV', verbose_name="Loại GV")
    ghi_chu = models.CharField(max_length=300, null=True, blank=True, db_column='GhiChu', verbose_name="Ghi chú")
    email = models.CharField(max_length=200, null=True, blank=True, db_column='Email', verbose_name="Email")
    
    class Meta:
        db_table = 'tb_GIANG_VIEN'
        verbose_name = "Giảng viên"
        verbose_name_plural = "Giảng viên"
        ordering = ['ma_gv']
        indexes = [
            models.Index(fields=['ma_bo_mon'], name='IX_GV_MaBoMon'),
        ]
    
    def __str__(self):
        return f"{self.ma_gv} - {self.ten_gv}"


class DuKienDT(models.Model):
    """Dự kiến đào tạo - Training Plan - tb_DUKIEN_DT"""
    HOCKY_CHOICES = [
        (1, 'Học kỳ 1'),
        (2, 'Học kỳ 2'),
        (3, 'Học kỳ Hè'),
        (4, 'Học kỳ 4'),
    ]
    
    ma_du_kien_dt = models.CharField(max_length=15, primary_key=True, db_column='MaDuKienDT', 
                                     verbose_name="Mã dự kiến ĐT")  # VD: 2025-2026_HK1
    nam_hoc = models.CharField(max_length=9, null=True, blank=True, db_column='NamHoc', verbose_name="Năm học")
    hoc_ky = models.SmallIntegerField(choices=HOCKY_CHOICES, db_column='HocKy', verbose_name="Học kỳ")
    ngay_bd = models.DateTimeField(null=True, blank=True, db_column='NgayBD', verbose_name="Ngày bắt đầu")
    ngay_kt = models.DateTimeField(null=True, blank=True, db_column='NgayKT', verbose_name="Ngày kết thúc")
    mo_ta_hoc_ky = models.CharField(max_length=100, null=True, blank=True, db_column='MoTaHocKy', 
                                    verbose_name="Mô tả học kỳ")
    
    class Meta:
        db_table = 'tb_DUKIEN_DT'
        verbose_name = "Dự kiến đào tạo"
        verbose_name_plural = "Dự kiến đào tạo"
        ordering = ['-nam_hoc', '-hoc_ky']
    
    def __str__(self):
        return f"{self.ma_du_kien_dt} - {self.mo_ta_hoc_ky or ''}"


class MonHoc(models.Model):
    """Môn học - Subject/Course - tb_MON_HOC"""
    ma_mon_hoc = models.CharField(max_length=10, primary_key=True, db_column='MaMonHoc', verbose_name="Mã môn học")
    ten_mon_hoc = models.CharField(max_length=200, db_column='TenMonHoc', verbose_name="Tên môn học")
    so_tin_chi = models.SmallIntegerField(null=True, blank=True, db_column='SoTinChi',
                                          validators=[MinValueValidator(1)], verbose_name="Số tín chỉ")
    so_tiet_lt = models.SmallIntegerField(null=True, blank=True, db_column='SoTietLT',
                                          validators=[MinValueValidator(0)], verbose_name="Số tiết LT")
    so_tiet_th = models.SmallIntegerField(null=True, blank=True, db_column='SoTietTH',
                                          validators=[MinValueValidator(0)], verbose_name="Số tiết TH")
    so_tuan = models.SmallIntegerField(default=15, db_column='SoTuan',
                                       validators=[MinValueValidator(1)], verbose_name="Số tuần")
    
    class Meta:
        db_table = 'tb_MON_HOC'
        verbose_name = "Môn học"
        verbose_name_plural = "Môn học"
        ordering = ['ma_mon_hoc']
    
    def __str__(self):
        return f"{self.ma_mon_hoc} - {self.ten_mon_hoc}"


class GVDayMon(models.Model):
    """GV đủ điều kiện dạy môn - tb_GV_DAY_MON
    Updated: Now has auto-increment id as PK, composite key is UNIQUE constraint"""
    id = models.AutoField(primary_key=True)
    ma_mon_hoc = models.ForeignKey(MonHoc, on_delete=models.CASCADE, db_column='MaMonHoc',
                                   related_name='gv_day_list', verbose_name="Môn học")
    ma_gv = models.ForeignKey(GiangVien, on_delete=models.CASCADE, db_column='MaGV',
                             related_name='mon_day_list', verbose_name="Giảng viên")
    
    class Meta:
        db_table = 'tb_GV_DAY_MON'
        verbose_name = "GV dạy môn"
        verbose_name_plural = "GV dạy môn"
        unique_together = [['ma_mon_hoc', 'ma_gv']]
    
    def __str__(self):
        return f"{self.ma_gv.ten_gv} -> {self.ma_mon_hoc.ten_mon_hoc}"


class KhungTG(models.Model):
    """Khung thời gian - Ca học - tb_KHUNG_TG"""
    ma_khung_gio = models.SmallIntegerField(primary_key=True, db_column='MaKhungGio', verbose_name="Mã ca")
    ten_ca = models.CharField(max_length=50, null=True, blank=True, db_column='TenCa', verbose_name="Tên ca")
    gio_bat_dau = models.TimeField(db_column='GioBatDau', verbose_name="Giờ bắt đầu")
    gio_ket_thuc = models.TimeField(db_column='GioKetThuc', verbose_name="Giờ kết thúc")
    so_tiet = models.SmallIntegerField(default=3, db_column='SoTiet', verbose_name="Số tiết")
    
    class Meta:
        db_table = 'tb_KHUNG_TG'
        verbose_name = "Khung thời gian"
        verbose_name_plural = "Khung thời gian"
        ordering = ['ma_khung_gio']
    
    def __str__(self):
        return f"{self.ten_ca} ({self.gio_bat_dau.strftime('%H:%M')}-{self.gio_ket_thuc.strftime('%H:%M')})"


class TimeSlot(models.Model):
    """Time Slot - Khe giờ học cụ thể - tb_TIME_SLOT"""
    time_slot_id = models.CharField(max_length=10, primary_key=True, db_column='TimeSlotID', 
                                    verbose_name="TimeSlot ID")  # Thu2-Ca1
    thu = models.SmallIntegerField(db_column='Thu', validators=[MinValueValidator(2), MaxValueValidator(8)],
                                   verbose_name="Thứ (2-8, 8=CN)")
    ca = models.ForeignKey(KhungTG, on_delete=models.CASCADE, db_column='Ca',
                          related_name='time_slot_list', verbose_name="Ca")
    
    class Meta:
        db_table = 'tb_TIME_SLOT'
        verbose_name = "Time Slot"
        verbose_name_plural = "Time Slots"
        ordering = ['thu', 'ca']
        unique_together = [['thu', 'ca']]
    
    def __str__(self):
        thu_name = 'CN' if self.thu == 8 else f'Thứ {self.thu}'
        return f"{thu_name}-{self.ca.ten_ca}"


class PhongHoc(models.Model):
    """Phòng học - Classroom/Room - tb_PHONG_HOC"""
    ma_phong = models.CharField(max_length=12, primary_key=True, db_column='MaPhong', verbose_name="Mã phòng")
    loai_phong = models.CharField(max_length=100, null=True, blank=True, db_column='LoaiPhong', 
                                  verbose_name="Loại phòng")
    suc_chua = models.SmallIntegerField(null=True, blank=True, db_column='SucChua',
                                        validators=[MinValueValidator(1)], verbose_name="Sức chứa")
    thiet_bi = models.CharField(max_length=400, null=True, blank=True, db_column='ThietBi', 
                               verbose_name="Thiết bị")
    ghi_chu = models.CharField(max_length=200, null=True, blank=True, db_column='GhiChu', 
                              verbose_name="Ghi chú")
    
    class Meta:
        db_table = 'tb_PHONG_HOC'
        verbose_name = "Phòng học"
        verbose_name_plural = "Phòng học"
        ordering = ['ma_phong']
    
    def __str__(self):
        return f"{self.ma_phong} ({self.suc_chua or 'N/A'} chỗ)"


class RangBuocMem(models.Model):
    """Ràng buộc mềm - tb_RANG_BUOC_MEM"""
    ma_rang_buoc = models.CharField(max_length=15, primary_key=True, db_column='MaRangBuoc', 
                                   verbose_name="Mã ràng buộc")
    ten_rang_buoc = models.CharField(max_length=200, db_column='TenRangBuoc', verbose_name="Tên ràng buộc")
    mo_ta = models.CharField(max_length=500, null=True, blank=True, db_column='MoTa', verbose_name="Mô tả")
    trong_so = models.FloatField(db_column='TrongSo', verbose_name="Trọng số")
    
    class Meta:
        db_table = 'tb_RANG_BUOC_MEM'
        verbose_name = "Ràng buộc mềm"
        verbose_name_plural = "Ràng buộc mềm"
        ordering = ['ma_rang_buoc']
    
    def __str__(self):
        return f"{self.ma_rang_buoc} - {self.ten_rang_buoc}"


class LopMonHoc(models.Model):
    """Lớp môn học - Class - tb_LOP_MONHOC"""
    ma_lop = models.CharField(max_length=12, primary_key=True, db_column='MaLop', verbose_name="Mã lớp")
    ma_mon_hoc = models.ForeignKey(MonHoc, on_delete=models.CASCADE, db_column='MaMonHoc',
                                   related_name='lop_list', verbose_name="Môn học")
    nhom_mh = models.SmallIntegerField(db_column='Nhom_MH', validators=[MinValueValidator(1)],
                                       verbose_name="Nhóm")
    to_mh = models.SmallIntegerField(null=True, blank=True, db_column='To_MH',
                                     validators=[MinValueValidator(0)], verbose_name="Tổ")
    so_luong_sv = models.SmallIntegerField(null=True, blank=True, db_column='SoLuongSV',
                                           validators=[MinValueValidator(0)], verbose_name="Số lượng SV")
    he_dao_tao = models.CharField(max_length=200, null=True, blank=True, db_column='HeDaoTao',
                                  verbose_name="Hệ đào tạo")
    ngon_ngu = models.CharField(max_length=50, null=True, blank=True, db_column='NgonNgu',
                               verbose_name="Ngôn ngữ")
    thiet_bi_yeu_cau = models.CharField(max_length=400, null=True, blank=True, db_column='ThietBiYeuCau',
                                        verbose_name="Thiết bị yêu cầu")
    so_ca_tuan = models.SmallIntegerField(default=1, db_column='SoCaTuan',
                                          validators=[MinValueValidator(1), MaxValueValidator(5)],
                                          verbose_name="Số ca/tuần")
    
    class Meta:
        db_table = 'tb_LOP_MONHOC'
        verbose_name = "Lớp môn học"
        verbose_name_plural = "Lớp môn học"
        ordering = ['ma_lop']
        unique_together = [['ma_mon_hoc', 'nhom_mh', 'to_mh']]
        indexes = [
            models.Index(fields=['ma_mon_hoc'], name='IX_LMH_MaMonHoc'),
        ]
    
    def __str__(self):
        return f"{self.ma_lop}"


class DotXep(models.Model):
    """Đợt xếp lịch - Scheduling Period - tb_DOT_XEP"""
    TRANG_THAI_CHOICES = [
        ('DRAFT', 'Draft'),
        ('RUNNING', 'Running'),
        ('LOCKED', 'Locked'),
        ('PUBLISHED', 'Published'),
    ]
    
    ma_dot = models.CharField(max_length=20, primary_key=True, db_column='MaDot', verbose_name="Mã đợt")
    ma_du_kien_dt = models.ForeignKey(DuKienDT, on_delete=models.CASCADE, db_column='MaDuKienDT',
                                      related_name='dot_xep_list', verbose_name="Dự kiến ĐT")
    ten_dot = models.CharField(max_length=200, null=True, blank=True, db_column='TenDot', 
                              verbose_name="Tên đợt")
    trang_thai = models.CharField(max_length=20, default='DRAFT', choices=TRANG_THAI_CHOICES,
                                 db_column='TrangThai', verbose_name="Trạng thái")
    ngay_tao = models.DateTimeField(auto_now_add=True, db_column='NgayTao', verbose_name="Ngày tạo")
    ngay_khoa = models.DateTimeField(null=True, blank=True, db_column='NgayKhoa', 
                                    verbose_name="Ngày khóa")
    
    class Meta:
        db_table = 'tb_DOT_XEP'
        verbose_name = "Đợt xếp lịch"
        verbose_name_plural = "Đợt xếp lịch"
        ordering = ['-ngay_tao']
    
    def __str__(self):
        return f"{self.ma_dot} - {self.ten_dot or ''}"


class PhanCong(models.Model):
    """Phân công giảng dạy - Teaching Assignment - tb_PHAN_CONG
    Updated: Now has auto-increment id as PK, composite key is UNIQUE constraint
    Thêm: TuanBD, TuanKT để xác định phạm vi tuần dạy của từng lớp
    - TuanBD: 1-15 (tuần bắt đầu)
    - TuanKT: >= TuanBD, không vượt quá 15 (tuần kết thúc)"""
    id = models.AutoField(primary_key=True)
    ma_dot = models.ForeignKey(DotXep, on_delete=models.CASCADE, db_column='MaDot',
                              related_name='phan_cong_list', verbose_name="Đợt xếp")
    ma_lop = models.ForeignKey(LopMonHoc, on_delete=models.CASCADE, db_column='MaLop',
                              related_name='phan_cong_list', verbose_name="Lớp môn học")
    ma_gv = models.ForeignKey(GiangVien, on_delete=models.CASCADE, null=True, blank=True,
                             db_column='MaGV', related_name='phan_cong_list', 
                             verbose_name="Giảng viên")
    tuan_bd = models.SmallIntegerField(db_column='TuanBD', 
                                       validators=[MinValueValidator(1), MaxValueValidator(20)],
                                       verbose_name="Tuần bắt đầu (1-20)")
    tuan_kt = models.SmallIntegerField(db_column='TuanKT',
                                       validators=[MinValueValidator(1), MaxValueValidator(20)],
                                       verbose_name="Tuần kết thúc (>= TuanBD, ≤ 20)")

    def clean(self):
        """Validate: tuan_kt >= tuan_bd"""
        super().clean()
        if self.tuan_bd and self.tuan_kt and self.tuan_bd > self.tuan_kt:
            raise ValidationError({
                'tuan_kt': f'Tuần kết thúc ({self.tuan_kt}) phải ≥ tuần bắt đầu ({self.tuan_bd})'
            })
    
    class Meta:
        db_table = 'tb_PHAN_CONG'
        verbose_name = "Phân công"
        verbose_name_plural = "Phân công giảng dạy"
        unique_together = [['ma_dot', 'ma_lop']]
        indexes = [
            models.Index(fields=['ma_gv'], name='IX_PC_MaGV'),
            models.Index(fields=['ma_lop'], name='IX_PC_MaLop'),
            models.Index(fields=['ma_dot'], name='IX_PC_MaDot'),
            models.Index(fields=['ma_dot', 'ma_gv'], name='IX_PC_MaDot_MaGV'),
        ]
    
    def __str__(self):
        gv_name = self.ma_gv.ten_gv if self.ma_gv else 'Chưa phân'
        return f"{gv_name} -> {self.ma_lop.ma_lop} (T{self.tuan_bd}-{self.tuan_kt})"


class NgayNghiCoDinh(models.Model):
    """Ngày nghỉ cố định - tb_NGAY_NGHI_CO_DINH
    Lưu danh sách ngày nghỉ cố định (lặp lại mỗi năm): Tết, 30/4, 1/5, 2/9, v.v.
    Dùng làm gợi ý mặc định khi tạo đợt mới"""
    id = models.AutoField(primary_key=True)
    ten_ngay_nghi = models.CharField(max_length=100, db_column='TenNgayNghi', 
                                    verbose_name="Tên ngày nghỉ")
    ngay = models.CharField(max_length=5, db_column='Ngay',
                           verbose_name="Ngày (MM-DD)")  # Định dạng MM-DD, VD: "09-02"
    ghi_chu = models.CharField(max_length=200, null=True, blank=True, db_column='GhiChu',
                              verbose_name="Ghi chú")
    
    class Meta:
        db_table = 'tb_NGAY_NGHI_CO_DINH'
        verbose_name = "Ngày nghỉ cố định"
        verbose_name_plural = "Ngày nghỉ cố định"
        ordering = ['ngay']
    
    def __str__(self):
        return f"{self.ten_ngay_nghi} ({self.ngay})"


class NgayNghiDot(models.Model):
    """Ngày nghỉ theo đợt xếp lịch - tb_NGAY_NGHI_DOT
    Lưu các khoảng ngày/tuần nghỉ cho từng đợt (tết, thi, v.v.)"""
    id = models.AutoField(primary_key=True)
    ma_dot = models.ForeignKey(DotXep, on_delete=models.CASCADE, db_column='MaDot',
                              related_name='ngay_nghi_list', verbose_name="Đợt xếp")
    ngay_bd = models.DateField(db_column='NgayBD', verbose_name="Ngày bắt đầu nghỉ")
    so_ngay_nghi = models.SmallIntegerField(db_column='SoNgayNghi',
                                           validators=[MinValueValidator(1)],
                                           verbose_name="Số ngày nghỉ")
    tuan_bd = models.SmallIntegerField(null=True, blank=True, db_column='TuanBD',
                                      validators=[MinValueValidator(1), MaxValueValidator(15)],
                                      verbose_name="Tuần bắt đầu (tham khảo)")
    tuan_kt = models.SmallIntegerField(null=True, blank=True, db_column='TuanKT',
                                      validators=[MinValueValidator(1), MaxValueValidator(15)],
                                      verbose_name="Tuần kết thúc (tham khảo)")
    ten_ngay_nghi = models.CharField(max_length=100, null=True, blank=True, db_column='TenNgayNghi',
                                    verbose_name="Tên khoảng nghỉ")
    ghi_chu = models.CharField(max_length=200, null=True, blank=True, db_column='GhiChu',
                              verbose_name="Ghi chú")
    
    class Meta:
        db_table = 'tb_NGAY_NGHI_DOT'
        verbose_name = "Ngày nghỉ theo đợt"
        verbose_name_plural = "Ngày nghỉ theo đợt"
        unique_together = [['ma_dot', 'ngay_bd', 'so_ngay_nghi']]
        indexes = [
            models.Index(fields=['ma_dot'], name='IX_NGAYNGHI_MaDot'),
        ]
    
    def __str__(self):
        return f"{self.ma_dot.ma_dot} - {self.ten_ngay_nghi or f'{self.ngay_bd} ({self.so_ngay_nghi} ngày)'}"


class RangBuocTrongDot(models.Model):
    """Ràng buộc mềm áp dụng trong đợt - tb_RANG_BUOC_TRONG_DOT
    Updated: Now has auto-increment id as PK, composite key is UNIQUE constraint"""
    id = models.AutoField(primary_key=True)
    ma_dot = models.ForeignKey(DotXep, on_delete=models.CASCADE, db_column='MaDot',
                              related_name='rang_buoc_list', verbose_name="Đợt xếp")
    ma_rang_buoc = models.ForeignKey(RangBuocMem, on_delete=models.CASCADE, db_column='MaRangBuoc',
                                    related_name='dot_ap_dung_list', verbose_name="Ràng buộc")
    
    class Meta:
        db_table = 'tb_RANG_BUOC_TRONG_DOT'
        verbose_name = "Ràng buộc trong đợt"
        verbose_name_plural = "Ràng buộc trong đợt"
        unique_together = [['ma_dot', 'ma_rang_buoc']]
    
    def __str__(self):
        return f"{self.ma_dot.ma_dot} - {self.ma_rang_buoc.ten_rang_buoc}"


class NguyenVong(models.Model):
    """Nguyện vọng giảng viên - tb_NGUYEN_VONG
    Updated: Now has auto-increment id as PK, composite key is UNIQUE constraint"""
    id = models.AutoField(primary_key=True)
    ma_gv = models.ForeignKey(GiangVien, on_delete=models.CASCADE, db_column='MaGV',
                             related_name='nguyen_vong_list', verbose_name="Giảng viên")
    ma_dot = models.ForeignKey(DotXep, on_delete=models.CASCADE, db_column='MaDot',
                              related_name='nguyen_vong_list', verbose_name="Đợt xếp")
    time_slot_id = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, db_column='TimeSlotID',
                                    related_name='nguyen_vong_list', verbose_name="Time slot")
    
    class Meta:
        db_table = 'tb_NGUYEN_VONG'
        verbose_name = "Nguyện vọng"
        verbose_name_plural = "Nguyện vọng giảng viên"
        unique_together = [['ma_gv', 'ma_dot', 'time_slot_id']]
    
    def __str__(self):
        return f"{self.ma_gv.ten_gv} - {self.time_slot_id}"


class ThoiKhoaBieu(models.Model):
    """Thời khóa biểu - Schedule/Timetable - tb_TKB
    Lưu lịch dạy cụ thể cho mỗi buổi học
    - TuanHoc: Pattern tuần học (VD: "1111010100000000" = tuần 1-4, 6-8 học)
    - NgayBD, NgayKT: Ngày bắt đầu/kết thúc toàn bộ khoá học (không phải từng buổi)"""
    ma_tkb = models.CharField(max_length=15, primary_key=True, db_column='MaTKB', verbose_name="Mã TKB")
    ma_dot = models.ForeignKey(DotXep, on_delete=models.CASCADE, db_column='MaDot',
                              related_name='tkb_list', verbose_name="Đợt xếp")
    ma_lop = models.ForeignKey(LopMonHoc, on_delete=models.CASCADE, db_column='MaLop',
                              related_name='tkb_list', verbose_name="Lớp môn học")
    ma_phong = models.ForeignKey(PhongHoc, on_delete=models.CASCADE, null=True, blank=True,
                                db_column='MaPhong', related_name='tkb_list',
                                verbose_name="Phòng học")  # Nullable: có thể chưa sắp xếp phòng
    time_slot_id = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, db_column='TimeSlotID',
                                    related_name='tkb_list', verbose_name="Time slot")
    tuan_hoc = models.CharField(max_length=64, db_column='TuanHoc',
                               verbose_name="Pattern tuần học")  # VD: "1111111000000000"
    ngay_bd = models.DateField(db_column='NgayBD',
                              verbose_name="Ngày bắt đầu khoá học")  # Ngày bắt đầu toàn bộ môn
    ngay_kt = models.DateField(db_column='NgayKT',
                              verbose_name="Ngày kết thúc khoá học")  # Ngày kết thúc toàn bộ môn
    ngay_tao = models.DateTimeField(auto_now_add=True, db_column='NgayTao',
                                   verbose_name="Ngày tạo")
    ghi_chu = models.CharField(max_length=200, null=True, blank=True, db_column='GhiChu',
                              verbose_name="Ghi chú")
    
    class Meta:
        db_table = 'tb_TKB'
        verbose_name = "Thời khóa biểu"
        verbose_name_plural = "Thời khóa biểu"
        ordering = ['ma_dot', 'time_slot_id__thu', 'time_slot_id__ca']
        unique_together = [['ma_dot', 'ma_lop', 'ma_phong', 'time_slot_id']]
        indexes = [
            models.Index(fields=['ma_dot'], name='IX_TKB_MaDot'),
            models.Index(fields=['ma_lop'], name='IX_TKB_MaLop'),
            models.Index(fields=['time_slot_id'], name='IX_TKB_TimeSlotID'),
            models.Index(fields=['ngay_bd'], name='IX_TKB_NgayBD'),
            models.Index(fields=['ma_dot', 'ma_lop'], name='IX_TKB_MaDot_MaLop'),
        ]
    
    def __str__(self):
        phong = self.ma_phong.ma_phong if self.ma_phong else "Chưa xác định"
        return f"{self.ma_lop.ma_lop} - {phong} - {self.time_slot_id}"
