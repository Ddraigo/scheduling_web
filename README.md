# Hệ Thống Xếp Lịch Học - Scheduling Web

Hệ thống quản lý và xếp lịch học tự động cho trường đại học, xây dựng trên nền tảng Django.

## 📋 Mục Lục

- [Yêu Cầu Hệ Thống](#yêu-cầu-hệ-thống)
- [Cài Đặt](#cài-đặt)
- [Cấu Hình](#cấu-hình)
- [Chạy Dự Án](#chạy-dự-án)
- [Cấu Trúc Dự Án](#cấu-trúc-dự-án)
- [Tính Năng](#tính-năng)

## 🔧 Yêu Cầu Hệ Thống

### Phần Mềm Cần Thiết

- **Python**: 3.9 hoặc cao hơn
- **Node.js**: 16.x hoặc cao hơn
- **npm**: 8.x hoặc cao hơn
- **Database**: SQLite (mặc định) hoặc SQL Server

### Kiểm Tra Phiên Bản

```bash
python --version
node --version
npm --version
```

## 📦 Cài Đặt

### Bước 1: Clone Dự Án

```bash
git clone <repository-url>
cd scheduling_web
```

### Bước 2: Tạo Môi Trường Ảo Python

#### Windows (PowerShell)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### Windows (Command Prompt)
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

#### Linux/macOS
```bash
python -m venv venv
source venv/bin/activate
```

### Bước 3: Cài Đặt Dependencies Python

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Bước 4: Cài Đặt Dependencies Frontend

```bash
npm install
```

## ⚙️ Cấu Hình

### Bước 1: Tạo File Environment

Sao chép file mẫu và chỉnh sửa:

```bash
cp env.sample .env
```

### Bước 2: Chỉnh Sửa File `.env`

Mở file `.env` và cấu hình các thông số:

```env
# Chế độ chạy (True = development, False = production)
DEBUG=True

# Secret key cho Django (đổi thành key bảo mật của cá nhân)
SECRET_KEY=your-secret-key

# Cấu hình Database (mặc định sử dụng SQLite)
# Bỏ comment và cấu hình nếu dùng SQL Server

# DB_ENGINE=mssql
# DB_HOST=.\SQLEXPRESS
# DB_NAME=CSDL_TKB
# DB_USERNAME=your_username
# DB_PASS=your_password
# DB_PORT=3306
```

### Bước 3: Khởi Tạo Database

```bash
# Tạo migrations
python manage.py makemigrations

# Chạy migrations
python manage.py migrate

# Tạo superuser (admin)
python manage.py createsuperuser
```

Nhập thông tin admin khi được hỏi:
- Username
- Email
- Password

### Bước 4: Thu Thập Static Files

```bash
python manage.py collectstatic --noinput
```

## 🚀 Chạy Dự Án

### Development Mode

#### Terminal 1: Chạy Django Backend

```bash
# Kích hoạt virtual environment (nếu chưa)
.\venv\Scripts\Activate.ps1  # Windows PowerShell
# hoặc
source venv/bin/activate      # Linux/macOS

# Chạy development server
python manage.py runserver
```

Server sẽ chạy tại: `http://127.0.0.1:8000/`

#### Terminal 2: Chạy Frontend Build (Tùy chọn)

Nếu muốn phát triển frontend với hot reload:

```bash
npm run dev
```

### Production Mode

#### Sử dụng Gunicorn (Linux/macOS)

```bash
gunicorn --config gunicorn-cfg.py config.wsgi
```

#### Sử dụng Docker

```bash
# Build image
docker-compose build

# Chạy container
docker-compose up -d
```

## 📁 Cấu Trúc Dự Án

```
scheduling_web/
├── apps/                    # Các Django apps
│   ├── scheduling/         # Module xếp lịch chính
│   ├── data_table/         # Quản lý dữ liệu
│   ├── charts/             # Biểu đồ và thống kê
│   ├── pages/              # Các trang web
│   └── sap_lich/           # Xử lý thuật toán xếp lịch
├── config/                  # Cấu hình Django
│   ├── settings.py         # Cài đặt chính
│   ├── urls.py             # URL routing
│   └── wsgi.py             # WSGI config
├── static/                  # Static files (CSS, JS, images)
├── templates/               # HTML templates
├── docs/                    # Tài liệu dự án
├── cli/                     # CLI tools và helpers
├── manage.py               # Django management script
├── requirements.txt        # Python dependencies
├── package.json            # Node.js dependencies
└── .env                    # Environment variables
```

## ✨ Tính Năng

- 🗓️ **Xếp Lịch Tự Động**: Thuật toán xếp lịch thông minh
- 👥 **Quản Lý Giảng Viên**: Theo dõi phân công giảng dạy
- 🏫 **Quản Lý Phòng Học**: Sắp xếp phòng học tối ưu
- 📊 **Thống Kê & Báo Cáo**: Biểu đồ trực quan
- 📤 **Xuất Excel**: Export thời khóa biểu
- 🔐 **Xác Thực & Phân Quyền**: Hệ thống Django auth

## 🔑 Truy Cập Hệ Thống

### Admin Panel
- URL: `http://127.0.0.1:8000/admin/`
- Đăng nhập bằng superuser đã tạo

### User Interface
- URL: `http://127.0.0.1:8000/`

## 📝 Các Lệnh Hữu Ích

```bash
# Tạo app mới
python manage.py startapp <app_name>

# Xem cấu trúc database
python manage.py dbshell

# Chạy tests
python manage.py test

# Tạo backup database
python manage.py dbbackup

# Load dữ liệu mẫu (nếu có fixtures)
python manage.py loaddata <fixture_name>

# Xóa cache
python manage.py clearcache

# Build frontend production
npm run build
```

## 🐛 Troubleshooting

### Lỗi: "No module named 'django'"
```bash
# Đảm bảo virtual environment đã được kích hoạt
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Lỗi: "port 8000 is already in use"
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/macOS
lsof -ti:8000 | xargs kill -9
```

### Lỗi Database Migration
```bash
python manage.py migrate --fake-initial
# hoặc
python manage.py migrate --run-syncdb
```

## 📄 License

[Thêm thông tin license của bạn ở đây]

## 👥 Contributors

[Thêm thông tin về nhóm phát triển]

## 📞 Liên Hệ

[Thêm thông tin liên hệ]
