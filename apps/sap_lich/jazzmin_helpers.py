"""
Custom Jazzmin settings helpers để filter menu dựa trên user groups
"""
from django.urls import reverse
from django.conf import settings


def jazzmin_menu_context(request):
    """
    Context processor để thêm custom links động vào Jazzmin
    """
    if not request or not request.user.is_authenticated:
        return {}
    
    user = request.user
    is_admin = user.is_superuser
    
    # Lấy custom links dựa trên user
    custom_links = get_custom_links_for_user(request)
    
    # Tạo hide_apps list
    hide_apps = []
    if not is_admin:
        hide_apps = ['auth', 'authtoken']
    
    return {
        'jazzmin_custom_links': custom_links,
        'jazzmin_hide_apps': hide_apps,
    }


def get_custom_links_for_user(request):
    """
    Trả về custom links dựa trên role của user
    """
    if not request or not request.user.is_authenticated:
        return {}
    
    user = request.user
    is_admin = user.is_superuser
    groups = user.groups.values_list('name', flat=True)
    is_truong_khoa = 'Trưởng Khoa' in groups
    is_truong_bo_mon = 'Trưởng Bộ Môn' in groups
    is_giang_vien = 'Giảng Viên' in groups or (not is_admin and not is_truong_khoa and not is_truong_bo_mon)
    
    sap_lich_links = []
    scheduling_links = []
    pages_links = []
    
    # Chỉ Admin mới thấy menu Sắp lịch
    if is_admin:
        sap_lich_links.extend([
            {
                "name": "Sắp lịch (Thuật toán)",
                "url": "/admin/sap_lich/algo-scheduler/",
                "icon": "fas fa-robot",
            },
            {
                "name": "Chat Bot Hỗ trợ (LLM)",
                "url": "/admin/sap_lich/llm-scheduler/",
                "icon": "fas fa-comments",
            },
        ])
    
    # Tất cả users thấy Xem và Quản lý TKB
    scheduling_links.extend([
        {
            "name": "Xem Thời Khóa Biểu",
            "url": "/admin/sap_lich/thoikhoabieu/",
            "icon": "fas fa-calendar-alt",
        },
        {
            "name": "Quản lý TKB",
            "url": "/admin/sap_lich/tkb-manage/",
            "icon": "fas fa-edit",
        },
    ])
    
    # Tất cả users thấy Hồ sơ cá nhân
    pages_links.append({
        "name": "Hồ sơ cá nhân",
        "url": "/user-profile/",
        "icon": "fas fa-user-circle",
    })
    
    return {
        "sap_lich": sap_lich_links,
        "scheduling": scheduling_links,
        "pages": pages_links
    }


def filter_jazzmin_menu(request, menu_dict):
    """
    Filter Jazzmin menu items dựa trên user groups
    
    Args:
        request: Django request object
        menu_dict: Dictionary of menu items từ JAZZMIN_SETTINGS
    
    Returns:
        Filtered menu dictionary
    """
    if not request or not request.user.is_authenticated:
        return menu_dict
    
    user = request.user
    is_admin = user.is_superuser
    
    # Filter menu items
    filtered_menu = menu_dict.copy()
    
    # Ẩn auth app với non-admin
    if not is_admin:
        if 'hide_apps' not in filtered_menu:
            filtered_menu['hide_apps'] = []
        if 'auth' not in filtered_menu['hide_apps']:
            filtered_menu['hide_apps'].append('auth')
        if 'authtoken' not in filtered_menu['hide_apps']:
            filtered_menu['hide_apps'].append('authtoken')
    
    # Update custom_links động dựa trên user
    filtered_menu['custom_links'] = get_custom_links_for_user(request)
    
    return filtered_menu
