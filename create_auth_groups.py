"""
Script tạo Auth Groups và Users mẫu cho hệ thống phân quyền TKB
Chạy: python manage.py shell < create_auth_groups.py
"""

from django.contrib.auth.models import User, Group
from apps.scheduling.models import GiangVien

print("=" * 60)
print("BẮT ĐẦU TẠO AUTH GROUPS VÀ USERS MẪU")
print("=" * 60)

# 1. Tạo Groups
print("\n1. Tạo Auth Groups...")
groups_data = ['Truong_Khoa', 'Truong_Bo_Mon', 'Giang_Vien']
for group_name in groups_data:
    group, created = Group.objects.get_or_create(name=group_name)
    if created:
        print(f"  ✅ Tạo group mới: {group_name}")
    else:
        print(f"  ℹ️  Group đã tồn tại: {group_name}")

# 2. Lấy danh sách giảng viên có sẵn
print("\n2. Lấy danh sách giảng viên có sẵn trong DB...")
giang_vien_list = GiangVien.objects.select_related('ma_bo_mon', 'ma_bo_mon__ma_khoa').all()[:10]
print(f"  Tìm thấy {giang_vien_list.count()} giảng viên")

if not giang_vien_list.exists():
    print("  ⚠️  Không tìm thấy giảng viên nào trong database!")
    print("  ⚠️  Vui lòng thêm dữ liệu giảng viên trước khi chạy script này")
    exit(1)

# 3. Tạo users cho các giảng viên
print("\n3. Tạo users cho giảng viên...")
created_count = 0
exists_count = 0

for gv in giang_vien_list:
    username = gv.ma_gv
    
    # Kiểm tra user đã tồn tại chưa
    if User.objects.filter(username=username).exists():
        exists_count += 1
        print(f"  ℹ️  User đã tồn tại: {username} - {gv.ten_gv}")
        continue
    
    # Tạo user mới
    try:
        user = User.objects.create_user(
            username=username,
            password='123456',  # Password mặc định - NÊN ĐỔI SAU!
            email=f'{username}@university.edu.vn',
            first_name=gv.ten_gv.split()[-1] if gv.ten_gv else '',
            last_name=' '.join(gv.ten_gv.split()[:-1]) if gv.ten_gv else ''
        )
        
        # Gán group mặc định là Giang_Vien
        giang_vien_group = Group.objects.get(name='Giang_Vien')
        user.groups.add(giang_vien_group)
        
        created_count += 1
        
        # Hiển thị thông tin
        khoa_name = gv.ma_bo_mon.ma_khoa.ten_khoa if gv.ma_bo_mon and gv.ma_bo_mon.ma_khoa else 'N/A'
        bo_mon_name = gv.ma_bo_mon.ten_bo_mon if gv.ma_bo_mon else 'N/A'
        
        print(f"  ✅ Tạo user: {username} - {gv.ten_gv}")
        print(f"     Khoa: {khoa_name}")
        print(f"     Bộ môn: {bo_mon_name}")
        print(f"     Group: Giang_Vien")
        print(f"     Password: 123456 (NÊN ĐỔI NGAY!)")
        
    except Exception as e:
        print(f"  ❌ Lỗi khi tạo user {username}: {str(e)}")

print(f"\n📊 Tóm tắt:")
print(f"  - Users mới: {created_count}")
print(f"  - Users đã tồn tại: {exists_count}")

# 4. Hiển thị hướng dẫn tạo Trưởng Khoa và Trưởng Bộ Môn
print("\n" + "=" * 60)
print("4. HƯỚNG DẪN TẠO TRƯỞNG KHOA VÀ TRƯỞNG BỘ MÔN")
print("=" * 60)

print("\nĐể gán quyền Trưởng Khoa hoặc Trưởng Bộ Môn, chạy lệnh sau:")
print("\nVí dụ - Gán quyền Trưởng Khoa cho user GV001:")
print("  python manage.py shell")
print("  >>> from django.contrib.auth.models import User, Group")
print("  >>> user = User.objects.get(username='GV001')")
print("  >>> user.groups.clear()  # Xóa groups cũ")
print("  >>> truong_khoa_group = Group.objects.get(name='Truong_Khoa')")
print("  >>> user.groups.add(truong_khoa_group)")
print("  >>> print('Đã gán quyền Trưởng Khoa cho', user.username)")

