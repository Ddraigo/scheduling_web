"""
Django Admin for Scheduling System
FIXED: Field names now match actual model definitions
Enhanced UI with custom styling
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Khoa, BoMon, GiangVien, MonHoc, PhongHoc,
    LopMonHoc, DotXep, PhanCong, TimeSlot, ThoiKhoaBieu,
    DuKienDT, GVDayMon, KhungTG, RangBuocMem, RangBuocTrongDot, NguyenVong
)

# Small admin view to expose the LLM interactive tester under /admin/llm-scheduler/
from django.urls import path
from django.shortcuts import render


def _llm_scheduler_admin_view(request):
    """Admin view for LLM-based scheduler"""
    try:
        periods = list(DotXep.objects.all().values('ma_dot', 'ten_dot', 'trang_thai'))
    except Exception:
        periods = []
    context = {
        'periods': periods,
        'title': 'Sắp lịch bằng LLM',
        'site_title': 'Quản lý lịch dạy học',
        'site_header': 'Hệ thống quản lý lịch dạy học',
    }
    return render(request, 'admin/llm_scheduler.html', context)


def _algo_scheduler_admin_view(request):
    """Admin view for algorithm-based scheduler"""
    try:
        periods = list(DotXep.objects.all().values('ma_dot', 'ten_dot', 'trang_thai'))
    except Exception:
        periods = []
    context = {
        'periods': periods,
        'title': 'Sắp lịch bằng thuật toán',
        'site_title': 'Quản lý lịch dạy học',
        'site_header': 'Hệ thống quản lý lịch dạy học',
    }
    return render(request, 'admin/llm_scheduler.html', context)


def _wrap_get_urls(original_get_urls):
    def get_urls():
        custom_urls = [
            path('llm-scheduler/', admin.site.admin_view(_llm_scheduler_admin_view), name='llm_scheduler'),
            path('algo-scheduler/', admin.site.admin_view(_algo_scheduler_admin_view), name='algo_scheduler'),
        ]
        return custom_urls + original_get_urls()
    return get_urls


# Patch admin.site.get_urls once (idempotent-ish)
if not getattr(admin.site, '_llm_scheduler_hooked', False):
    admin.site.get_urls = _wrap_get_urls(admin.site.get_urls)
    admin.site._llm_scheduler_hooked = True


# Rename "Scheduling System" app label to "Dữ liệu" in admin
class CustomAdminSite(admin.AdminSite):
    pass


# Create custom admin site instance
custom_admin_site = CustomAdminSite(name='custom_admin')


# Hook into default admin site to rename scheduling app
original_app_index = admin.site.app_index

def patched_app_index(request, app_label, extra_context=None):
    # Rename 'scheduling' to 'Dữ liệu' for display
    if app_label == 'scheduling':
        if extra_context is None:
            extra_context = {}
        extra_context['app_name'] = 'Dữ liệu'
        extra_context['app_icon'] = 'fas fa-database'
    return original_app_index(request, app_label, extra_context)


admin.site.app_index = patched_app_index



class BaseAdmin(admin.ModelAdmin):
    """Base admin class with common settings"""
    date_hierarchy = None


@admin.register(Khoa)
class KhoaAdmin(BaseAdmin):
    list_display = ['ma_khoa', 'ten_khoa', 'bo_mon_count']
    search_fields = ['ma_khoa', 'ten_khoa']
    list_per_page = 20
    
    def bo_mon_count(self, obj):
        count = obj.bo_mon_list.count()
        return format_html('<span style="background-color: #0066cc; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>', count)
    bo_mon_count.short_description = 'Số Bộ môn'

    # Ẩn trường ma_khoa khi thêm mới
    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if obj is None:
            # Thêm mới: ẩn ma_khoa
            return [f for f in fields if f != 'ma_khoa']
        return fields

    def save_model(self, request, obj, form, change):
        if not change:
            # Tự động sinh mã khoa khi thêm mới
            existing = type(obj).objects.filter(ma_khoa__startswith='KHOA-')
            used_nums = set()
            for item in existing:
                try:
                    num = int(item.ma_khoa.split('-')[1])
                    used_nums.add(num)
                except Exception:
                    continue
            next_num = 1
            while next_num in used_nums:
                next_num += 1
            obj.ma_khoa = f"KHOA-{next_num:03d}"
        super().save_model(request, obj, form, change)


@admin.register(BoMon)
class BoMonAdmin(BaseAdmin):
    list_display = ['ma_bo_mon', 'ten_bo_mon', 'ma_khoa', 'giang_vien_count']
    list_filter = ['ma_khoa']
    search_fields = ['ma_bo_mon', 'ten_bo_mon']
    list_per_page = 20
    
    def giang_vien_count(self, obj):
        count = obj.giang_vien_list.count()
        return format_html('<span style="background-color: #28a745; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>', count)
    giang_vien_count.short_description = 'Số Giảng viên'


@admin.register(GiangVien)
class GiangVienAdmin(BaseAdmin):
    list_display = ['ma_gv', 'ten_gv', 'email', 'ma_bo_mon', 'loai_gv_colored']
    list_filter = ['ma_bo_mon', 'loai_gv']
    search_fields = ['ma_gv', 'ten_gv', 'email']
    list_per_page = 50
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('ma_gv', 'ten_gv', 'email')
        }),
        ('Thông tin bộ môn', {
            'fields': ('ma_bo_mon', 'loai_gv')
        }),
        ('Ghi chú', {
            'fields': ('ghi_chu',),
            'classes': ('collapse',)
        }),
    )
    
    def loai_gv_colored(self, obj):
        colors = {'Chính': '#0066cc', 'Phụ': '#ffc107', 'Hợp tác': '#28a745'}
        color = colors.get(obj.loai_gv, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>', color, obj.loai_gv or 'N/A')
    loai_gv_colored.short_description = 'Loại GV'


@admin.register(MonHoc)
class MonHocAdmin(BaseAdmin):
    list_display = ['ma_mon_hoc', 'ten_mon_hoc', 'so_tin_chi', 'so_tiet_lt', 'so_tiet_th', 'so_tuan']
    search_fields = ['ma_mon_hoc', 'ten_mon_hoc']
    list_per_page = 50
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('ma_mon_hoc', 'ten_mon_hoc')
        }),
        ('Thông tin học tập', {
            'fields': ('so_tin_chi', 'so_tiet_lt', 'so_tiet_th', 'so_tuan')
        }),
    )


@admin.register(PhongHoc)
class PhongHocAdmin(BaseAdmin):
    list_display = ['ma_phong', 'loai_phong', 'suc_chua', 'thiet_bi_truncated']
    list_filter = ['loai_phong']
    search_fields = ['ma_phong', 'thiet_bi']
    list_per_page = 50
    
    def thiet_bi_truncated(self, obj):
        text = obj.thiet_bi[:50] + '...' if obj.thiet_bi and len(obj.thiet_bi) > 50 else obj.thiet_bi or 'N/A'
        return text
    thiet_bi_truncated.short_description = 'Thiết bị'


@admin.register(LopMonHoc)
class LopMonHocAdmin(BaseAdmin):
    list_display = ['ma_lop', 'ma_mon_hoc', 'nhom_mh', 'so_luong_sv', 'so_ca_tuan']
    list_filter = ['he_dao_tao', 'ngon_ngu', 'ma_mon_hoc']
    search_fields = ['ma_lop']
    list_per_page = 50


@admin.register(DotXep)
class DotXepAdmin(BaseAdmin):
    list_display = ['ma_dot', 'ten_dot', 'trang_thai_colored', 'ngay_tao', 'ngay_khoa']
    list_filter = ['trang_thai', 'ngay_tao']
    search_fields = ['ma_dot', 'ten_dot']
    date_hierarchy = 'ngay_tao'
    list_per_page = 50
    
    def trang_thai_colored(self, obj):
        colors = {'DRAFT': '#6c757d', 'RUNNING': '#0066cc', 'LOCKED': '#ffc107', 'PUBLISHED': '#28a745'}
        color = colors.get(obj.trang_thai, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>', color, obj.trang_thai)
    trang_thai_colored.short_description = 'Trạng thái'


@admin.register(TimeSlot)
class TimeSlotAdmin(BaseAdmin):
    list_display = ['time_slot_id', 'thu_display', 'ca']
    list_filter = ['thu']
    ordering = ['thu', 'ca']
    list_per_page = 50
    
    def thu_display(self, obj):
        thu_names = {2: 'Thứ 2', 3: 'Thứ 3', 4: 'Thứ 4', 5: 'Thứ 5', 6: 'Thứ 6', 7: 'Thứ 7', 8: 'Chủ Nhật'}
        return thu_names.get(obj.thu, f'Thứ {obj.thu}')
    thu_display.short_description = 'Thứ'


@admin.register(ThoiKhoaBieu)
class ThoiKhoaBieuAdmin(BaseAdmin):
    list_display = ['ma_tkb', 'ma_dot', 'ma_lop', 'ma_phong', 'time_slot_id', 'tuan_hoc']
    list_filter = ['ma_dot', 'time_slot_id__thu']
    search_fields = ['ma_lop__ma_lop', 'ma_phong__ma_phong']
    raw_id_fields = ['ma_lop', 'ma_phong', 'time_slot_id']
    list_per_page = 100
    date_hierarchy = 'ngay_bd'


@admin.register(DuKienDT)
class DuKienDTAdmin(admin.ModelAdmin):
    list_display = ['ma_du_kien_dt', 'nam_hoc', 'hoc_ky', 'mo_ta_hoc_ky']
    list_filter = ['nam_hoc', 'hoc_ky']
    search_fields = ['ma_du_kien_dt', 'mo_ta_hoc_ky']


@admin.register(GVDayMon)
class GVDayMonAdmin(admin.ModelAdmin):
    list_display = ['id', 'ma_gv', 'ma_mon_hoc']
    list_filter = ['ma_mon_hoc']
    search_fields = ['ma_gv__ten_gv', 'ma_mon_hoc__ten_mon_hoc']
    ordering = ['id']
    list_per_page = 50


@admin.register(PhanCong)
class PhanCongAdmin(BaseAdmin):
    list_display = ['id', 'ma_dot', 'ma_lop', 'ma_gv', 'gv_name']
    list_filter = ['ma_dot']
    search_fields = ['ma_gv__ten_gv', 'ma_lop__ma_lop']
    raw_id_fields = ['ma_gv', 'ma_lop']
    list_per_page = 100
    
    def gv_name(self, obj):
        return obj.ma_gv.ten_gv if obj.ma_gv else 'Chưa phân công'
    gv_name.short_description = 'Tên Giảng viên'


@admin.register(RangBuocTrongDot)
class RangBuocTrongDotAdmin(admin.ModelAdmin):
    list_display = ['id', 'ma_dot', 'ma_rang_buoc']
    list_filter = ['ma_dot']
    ordering = ['id']


@admin.register(NguyenVong)
class NguyenVongAdmin(admin.ModelAdmin):
    list_display = ['id', 'ma_gv', 'ma_dot', 'time_slot_id']
    list_filter = ['ma_dot']
    ordering = ['id']


@admin.register(KhungTG)
class KhungTGAdmin(admin.ModelAdmin):
    list_display = ['ma_khung_gio', 'ten_ca', 'gio_bat_dau', 'gio_ket_thuc', 'so_tiet']
    ordering = ['ma_khung_gio']


@admin.register(RangBuocMem)
class RangBuocMemAdmin(admin.ModelAdmin):
    list_display = ['ma_rang_buoc', 'ten_rang_buoc', 'trong_so']
    search_fields = ['ma_rang_buoc', 'ten_rang_buoc']
