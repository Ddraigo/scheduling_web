"""
Custom Jazzmin settings helpers để filter menu dựa trên user role
ROLE-DRIVEN: Menu hiển thị theo role, enforcement thực thi ở views
"""
from django.urls import reverse
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def jazzmin_menu_context(request):
    """
    Context processor để thêm custom links động vào Jazzmin
    KHÔNG hardcode hide_apps - để Jazzmin tự filter
    """
    if not request or not request.user.is_authenticated:
        return {}
    
    user = request.user
    
    # Lấy custom links dựa trên role
    custom_links = get_custom_links_for_user(request)
    
    # KHÔNG hardcode hide_apps - chỉ ẩn những app thực sự cần thiết
    # Jazzmin tự động ẩn auth app nếu user không có permission
    hide_apps = []
    
    logger.debug(f"Jazzmin menu context for user={user.username}, custom_links_keys={list(custom_links.keys())}")
    
    return {
        'jazzmin_custom_links': custom_links,
        'jazzmin_hide_apps': hide_apps,
    }


def get_custom_links_for_user(request):
    """
    Trả về custom links dựa trên role của user
    
    STRATEGY: Hiển thị menu dựa trên role, KHÔNG check permissions ở đây
    Permissions sẽ được check ở views (backend enforcement)
    
    MENU LOGIC:
    - Admin: Tất cả menu
    - Trưởng Khoa: Xem TKB + Quản lý TKB
    - Trưởng Bộ Môn: Xem TKB
    - Giảng Viên: Xem TKB
    """
    if not request or not request.user.is_authenticated:
        return {}
    
    user = request.user
    from apps.sap_lich.rbac import get_user_role_info
    role_info = get_user_role_info(user)
    user_role = role_info['role']
    ma_gv = role_info.get('ma_gv') or user.username
    
    sap_lich_links = []
    scheduling_links = []
    pages_links = []
    
    logger.debug(f"Building custom links for user={user.username}, role={user_role}, superuser={user.is_superuser}")
    
    # SAP_LICH: Chỉ admin
    if user_role == 'admin':
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
        logger.debug(f"User {user.username}: Added sap_lich links (admin)")
    
    # SCHEDULING: Xem TKB - tất cả users nhưng dùng URL theo role (tránh /admin/ cho non-admin)
    if user_role == 'admin':
        xem_tkb_url = "/admin/sap_lich/thoikhoabieu/"
    elif user_role == 'truong_khoa':
        xem_tkb_url = f"/truong-khoa/{ma_gv}/xem-tkb/"
    elif user_role == 'truong_bo_mon':
        xem_tkb_url = f"/truong-bo-mon/{ma_gv}/xem-tkb/"
    else:
        xem_tkb_url = f"/giang-vien/{ma_gv}/xem-tkb/"

    scheduling_links.append({
        "name": "Xem Thời Khóa Biểu",
        "url": xem_tkb_url,
        "icon": "fas fa-calendar-alt",
    })
    logger.debug(f"User {user.username}: Added 'Xem TKB' link -> {xem_tkb_url}")

    # SCHEDULING: Quản lý TKB - ADMIN + TRƯỞNG KHOA (role-based URLs)
    manage_tkb_url = None
    if user_role == 'admin':
        manage_tkb_url = "/admin/sap_lich/tkb-manage/"
    elif user_role == 'truong_khoa':
        manage_tkb_url = f"/truong-khoa/{ma_gv}/quan-ly-tkb/"

    if manage_tkb_url:
        scheduling_links.append({
            "name": "Quản lý TKB",
            "url": manage_tkb_url,
            "icon": "fas fa-edit",
        })
        logger.debug(f"User {user.username}: Added 'Quản lý TKB' link -> {manage_tkb_url}")

    # SCHEDULING: Nguyện vọng - chỉ giảng viên
    if user_role == 'giang_vien':
        nguyen_vong_url = f"/giang-vien/{ma_gv}/nguyen-vong/"
        scheduling_links.append({
            "name": "Nguyện vọng",
            "url": nguyen_vong_url,
            "icon": "fas fa-heart",
        })
        logger.debug(f"User {user.username}: Added 'Nguyện vọng' link -> {nguyen_vong_url}")
    
    # PAGES: Hồ sơ cá nhân (tất cả users)
    pages_links.append({
        "name": "Hồ sơ cá nhân",
        "url": "/user-profile/",
        "icon": "fas fa-user-circle",
    })
    
    logger.debug(f"Final links for {user.username}: sap_lich={len(sap_lich_links)}, scheduling={len(scheduling_links)}, pages={len(pages_links)}")
    
    return {
        "sap_lich": sap_lich_links,
        "scheduling": scheduling_links,
        "pages": pages_links
    }


def filter_jazzmin_menu(request, menu_dict):
    """
    Filter Jazzmin menu items dựa trên user permissions
    KHÔNG hardcode hide_apps - để Jazzmin tự filter
    
    Args:
        request: Django request object
        menu_dict: Dictionary of menu items từ JAZZMIN_SETTINGS
    
    Returns:
        Filtered menu dictionary
    """
    if not request or not request.user.is_authenticated:
        return menu_dict
    
    user = request.user
    
    # Filter menu items
    filtered_menu = menu_dict.copy()
    
    # KHÔNG hardcode hide_apps cho auth
    # Jazzmin tự động ẩn auth nếu user không có permission
    # Chỉ giữ các app thực sự cần ẩn (như authtoken)
    if 'hide_apps' not in filtered_menu:
        filtered_menu['hide_apps'] = []
    
    # Update custom_links động dựa trên permissions
    filtered_menu['custom_links'] = get_custom_links_for_user(request)
    
    logger.debug(f"Filtered menu for {user.username}: hide_apps={filtered_menu.get('hide_apps', [])}")
    
    return filtered_menu
