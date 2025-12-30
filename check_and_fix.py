import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User

print('=== KIỂM TRA VÀ SỬA LẠI ===\n')

# Kiểm tra users
for username in ['GV001', 'GV002', 'GV003']:
    try:
        user = User.objects.get(username=username)
        print(f'{username}:')
        print(f'  is_superuser: {user.is_superuser}')
        print(f'  is_staff: {user.is_staff}')
        print(f'  groups: {list(user.groups.values_list("name", flat=True))}')
        
        # Đảm bảo KHÔNG phải superuser
        if user.is_superuser:
            user.is_superuser = False
            user.save()
            print(f'  ✅ Đã sửa: is_superuser = False')
        print()
    except User.DoesNotExist:
        print(f'{username}: KHÔNG TỒN TẠI!\n')

print('\n=== LINKS ĐỂ TEST PHÂN QUYỀN ===')
print('\n📌 QUAN TRỌNG: Phải vào link này, KHÔNG phải admin/scheduling/thoikhoabieu/')
print('\n✅ Link đúng để test:')
print('   http://127.0.0.1:8000/admin/sap_lich/thoikhoabieu/')
print('\n❌ Link SAI (Django admin mặc định):')
print('   http://127.0.0.1:8000/admin/scheduling/thoikhoabieu/')
print('\nCustom view có phân quyền nằm ở /admin/sap_lich/thoikhoabieu/')
