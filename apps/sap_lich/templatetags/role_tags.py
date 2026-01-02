"""
Custom template tags cho role-based menu filtering
"""
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def user_can_see_menu_item(context, menu_url):
    """
    Check nếu user có quyền xem menu item này
    
    Usage in template:
        {% user_can_see_menu_item "/admin/sap_lich/algo-scheduler/" as can_see %}
        {% if can_see %}
            <li>Menu item</li>
        {% endif %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return False
    
    user = request.user
    is_admin = user.is_superuser
    
    # Admin thấy tất cả
    if is_admin:
        return True
    
    groups = user.groups.values_list('name', flat=True)
    is_truong_khoa = 'Trưởng Khoa' in groups
    is_truong_bo_mon = 'Trưởng Bộ Môn' in groups
    is_giang_vien = 'Giảng Viên' in groups or (not is_truong_khoa and not is_truong_bo_mon)
    
    # Check permissions theo URL
    if 'algo-scheduler' in menu_url or 'llm-scheduler' in menu_url or 'tkb-manage' in menu_url:
        # Chỉ admin và truong_khoa thấy
        return is_admin or is_truong_khoa
    elif 'thoikhoabieu' in menu_url:
        # Tất cả users thấy
        return True
    elif '/scheduling/' in menu_url:
        # Models trong scheduling app
        if is_admin or is_truong_khoa:
            return True
        elif is_truong_bo_mon:
            # Truong Bo Mon chỉ thấy một số models
            allowed = ['monhoc', 'giangvien', 'nguyenvong', 'gvdaymon', 'phancong']
            return any(model in menu_url for model in allowed)
        else:
            return False
    elif '/auth/' in menu_url:
        # Auth app - chỉ admin
        return is_admin
    elif '/data_table/' in menu_url:
        # Data table - admin và truong_khoa
        return is_admin or is_truong_khoa
    
    # Mặc định: chỉ admin thấy
    return is_admin


@register.filter
def user_role_display(user):
    """
    Trả về role của user để display
    
    Usage in template:
        {{ request.user|user_role_display }}
    """
    if not user or not user.is_authenticated:
        return "Guest"
    
    if user.is_superuser:
        return "Admin"
    
    groups = user.groups.values_list('name', flat=True)
    if 'Trưởng Khoa' in groups:
        return "Trưởng Khoa"
    elif 'Trưởng Bộ Môn' in groups:
        return "Trưởng Bộ Môn"
    elif 'Giảng Viên' in groups:
        return "Giảng Viên"
    
    return "User"
