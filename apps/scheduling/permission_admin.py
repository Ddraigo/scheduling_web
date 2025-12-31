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
from .models import GiangVien

# Unregister default User and Group admin
admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    """Custom User Admin with better display"""
    list_display = ['username', 'email', 'ten_gv_display', 'groups_display', 'is_staff', 'is_active', 'last_login']
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
        ('📅 Thông tin khác', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    def ten_gv_display(self, obj):
        """Hiển thị tên giảng viên nếu có"""
        try:
            gv = GiangVien.objects.get(ma_gv=obj.username)
            bo_mon = gv.ma_bo_mon.ten_bo_mon if gv.ma_bo_mon else 'N/A'
            return format_html(
                '<div style="line-height: 1.5;"><strong>{}</strong><br><small style="color: #6b7280;">{}</small></div>',
                gv.ten_gv,
                bo_mon
            )
        except GiangVien.DoesNotExist:
            return format_html('<span style="color: #9ca3af;">—</span>')
    ten_gv_display.short_description = 'Tên giảng viên'
    
    def groups_display(self, obj):
        """Hiển thị các groups với màu sắc"""
        groups = obj.groups.all()
        if not groups:
            return format_html('<span style="color: #9ca3af;">Chưa có role</span>')
        
        colors = {
            'Truong_Khoa': '#dc2626',
            'Truong_Bo_Mon': '#ea580c',
            'Giang_Vien': '#16a34a'
        }
        
        labels = {
            'Truong_Khoa': '👔 Trưởng Khoa',
            'Truong_Bo_Mon': '📚 Trưởng Bộ Môn',
            'Giang_Vien': '👨‍🏫 Giảng Viên'
        }
        
        html = ''
        for group in groups:
            color = colors.get(group.name, '#6b7280')
            label = labels.get(group.name, group.name)
            html += f'<span style="background: {color}; color: white; padding: 2px 8px; border-radius: 4px; margin-right: 4px; font-size: 11px; display: inline-block;">{label}</span>'
        
        return format_html(html)
    groups_display.short_description = 'Vai trò'


@admin.register(Group)
class CustomGroupAdmin(BaseGroupAdmin):
    """Custom Group Admin with better display"""
    list_display = ['name', 'users_count', 'permissions_count']
    search_fields = ['name']
    
    fieldsets = (
        ('📋 Thông tin nhóm', {
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
        
        context = {
            'users': users,
            'groups': groups,
            'giang_vien_map': giang_vien_map,
            'title': 'Gán vai trò hàng loạt',
        }
        
        return render(request, 'admin/scheduling/assign_roles.html', context)
