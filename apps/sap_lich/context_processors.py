"""
Context processor để cung cấp thông tin role và menu cho template
SỬA: Menu hiển thị dựa trên PERMISSIONS thực tế đã gán, không cứng theo role
"""
import logging
from apps.sap_lich.rbac import get_user_role_info

logger = logging.getLogger(__name__)


def user_has_any_permission(user, permissions):
    """
    Kiểm tra user có ít nhất một trong các permissions
    Args:
        user: Django User object
        permissions: list tên permissions (vd: ['sap_lich.add_saplich', 'sap_lich.change_saplich'])
    Returns:
        bool: True nếu user có ít nhất 1 permission
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return any(user.has_perm(perm) for perm in permissions)


def user_has_all_permissions(user, permissions):
    """
    Kiểm tra user có tất cả các permissions
    Args:
        user: Django User object
        permissions: list tên permissions
    Returns:
        bool: True nếu user có tất cả permissions
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return all(user.has_perm(perm) for perm in permissions)


def user_role_context(request):
    """
    Context processor để thêm thông tin role và menu dựa trên PERMISSIONS vào template
    Menu items sẽ hiển thị dựa vào permissions thực tế của user
    """
    role_info = get_user_role_info(request.user)
    user = request.user
    ma_gv = role_info['ma_gv'] or user.username
    
    # Luôn có Dashboard
    menu_items = [
        {
            'icon': 'tim-icons icon-chart-pie-36',
            'title': 'Dashboard',
            'url': '/',
            'segment': 'dashboard'
        }
    ]
    
    logger.info(
        f"Context processor: user={user.username}, role={role_info['role']}, "
        f"is_superuser={user.is_superuser}, groups={list(user.groups.values_list('name', flat=True))}"
    )
    
    # Kiểm tra các permissions (sử dụng tên permissions THỰC TẾ trong DB)
    # Lưu ý: Tên model là 'saplich' (không phải 'tkb')
    has_view_saplich = user.has_perm('sap_lich.view_saplich')
    has_change_saplich = user.has_perm('sap_lich.change_saplich')
    has_add_saplich = user.has_perm('sap_lich.add_saplich')
    has_view_data = user.has_perm('scheduling.view_monhoc') or user.has_perm('scheduling.view_giangvien')
    has_view_nguyenvong = user.has_perm('scheduling.view_nguyenvong')
    has_add_nguyenvong = user.has_perm('scheduling.add_nguyenvong')
    
    logger.info(
        f"Permissions: view_saplich={has_view_saplich}, change_saplich={has_change_saplich}, "
        f"add_saplich={has_add_saplich}, view_data={has_view_data}"
    )
    
    # Xây dựng menu "Sắp lịch" nếu có quyền
    sap_lich_children = []
    if has_add_saplich or has_change_saplich:
        sap_lich_children.extend([
            {
                'icon': 'tim-icons icon-bulb-63',
                'title': 'Sắp lịch TKB (LLM)',
                'url': '/admin/sap_lich/llm-scheduler/',
                'segment': 'llm-scheduler'
            },
            {
                'icon': 'tim-icons icon-time-alarm',
                'title': 'Sắp lịch TKB (Thuật toán)',
                'url': '/admin/sap_lich/algo-scheduler/',
                'segment': 'algo-scheduler'
            },
        ])
    
    # Xây dựng submenu "Xem và Quản lý TKB"
    quan_ly_children = []
    if has_change_saplich:
        quan_ly_children.append({
            'icon': 'tim-icons icon-settings',
            'title': 'Quản lý TKB',
            'url': f'/truong-khoa/{ma_gv}/quan-ly-tkb/',
            'segment': 'quan-ly-tkb'
        })
    if has_view_saplich:
        quan_ly_children.append({
            'icon': 'tim-icons icon-notes',
            'title': 'Xem thời khóa biểu',
            'url': f'/truong-khoa/{ma_gv}/xem-tkb/',
            'segment': 'xem-tkb'
        })
    
    # Thêm menu "Sắp lịch" nếu có children
    if sap_lich_children:
        menu_items.append({
            'icon': 'tim-icons icon-calendar-60',
            'title': 'Sắp lịch',
            'segment': 'sap-lich',
            'children': sap_lich_children
        })
    
    # Thêm menu "Xem và Quản lý TKB" nếu có children
    if quan_ly_children:
        menu_items.append({
            'icon': 'tim-icons icon-book-bookmark',
            'title': 'Xem và Quản lý TKB',
            'segment': 'xem-quan-ly-tkb',
            'children': quan_ly_children
        })
    
    # Thêm menu "Dữ liệu" nếu có permission
    if has_view_data:
        menu_items.append({
            'icon': 'tim-icons icon-puzzle-10',
            'title': 'Dữ liệu',
            'url': '/data_table/',
            'segment': 'data_table'
        })
        logger.info(f"Added 'Dữ liệu' menu - has_view_data={has_view_data}")
    else:
        logger.info(f"NOT adding 'Dữ liệu' menu - has_view_data={has_view_data}, view_monhoc={user.has_perm('scheduling.view_monhoc')}, view_giangvien={user.has_perm('scheduling.view_giangvien')}")
    
    # Menu cho Giảng viên nếu role là giang_vien
    if role_info['role'] == 'giang_vien':
        if has_view_saplich:
            menu_items.append({
                'icon': 'tim-icons icon-notes',
                'title': 'Xem TKB của tôi',
                'url': f'/giang-vien/{ma_gv}/xem-tkb/',
                'segment': 'xem-tkb'
            })
        if has_view_nguyenvong or has_add_nguyenvong:
            menu_items.append({
                'icon': 'tim-icons icon-heart',
                'title': 'Nguyện vọng',
                'url': f'/giang-vien/{ma_gv}/nguyen-vong/',
                'segment': 'nguyen-vong'
            })
    
    # Tài khoản - luôn thêm
    menu_items.append({
        'icon': 'tim-icons icon-single-02',
        'title': 'Tài khoản',
        'segment': 'tai-khoan',
        'children': [
            {
                'icon': 'tim-icons icon-badge',
                'title': 'Hồ sơ cá nhân',
                'url': '/user-profile/',
                'segment': 'user-profile'
            }
        ]
    })
    
    logger.info(f"Final menu_items count: {len(menu_items)}, items: {[item.get('title') for item in menu_items]}")
    
    return {
        'user_role_info': role_info,
        'user_role': role_info['role'],
        'menu_items': menu_items,
        'is_admin': role_info['role'] == 'admin',
        'is_truong_khoa': role_info['role'] == 'truong_khoa',
        'is_truong_bo_mon': role_info['role'] == 'truong_bo_mon',
        'is_giang_vien': role_info['role'] == 'giang_vien',
    }
