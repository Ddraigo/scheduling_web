"""
Script kiểm tra toàn bộ hệ thống phân quyền
Kiểm tra các điểm sau:
1. Quyền group (view, add, change, delete)
2. Quyền hiển thị nút trong templates
3. Quyền truy cập views (create, update, delete)
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import Group
from apps.scheduling.models import User

def check_group_permissions():
    """Kiểm tra quyền của từng group"""
    print("=" * 80)
    print("KIỂM TRA QUYỀN CỦA CÁC GROUP")
    print("=" * 80)
    
    groups = ['Admin', 'Trưởng Khoa', 'Trưởng Bộ Môn', 'Giảng Viên']
    
    for group_name in groups:
        print(f"\n{group_name}:")
        print("-" * 40)
        try:
            group = Group.objects.get(name=group_name)
            perms = group.permissions.all()
            
            # Tách ra theo model
            khoa_perms = [p for p in perms if 'khoa' in p.codename.lower()]
            bomon_perms = [p for p in perms if 'bomon' in p.codename.lower()]
            giangvien_perms = [p for p in perms if 'giangvien' in p.codename.lower()]
            other_perms = [p for p in perms if 'khoa' not in p.codename.lower() and 'bomon' not in p.codename.lower() and 'giangvien' not in p.codename.lower()]
            
            if khoa_perms:
                print("  Khoa:")
                for p in khoa_perms:
                    print(f"    - {p.codename}")
            
            if bomon_perms:
                print("  Bộ Môn:")
                for p in bomon_perms:
                    print(f"    - {p.codename}")
            
            if giangvien_perms:
                print("  Giảng Viên:")
                for p in giangvien_perms:
                    print(f"    - {p.codename}")
            
            if other_perms:
                print("  Khác:")
                for p in other_perms:
                    print(f"    - {p.codename}")
            
        except Group.DoesNotExist:
            print(f"  ❌ Group không tồn tại")

def check_user_permissions():
    """Kiểm tra quyền của user cụ thể"""
    print("\n" + "=" * 80)
    print("KIỂM TRA QUYỀN CỦA USER")
    print("=" * 80)
    
    test_users = ['admin', 'GV001', 'GV002']
    
    for username in test_users:
        try:
            user = User.objects.get(username=username)
            print(f"\nUser: {username} ({user.get_full_name() or 'No name'})")
            print("-" * 40)
            
            groups = user.groups.all()
            print(f"Groups: {', '.join([g.name for g in groups])}")
            
            # Kiểm tra quyền cụ thể
            models_to_check = ['khoaproxy', 'bomonproxy', 'giangvienproxy', 'monhocproxy']
            
            for model in models_to_check:
                print(f"\n  {model.upper()}:")
                view_perm = user.has_perm(f'data_table.view_{model}')
                add_perm = user.has_perm(f'data_table.add_{model}')
                change_perm = user.has_perm(f'data_table.change_{model}')
                delete_perm = user.has_perm(f'data_table.delete_{model}')
                
                print(f"    View:   {'✅' if view_perm else '❌'}")
                print(f"    Add:    {'✅' if add_perm else '❌'}")
                print(f"    Change: {'✅' if change_perm else '❌'}")
                print(f"    Delete: {'✅' if delete_perm else '❌'}")
            
        except User.DoesNotExist:
            print(f"  ❌ User {username} không tồn tại")

def check_admin_permissions():
    """Kiểm tra quyền trong admin classes"""
    print("\n" + "=" * 80)
    print("KIỂM TRA QUYỀN TRONG ADMIN CLASSES")
    print("=" * 80)
    
    from django.contrib import admin
    from apps.data_table.models import KhoaProxy
    from django.test import RequestFactory
    
    factory = RequestFactory()
    
    # Test với GV001 (Trưởng Khoa)
    try:
        user = User.objects.get(username='GV001')
        request = factory.get('/admin/data_table/khoaproxy/')
        request.user = user
        
        admin_site = admin.site
        model_admin = admin_site._registry.get(KhoaProxy)
        
        if model_admin:
            print(f"\nKhoaProxy Admin với user GV001 (Trưởng Khoa):")
            print("-" * 40)
            print(f"  has_view_permission:   {'✅' if model_admin.has_view_permission(request) else '❌'}")
            print(f"  has_add_permission:    {'✅' if model_admin.has_add_permission(request) else '❌'}")
            print(f"  has_change_permission: {'✅' if model_admin.has_change_permission(request) else '❌'}")
            print(f"  has_delete_permission: {'✅' if model_admin.has_delete_permission(request) else '❌'}")
        else:
            print("  ❌ KhoaProxy không có admin class")
    except User.DoesNotExist:
        print("  ❌ User GV001 không tồn tại")

def summary():
    """Tổng kết kiểm tra"""
    print("\n" + "=" * 80)
    print("TỔNG KẾT")
    print("=" * 80)
    print("""
QUYỀN CHO TỪNG ROLE:

1. ADMIN (Superuser):
   - Toàn quyền tất cả models

2. TRƯỞNG KHOA:
   - View: Tất cả models trong khoa
   - Add/Change/Delete: Tất cả models NGOẠI TRỪ Khoa (chỉ view Khoa)

3. TRƯỞNG BỘ MÔN:
   - View: MonHoc, GiangVien, GVDayMon, NguyenVong, PhanCong, LopMonHoc
   - Add: NguyenVong
   - Change: GiangVien, NguyenVong
   - Delete: Không có

4. GIẢNG VIÊN:
   - View: NguyenVong (của mình)
   - Add/Change/Delete: NguyenVong (của mình)

NÚT TRONG TEMPLATES:
- Nút "Nhập Excel": Hiện nếu có quyền add HOẶC change
- Nút "Xuất Excel": Luôn hiện (với dữ liệu mà user có quyền view)
- Nút "Xóa đã chọn": Hiện nếu có quyền delete
- Nút "Add": Hiện nếu có quyền add
- Nút "Edit": Hiện nếu có quyền change
- Nút "Delete": Hiện nếu có quyền delete
""")

if __name__ == '__main__':
    check_group_permissions()
    check_user_permissions()
    check_admin_permissions()
    summary()
