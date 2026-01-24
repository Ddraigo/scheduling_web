"""
Migration Script: Update existing users từ group cũ (có dấu) sang group mới (không dấu)

CONTEXT:
- Cũ: "Trưởng Khoa", "Trưởng Bộ Môn", "Giảng Viên" (có dấu)
- Mới: "Truong_Khoa", "Truong_Bo_Mon", "Giang_Vien" (không dấu, chuẩn)

CHỨC NĂNG:
1. Migrate users từ group cũ sang group mới
2. Giữ lại cả 2 groups để tương thích
3. Báo cáo chi tiết quá trình migrate

USAGE:
    python manage.py migrate_user_groups
    
HOẶC chạy trong Django shell:
    python manage.py shell
    >>> exec(open('apps/sap_lich/management/commands/migrate_user_groups.py').read())
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.db import transaction


class Command(BaseCommand):
    help = 'Migrate users từ group cũ (có dấu) sang group mới (không dấu)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== MIGRATE USER GROUPS ===\n'))
        
        # Mapping old -> new
        migrations = [
            ('Trưởng Khoa', 'Truong_Khoa'),
            ('Trưởng Bộ Môn', 'Truong_Bo_Mon'),
            ('Giảng Viên', 'Giang_Vien'),
        ]
        
        total_migrated = 0
        
        with transaction.atomic():
            for old_name, new_name in migrations:
                self.stdout.write(f'\n🔄 Migrate: "{old_name}" → "{new_name}"')
                
                try:
                    old_group = Group.objects.get(name=old_name)
                    new_group, created = Group.objects.get_or_create(name=new_name)
                    
                    if created:
                        self.stdout.write(self.style.SUCCESS(f'  ✓ Tạo group mới: {new_name}'))
                    
                    # Get users in old group
                    users = old_group.user_set.all()
                    count = users.count()
                    
                    if count == 0:
                        self.stdout.write(f'  - Không có user nào trong group "{old_name}"')
                        continue
                    
                    # Migrate users
                    for user in users:
                        # Add to new group
                        user.groups.add(new_group)
                        # Keep in old group (để tương thích)
                        # Không remove khỏi old group
                        self.stdout.write(f'    ✓ {user.username} -> {new_name}')
                    
                    total_migrated += count
                    self.stdout.write(self.style.SUCCESS(f'  ✅ Migrate {count} users'))
                    
                except Group.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'  ⚠ Group "{old_name}" không tồn tại'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ✗ Lỗi: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ HOÀN TẤT! Migrate {total_migrated} users tổng cộng.\n'))
        
        # Report summary
        self.stdout.write(' SUMMARY:')
        for migration in migrations:
            old_name, new_name = migration
            try:
                old_group = Group.objects.get(name=old_name)
                new_group = Group.objects.get(name=new_name)
                self.stdout.write(f'  {old_name}: {old_group.user_set.count()} users')
                self.stdout.write(f'  {new_name}: {new_group.user_set.count()} users')
            except Group.DoesNotExist:
                pass
        
        self.stdout.write('\n📝 LƯU Ý:')
        self.stdout.write('  - Users được add vào group mới nhưng vẫn giữ trong group cũ')
        self.stdout.write('  - Cả 2 groups đều có permissions giống nhau')
        self.stdout.write('  - RBAC module hỗ trợ cả 2 tên group (cũ + mới)\n')


# Standalone function để chạy trực tiếp
def migrate_users_standalone():
    """
    Chạy trực tiếp trong Django shell:
    >>> from apps.sap_lich.management.commands.migrate_user_groups import migrate_users_standalone
    >>> migrate_users_standalone()
    """
    from django.contrib.auth.models import User, Group
    
    migrations = [
        ('Trưởng Khoa', 'Truong_Khoa'),
        ('Trưởng Bộ Môn', 'Truong_Bo_Mon'),
        ('Giảng Viên', 'Giang_Vien'),
    ]
    
    for old_name, new_name in migrations:
        try:
            old_group = Group.objects.get(name=old_name)
            new_group, _ = Group.objects.get_or_create(name=new_name)
            
            users = old_group.user_set.all()
            for user in users:
                user.groups.add(new_group)
                print(f'✓ {user.username}: {old_name} -> {new_name}')
            
            print(f'✅ Migrate {users.count()} users từ "{old_name}" sang "{new_name}"')
        except Group.DoesNotExist:
            print(f'⚠ Group "{old_name}" không tồn tại')
