"""
Context processor để cung cấp thông tin role và menu cho template
"""
import logging
from apps.scheduling.models import GiangVien

logger = logging.getLogger(__name__)


def get_user_role_info(user):
    """
    Xác định role và thông tin liên quan của user
    """
    if not user.is_authenticated:
        return {'role': None, 'ma_khoa': None, 'ma_bo_mon': None, 'ma_gv': None}
    
    if user.is_superuser:
        return {'role': 'admin', 'ma_khoa': None, 'ma_bo_mon': None, 'ma_gv': None}
    
    # Lấy groups của user
    groups = user.groups.values_list('name', flat=True)
    
    # Tìm GiangVien theo username
    try:
        giang_vien = GiangVien.objects.select_related('ma_bo_mon', 'ma_bo_mon__ma_khoa').get(ma_gv=user.username)
        ma_gv = giang_vien.ma_gv
        ma_bo_mon = giang_vien.ma_bo_mon.ma_bo_mon if giang_vien.ma_bo_mon else None
        ma_khoa = giang_vien.ma_bo_mon.ma_khoa.ma_khoa if giang_vien.ma_bo_mon and giang_vien.ma_bo_mon.ma_khoa else None
    except GiangVien.DoesNotExist:
        ma_gv = user.username
        ma_bo_mon = None
        ma_khoa = None
    
    # Xác định role dựa trên group
    if 'Trưởng Khoa' in groups:
        return {'role': 'truong_khoa', 'ma_khoa': ma_khoa, 'ma_bo_mon': None, 'ma_gv': ma_gv}
    elif 'Trưởng Bộ Môn' in groups:
        return {'role': 'truong_bo_mon', 'ma_khoa': ma_khoa, 'ma_bo_mon': ma_bo_mon, 'ma_gv': ma_gv}
    elif 'Giảng Viên' in groups:
        return {'role': 'giang_vien', 'ma_khoa': None, 'ma_bo_mon': None, 'ma_gv': ma_gv}
    else:
        # Mặc định là giáo viên nếu không có group
        return {'role': 'giang_vien', 'ma_khoa': None, 'ma_bo_mon': None, 'ma_gv': ma_gv}


