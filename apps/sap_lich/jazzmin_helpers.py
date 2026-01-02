"""
Custom Jazzmin settings helpers để filter menu dựa trên user groups
"""
from django.urls import reverse


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
    
    links = []
    
    # Admin và Truong_Khoa thấy tất cả
    if is_admin or is_truong_khoa:
        links.extend([
            {
                "name": "Sắp lịch bằng thuật toán",
                "url": "/admin/sap_lich/algo-scheduler/",
                "icon": "fas fa-cogs",
            },
            {
                "name": "Chat bot hỗ trợ",
                "url": "/admin/sap_lich/llm-scheduler/",
                "icon": "fas fa-robot",
            },
            {
                "name": "Quản lý TKB (Thêm/Sửa/Xóa)",
                "url": "/admin/sap_lich/tkb-manage/",
                "icon": "fas fa-edit",
            },
        ])
    
    # Tất cả users thấy Xem TKB
    links.append({
        "name": "Xem thời khóa biểu",
        "url": "/admin/sap_lich/thoikhoabieu/",
        "icon": "fas fa-calendar-alt",
    })
    
    return {"sap_lich": links}


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
    
    if is_admin:
        # Admin thấy tất cả
        return menu_dict
    
    groups = user.groups.values_list('name', flat=True)
    is_truong_khoa = 'Trưởng Khoa' in groups
    is_truong_bo_mon = 'Trưởng Bộ Môn' in groups
    is_giang_vien = 'Giảng Viên' in groups or (not is_truong_khoa and not is_truong_bo_mon)
    
    # Filter menu items
    filtered_menu = menu_dict.copy()
    
    # Filter custom_links trong sap_lich
    if 'custom_links' in filtered_menu and 'sap_lich' in filtered_menu['custom_links']:
        links = []
        for link in filtered_menu['custom_links']['sap_lich']:
            url = link.get('url', '')
            
            # Admin và Truong_Khoa thấy tất cả
            if is_admin or is_truong_khoa:
                links.append(link)
            # Truong_Bo_Mon và Giang_Vien chỉ thấy "Xem thời khóa biểu"
            elif (is_truong_bo_mon or is_giang_vien) and 'thoikhoabieu' in url:
                links.append(link)
        
        filtered_menu['custom_links']['sap_lich'] = links
    
    return filtered_menu
