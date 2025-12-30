from django.contrib.auth.models import User, Group
from apps.scheduling.models import GiangVien

# Tạo users cho 10 GV đầu tiên
gv_list = GiangVien.objects.select_related('ma_bo_mon', 'ma_bo_mon__ma_khoa').all()[:10]
giang_vien_group = Group.objects.get(name='Giang_Vien')
truong_khoa_group = Group.objects.get(name='Truong_Khoa')
truong_bo_mon_group = Group.objects.get(name='Truong_Bo_Mon')

print(f"Tìm thấy {len(gv_list)} giảng viên")

created = 0
for idx, gv in enumerate(gv_list):
    if not User.objects.filter(username=gv.ma_gv).exists():
        user = User.objects.create_user(
            username=gv.ma_gv,
            password='123456',
            email=f'{gv.ma_gv}@university.edu.vn'
        )
        
        # GV đầu tiên là Trưởng Khoa
        if idx == 0:
            user.groups.add(truong_khoa_group)
            print(f"✅ Trưởng Khoa: {gv.ma_gv} - {gv.ten_gv} (Khoa: {gv.ma_bo_mon.ma_khoa.ten_khoa if gv.ma_bo_mon and gv.ma_bo_mon.ma_khoa else 'N/A'})")
        # GV thứ 2 là Trưởng Bộ Môn
        elif idx == 1:
            user.groups.add(truong_bo_mon_group)
            print(f"✅ Trưởng Bộ Môn: {gv.ma_gv} - {gv.ten_gv} (Bộ môn: {gv.ma_bo_mon.ten_bo_mon if gv.ma_bo_mon else 'N/A'})")
        # Các GV còn lại là Giáo viên thường
        else:
            user.groups.add(giang_vien_group)
            print(f"✅ Giáo viên: {gv.ma_gv} - {gv.ten_gv}")
        
        created += 1
    else:
        print(f"ℹ️  User đã tồn tại: {gv.ma_gv}")

print(f"\n✅ Tạo thành công {created} users")
print("\n📝 Thông tin đăng nhập:")
print("  Username: [ma_gv]")
print("  Password: 123456")
