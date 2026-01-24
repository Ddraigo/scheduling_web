import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import Group, Permission

print("=" * 60)
print("TRƯỞNG KHOA PERMISSIONS")
print("=" * 60)

try:
    group = Group.objects.get(name='Trưởng Khoa')
    print(f'\nGroup: {group.name}')
    
    # Lọc permissions theo app
    print(f'\nScheduling permissions:')
    scheduling_perms = [p for p in group.permissions.all() if p.content_type.app_label == 'scheduling']
    for perm in scheduling_perms:
        print(f'  - {perm.content_type.app_label}.{perm.codename}')
    
    print(f'\nSap Lich permissions:')
    sap_lich_perms = [p for p in group.permissions.all() if p.content_type.app_label == 'sap_lich']
    for perm in sap_lich_perms:
        print(f'  - {perm.content_type.app_label}.{perm.codename}')
    
    print(f'\nData Table permissions:')
    data_table_perms = [p for p in group.permissions.all() if p.content_type.app_label == 'data_table']
    for perm in data_table_perms:
        print(f'  - {perm.content_type.app_label}.{perm.codename}')
    
    # Check specific permissions
    print(f'\n\nKiểm tra permissions cụ thể:')
    print(f'  add_thoikhoabieu: {group.permissions.filter(codename="add_thoikhoabieu").exists()}')
    print(f'  change_thoikhoabieu: {group.permissions.filter(codename="change_thoikhoabieu").exists()}')
    print(f'  delete_thoikhoabieu: {group.permissions.filter(codename="delete_thoikhoabieu").exists()}')
    print(f'  view_thoikhoabieu: {group.permissions.filter(codename="view_thoikhoabieu").exists()}')
    
except Group.DoesNotExist:
    print('Group "Trưởng Khoa" does not exist')
