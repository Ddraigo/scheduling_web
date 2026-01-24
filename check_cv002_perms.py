import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User

user = User.objects.get(username='GV002')
print(f'User: {user.username}')
print(f'Groups: {[g.name for g in user.groups.all()]}')
print(f'view_saplich: {user.has_perm("sap_lich.view_saplich")}')
print(f'change_saplich: {user.has_perm("sap_lich.change_saplich")}')
print(f'add_saplich: {user.has_perm("sap_lich.add_saplich")}')
print(f'view_monhoc: {user.has_perm("scheduling.view_monhoc")}')
print(f'view_giangvien: {user.has_perm("scheduling.view_giangvien")}')
print('\nAll permissions:')
for perm in sorted(user.get_all_permissions()):
    print(f'  - {perm}')
