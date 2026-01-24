import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import Group

print("=" * 60)
print("GIẢNG VIÊN GROUP PERMISSIONS")
print("=" * 60)

try:
    group = Group.objects.get(name='Giảng Viên')
    print(f'\nGroup: {group.name}')
    perms = group.permissions.all()
    
    print(f'\nSap Lich permissions:')
    sap_lich_perms = [p for p in perms if p.content_type.app_label == 'sap_lich']
    if sap_lich_perms:
        for perm in sap_lich_perms:
            print(f'  - {perm.content_type.app_label}.{perm.codename}')
    else:
        print('  (No sap_lich permissions)')
    
    print(f'\nAll permissions count: {perms.count()}')
    
except Group.DoesNotExist:
    print('Group "Giảng Viên" does not exist')
