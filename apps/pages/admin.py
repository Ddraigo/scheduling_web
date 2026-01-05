from django.contrib import admin
from .models import UserProfile

# Register your models here.

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """
    Dummy admin để tạo app 'Tài khoản' trong sidebar
    Không có records thực tế, chỉ dùng custom_links
    """
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_view_permission(self, request, obj=None):
        # Cho phép xem để app hiển thị trong sidebar
        return True
