"""
Custom Admin cho Auth models (User, Group) để ẩn với non-superusers
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import User, Group


class CustomUserAdmin(BaseUserAdmin):
    """
    Custom UserAdmin chỉ cho phép superuser truy cập
    """
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


# Unregister default admin
admin.site.unregister(User)
admin.site.unregister(Group)

# Register custom admin
admin.site.register(User, CustomUserAdmin)
admin.site.register(Group, CustomGroupAdmin)
