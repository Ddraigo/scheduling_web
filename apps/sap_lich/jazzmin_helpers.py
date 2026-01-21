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
    Jazzmin sẽ override JAZZMIN_SETTINGS['custom_links'] với giá trị từ đây
    """
    if not request or not request.user.is_authenticated:
        return {}
    
    user = request.user
    
    # Lấy custom links dựa trên permissions
    custom_links = get_custom_links_for_user(request)
    
    logger.info(f"[jazzmin_menu_context] User: {user.username}, custom_links: {list(custom_links.keys())}")
    for app, links in custom_links.items():
        logger.info(f"  {app}: {len(links)} links - {[l.get('name') for l in links]}")
    
    return {
        'jazzmin_custom_links': custom_links,
    }


def get_custom_links_for_user(request):
    """
    Trả về custom links dựa trên PERMISSIONS của user (chứ không phải role)
    
    STRATEGY: Hiển thị menu dựa trên actual Django permissions
    Permissions check:
      - view_saplich → Xem TKB
      - change_saplich, add_saplich → Quản lý TKB
      - view_nguyenvong, add_nguyenvong → Nguyện vọng
    """
    if not request or not request.user.is_authenticated:
        return {}
    
    user = request.user
    from apps.sap_lich.rbac import get_user_role_info
    role_info = get_user_role_info(user)
    ma_gv = role_info.get('ma_gv') or user.username
    
    # Check permissions
    has_view_saplich = user.has_perm('sap_lich.view_saplich')
    has_change_saplich = user.has_perm('sap_lich.change_saplich')
    has_add_saplich = user.has_perm('sap_lich.add_saplich')
    has_view_nguyenvong = user.has_perm('scheduling.view_nguyenvong')
    has_add_nguyenvong = user.has_perm('scheduling.add_nguyenvong')
    has_view_monhoc = user.has_perm('scheduling.view_monhoc')
    has_view_giangvien = user.has_perm('scheduling.view_giangvien')
    
    sap_lich_links = []
    scheduling_links = []
    pages_links = []
    
    logger.debug(f"Building custom links for user={user.username}, role={role_info['role']}")
    logger.debug(f"Permissions: view_saplich={has_view_saplich}, change_saplich={has_change_saplich}, add_saplich={has_add_saplich}")
    
    # SAP_LICH: Thêm scheduler links nếu có quyền add/change
    if has_add_saplich or has_change_saplich:
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
        logger.debug(f"User {user.username}: Added scheduler links")
    
    # XEM TKB: Nếu có permission view_saplich
    if has_view_saplich:
        # Determine URL based on role
        if role_info['role'] == 'admin':
            xem_tkb_url = "/admin/sap_lich/thoikhoabieu/"
        elif role_info['role'] == 'truong_khoa':
            xem_tkb_url = f"/truong-khoa/{ma_gv}/xem-tkb/"
        elif role_info['role'] == 'truong_bo_mon':
            xem_tkb_url = f"/truong-bo-mon/{ma_gv}/xem-tkb/"
        else:
            xem_tkb_url = f"/giang-vien/{ma_gv}/xem-tkb/"
        
        scheduling_links.append({
            "name": "Xem Thời Khóa Biểu",
            "url": xem_tkb_url,
            "icon": "fas fa-calendar-alt",
        })
        logger.debug(f"User {user.username}: Added 'Xem TKB' link")
    
    # QUẢN LÝ TKB: Nếu có permission change_saplich
    if has_change_saplich:
        if role_info['role'] == 'admin':
            manage_tkb_url = "/admin/sap_lich/tkb-manage/"
        elif role_info['role'] == 'truong_khoa':
            manage_tkb_url = f"/truong-khoa/{ma_gv}/quan-ly-tkb/"
        else:
            # Trưởng bộ môn, giảng viên không có quyền quản lý
            manage_tkb_url = None
        
        if manage_tkb_url:
            scheduling_links.append({
                "name": "Quản lý TKB",
                "url": manage_tkb_url,
                "icon": "fas fa-edit",
            })
            logger.debug(f"User {user.username}: Added 'Quản lý TKB' link")
    
    # NGUYỆN VỌNG: Nếu có permission
    if has_view_nguyenvong or has_add_nguyenvong:
        nguyen_vong_url = f"/giang-vien/{ma_gv}/nguyen-vong/"
        scheduling_links.append({
            "name": "Nguyện vọng",
            "url": nguyen_vong_url,
            "icon": "fas fa-heart",
        })
        logger.debug(f"User {user.username}: Added 'Nguyện vọng' link")
    
    # HỒ SƠ CÁ NHÂN: Luôn thêm cho authenticated users
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
