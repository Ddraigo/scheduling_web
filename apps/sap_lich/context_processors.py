"""
Context processor để cung cấp thông tin role và menu cho template
"""

def user_role_context(request):
    """
    Thêm thông tin role và menu vào context
    """
    if not request.user.is_authenticated:
        return {
            'user_role': None,
            'is_admin': False,
            'is_truong_khoa': False,
            'is_truong_bo_mon': False,
            'is_giang_vien': False,
            'available_menus': []
        }
    
    user = request.user
    
    # Kiểm tra superuser/admin
    is_admin = user.is_superuser
    
    # Kiểm tra groups
    groups = user.groups.values_list('name', flat=True)
    is_truong_khoa = 'Truong_Khoa' in groups
    is_truong_bo_mon = 'Truong_Bo_Mon' in groups
    is_giang_vien = 'Giang_Vien' in groups
    
    # Xác định role chính
    if is_admin:
        user_role = 'admin'
    elif is_truong_khoa:
        user_role = 'truong_khoa'
    elif is_truong_bo_mon:
        user_role = 'truong_bo_mon'
    else:
        user_role = 'giang_vien'
    
    # Định nghĩa menu cho từng role
    menus = {
        'admin': [
            'algo_scheduler',
            'llm_scheduler',
            'view_schedule',
            'manage_schedule',
            'all_models',  # Admin thấy tất cả models
        ],
        'truong_khoa': [
            'algo_scheduler',
            'llm_scheduler',
            'view_schedule',
            'manage_schedule',
            'models_khoa',  # Chỉ thấy models liên quan khoa
        ],
        'truong_bo_mon': [
            'view_schedule',
            'models_bo_mon',  # Chỉ thấy models liên quan bộ môn
        ],
        'giang_vien': [
            'view_schedule',  # Chỉ xem TKB của mình
        ]
    }
    
    available_menus = menus.get(user_role, [])
    
    return {
        'user_role': user_role,
        'is_admin': is_admin,
        'is_truong_khoa': is_truong_khoa,
        'is_truong_bo_mon': is_truong_bo_mon,
        'is_giang_vien': is_giang_vien,
        'available_menus': available_menus,
    }
