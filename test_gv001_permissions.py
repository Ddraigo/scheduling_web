import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User

print("=" * 60)
print("USER GV001 (TRƯỞNG KHOA) - KIỂM TRA QUYỀN")
print("=" * 60)

try:
    user = User.objects.get(username='GV001')
    print(f'\nUsername: {user.username}')
    print(f'Groups: {list(user.groups.values_list("name", flat=True))}')
    print(f'Is superuser: {user.is_superuser}')
    
    # Kiểm tra permissions cụ thể
    print(f'\n\nKIỂM TRA QUYỀN THÊM/XÓA/SỬA:')
    print(f'  scheduling.add_thoikhoabieu: {user.has_perm("scheduling.add_thoikhoabieu")}')
    print(f'  scheduling.change_thoikhoabieu: {user.has_perm("scheduling.change_thoikhoabieu")}')
    print(f'  scheduling.delete_thoikhoabieu: {user.has_perm("scheduling.delete_thoikhoabieu")}')
    print(f'  scheduling.view_thoikhoabieu: {user.has_perm("scheduling.view_thoikhoabieu")}')
    
    print(f'\n  data_table.add_giangvienproxy: {user.has_perm("data_table.add_giangvienproxy")}')
    print(f'  data_table.change_giangvienproxy: {user.has_perm("data_table.change_giangvienproxy")}')
    print(f'  data_table.delete_giangvienproxy: {user.has_perm("data_table.delete_giangvienproxy")}')
    
    print(f'\n  data_table.add_bomonproxy: {user.has_perm("data_table.add_bomonproxy")}')
    print(f'  data_table.change_bomonproxy: {user.has_perm("data_table.change_bomonproxy")}')
    print(f'  data_table.delete_bomonproxy: {user.has_perm("data_table.delete_bomonproxy")}')
    
    print(f'\n  sap_lich.add_saplich: {user.has_perm("sap_lich.add_saplich")}')
    print(f'  sap_lich.change_saplich: {user.has_perm("sap_lich.change_saplich")}')
    
    # Test với admin request
    from django.test import RequestFactory
    from apps.sap_lich.rbac import get_user_role_info
    
    factory = RequestFactory()
    request = factory.get('/')
    request.user = user
    
    role_info = get_user_role_info(user)
    print(f'\n\nROLE INFO:')
    print(f'  role: {role_info["role"]}')
    print(f'  ma_khoa: {role_info["ma_khoa"]}')
    print(f'  ma_bo_mon: {role_info["ma_bo_mon"]}')
    print(f'  ma_gv: {role_info["ma_gv"]}')
    
except User.DoesNotExist:
    print('User GV001 không tồn tại')
except Exception as e:
    print(f'Lỗi: {e}')
    import traceback
    traceback.print_exc()
