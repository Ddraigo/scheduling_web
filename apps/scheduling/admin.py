"""
Django Admin for Scheduling System
FIXED: Field names now match actual model definitions
Enhanced UI with custom styling
"""

import re
import unicodedata
from datetime import datetime

from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import (
    Khoa, BoMon, GiangVien, MonHoc, PhongHoc,
    LopMonHoc, DotXep, PhanCong, TimeSlot, ThoiKhoaBieu,
    DuKienDT, GVDayMon, KhungTG, RangBuocMem, RangBuocTrongDot, NguyenVong,
    NgayNghiCoDinh, NgayNghiDot
)
from .utils.excel_export import ExcelExporter
from .utils.excel_import import ExcelImporter

# Import custom permission admin (phải import sau khi đăng ký các model khác)
# Sẽ được import ở cuối file

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
    change_list_template = 'admin/scheduling/change_list_with_import.html'
    actions = ['export_to_excel', 'delete_selected_custom']

    def has_module_permission(self, request):
        """
        Override để check permission dựa trên user groups
        """
        user = request.user
        
        # Superuser thấy tất cả
        if user.is_superuser:
            return True
        
        # Kiểm tra groups
        groups = user.groups.values_list('name', flat=True)
        is_truong_khoa = 'Truong_Khoa' in groups
        is_truong_bo_mon = 'Truong_Bo_Mon' in groups
        
        # Truong_Khoa thấy tất cả models
        if is_truong_khoa:
            return True
        
        # Truong_Bo_Mon chỉ thấy một số models
        if is_truong_bo_mon:
            model_name = self.model.__name__.lower()
            allowed_models = ['monhoc', 'giangvien', 'nguyenvong', 'gvdaymon', 'phancong']
            return model_name in allowed_models
        
        # Giang_Vien không thấy models
        return False
    def get_urls(self):
        """Add custom URLs for import"""
        urls = super().get_urls()
        custom_urls = [
            path('download-template/', self.admin_site.admin_view(self.download_template), name=f'{self.model._meta.app_label}_{self.model._meta.model_name}_download_template'),
            path('import-excel/', self.admin_site.admin_view(self.import_excel_view), name=f'{self.model._meta.app_label}_{self.model._meta.model_name}_import_excel'),
        ]
        return custom_urls + urls

    def download_template(self, request):
        """Download Excel template for this model"""
        return ExcelImporter.generate_template(self.model)

    def import_excel_view(self, request):
        """Handle Excel file upload and import"""
        print(f"=== IMPORT VIEW CALLED ===")
        print(f"Method: {request.method}")
        print(f"FILES: {request.FILES}")
        print(f"POST: {request.POST}")
        
        if request.method == 'POST':
            if request.FILES.get('excel_file'):
                file = request.FILES['excel_file']
                print(f"File received: {file.name}")
                ExcelImporter.validate_and_import(file, self.model, request)
            else:
                messages.error(request, "Không tìm thấy file Excel trong request")
        else:
            messages.warning(request, "Phương thức không hợp lệ (cần POST)")
        return redirect('..')

    @staticmethod
    def _safe_filename(name: str) -> str:
        """Sanitize filename: remove Vietnamese accents, keep letters."""
        # Bỏ dấu tiếng Việt
        name = unicodedata.normalize('NFKD', name)
        name = name.encode('ascii', 'ignore').decode('ascii')
        # Loại bỏ ký tự không hợp lệ, giữ chữ số, chữ cái, khoảng trắng, gạch ngang
        safe = re.sub(r'[^\w\s-]', '', name).strip()
        # Thay khoảng trắng liên tiếp bằng underscore
        safe = re.sub(r'\s+', '_', safe)
        return safe or "export"

    def _extract_dot_code(self, request, queryset):
        """Try to get mã đợt từ filter hoặc bản ghi."""
        # Từ bộ lọc trên changelist
        for key in ["ma_dot__id__exact", "ma_dot__exact", "ma_dot"]:
            val = request.GET.get(key)
            if val:
                return val

        # Từ bản ghi đầu tiên (nếu có)
        first = queryset.first()
        if first is not None and hasattr(first, "ma_dot"):
            dot_obj = getattr(first, "ma_dot")
            if dot_obj is not None:
                return getattr(dot_obj, "ma_dot", None) or str(dot_obj)
        return None
    
    def export_to_excel(self, request, queryset):
        """Action to export selected items to Excel"""
        # Nếu không chọn bản ghi nào, dùng toàn bộ queryset đã lọc ở changelist
        if queryset.count() == 0:
            try:
                changelist = self.get_changelist_instance(request)
                queryset = changelist.get_queryset(request)
            except Exception:
                queryset = self.model.objects.none()

        if queryset.count() == 0:
            messages.warning(request, "Không có bản ghi để xuất (sau filter).")
            return None

        model_name = self.model.__name__
        exporter_method = f'export_{model_name.lower()}'
        
        if hasattr(ExcelExporter, exporter_method):
            return getattr(ExcelExporter, exporter_method)(queryset)
        else:
            # Generic export for models without custom exporter
            fields = [f.name for f in self.model._meta.fields if f.name != 'id']
            headers = [f.verbose_name for f in self.model._meta.fields if f.name != 'id']
            filename = f'{model_name}_{queryset.model._meta.verbose_name_plural}'
            response = ExcelExporter.export_queryset(queryset, fields, headers, filename)
        
        # Ghi đè tên file: mã đợt + tên bảng + timestamp, tránh ký tự không hợp lệ
        dot_code = self._extract_dot_code(request, queryset)
        table_name = self.model._meta.verbose_name_plural or self.model._meta.verbose_name
        base_name = f"{dot_code}_{table_name}" if dot_code else table_name
        safe_name = self._safe_filename(base_name)
        response['Content-Disposition'] = f'attachment; filename="{safe_name}.xlsx"'
        return response

    def changelist_view(self, request, extra_context=None):
        """Override để xử lý export action trước validation của Django admin."""
        if request.method == 'POST' and request.POST.get('action') == 'export_to_excel':
            try:
                changelist = self.get_changelist_instance(request)
                export_qs = changelist.get_queryset(request)
            except Exception:
                export_qs = self.model.objects.none()

            # Nếu có chọn cụ thể (loại bỏ giá trị dummy), ưu tiên subset đó
            selected = request.POST.getlist(ACTION_CHECKBOX_NAME)
            selected = [pk for pk in selected if pk != 'dummy']
            
            if selected and request.POST.get('select_across') != '1':
                export_qs = export_qs.filter(pk__in=selected)
            
            # Xuất file trực tiếp, bỏ qua toàn bộ validation của Django admin
            return self.export_to_excel(request, export_qs)
        
        return super().changelist_view(request, extra_context)

    def response_action(self, request, queryset):
        """Giữ lại cho các action khác."""
        return super().response_action(request, queryset)
    
    export_to_excel.short_description = "Xuất Excel (.xlsx)"
    
    def delete_selected_custom(self, request, queryset):
        """Custom delete action"""
        from django.contrib import messages
        count = queryset.count()
        queryset.delete()
        messages.success(request, f'Đã xóa {count} bản ghi thành công.')
    
    delete_selected_custom.short_description = "Xóa đã chọn"


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
        # Lấy giá trị từ DB, không thay đổi nội dung
        value = obj.loai_gv or 'N/A'
        # Chỉ dùng 3 màu cố định
        palette = ['#0066cc', "#cfa629", '#28a745']
        known = {
            'Chính': 0,
            'Phụ': 1,
            'Hợp tác': 2,
        }
        if value in known:
            color = palette[known[value]]
        else:
            # Giá trị khác: gán màu ổn định dựa trên hash để mỗi value khác nhau sẽ dùng màu khác trong palette
            idx = abs(hash(value)) % len(palette)
            color = palette[idx]

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            value
        )
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
class DuKienDTAdmin(BaseAdmin):
    list_display = ['ma_du_kien_dt', 'nam_hoc', 'hoc_ky', 'mo_ta_hoc_ky']
    list_filter = ['nam_hoc', 'hoc_ky']
    search_fields = ['ma_du_kien_dt', 'mo_ta_hoc_ky']


