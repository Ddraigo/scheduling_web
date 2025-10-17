# Scheduling App - Hệ thống Sắp xếp Thời Khóa Biểu

## 📋 Tổng quan

Django app quản lý và tự động sắp xếp thời khóa biểu cho trường đại học, sử dụng AI (Google Gemini) và thuật toán tối ưu.

## 🏗️ Cấu trúc

```
apps/scheduling/
├── models.py              # Django ORM models
├── admin.py               # Django Admin config
├── views.py               # REST API ViewSets
├── serializers.py         # DRF Serializers
├── urls.py                # URL routing
├── services/              # Business logic layer
│   ├── schedule_service.py       # Main scheduling service
│   ├── ai_service.py             # AI integration (Gemini)
│   ├── schedule_validator.py    # Schedule validation & metrics
│   ├── batch_scheduler.py       # Batch processing with AI
│   └── query_handler.py         # Query & analysis utilities
├── algorithms/            # Scheduling algorithms
│   ├── genetic_algorithm.py   # GA optimization
│   └── greedy_heuristic.py    # Greedy fallback
├── validators/            # Constraint validation
│   ├── constraint_checker.py
│   └── metrics_calculator.py
├── utils/                 # Helper functions
└── management/commands/   # CLI commands
    └── generate_schedule.py
```

## 📊 Models

### Core Models
- **Khoa** - Khoa/Viện
- **BoMon** - Bộ môn
- **GiangVien** - Giảng viên
- **MonHoc** - Môn học
- **PhongHoc** - Phòng học
- **LopMonHoc** - Lớp môn học

### Scheduling Models
- **DotXep** - Đợt xếp lịch
- **PhanCong** - Phân công giảng dạy
- **TimeSlot** - Khe giờ học
- **ThoiKhoaBieu** - Thời khóa biểu chính thức

## 🚀 API Endpoints

### Base URL: `/scheduling/`

#### Master Data
- `GET /khoa/` - Danh sách khoa
- `GET /bo-mon/` - Danh sách bộ môn
- `GET /giang-vien/` - Danh sách giảng viên
- `GET /mon-hoc/` - Danh sách môn học
- `GET /phong-hoc/` - Danh sách phòng học
- `GET /lop-mon-hoc/` - Danh sách lớp môn học

#### Scheduling
- `GET /dot-xep/` - Danh sách đợt xếp lịch
- `GET /phan-cong/` - Phân công giảng dạy
- `GET /time-slot/` - Danh sách time slots
- `GET /thoi-khoa-bieu/` - Thời khóa biểu

#### Schedule Generation
- `POST /schedule-generation/generate/` - Tạo lịch tự động
  ```json
  {
    "ma_dot": "2025-2026_HK1",
    "use_ai": true,
    "force_regenerate": false
  }
  ```

- `GET /schedule-generation/status/?ma_dot=2025-2026_HK1` - Kiểm tra trạng thái

- `POST /schedule-generation/validate/` - Validate lịch đã tạo
  ```json
  {
    "ma_dot": "2025-2026_HK1"
  }
  ```

- `POST /schedule-generation/batch_generate/` - Tạo lịch theo batch (cho dataset lớn)
  ```json
  {
    "ma_dot": "2025-2026_HK1",
    "batch_size": 25
  }
  ```

#### Analysis & Reports
- `GET /schedule-generation/conflicts/?ma_dot=2025-2026_HK1` - Kiểm tra xung đột
- `GET /schedule-generation/teacher_schedule/?ma_gv=GV001&ma_dot=2025-2026_HK1` - Lịch giảng viên
- `GET /schedule-generation/room_utilization/?ma_dot=2025-2026_HK1` - Mức sử dụng phòng
- `GET /schedule-generation/class_distribution/?ma_dot=2025-2026_HK1` - Phân bố lớp học

#### Custom Queries
- `GET /thoi-khoa-bieu/by_period/?ma_dot=2025-2026_HK1` - TKB theo đợt
- `GET /thoi-khoa-bieu/by_teacher/?ma_gv=GV001&ma_dot=2025-2026_HK1` - TKB giảng viên
- `GET /thoi-khoa-bieu/by_room/?ma_phong=A101&ma_dot=2025-2026_HK1` - TKB phòng học


## 💻 Usage

### Via API

```python
import requests

# Generate schedule
response = requests.post(
    'http://localhost:8000/scheduling/schedule-generation/generate/',
    json={
        'ma_dot': '2025-2026_HK1',
        'use_ai': True
    },
    headers={'Authorization': 'Token YOUR_TOKEN'}
)

print(response.json())
```

### Via Management Command

```bash
# Generate with AI
python manage.py generate_schedule --period 2025-2026_HK1

# Generate with greedy algorithm
python manage.py generate_schedule --period 2025-2026_HK1 --greedy
```

### Via Django Shell

```python
from apps.scheduling.services.schedule_service import ScheduleService

service = ScheduleService()
result = service.generate_schedule('2025-2026_HK1', use_ai=True)
print(result)
```

## 🔧 Configuration

### Environment Variables

```env
# AI Configuration
GEMINI_API_KEY=your_api_key_here
AI_MODEL_NAME=gemini-2.0-flash-exp

# Database (sử dụng Django DATABASE settings)
```

### Django Settings

App đã được thêm vào `INSTALLED_APPS`:
```python
INSTALLED_APPS = [
    ...
    'apps.scheduling',
    'rest_framework',
    'django_filters',
]
```

## 🧪 Testing

```bash
# Run tests
python manage.py test apps.scheduling

# Run specific test
python manage.py test apps.scheduling.tests.test_schedule_service
```

## 📝 Migration từ src/

Code đã được migrate từ folder `src/` cũ:

- `src/ai/schedule_ai.py` → `services/ai_service.py`
- `src/scheduling/schedule_system.py` → `services/schedule_service.py`
- `src/algorithm/` → `algorithms/`
- `src/validation/` → `validators/`

## 🎯 Next Steps

1. ✅ Tích hợp thuật toán GA từ `src/algorithm/`
2. ✅ Migrate validators từ `src/validation/`
3. ✅ Tạo UI dashboard
4. ✅ Thêm real-time updates (WebSocket)
5. ✅ Export/Import Excel

## 📞 Support

Liên hệ: development team
