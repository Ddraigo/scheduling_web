"""
RBAC (Role-Based Access Control) - Single Source of Truth
Chuẩn hóa role detection và quản lý phạm vi (scope) cho hệ thống TKB

ROLE HIERARCHY:
1. admin (superuser): toàn quyền
2. truong_khoa: chỉ xem/quản lý TKB trong khoa
3. truong_bo_mon: chỉ xem TKB trong bộ môn
4. giang_vien: chỉ xem TKB của chính mình

TƯƠNG THÍCH VỚI TÊN CŨ:
- Hỗ trợ cả group name có dấu ("Trưởng Khoa") và không dấu ("Truong_Khoa")
"""

import logging
from apps.scheduling.models import GiangVien

logger = logging.getLogger(__name__)

# Mapping các tên group có thể có (tương thích cũ + mới)
ROLE_ALIASES = {
    "truong_khoa": ["Truong_Khoa", "Trưởng Khoa", "truong_khoa"],
    "truong_bo_mon": ["Truong_Bo_Mon", "Trưởng Bộ Môn", "truong_bo_mon"],
    "giang_vien": ["Giang_Vien", "Giảng Viên", "giang_vien"],
}

def normalize_role_from_groups(groups):
    """
    Chuyển đổi danh sách groups thành role chuẩn
    
    Args:
        groups: QuerySet hoặc list tên groups
        
    Returns:
        str: 'truong_khoa' | 'truong_bo_mon' | 'giang_vien' | None
    """
    group_names = list(groups) if not isinstance(groups, list) else groups
    
    # Check theo thứ tự ưu tiên (cao nhất trước)
    for role, aliases in ROLE_ALIASES.items():
        if any(alias in group_names for alias in aliases):
            return role
    
    return None


def get_user_role_info(user):
    """
    XÁC ĐỊNH ROLE VÀ SCOPE CỦA USER - SINGLE SOURCE OF TRUTH
    
    Args:
        user: Django User object
        
    Returns:
        dict: {
            'role': str - 'admin' | 'truong_khoa' | 'truong_bo_mon' | 'giang_vien' | None
            'ma_gv': str | None - Mã giảng viên
            'ma_bo_mon': str | None - Mã bộ môn (cho trưởng bộ môn)
            'ma_khoa': str | None - Mã khoa (cho trưởng khoa)
            'giang_vien_obj': GiangVien | None - Object GiangVien đầy đủ
        }
    """
    if not user.is_authenticated:
        return {
            'role': None,
            'ma_gv': None,
            'ma_bo_mon': None,
            'ma_khoa': None,
            'giang_vien_obj': None,
        }
    
    # Superuser = admin (toàn quyền)
    if user.is_superuser:
        return {
            'role': 'admin',
            'ma_gv': None,
            'ma_bo_mon': None,
            'ma_khoa': None,
            'giang_vien_obj': None,
        }
    
    # Lấy groups của user
    groups = user.groups.values_list('name', flat=True)
    role = normalize_role_from_groups(groups)
    
    # Tìm thông tin GiangVien theo username
    giang_vien_obj = None
    ma_gv = None
    ma_bo_mon = None
    ma_khoa = None
    
    try:
        giang_vien_obj = GiangVien.objects.select_related(
            'ma_bo_mon', 
            'ma_bo_mon__ma_khoa'
        ).get(ma_gv=user.username)
        
        ma_gv = giang_vien_obj.ma_gv
        
        if giang_vien_obj.ma_bo_mon:
            ma_bo_mon = giang_vien_obj.ma_bo_mon.ma_bo_mon
            
            if giang_vien_obj.ma_bo_mon.ma_khoa:
                ma_khoa = giang_vien_obj.ma_bo_mon.ma_khoa.ma_khoa
        
        logger.debug(
            f"get_user_role_info: user={user.username}, role={role}, "
            f"ma_gv={ma_gv}, ma_khoa={ma_khoa}, ma_bo_mon={ma_bo_mon}"
        )
                
    except GiangVien.DoesNotExist:
        # User không map được GiangVien
        logger.warning(
            f"User '{user.username}' không tìm thấy GiangVien tương ứng. "
            f"Role phân quyền có thể bị giới hạn."
        )
        ma_gv = user.username  # Fallback
    
    # Nếu không có role từ group => mặc định None (KHÔNG tự động gán giang_vien)
    # => User phải được add vào group đúng để có quyền truy cập
    if role is None:
        logger.warning(
            f"User '{user.username}' không thuộc group nào được định nghĩa "
            f"(Truong_Khoa/Truong_Bo_Mon/Giang_Vien). Truy cập sẽ bị hạn chế."
        )
    
    return {
        'role': role,
        'ma_gv': ma_gv,
        'ma_bo_mon': ma_bo_mon,
        'ma_khoa': ma_khoa,
        'giang_vien_obj': giang_vien_obj,
    }


def has_admin_access(user):
    """Kiểm tra user có quyền admin không"""
    return user.is_authenticated and user.is_superuser


def has_truong_khoa_access(user):
    """Kiểm tra user có quyền trưởng khoa không"""
    if has_admin_access(user):
        return True
    role_info = get_user_role_info(user)
    return role_info['role'] == 'truong_khoa'


def has_truong_bo_mon_access(user):
    """Kiểm tra user có quyền trưởng bộ môn không"""
    if has_admin_access(user) or has_truong_khoa_access(user):
        return True
    role_info = get_user_role_info(user)
    return role_info['role'] == 'truong_bo_mon'


def can_manage_schedule(user):
    """
    Kiểm tra user có quyền quản lý lịch không
    - Admin: toàn quyền
    - Trưởng Khoa: quản lý trong khoa
    - Trưởng Bộ Môn: chỉ xem (không quản lý)
    - Giảng viên: chỉ xem của mình
    """
    if has_admin_access(user):
        return True
    if has_truong_khoa_access(user):
        return True
    return False


def can_run_scheduler(user):
    """
    Kiểm tra user có quyền chạy thuật toán xếp lịch không
    Chỉ admin mới được phép
    """
    return has_admin_access(user)