@admin.register(GVDayMon)
class GVDayMonAdmin(BaseAdmin):
    list_display = ['id', 'ma_gv', 'ma_mon_hoc']
    list_filter = ['ma_mon_hoc']
    search_fields = ['ma_gv__ten_gv', 'ma_mon_hoc__ten_mon_hoc']
    ordering = ['id']
    list_per_page = 50


@admin.register(PhanCong)
class PhanCongAdmin(BaseAdmin):
    list_display = ['id', 'ma_dot', 'ma_lop', 'ma_gv', 'gv_name', 'tuan_range']
    list_filter = ['ma_dot']
    search_fields = ['ma_gv__ten_gv', 'ma_lop__ma_lop']
    raw_id_fields = ['ma_gv', 'ma_lop']
    list_per_page = 100
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('ma_dot', 'ma_lop', 'ma_gv')
        }),
        ('Phạm vi tuần dạy', {
            'fields': ('tuan_bd', 'tuan_kt')
        }),
    )
    
    def gv_name(self, obj):
        return obj.ma_gv.ten_gv if obj.ma_gv else 'Chưa phân công'
    gv_name.short_description = 'Tên Giảng viên'
    
    def tuan_range(self, obj):
        """Hiển thị khoảng tuần dạy"""
        return f"Tuần {obj.tuan_bd}-{obj.tuan_kt}"
    tuan_range.short_description = 'Khoảng tuần'


