import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User, Group

# Check user GV001
print("=" * 60)
print("USER GV001 INFORMATION")
print("=" * 60)
user = User.objects.get(username='GV001')
print(f'Username: {user.username}')
print(f'Groups: {list(user.groups.values_list("name", flat=True))}')
print(f'Is superuser: {user.is_superuser}')
print()

# Check permissions
print("PERMISSIONS CHECK:")
print(f'  view_saplich: {user.has_perm("sap_lich.view_saplich")}')
print(f'  change_saplich: {user.has_perm("sap_lich.change_saplich")}')
print(f'  add_saplich: {user.has_perm("sap_lich.add_saplich")}')
print(f'  view_monhoc: {user.has_perm("scheduling.view_monhoc")}')
print(f'  view_giangvien: {user.has_perm("scheduling.view_giangvien")}')
print()

print("ALL PERMISSIONS:")
all_perms = sorted(user.get_all_permissions())
if all_perms:
    for perm in all_perms:
        print(f'  - {perm}')
else:
    print('  (No permissions)')
print()

# Check groups
print("=" * 60)
print("GROUP INFORMATION")
print("=" * 60)
for group_name in ['Truong_Khoa', 'Trưởng Khoa', 'Truong_Bo_Mon', 'Trưởng Bộ Môn']:
    try:
        group = Group.objects.get(name=group_name)
        print(f'\nGroup: {group.name}')
        perms = group.permissions.all()
        if perms:
            for perm in perms:
                print(f'  - {perm.content_type.app_label}.{perm.codename}')
        else:
            print('  (No permissions)')
    except Group.DoesNotExist:
        print(f'\nGroup "{group_name}" does not exist')
