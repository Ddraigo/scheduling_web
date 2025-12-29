#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        print("✅ KẾT NỐI THÀNH CÔNG!")
        print(f"📌 Database: {connection.settings_dict['NAME']}")
        print(f"📌 Host: {connection.settings_dict['HOST']}")
        print(f"📌 SQL Server Version:\n{version[:100]}...")
        
        # Kiểm tra số lượng bảng
        cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'")
        table_count = cursor.fetchone()[0]
        print(f"📌 Số bảng trong database: {table_count}")
        
except Exception as e:
    print("❌ KẾT NỐI THẤT BẠI!")
    print(f"Lỗi: {e}")