@admin.register(RangBuocTrongDot)
class RangBuocTrongDotAdmin(BaseAdmin):
    list_display = ['id', 'ma_dot', 'ma_rang_buoc', 'trong_so', 'get_global_weight']
    list_filter = ['ma_dot']
    ordering = ['id']
    
    def get_global_weight(self, obj):
        """Hiển thị trọng số global từ RangBuocMem để so sánh"""
        return obj.ma_rang_buoc.trong_so
    get_global_weight.short_description = 'Trọng số global'


@admin.register(NguyenVong)
class NguyenVongAdmin(BaseAdmin):
    list_display = ['id', 'ma_gv', 'ma_dot', 'time_slot_id']
    list_filter = ['ma_dot']
    ordering = ['id']
    
    def export_to_excel(self, request, queryset):
        return ExcelExporter.export_nguyen_vong(queryset)
    export_to_excel.short_description = "Xuất Excel (.xlsx)"


@admin.register(KhungTG)
class KhungTGAdmin(BaseAdmin):
    list_display = ['ma_khung_gio', 'ten_ca', 'gio_bat_dau', 'gio_ket_thuc', 'so_tiet']
    ordering = ['ma_khung_gio']


@admin.register(RangBuocMem)
class RangBuocMemAdmin(BaseAdmin):
    list_display = ['ma_rang_buoc', 'ten_rang_buoc', 'trong_so']
    search_fields = ['ma_rang_buoc', 'ten_rang_buoc']


@admin.register(NgayNghiCoDinh)
class NgayNghiCoDinhAdmin(BaseAdmin):
    """Ngày nghỉ cố định (lặp lại hằng năm)"""
    list_display = ['id', 'ten_ngay_nghi', 'ngay', 'ghi_chu']
    search_fields = ['ten_ngay_nghi', 'ngay']
    ordering = ['ngay']
    list_per_page = 30
    fieldsets = (
        ('Thông tin ngày nghỉ', {
            'fields': ('ten_ngay_nghi', 'ngay')
        }),
        ('Ghi chú', {
            'fields': ('ghi_chu',),
            'classes': ('collapse',)
        }),
    )


@admin.register(NgayNghiDot)
class NgayNghiDotAdmin(BaseAdmin):
    """Ngày nghỉ theo đợt xếp lịch (riêng cho mỗi đợt)"""
    list_display = ['id', 'ma_dot', 'ten_ngay_nghi', 'ngay_bd', 'so_ngay_nghi', 'tuan_info']
    list_filter = ['ma_dot', 'ngay_bd']
    search_fields = ['ma_dot__ma_dot', 'ten_ngay_nghi']
    list_per_page = 50
    fieldsets = (
        ('Thông tin đợt', {
            'fields': ('ma_dot',)
        }),
        ('Khoảng nghỉ', {
            'fields': ('ngay_bd', 'so_ngay_nghi', 'ten_ngay_nghi')
        }),
        ('Tuần tham khảo', {
            'fields': ('tuan_bd', 'tuan_kt'),
            'classes': ('collapse',)
        }),
        ('Ghi chú', {
            'fields': ('ghi_chu',),
            'classes': ('collapse',)
        }),
    )
    
    def tuan_info(self, obj):
        """Hiển thị thông tin tuần tham khảo"""
        if obj.tuan_bd and obj.tuan_kt:
            return f"Tuần {obj.tuan_bd}-{obj.tuan_kt}"
        return '-'
    tuan_info.short_description = 'Tuần (tham khảo)'


# Import custom permission admin at the end
# This will override default User and Group admin with custom ones
from . import permission_admin
