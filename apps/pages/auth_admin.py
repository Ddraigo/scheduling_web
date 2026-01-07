"""
Custom Admin cho Auth models (User, Group) để ẩn với non-superusers
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import User, Group
from django.utils.html import format_html


class CustomUserAdmin(BaseUserAdmin):
    """
    Custom UserAdmin chỉ cho phép superuser truy cập
    """
    # Thêm các cột hiển thị
    list_display = ['username', 'ho_ten_display', 'email', 'vai_tro_display', 'loai_gv_display', 'bo_mon_display', 'is_staff', 'is_active', 'last_login']
    list_filter = ['is_staff', 'is_active', 'groups']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['username']
    
    def has_module_permission(self, request):
        """
        Chỉ superuser mới thấy module User trong admin sidebar
        """
        return request.user.is_superuser
    
    def has_view_permission(self, request, obj=None):
        """
        Chỉ superuser mới có quyền xem User
        """
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        """
        Chỉ superuser mới có quyền thêm User
        """
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """
        Chỉ superuser mới có quyền sửa User
        """
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        """
        Chỉ superuser mới có quyền xóa User
        """
        return request.user.is_superuser
    
    def ho_ten_display(self, obj):
        """Hiển thị họ và tên đầy đủ từ GiangVien model hoặc User model"""
        try:
            from apps.scheduling.models import GiangVien
            gv = GiangVien.objects.select_related('ma_bo_mon').get(ma_gv=obj.username)
            return format_html(
                '<strong style="color: #1f2937;">{}</strong>',
                gv.ten_gv
            )
        except:
            # Nếu không phải GV, hiển thị first_name + last_name từ User
            full_name = f"{obj.last_name} {obj.first_name}".strip()
            if full_name:
                return format_html(
                    '<span style="color: #6b7280;">{}</span>',
                    full_name
                )
            return format_html('<span style="color: #9ca3af;">—</span>')
    ho_ten_display.short_description = 'Tên'
    ho_ten_display.admin_order_field = 'username'
    
    def vai_tro_display(self, obj):
        """Hiển thị vai trò/chức vụ từ Groups"""
        groups = obj.groups.all()
        
        if obj.is_superuser:
            return format_html(
                '<span style="background: #7c3aed; color: white; padding: 3px 8px; border-radius: 4px; '
                'font-size: 11px; font-weight: 600;">👑 Admin</span>'
            )
        
        if not groups:
            return format_html('<span style="color: #9ca3af; font-size: 11px;">Chưa có</span>')
        
        # Map groups sang display với icon và màu
        role_config = {
            'Truong_Khoa': {'label': '👔 Trưởng Khoa', 'color': '#dc2626'},
            'Truong_Bo_Mon': {'label': '📚 Trưởng Bộ Môn', 'color': '#ea580c'},
            'Giang_Vien': {'label': '👨‍🏫 Giảng Viên', 'color': '#16a34a'}
        }
        
        html_parts = []
        for group in groups:
            config = role_config.get(group.name, {'label': group.name, 'color': '#6b7280'})
            html_parts.append(
                f'<span style="background: {config["color"]}; color: white; padding: 3px 8px; '
                f'border-radius: 4px; font-size: 11px; font-weight: 600; margin-right: 2px;">{config["label"]}</span>'
            )
        
        return format_html(''.join(html_parts))
    vai_tro_display.short_description = 'Vai trò'
    
    def loai_gv_display(self, obj):
        """Hiển thị loại giảng viên"""
        try:
            from apps.scheduling.models import GiangVien
            gv = GiangVien.objects.get(ma_gv=obj.username)
            if gv.loai_gv:
                # Mapping màu sắc cho loại GV
                loai_colors = {
                    'Cơ hữu': '#2563eb',  # blue
                    'Thỉnh giảng': '#f59e0b',  # amber
                    'Hợp đồng': '#8b5cf6',  # purple
                }
                color = loai_colors.get(gv.loai_gv, '#6b7280')
                return format_html(
                    '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 4px; '
                    'font-size: 11px; font-weight: 600;">{}</span>',
                    color,
                    gv.loai_gv
                )
            return format_html('<span style="color: #9ca3af;">—</span>')
        except:
            return format_html('<span style="color: #9ca3af;">—</span>')
    loai_gv_display.short_description = 'Loại giảng viên'
    
    def bo_mon_display(self, obj):
        """Hiển thị bộ môn của giảng viên"""
        try:
            from apps.scheduling.models import GiangVien
            gv = GiangVien.objects.select_related('ma_bo_mon').get(ma_gv=obj.username)
            if gv.ma_bo_mon:
                return format_html(
                    '<span style="color: #059669; font-weight: 600;">{}</span>',
                    gv.ma_bo_mon.ten_bo_mon
                )
            return format_html('<span style="color: #9ca3af;">—</span>')
        except:
            return format_html('<span style="color: #9ca3af;">—</span>')
    bo_mon_display.short_description = 'Bộ môn'


class CustomGroupAdmin(BaseGroupAdmin):
    """
    Custom GroupAdmin chỉ cho phép superuser truy cập
    """
    def has_module_permission(self, request):
        """
        Chỉ superuser mới thấy module Group trong admin sidebar
        """
        return request.user.is_superuser
    
    def has_view_permission(self, request, obj=None):
        """
        Chỉ superuser mới có quyền xem Group
        """
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        """
        Chỉ superuser mới có quyền thêm Group
        """
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """
        Chỉ superuser mới có quyền sửa Group
        """
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        """
        Chỉ superuser mới có quyền xóa Group
        """
        return request.user.is_superuser


# NOTE: Không register User/Group ở đây nữa
# Để apps.scheduling.permission_admin.py xử lý vì nó có đầy đủ hơn
# Giữ CustomUserAdmin class ở đây để backup hoặc tham khảo

# # Unregister default admin
# admin.site.unregister(User)
# admin.site.unregister(Group)

# # Register custom admin
# admin.site.register(User, CustomUserAdmin)
# admin.site.register(Group, CustomGroupAdmin)
