import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

cursor = connection.cursor()

# Xóa migration record của scheduling.0005
cursor.execute("""
    DELETE FROM django_migrations 
    WHERE app = 'scheduling' AND name = '0005_tkblog_thoikhoabieu_is_deleted_alter_bomon_ma_bo_mon_and_more'
""")

print("✓ Đã xóa migration record 0005 của scheduling")
print("Bây giờ chạy: python manage.py migrate scheduling")