print("\nVí dụ - Gán quyền Trưởng Bộ Môn cho user GV002:")
print("  >>> user = User.objects.get(username='GV002')")
print("  >>> user.groups.clear()")
print("  >>> truong_bo_mon_group = Group.objects.get(name='Truong_Bo_Mon')")
print("  >>> user.groups.add(truong_bo_mon_group)")
print("  >>> print('Đã gán quyền Trưởng Bộ Môn cho', user.username)")

# 5. Tạo 1 user mẫu cho mỗi role (nếu có đủ giảng viên)
print("\n" + "=" * 60)
print("5. TẠO USERS MẪU CHO CÁC ROLE")
print("=" * 60)

# Lấy 3 giảng viên đầu tiên làm mẫu
sample_gv = list(giang_vien_list[:3])

if len(sample_gv) >= 3:
    # Gán Trưởng Khoa
    try:
        gv_truong_khoa = sample_gv[0]
        user_tk = User.objects.get(username=gv_truong_khoa.ma_gv)
        user_tk.groups.clear()
        user_tk.groups.add(Group.objects.get(name='Truong_Khoa'))
        khoa_name = gv_truong_khoa.ma_bo_mon.ma_khoa.ten_khoa if gv_truong_khoa.ma_bo_mon and gv_truong_khoa.ma_bo_mon.ma_khoa else 'N/A'
        print(f"\n✅ Trưởng Khoa: {gv_truong_khoa.ma_gv} - {gv_truong_khoa.ten_gv}")
        print(f"   Khoa: {khoa_name}")
        print(f"   Username: {gv_truong_khoa.ma_gv}")
        print(f"   Password: 123456")
    except Exception as e:
        print(f"\n❌ Lỗi khi tạo Trưởng Khoa: {e}")
    
    # Gán Trưởng Bộ Môn
    try:
        gv_truong_bm = sample_gv[1]
        user_tbm = User.objects.get(username=gv_truong_bm.ma_gv)
        user_tbm.groups.clear()
        user_tbm.groups.add(Group.objects.get(name='Truong_Bo_Mon'))
        bo_mon_name = gv_truong_bm.ma_bo_mon.ten_bo_mon if gv_truong_bm.ma_bo_mon else 'N/A'
        print(f"\n✅ Trưởng Bộ Môn: {gv_truong_bm.ma_gv} - {gv_truong_bm.ten_gv}")
        print(f"   Bộ môn: {bo_mon_name}")
        print(f"   Username: {gv_truong_bm.ma_gv}")
        print(f"   Password: 123456")
    except Exception as e:
        print(f"\n❌ Lỗi khi tạo Trưởng Bộ Môn: {e}")
    
    # Giữ nguyên Giáo Viên
    try:
        gv_thuong = sample_gv[2]
        user_gv = User.objects.get(username=gv_thuong.ma_gv)
        # Đảm bảo có group Giang_Vien
        if not user_gv.groups.filter(name='Giang_Vien').exists():
            user_gv.groups.add(Group.objects.get(name='Giang_Vien'))
        print(f"\n✅ Giáo Viên: {gv_thuong.ma_gv} - {gv_thuong.ten_gv}")
        print(f"   Username: {gv_thuong.ma_gv}")
        print(f"   Password: 123456")
    except Exception as e:
        print(f"\n❌ Lỗi khi tạo Giáo Viên: {e}")

print("\n" + "=" * 60)
print("HOÀN THÀNH!")
print("=" * 60)
print("\n⚠️  LƯU Ý QUAN TRỌNG:")
print("1. Tất cả users được tạo với password mặc định: 123456")
print("2. NÊN ĐỔI PASSWORD NGAY sau khi đăng nhập lần đầu!")
print("3. Superuser (admin) vẫn có toàn quyền truy cập")
print("4. Đăng nhập Django Admin để quản lý users và groups")
print("\n📝 Kiểm tra phân quyền:")
print("   - Đăng nhập với các tài khoản vừa tạo")
print("   - Truy cập /admin/sap_lich/thoikhoabieu/")
print("   - Kiểm tra xem dữ liệu hiển thị có đúng phạm vi quyền")
print("\n" + "=" * 60)
