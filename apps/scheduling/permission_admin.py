"""
Custom Admin for User and Group Management
Adds permission management to Django Admin
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import User, Group
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import redirect
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
from .models import GiangVien

# Unregister default User and Group admin
admin.site.unregister(User)
admin.site.unregister(Group)


# Signal handler to auto-assign Giang_Vien role for new users
@receiver(post_save, sender=User)
def assign_default_role_to_new_user(sender, instance, created, **kwargs):
    """
    Tự động gán role Giảng Viên cho user mới nếu chưa có role nào
    Chỉ áp dụng cho non-superuser
    """
    if created and not instance.is_superuser:
        # Check if user has any groups
        if not instance.groups.exists():
            try:
                giang_vien_group = Group.objects.get(name='Giang_Vien')
                instance.groups.add(giang_vien_group)
                # Set is_staff=True luôn
                if not instance.is_staff:
                    instance.is_staff = True
                    instance.save(update_fields=['is_staff'])
            except Group.DoesNotExist:
                pass  # Group chưa tồn tại, bỏ qua


# Signal handler to auto-set is_staff when user gets a role
@receiver(m2m_changed, sender=User.groups.through)
def update_staff_status_on_group_change(sender, instance, action, reverse, model, pk_set, **kwargs):
    """
    Tự động set is_staff=True khi user được thêm vào groups
    Điều này cho phép user truy cập /admin/ URLs mà không bị chặn
    """
    if action == 'post_add' and not reverse:
        user = instance
        groups = user.groups.values_list('name', flat=True)
        allowed_groups = ['Truong_Khoa', 'Truong_Bo_Mon', 'Giang_Vien']
        
        # Nếu user có bất kỳ role nào, set is_staff=True
        if any(group in allowed_groups for group in groups):
            if not user.is_staff and not user.is_superuser:
                user.is_staff = True
                user.save(update_fields=['is_staff'])
    
    # Nếu user bị xóa khỏi tất cả groups, remove is_staff
    elif action == 'post_clear' and not reverse:
        user = instance
        if not user.is_superuser and user.is_staff:
            # Check if user still has any groups
            if not user.groups.exists():
                user.is_staff = False
                user.save(update_fields=['is_staff'])


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    """Custom User Admin with better display"""
    # Override list_display để hiển thị thông tin giảng viên
    list_display = ['username', 'ho_ten_gv_display', 'email', 'vai_tro_display', 'loai_gv_display', 'bo_mon_display', 'is_staff', 'is_active', 'last_login']
    list_filter = ['is_staff', 'is_active', 'groups']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['username']
    
    change_list_template = 'admin/auth/user/change_list.html'
    
    def get_urls(self):
        """Add custom URL for bulk role assignment"""
        urls = super().get_urls()
        custom_urls = [
            path('assign-roles/', self.admin_site.admin_view(self.assign_roles_view), name='auth_user_assign_roles'),
        ]
        return custom_urls + urls
    
    def assign_roles_view(self, request):
        """Redirect to the assign roles page"""
        from django.shortcuts import redirect
        return redirect('scheduling_assign_roles')
    
    fieldsets = (
        ('🔐 Thông tin đăng nhập', {
            'fields': ('username', 'password')
        }),
        ('👤 Thông tin cá nhân', {
            'fields': ('first_name', 'last_name', 'email')
        }),
        ('🔑 Phân quyền', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        (' Thông tin khác', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    def ho_ten_gv_display(self, obj):
        """Hiển thị họ và tên đầy đủ từ GiangVien model theo mã GV (username)"""
        try:
            gv = GiangVien.objects.select_related('ma_bo_mon').get(ma_gv=obj.username)
            return format_html(
                '<div style="line-height: 1.4;"><strong style="color: #1f2937; font-size: 14px;">{}</strong><br>'
                '<small style="color: #6b7280;">📧 {}</small></div>',
                gv.ten_gv,
                obj.email or '—'
            )
        except GiangVien.DoesNotExist:
            # Nếu không phải GV, hiển thị first_name + last_name từ User
            full_name = f"{obj.first_name} {obj.last_name}".strip()
            if full_name:
                return format_html(
                    '<div style="line-height: 1.4;"><span style="color: #6b7280; font-size: 14px;">{}</span><br>'
                    '<small style="color: #9ca3af;">Không phải GV</small></div>',
                    full_name
                )
            return format_html('<span style="color: #9ca3af; font-size: 14px;">—</span>')
    ho_ten_gv_display.short_description = 'Họ và tên'
    ho_ten_gv_display.admin_order_field = 'username'  # Cho phép sort theo username
    
    def vai_tro_display(self, obj):
        """Hiển thị vai trò/chức vụ từ Groups"""
        groups = obj.groups.all()
        
        if obj.is_superuser:
            return format_html(
                '<span style="background: #7c3aed; color: white; padding: 4px 10px; border-radius: 4px; '
                'font-size: 12px; font-weight: 600; display: inline-block;">👑 Admin</span>'
            )
        
        if not groups:
            return format_html('<span style="color: #9ca3af; font-size: 12px;">Chưa có vai trò</span>')
        
        # Map groups sang display với icon và màu
        role_config = {
            'Truong_Khoa': {'label': ' Trưởng Khoa', 'color': '#dc2626'},
            'Truong_Bo_Mon': {'label': ' Trưởng Bộ Môn', 'color': '#ea580c'},
            'Giang_Vien': {'label': ' Giảng Viên', 'color': '#16a34a'}
        }
        
        html_parts = []
        for group in groups:
            config = role_config.get(group.name, {'label': group.name, 'color': '#6b7280'})
            html_parts.append(
                f'<span style="background: {config["color"]}; color: white; padding: 4px 10px; '
                f'border-radius: 4px; font-size: 12px; font-weight: 600; display: inline-block; '
                f'margin-right: 4px; margin-bottom: 2px;">{config["label"]}</span>'
            )
        
        return format_html(''.join(html_parts))
    vai_tro_display.short_description = 'Vai trò'
    
    def loai_gv_display(self, obj):
        """Hiển thị loại giảng viên"""
        try:
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
            return format_html('<span style="color: #9ca3af; font-size: 12px;">—</span>')
        except GiangVien.DoesNotExist:
            return format_html('<span style="color: #9ca3af; font-size: 12px;">—</span>')
    loai_gv_display.short_description = 'Loại giảng viên'
    
    def bo_mon_display(self, obj):
        """Hiển thị bộ môn và khoa của giảng viên"""
        try:
            gv = GiangVien.objects.select_related('ma_bo_mon', 'ma_bo_mon__ma_khoa').get(ma_gv=obj.username)
            if gv.ma_bo_mon:
                return format_html(
                    '<div style="line-height: 1.4;"><span style="color: #059669; font-weight: 600; font-size: 13px;">{}</span><br>'
                    '<small style="color: #6b7280;"> {}</small></div>',
                    gv.ma_bo_mon.ten_bo_mon,
                    gv.ma_bo_mon.ma_khoa.ten_khoa if gv.ma_bo_mon.ma_khoa else '—'
                )
            return format_html('<span style="color: #9ca3af;">—</span>')
        except GiangVien.DoesNotExist:
            return format_html('<span style="color: #9ca3af;">—</span>')
    bo_mon_display.short_description = 'Bộ môn / Khoa'


@admin.register(Group)
class CustomGroupAdmin(BaseGroupAdmin):
    """Custom Group Admin with better display"""
    list_display = ['name', 'users_count', 'permissions_count']
    search_fields = ['name']
    
    fieldsets = (
        (' Thông tin nhóm', {
            'fields': ('name',)
        }),
        ('🔑 Quyền hạn', {
            'fields': ('permissions',),
            'description': 'Chọn các quyền cho nhóm này. Users trong nhóm sẽ có các quyền này.'
        }),
    )
    
    def users_count(self, obj):
        """Đếm số users trong group"""
        count = obj.user_set.count()
        if count > 0:
            return format_html(
                '<span style="background: #dbeafe; color: #1e40af; padding: 2px 8px; border-radius: 4px; font-weight: 600;">{} users</span>',
                count
            )
        return format_html('<span style="color: #9ca3af;">0 users</span>')
    users_count.short_description = 'Số lượng users'
    
    def permissions_count(self, obj):
        """Đếm số permissions"""
        count = obj.permissions.count()
        return format_html(
            '<span style="color: #6b7280;">{} quyền</span>',
            count
        )
    permissions_count.short_description = 'Số quyền'


# Custom view for easy role assignment
class RoleManagementView:
    """View để gán role nhanh cho users"""
    
    @staticmethod
    def assign_role_view(request):
        """Assign role to multiple users at once"""
        from django.shortcuts import render
        from django.contrib import messages
        from django.contrib import admin
        
        if request.method == 'POST':
            usernames = request.POST.getlist('users')
            role = request.POST.get('role')
            
            if not usernames or not role:
                messages.error(request, 'Vui lòng chọn users và role!')
                return redirect('admin:auth_user_changelist')
            
            try:
                group = Group.objects.get(name=role)
                users = User.objects.filter(username__in=usernames)
                
                for user in users:
                    user.groups.clear()
                    user.groups.add(group)
                
                messages.success(request, f'Đã gán role {role} cho {len(usernames)} users!')
            except Exception as e:
                messages.error(request, f'Lỗi: {str(e)}')
            
            return redirect('admin:auth_user_changelist')
        
        # GET request - show form
        users = User.objects.all().order_by('username')
        groups = Group.objects.all()
        giang_vien_map = {gv.ma_gv: gv for gv in GiangVien.objects.all()}
        
        # Set current_app for proper admin context
        request.current_app = admin.site.name
        
        base_ctx = admin.site.each_context(request)
        context = {
            **base_ctx,
            'users': users,
            'groups': groups,
            'giang_vien_map': giang_vien_map,
            'title': 'Gán vai trò hàng loạt',
        }
        
        return render(request, 'admin/scheduling/assign_roles.html', context)
