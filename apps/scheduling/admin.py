"""
Django Admin for Scheduling System
"""

from django.contrib import admin
from .models import (
    Khoa, BoMon, GiangVien, MonHoc, PhongHoc,
    LopMonHoc, DotXep, PhanCong, TimeSlot, ThoiKhoaBieu
)


@admin.register(Khoa)
class KhoaAdmin(admin.ModelAdmin):
    list_display = ['ma_khoa', 'ten_khoa']
    search_fields = ['ma_khoa', 'ten_khoa']


@admin.register(BoMon)
class BoMonAdmin(admin.ModelAdmin):
    list_display = ['ma_bo_mon', 'ten_bo_mon', 'khoa']
    list_filter = ['khoa']
    search_fields = ['ma_bo_mon', 'ten_bo_mon']


@admin.register(GiangVien)
class GiangVienAdmin(admin.ModelAdmin):
    list_display = ['ma_gv', 'ten_gv', 'email', 'sdt', 'bo_mon']
    list_filter = ['bo_mon']
    search_fields = ['ma_gv', 'ten_gv', 'email']
    list_per_page = 50


@admin.register(MonHoc)
class MonHocAdmin(admin.ModelAdmin):
    list_display = ['ma_mon_hoc', 'ten_mon_hoc', 'so_tin_chi', 'so_tiet_lt', 'so_tiet_th', 'so_tiet_tong']
    search_fields = ['ma_mon_hoc', 'ten_mon_hoc']
    list_per_page = 50


@admin.register(PhongHoc)
class PhongHocAdmin(admin.ModelAdmin):
    list_display = ['ma_phong', 'ten_phong', 'suc_chua', 'loai_phong', 'toa_nha']
    list_filter = ['loai_phong', 'toa_nha']
    search_fields = ['ma_phong', 'ten_phong']


@admin.register(LopMonHoc)
class LopMonHocAdmin(admin.ModelAdmin):
    list_display = ['ma_lop', 'ten_lop', 'mon_hoc', 'si_so', 'loai_lop', 'hoc_ky', 'nam_hoc']
    list_filter = ['loai_lop', 'hoc_ky', 'nam_hoc', 'mon_hoc']
    search_fields = ['ma_lop', 'ten_lop']
    list_per_page = 50


@admin.register(DotXep)
class DotXepAdmin(admin.ModelAdmin):
    list_display = ['ma_dot', 'ten_dot', 'nam_hoc', 'hoc_ky', 'ngay_bat_dau', 'ngay_ket_thuc', 'trang_thai']
    list_filter = ['trang_thai', 'nam_hoc', 'hoc_ky']
    search_fields = ['ma_dot', 'ten_dot']
    date_hierarchy = 'ngay_bat_dau'


@admin.register(PhanCong)
class PhanCongAdmin(admin.ModelAdmin):
    list_display = ['ma_phan_cong', 'dot_xep', 'giang_vien', 'lop_mon_hoc']
    list_filter = ['dot_xep']
    search_fields = ['giang_vien__ten_gv', 'lop_mon_hoc__ten_lop']
    raw_id_fields = ['giang_vien', 'lop_mon_hoc']
    list_per_page = 100


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ['ma_time_slot', 'thu', 'tiet_bat_dau', 'so_tiet', 'gio_bat_dau', 'gio_ket_thuc']
    list_filter = ['thu', 'tiet_bat_dau']
    ordering = ['thu', 'tiet_bat_dau']


@admin.register(ThoiKhoaBieu)
class ThoiKhoaBieuAdmin(admin.ModelAdmin):
    list_display = ['ma_tkb', 'dot_xep', 'lop_mon_hoc', 'phong_hoc', 'time_slot', 'tuan_hoc']
    list_filter = ['dot_xep', 'tuan_hoc', 'time_slot__thu']
    search_fields = ['lop_mon_hoc__ten_lop', 'phong_hoc__ma_phong']
    raw_id_fields = ['phan_cong', 'lop_mon_hoc', 'phong_hoc', 'time_slot']
    list_per_page = 100
    date_hierarchy = 'ngay_hoc'