def user_role_context(request):
    """
    Context processor để thêm thông tin role vào tất cả templates
    """
    role_info = get_user_role_info(request.user)
    
    # Tạo menu dựa trên role
    menu_items = []
    
    logger.info(f"DEBUG: Context processor running for user={request.user.username}, role={role_info['role']}")
    
    if role_info['role'] == 'admin':
        menu_items = [
            {
                'icon': 'tim-icons icon-chart-pie-36',
                'title': 'Dashboard',
                'url': '/',
                'segment': 'dashboard'
            },
            {
                'icon': 'tim-icons icon-calendar-60',
                'title': 'Sắp lịch',
                'segment': 'sap-lich',
                'children': [
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
                ]
            },
            {
                'icon': 'tim-icons icon-book-bookmark',
                'title': 'Xem và Quản lý TKB',
                'segment': 'xem-quan-ly-tkb',
                'children': [
                    {
                        'icon': 'tim-icons icon-settings',
                        'title': 'Quản lý TKB',
                        'url': '/admin/sap_lich/tkb-manage/',
                        'segment': 'tkb-manage'
                    },
                    {
                        'icon': 'tim-icons icon-notes',
                        'title': 'Xem thời khóa biểu',
                        'url': '/admin/sap_lich/thoikhoabieu/',
                        'segment': 'thoikhoabieu'
                    },
                ]
            },
            {
                'icon': 'tim-icons icon-puzzle-10',
                'title': 'Dữ liệu',
                'url': '/data_table/',
                'segment': 'data_table'
            },
            {
                'icon': 'tim-icons icon-single-02',
                'title': 'Tài khoản',
                'segment': 'tai-khoan',
                'children': [
                    {
                        'icon': 'tim-icons icon-badge',
                        'title': 'Hồ sơ cá nhân',
                        'url': '/user-profile/',
                        'segment': 'user-profile'
                    },
                ]
            },
        ]
    
    elif role_info['role'] == 'truong_khoa':
        ma_gv = role_info['ma_gv'] or request.user.username
        logger.info(f"Building menu for Truong Khoa: ma_gv={ma_gv}, role_info={role_info}")
        menu_items = [
            {
                'icon': 'tim-icons icon-chart-pie-36',
                'title': 'Dashboard',
                'url': '/',
                'segment': 'dashboard'
            },
            {
                'icon': 'tim-icons icon-calendar-60',
                'title': 'Sắp lịch',
                'segment': 'sap-lich',
                'children': [
                    {
                        'icon': 'tim-icons icon-settings',
                        'title': 'Quản lý TKB',
                        'url': f'/truong-khoa/{ma_gv}/quan-ly-tkb/',
                        'segment': 'quan-ly-tkb'
                    },
                    {
                        'icon': 'tim-icons icon-notes',
                        'title': 'Xem TKB',
                        'url': f'/truong-khoa/{ma_gv}/xem-tkb/',
                        'segment': 'xem-tkb'
                    },
                ]
            },
            {
                'icon': 'tim-icons icon-single-02',
                'title': 'Tài khoản',
                'segment': 'tai-khoan',
                'children': [
                    {
                        'icon': 'tim-icons icon-badge',
                        'title': 'Hồ sơ cá nhân',
                        'url': '/user-profile/',
                        'segment': 'user-profile'
                    },
                ]
            },
        ]
    
    elif role_info['role'] == 'truong_bo_mon':
        ma_gv = role_info['ma_gv'] or request.user.username
        menu_items = [
            {
                'icon': 'tim-icons icon-chart-pie-36',
                'title': 'Dashboard',
                'url': '/',
                'segment': 'dashboard'
            },
            {
                'icon': 'tim-icons icon-calendar-60',
                'title': 'Sắp lịch',
                'segment': 'sap-lich',
                'children': [
                    {
                        'icon': 'tim-icons icon-notes',
                        'title': 'Xem TKB Bộ Môn',
                        'url': f'/truong-bo-mon/{ma_gv}/xem-tkb/',
                        'segment': 'xem-tkb'
                    },
                ]
            },
            {
                'icon': 'tim-icons icon-single-02',
                'title': 'Tài khoản',
                'segment': 'tai-khoan',
                'children': [
                    {
                        'icon': 'tim-icons icon-badge',
                        'title': 'Hồ sơ cá nhân',
                        'url': '/user-profile/',
                        'segment': 'user-profile'
                    },
                ]
            },
        ]
    
    elif role_info['role'] == 'giang_vien':
        ma_gv = role_info['ma_gv'] or request.user.username
        menu_items = [
            {
                'icon': 'tim-icons icon-chart-pie-36',
                'title': 'Dashboard',
                'url': '/',
                'segment': 'dashboard'
            },
            {
                'icon': 'tim-icons icon-notes',
                'title': 'Xem TKB của tôi',
                'url': f'/giang-vien/{ma_gv}/xem-tkb/',
                'segment': 'xem-tkb'
            },
            {
                'icon': 'tim-icons icon-heart',
                'title': 'Nguyện vọng',
                'url': f'/giang-vien/{ma_gv}/nguyen-vong/',
                'segment': 'nguyen-vong'
            },
            {
                'icon': 'tim-icons icon-single-02',
                'title': 'Tài khoản',
                'segment': 'tai-khoan',
                'children': [
                    {
                        'icon': 'tim-icons icon-badge',
                        'title': 'Hồ sơ cá nhân',
                        'url': '/user-profile/',
                        'segment': 'user-profile'
                    },
                ]
            },
        ]
    
    return {
        'user_role_info': role_info,
        'user_role': role_info['role'],
        'menu_items': menu_items,
        'is_admin': role_info['role'] == 'admin',
        'is_truong_khoa': role_info['role'] == 'truong_khoa',
        'is_truong_bo_mon': role_info['role'] == 'truong_bo_mon',
        'is_giang_vien': role_info['role'] == 'giang_vien',
    }
