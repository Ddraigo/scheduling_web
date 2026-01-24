import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import Group

print("=" * 60)
print("KHOA PERMISSIONS FOR TRƯỞNG KHOA")
print("=" * 60)

group = Group.objects.get(name='Trưởng Khoa')
perms = [p for p in group.permissions.all() if 'khoa' in p.codename.lower()]
print('\nPermissions có chứa "khoa":')
for p in perms:
    print(f'  - {p.content_type.app_label}.{p.codename}')

# Check specific
print('\n\nKiểm tra cụ thể KhoaProxy:')
print(f'  view_khoaproxy: {group.permissions.filter(codename="view_khoaproxy").exists()}')
print(f'  add_khoaproxy: {group.permissions.filter(codename="add_khoaproxy").exists()}')
print(f'  change_khoaproxy: {group.permissions.filter(codename="change_khoaproxy").exists()}')
print(f'  delete_khoaproxy: {group.permissions.filter(codename="delete_khoaproxy").exists()}')
