#  Quick Start Guide - Testing Scheduling App

## Bước 1: Kiểm tra cài đặt

```bash
# Check Python version
python --version  # Should be 3.8+

# Check Django
python -c "import django; print(django.VERSION)"
```

## Bước 2: Install dependencies

```bash
# Install/Update packages
pip install -r requirements.txt

# Verify key packages
pip show djangorestframework django-filter google-genai
```

## Bước 3: Database Migrations

```bash
# Tạo migrations cho scheduling app
python manage.py makemigrations scheduling

# Apply migrations
python manage.py migrate

# Check migration status
python manage.py showmigrations scheduling
```

## Bước 4: Create Superuser

```bash
# Create admin user
python manage.py createsuperuser

# Username: admin
# Email: admin@gmail.com  
# Password: [your_password]
```

## Bước 5: Run Development Server

```bash
# Start server
python manage.py runserver

# Server should start at: http://localhost:8000/
```

## Bước 6: Test Django Admin

1. Open browser: **http://localhost:8000/admin/**
2. Login with superuser credentials
3. You should see these sections:
   - **SCHEDULING SYSTEM** section with:
     - Khoa
     - Bộ môn
     - Giảng viên
     - Môn học
     - Phòng học
     - Lớp môn học
     - Đợt xếp lịch
     - Phân công
     - Time Slots
     - Thời khóa biểu

## Bước 7: Test REST API

### Via Browser (DRF Browsable API)

1. **Master Data APIs:**
   - http://localhost:8000/scheduling/khoa/
   - http://localhost:8000/scheduling/giang-vien/
   - http://localhost:8000/scheduling/mon-hoc/
   - http://localhost:8000/scheduling/phong-hoc/

2. **Scheduling APIs:**
   - http://localhost:8000/scheduling/dot-xep/
   - http://localhost:8000/scheduling/phan-cong/
   - http://localhost:8000/scheduling/thoi-khoa-bieu/

### Via cURL/Postman

```bash
# Get API token first
curl -X POST http://localhost:8000/login/jwt/ \
  -d "username=admin&password=your_password"

# Use token in requests
curl -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:8000/scheduling/giang-vien/
```

## Bước 8: Create Test Data (Optional)

```bash
python manage.py shell
```

```python
from apps.scheduling.models import *
from datetime import date, time

# Create Khoa
khoa = Khoa.objects.create(
    ma_khoa='CNTT',
    ten_khoa='Công Nghệ Thông Tin'
)

# Create BoMon
bo_mon = BoMon.objects.create(
    ma_bo_mon='HTTT',
    ten_bo_mon='Hệ Thống Thông Tin',
    khoa=khoa
)

# Create GiangVien
gv = GiangVien.objects.create(
    ma_gv='GV001',
    ten_gv='Nguyễn Văn A',
    email='nguyenvana@example.com',
    bo_mon=bo_mon
)

# Create MonHoc
mon_hoc = MonHoc.objects.create(
    ma_mon_hoc='CS101',
    ten_mon_hoc='Lập trình cơ bản',
    so_tin_chi=3,
    so_tiet_lt=30,
    so_tiet_th=15,
    so_tiet_tong=45
)

# Create PhongHoc
phong = PhongHoc.objects.create(
    ma_phong='A101',
    ten_phong='Phòng A101',
    suc_chua=50,
    loai_phong='LT'
)

# Create TimeSlot
ts = TimeSlot.objects.create(
    ma_time_slot='TS_T2_C1',
    thu=2,
    tiet_bat_dau=1,
    so_tiet=3,
    gio_bat_dau=time(7, 0),
    gio_ket_thuc=time(9, 30)
)

# Create DotXep
dot_xep = DotXep.objects.create(
    ma_dot='2025-2026_HK1',
    ten_dot='Học kỳ 1 năm học 2025-2026',
    nam_hoc='2025-2026',
    hoc_ky='HK1',
    ngay_bat_dau=date(2025, 9, 1),
    ngay_ket_thuc=date(2026, 1, 31),
    trang_thai='CHUA_XEP'
)

print("✅ Test data created successfully!")
```

## Bước 9: Test Schedule Generation

### Via Management Command

```bash
# Generate schedule using AI
python manage.py generate_schedule --period 2025-2026_HK1

# Generate schedule using greedy algorithm
python manage.py generate_schedule --period 2025-2026_HK1 --greedy
```

### Via API

```python
import requests

# Login to get token
response = requests.post('http://localhost:8000/login/jwt/', {
    'username': 'admin',
    'password': 'your_password'
})
token = response.json()['token']

# Generate schedule
response = requests.post(
    'http://localhost:8000/scheduling/schedule-generation/generate/',
    json={
        'ma_dot': '2025-2026_HK1',
        'use_ai': True
    },
    headers={'Authorization': f'Token {token}'}
)

print(response.json())
```

## Bước 10: Verify Structure

```bash
# Check app structure
python manage.py check scheduling

# Verify models
python manage.py shell -c "from apps.scheduling.models import *; print('✅ Models imported successfully')"

# Verify services
python manage.py shell -c "from apps.scheduling.services.schedule_service import ScheduleService; print('✅ Services imported successfully')"
```

## 🔧 Troubleshooting

### Problem: ModuleNotFoundError

```bash
# Solution: Install missing package
pip install <package_name>

# Or reinstall all
pip install -r requirements.txt --force-reinstall
```

### Problem: Migration errors

```bash
# Reset migrations
python manage.py migrate scheduling zero
rm apps/scheduling/migrations/00*.py

# Recreate
python manage.py makemigrations scheduling
python manage.py migrate
```

### Problem: Import errors

```bash
# Check PYTHONPATH
python -c "import sys; print('\n'.join(sys.path))"

# Verify apps.scheduling exists
python -c "import apps.scheduling; print(apps.scheduling.__file__)"
```

### Problem: No module named 'google.genai'

```bash
# Install Google Generative AI
pip install google-genai

# Set API key in .env
GEMINI_API_KEY=your_api_key_here
```

## ✅ Success Checklist

- [ ] Server starts without errors
- [ ] Django Admin accessible at /admin/
- [ ] Scheduling section visible in admin
- [ ] REST API accessible at /scheduling/
- [ ] Can browse DRF API interface
- [ ] Models can be created via shell
- [ ] No import errors in services/validators
- [ ] Management command works

##  Next Steps

1. **Import Real Data**
   - Connect to SQL Server database
   - Import existing scheduling data
   - Verify data integrity

2. **Test Full Workflow**
   - Create DotXep
   - Create PhanCong
   - Generate ThoiKhoaBieu
   - Validate constraints

3. **Frontend Integration**
   - Build React/Vue dashboard
   - Consume REST APIs
   - Display schedules visually

4. **Production Deploy**
   - Configure production database
   - Set up static files
   - Configure web server (Nginx/Apache)
   - Set up HTTPS

---

**Good luck! 🎉**
