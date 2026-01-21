#!/usr/bin/env python
"""
Script DEBUG PERMISSIONS - Kiểm tra xem user có những quyền nào
Chạy: python check_permissions.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User, Group, Permission
from apps.sap_lich.rbac import get_user_role_info

print("\n" + "="*80)
print("DEBUG PERMISSIONS - KIỂM TRA QUYỀN CỦA USER")
print("="*80)

# 1. Danh sách tất cả users
print("\n1. DANH SÁCH USER:")
print("-" * 80)
for user in User.objects.all()[:20]:  # 20 users đầu
    role_info = get_user_role_info(user)
    groups = list(user.groups.values_list('name', flat=True))
    print(f"  User: {user.username:15} | Role: {str(role_info['role']):15} | Groups: {groups}")

# 2. Danh sách tất cả groups và permissions
print("\n2. DANH SÁCH GROUPS & PERMISSIONS:")
print("-" * 80)
for group in Group.objects.all():
    perms = list(group.permissions.values_list('codename', flat=True))
    print(f"\n  Group: {group.name}")
    if perms:
        for perm in perms:
            print(f"    ✓ {perm}")
    else:
        print(f"    (Không có permissions)")

# 3. Kiểm tra permissions của một user cụ thể
print("\n3. KIỂM TRA PERMISSIONS CHI TIẾT (user=GV001):")
print("-" * 80)
try:
    user = User.objects.get(username='GV001')
    print(f"\nUser: {user.username}")
    print(f"Is Superuser: {user.is_superuser}")
    print(f"Groups: {list(user.groups.values_list('name', flat=True))}")
    
    # Kiểm tra từng permission cụ thể
    permissions_to_check = [
        'sap_lich.view_tkb',
        'sap_lich.add_tkb',
        'sap_lich.change_tkb',
        'scheduling.view_monhoc',
        'scheduling.view_giangvien',
        'sap_lich.view_nguyenvong',
        'sap_lich.add_nguyenvong',
    ]
    
    print("\nPermissions kiểm tra:")
    for perm in permissions_to_check:
        has_perm = user.has_perm(perm)
        status = "✓" if has_perm else "✗"
        print(f"  {status} {perm:40} {has_perm}")
    
    # Danh sách tất cả permissions của user
    print("\nTất cả permissions của user:")
    user_perms = user.get_all_permissions()
    if user_perms:
        for perm in sorted(user_perms):
            print(f"  ✓ {perm}")
    else:
        print(f"  (Không có permissions)")
        
except User.DoesNotExist:
    print("  User GV001 không tồn tại")

# 4. Danh sách tất cả permissions trong hệ thống
print("\n4. DANH SÁCH TẤT CẢ PERMISSIONS TRONG HỆ THỐNG:")
print("-" * 80)
for perm in Permission.objects.all().order_by('content_type', 'codename'):
    print(f"  {perm.content_type.app_label}.{perm.codename:30} | {perm.name}")

print("\n" + "="*80)
print("HƯỚNG DẪN:")
print("="*80)
print("""
1. Nếu user không có permissions: 
   - Vào Admin > Groups > Chọn group > Add permissions
   
2. Nếu permissions không xuất hiện:
   - Chạy: python manage.py makemigrations
   - Chạy: python manage.py migrate
   
3. Để gán permission cho user:
   - Cách 1: Vào Admin > Users > Chọn user > Permissions
   - Cách 2: Vào Admin > Groups > Thêm user vào group có permissions
   
4. Để test menu hiển thị:
   - Đăng nhập user
   - Kiểm tra sidebar có menu items không
   - Kiểm tra browser console xem logs không
""")
print("="*80 + "\n")
