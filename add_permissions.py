import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from apps.scheduling.models import (
    ThoiKhoaBieu, LopMonHoc, GiangVien, PhongHoc, 
    MonHoc, Khoa, BoMon, PhanCong, DotXep, TimeSlot
)

print('=== THÊM PERMISSIONS CHO USERS ===\n')

# Lấy tất cả permissions liên quan
models = [ThoiKhoaBieu, LopMonHoc, GiangVien, PhongHoc, MonHoc, 
          Khoa, BoMon, PhanCong, DotXep, TimeSlot]

view_perms = []
change_perms = []
add_perms = []
delete_perms = []

for model in models:
    ct = ContentType.objects.get_for_model(model)
    view_perms.extend(Permission.objects.filter(content_type=ct, codename__startswith='view_'))
    change_perms.extend(Permission.objects.filter(content_type=ct, codename__startswith='change_'))
    add_perms.extend(Permission.objects.filter(content_type=ct, codename__startswith='add_'))
    delete_perms.extend(Permission.objects.filter(content_type=ct, codename__startswith='delete_'))

print(f'Tìm thấy {len(view_perms)} view permissions')
print(f'Tìm thấy {len(change_perms)} change permissions')
print(f'Tìm thấy {len(add_perms)} add permissions')
print(f'Tìm thấy {len(delete_perms)} delete permissions\n')

# 1. Trưởng Khoa - Full permissions
user_tk = User.objects.get(username='GV001')
user_tk.user_permissions.clear()
user_tk.user_permissions.add(*view_perms)
user_tk.user_permissions.add(*change_perms)
user_tk.user_permissions.add(*add_perms)
user_tk.user_permissions.add(*delete_perms)
print(f'✅ GV001 (Trưởng Khoa): Full permissions')

# 2. Trưởng Bộ Môn - Full permissions
user_tbm = User.objects.get(username='GV002')
user_tbm.user_permissions.clear()
user_tbm.user_permissions.add(*view_perms)
user_tbm.user_permissions.add(*change_perms)
user_tbm.user_permissions.add(*add_perms)
user_tbm.user_permissions.add(*delete_perms)
print(f'✅ GV002 (Trưởng Bộ Môn): Full permissions')

# 3. Giáo Viên - Chỉ view
user_gv = User.objects.get(username='GV003')
user_gv.user_permissions.clear()
user_gv.user_permissions.add(*view_perms)
print(f'✅ GV003 (Giáo Viên): View only')

# 4. Các GV khác - View only
for username in ['GV004', 'GV005', 'GV006', 'GV007', 'GV008', 'GV009', 'GV0049']:
    try:
        user = User.objects.get(username=username)
        user.user_permissions.clear()
        user.user_permissions.add(*view_perms)
        print(f'✅ {username}: View only')
    except User.DoesNotExist:
        pass

print('\n=== HOÀN THÀNH ===')
print('\n📝 Giờ đăng nhập lại sẽ thấy menu "Sắp lịch" với:')
print('  - Trưởng Khoa (GV001): Xem/Thêm/Sửa/Xóa tất cả')
print('  - Trưởng Bộ Môn (GV002): Xem/Thêm/Sửa/Xóa tất cả')
print('  - Giáo Viên (GV003): Chỉ xem')
