from django.db import models
from django.utils.translation import gettext_lazy as _

# Import scheduling models to create proxies
from apps.scheduling.models import (
    Khoa, BoMon, GiangVien, MonHoc, GVDayMon,
    PhongHoc, LopMonHoc, KhungTG, TimeSlot,
    RangBuocMem, DuKienDT, ThoiKhoaBieu,
    DotXep, PhanCong, RangBuocTrongDot, NgayNghiCoDinh, NgayNghiDot, NguyenVong
)


# Proxy models for data management menu
class KhoaProxy(Khoa):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Khoa"
        verbose_name_plural = "Các Khoa"


class BoMonProxy(BoMon):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Bộ môn"
        verbose_name_plural = "Các Bộ môn"


class GiangVienProxy(GiangVien):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Giảng viên"
        verbose_name_plural = "Giảng viên"


class MonHocProxy(MonHoc):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Môn học"
        verbose_name_plural = "Môn học"


class GVDayMonProxy(GVDayMon):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "GV dạy môn"
        verbose_name_plural = "GV dạy môn"


class PhongHocProxy(PhongHoc):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Phòng học"
        verbose_name_plural = "Phòng học"


class LopMonHocProxy(LopMonHoc):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Lớp môn học"
        verbose_name_plural = "Lớp môn học"


class KhungTGProxy(KhungTG):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Khung thời gian"
        verbose_name_plural = "Khung thời gian"


class TimeSlotProxy(TimeSlot):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Time Slot"
        verbose_name_plural = "Time Slots"


class RangBuocMemProxy(RangBuocMem):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Ràng buộc mềm"
        verbose_name_plural = "Ràng buộc mềm"


class DuKienDTProxy(DuKienDT):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Dự kiến dạy học"
        verbose_name_plural = "Dự kiến dạy học"


class ThoiKhoaBieuProxy(ThoiKhoaBieu):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Thời khóa biểu"
        verbose_name_plural = "Thời khóa biểu"


class DotXepProxy(DotXep):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Đợt xếp lịch"
        verbose_name_plural = "Đợt xếp lịch"


class PhanCongProxy(PhanCong):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Phân công"
        verbose_name_plural = "Phân công giảng dạy"


class RangBuocTrongDotProxy(RangBuocTrongDot):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Ràng buộc trong đợt"
        verbose_name_plural = "Ràng buộc trong đợt"


class NgayNghiCoDinhProxy(NgayNghiCoDinh):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Ngày nghỉ cố định"
        verbose_name_plural = "Ngày nghỉ cố định"


class NgayNghiDotProxy(NgayNghiDot):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Ngày nghỉ theo đợt"
        verbose_name_plural = "Ngày nghỉ theo đợt"


class NguyenVongProxy(NguyenVong):
    class Meta:
        proxy = True
        app_label = 'data_table'
        verbose_name = "Nguyện vọng"
        verbose_name_plural = "Nguyện vọng giảng viên"


# Helper models for admin customization
class PageItems(models.Model):
	parent = models.CharField(max_length=255, null=True, blank=True)
	items_per_page = models.IntegerField(default=25)
	
class HideShowFilter(models.Model):
	parent = models.CharField(max_length=255, null=True, blank=True)
	key = models.CharField(max_length=255)
	value = models.BooleanField(default=False)

	def __str__(self):
		return self.key

class ModelFilter(models.Model):
	parent = models.CharField(max_length=255, null=True, blank=True)
	key = models.CharField(max_length=255)
	value = models.CharField(max_length=255)

	def __str__(self):
		return self.key