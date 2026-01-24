from django.contrib import admin
from .models import SapLich

# Register model để app "Sắp lịch" xuất hiện trong sidebar
@admin.register(SapLich)
class SapLichAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        """Kiểm tra xem user có quyền xem app Sắp lịch không"""
        if not request.user.is_authenticated:
            return False
        
        # Admin thấy tất cả
        if request.user.is_superuser:
            return True
        
        # Kiểm tra groups - Trưởng Khoa, Trưởng Bộ Môn, Giảng Viên chỉ thấy app để xem TKB
        groups = request.user.groups.values_list('name', flat=True)
        allowed_groups = ['Trưởng Khoa', 'Trưởng Bộ Môn', 'Giảng Viên']
        return any(group in allowed_groups for group in groups)
    
    def has_view_permission(self, request, obj=None):
        # Show model link để Jazzmin show app trong sidebar
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        groups = request.user.groups.values_list('name', flat=True)
        allowed_groups = ['Trưởng Khoa', 'Trưởng Bộ Môn', 'Giảng Viên']
        return any(group in allowed_groups for group in groups)


# Custom function để lọc menu theo role (gọi từ jazzmin_helpers hoặc middleware)
def get_sap_lich_menu_for_user(user):
    """
    Trả về danh sách menu items phù hợp với role của user
    - Admin: Tất cả (sắp lịch, chat bot, xem TKB, quản lý TKB)
    - Trưởng Khoa: Chat bot, Xem TKB và quản lý TKB (của khoa mình)
    - Trưởng Bộ Môn: Chat bot, Xem TKB và quản lý TKB (của bộ môn mình)
    - Giảng Viên: Chat bot, Xem TKB (của mình) - KHÔNG có quản lý TKB
    """
    if not user.is_authenticated:
        return []
    
    # Các role khác
    groups = user.groups.values_list('name', flat=True)
    
    # Trưởng Khoa: chat bot, xem và quản lý TKB (của khoa mình)
    if 'Trưởng Khoa' in groups:
        return [
            {"name": "🤖 Chat bot hỗ trợ", "url": "/admin/sap_lich/llm-scheduler/", "icon": "fas fa-robot"},
            {"name": " Xem thời khóa biểu", "url": "/admin/sap_lich/thoikhoabieu/", "icon": "fas fa-calendar-alt"},
            {"name": "✏️ Quản lý TKB", "url": "/admin/sap_lich/tkb-manage/", "icon": "fas fa-edit"},
        ]
    
    # Trưởng Bộ Môn: chat bot, xem và quản lý TKB (của bộ môn mình)
    if 'Trưởng Bộ Môn' in groups:
        return [
            {"name": "🤖 Chat bot hỗ trợ", "url": "/admin/sap_lich/llm-scheduler/", "icon": "fas fa-robot"},
            {"name": " Xem thời khóa biểu", "url": "/admin/sap_lich/thoikhoabieu/", "icon": "fas fa-calendar-alt"},
            {"name": "✏️ Quản lý TKB", "url": "/admin/sap_lich/tkb-manage/", "icon": "fas fa-edit"},
        ]
    
    # Giảng Viên: chat bot và xem TKB (KHÔNG có quản lý TKB)
    if 'Giảng Viên' in groups:
        return [
            {"name": "🤖 Chat bot hỗ trợ", "url": "/admin/sap_lich/llm-scheduler/", "icon": "fas fa-robot"},
            {"name": " Xem thời khóa biểu", "url": "/admin/sap_lich/thoikhoabieu/", "icon": "fas fa-calendar-alt"},
        ]
    
    return []
