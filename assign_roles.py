import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User, Group
from apps.scheduling.models import GiangVien

# Lấy 3 GV đầu tiên
gv_list = list(GiangVien.objects.select_related('ma_bo_mon', 'ma_bo_mon__ma_khoa').all()[:3])

print('=== GÁN ROLES CHO USERS ===\n')

# Gán Trưởng Khoa
u1 = User.objects.get(username=gv_list[0].ma_gv)
u1.groups.clear()
u1.groups.add(Group.objects.get(name='Truong_Khoa'))
khoa_name = gv_list[0].ma_bo_mon.ma_khoa.ten_khoa if gv_list[0].ma_bo_mon and gv_list[0].ma_bo_mon.ma_khoa else 'N/A'
print(f'✅ TRƯỞNG KHOA: {gv_list[0].ma_gv} - {gv_list[0].ten_gv}')
print(f'   Khoa: {khoa_name}')
print(f'   Username: {gv_list[0].ma_gv}')
print(f'   Password: 123456\n')

# Gán Trưởng Bộ Môn
u2 = User.objects.get(username=gv_list[1].ma_gv)
u2.groups.clear()
u2.groups.add(Group.objects.get(name='Truong_Bo_Mon'))
bo_mon_name = gv_list[1].ma_bo_mon.ten_bo_mon if gv_list[1].ma_bo_mon else 'N/A'
khoa_name2 = gv_list[1].ma_bo_mon.ma_khoa.ten_khoa if gv_list[1].ma_bo_mon and gv_list[1].ma_bo_mon.ma_khoa else 'N/A'
print(f'✅ TRƯỞNG BỘ MÔN: {gv_list[1].ma_gv} - {gv_list[1].ten_gv}')
print(f'   Khoa: {khoa_name2}')
print(f'   Bộ môn: {bo_mon_name}')
print(f'   Username: {gv_list[1].ma_gv}')
print(f'   Password: 123456\n')

# Gán Giáo Viên
u3 = User.objects.get(username=gv_list[2].ma_gv)
u3.groups.clear()
u3.groups.add(Group.objects.get(name='Giang_Vien'))
print(f'✅ GIÁO VIÊN: {gv_list[2].ma_gv} - {gv_list[2].ten_gv}')
print(f'   Username: {gv_list[2].ma_gv}')
print(f'   Password: 123456\n')

print('=== HOÀN THÀNH ===')
print('\n📝 Hãy đăng nhập với các tài khoản trên để kiểm tra phân quyền!')
