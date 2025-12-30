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

- **Python**: 3.9 - 3.11 (khuyến nghị 3.11)
- **Node.js**: 16.x hoặc cao hơn
- **npm**: 8.x hoặc cao hơn
- **Database**: Azure SQL Server
- **ODBC Driver**: Microsoft ODBC Driver 17 hoặc 18 for SQL Server

### Kiểm Tra Phiên Bản

```bash
python --version
node --version
npm --version
```

### Cài Đặt ODBC Driver (Bắt buộc cho Azure SQL)

#### Windows
1. Tải và cài đặt từ: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server (nếu có rồi thì bỏ qua)
2. Chọn **ODBC Driver 17** hoặc **ODBC Driver 18**
3. Chạy file cài đặt và hoàn tất

#### Linux (Ubuntu/Debian)
```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

#### macOS
```bash
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
brew update
brew install msodbcsql18
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

### ⚠️ QUAN TRỌNG: Dự Án Sử Dụng Azure SQL Server

Dự án này **BẮT BUỘC** sử dụng Azure SQL Server, không hỗ trợ SQLite hay database khác. Đảm bảo bạn đã có:
- ✅ Tài khoản Azure với SQL Server instance
- ✅ ODBC Driver 17/18 đã cài đặt
- ✅ Thông tin kết nối database (host, username, password)

### Bước 1: Tạo File Environment

Sao chép file mẫu và chỉnh sửa:

```bash
cp env.sample .env
```

### Bước 2: Cấu Hình Kết Nối Azure SQL Server

Mở file `.env` và **BẮT BUỘC** cấu hình các thông số sau:

```env
# Django Settings
DEBUG=True
SECRET_KEY=your-secret-key-change-this-in-production

# ===== AZURE SQL SERVER (BẮT BUỘC) =====
DB_ENGINE=mssql
DB_HOST=your-server.database.windows.net
DB_NAME=CSDL_TKB
DB_USERNAME=your_admin_username
DB_PASSWORD=your_strong_password
DB_PORT=1433

# ODBC Driver (chọn 17 hoặc 18 tùy version đã cài)
ODBC_DRIVER=ODBC Driver 18 for SQL Server
```

#### 📝 Cách Lấy Thông Tin Kết Nối Azure SQL: (bỏ qua vì đã có)

1. **Đăng nhập Azure Portal**: https://portal.azure.com
2. **Tìm SQL Database** của bạn: `Tìm kiếm > SQL databases > chọn database`
3. **Copy Connection String**: 
   - Vào **Settings > Connection strings**
   - Chọn tab **ODBC**
   - Copy thông tin:
     - `Server`: `your-server.database.windows.net,1433`
     - `Database`: `CSDL_TKB` (hoặc tên database của bạn)
     - `Uid`: username
     - `Pwd`: password

4. **Cấu hình Firewall** (quan trọng):
   - Vào **Settings > Networking/Firewalls and virtual networks**
   - Thêm IP máy tính của bạn: **Add client IP**
   - Hoặc cho phép Azure services: **Allow Azure services** = ON

### Bước 3: Kiểm Tra Kết Nối Database

Trước khi chạy migration, test kết nối:

```bash
python test_connection.py
```

Nếu thành công, bạn sẽ thấy:
```
✅ Kết nối database thành công!
Database: CSDL_TKB
Server: your-server.database.windows.net
```

Nếu lỗi, kiểm tra:
- ❌ Thông tin đăng nhập (username/password)
- ❌ Firewall Azure SQL chưa mở IP của bạn
- ❌ ODBC Driver chưa cài đặt
- ❌ Tên server sai (phải có `.database.windows.net`)

### Bước 4: Khởi Tạo Database

**LƯU Ý**: Database Azure SQL **đã có schema sẵn**, không cần chạy migration ban đầu.

#### Nếu database TRỐNG (lần đầu setup):

```bash
# Tạo migrations (nếu có thay đổi model)
python manage.py makemigrations

# Áp dụng migrations
python manage.py migrate

# Import dữ liệu mẫu (nếu có file SQL)
# Sử dụng Azure Data Studio hoặc SQL Server Management Studio
# để chạy file csdl_tkb.sql
```

#### Nếu database ĐÃ CÓ DATA (pull code về):

```bash
# KHÔNG chạy migrate, chỉ fake migrations
python manage.py migrate --fake-initial

# Hoặc nếu có lỗi:
python manage.py migrate --fake
```

### Bước 5: Tạo Superuser

```bash
python manage.py createsuperuser
```

Nhập thông tin:
- **Username**: admin
- **Email**: your-email@example.com
- **Password**: (mật khẩu mạnh)

### Bước 6: Thu Thập Static Files

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

- 🗓️ **Xếp Lịch Tự Động**: Thuật toán meta-heuristic (Simulated Annealing + Tabu Search)
- 👥 **Quản Lý Giảng Viên**: Phân công, nguyện vọng, tải giảng dạy
- 🏫 **Quản Lý Phòng Học**: Sắp xếp phòng theo loại (LT/TH), sức chứa
- 📊 **Thống Kê & Báo Cáo**: Dashboard trực quan, biểu đồ phân tích
- 📤 **Xuất/Nhập Excel**: Import/export dữ liệu, template tự động
- 🔐 **Xác Thực & Phân Quyền**: Django authentication + custom permissions
- 🤖 **Chatbot AI**: Hỗ trợ truy vấn thời khóa biểu qua Google Gemini
- ⚙️ **Cấu Hình Động**: Điều chỉnh trọng số ràng buộc mềm realtime
- 📅 **Quản Lý Đợt**: Nhiều đợt xếp lịch độc lập cho mỗi học kỳ
- 🔄 **Auto-generate Mã**: Tự động sinh mã khi tạo mới (Khoa, GV, Lớp, v.v.)

## 🎯 Workflow Cơ Bản

### 1️⃣ Khởi tạo dữ liệu nền tảng
```
Admin > Khoa > Thêm mới
Admin > Bộ môn > Thêm mới (gắn với Khoa)
Admin > Giảng viên > Thêm mới (gắn với Bộ môn)
Admin > Môn học > Thêm mới
Admin > GV dạy môn > Gán GV cho từng môn
Admin > Phòng học > Thêm mới (phân loại LT/TH)
Admin > Khung thời gian > Tạo ca học (Ca 1-5)
Admin > Time Slot > Tạo slot (Thu2-Ca1, Thu3-Ca2, ...)
```

### 2️⃣ Tạo đợt xếp lịch
```
Admin > Dự kiến đào tạo > Tạo học kỳ (VD: 2025-2026_HK1)
Admin > Lớp môn học > Nhập danh sách lớp (hoặc import Excel)
Admin > Đợt xếp > Tạo đợt mới
Admin > Phân công > Gán GV cho từng lớp
Admin > Nguyện vọng > GV đăng ký slot ưa thích
Admin > Ràng buộc trong đợt > Cấu hình trọng số
```

### 3️⃣ Chạy thuật toán xếp lịch
```
Web UI > Chọn đợt > Click "Chạy thuật toán"
Hệ thống tối ưu: Tránh xung đột, tối thiểu hóa vi phạm ràng buộc mềm
Kết quả: Thời khóa biểu hoàn chỉnh (lớp-GV-phòng-slot-tuần)
```

### 4️⃣ Xuất và chia sẻ
```
Web UI > Xem TKB theo GV/Lớp/Phòng
Export Excel > Chia sẻ cho khoa/giảng viên
Chatbot > Hỏi "Lịch dạy của GV001 tuần 5?"
```

## 🔑 Truy Cập Hệ Thống

### Admin Panel
- URL: `http://127.0.0.1:8000/admin/`
- Đăng nhập bằng superuser đã tạo

### User Interface
- URL: `http://127.0.0.1:8000/`

## 📝 Các Lệnh Hữu Ích

### Database Management
```bash
# Test kết nối Azure SQL
python test_connection.py

# Xem schema database
python manage.py inspectdb

# Backup database (qua Azure Portal)
# Vào SQL Database > Automated backups > Restore

# Export data to CSV/Excel
python manage.py dumpdata scheduling --output=data.json
```

### Migration Commands
```bash
# Tạo migration mới
python manage.py makemigrations

# Xem SQL sẽ chạy (không thực thi)
python manage.py sqlmigrate scheduling 0001

# Fake migration (database đã có table)
python manage.py migrate --fake-initial

# Rollback migration
python manage.py migrate scheduling 0001

# Show migrations status
python manage.py showmigrations
```

### Development Commands
```bash
# Tạo app mới
python manage.py startapp <app_name>

# Chạy tests
python manage.py test

# Load dữ liệu mẫu
python manage.py loaddata fixtures/sample_data.json

# Clear cache
python manage.py clearcache

# Check project issues
python manage.py check
```

### Frontend Commands
```bash
# Build production
npm run build

# Development với hot reload
npm run dev

# Lint code
npm run lint
```

### Azure Deployment (Production)
```bash
# Collect static files
python manage.py collectstatic --noinput

# Run with Gunicorn
gunicorn --config config/gunicorn_cfg.py config.wsgi

# Check production readiness
python manage.py check --deploy
```

## 🐛 Troubleshooting

### ❌ Lỗi Kết Nối Azure SQL Server

#### 1. "Login failed for user" / "Cannot open server"
```bash
# Kiểm tra lại thông tin đăng nhập trong .env
# Username phải đúng format: username (không thêm @server)
# Password không được chứa ký tự đặc biệt chưa escape
```

**Giải pháp:**
- Vào Azure Portal > SQL Database > Connection strings
- Copy lại chính xác username và password
- Kiểm tra **Firewall Rules** đã thêm IP máy của bạn chưa

#### 2. "SSL connection is required"
```env
# Trong .env, thêm:
DB_OPTIONS={"TrustServerCertificate": "yes"}
```

#### 3. "ODBC Driver not found"
```bash
# Windows: Cài đặt lại ODBC Driver
# Download: https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server

# Linux:
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18

# macOS:
brew install msodbcsql18
```

#### 4. "IP address is not allowed to connect"
**Giải pháp:**
1. Vào **Azure Portal**
2. Chọn SQL Server > **Networking**
3. **Add client IP** (thêm IP hiện tại)
4. Hoặc bật **Allow Azure services and resources to access this server**

### ❌ Lỗi Migration

#### "Table already exists"
```bash
# Database đã có table, fake migration:
python manage.py migrate --fake-initial
```

#### "No migrations to apply"
```bash
# Xóa cache migration:
find . -path "*/migrations/*.pyc" -delete
find . -path "*/migrations/__pycache__" -delete

# Tạo lại:
python manage.py makemigrations
python manage.py migrate --fake
```

### ❌ Lỗi Python Dependencies

#### "No module named 'django'"
```bash
# Kích hoạt virtual environment
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate      # Linux/macOS

# Cài lại dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### "No module named 'mssql'"
```bash
# Cài đặt SQL Server adapter
pip install mssql-django pyodbc
```

### ❌ Lỗi Port 8000 đã sử dụng

#### Windows
```powershell
# Tìm process đang dùng port 8000
netstat -ano | findstr :8000

# Kill process (thay <PID> bằng số PID tìm được)
taskkill /PID <PID> /F
```

#### Linux/macOS
```bash
# Tìm và kill process
lsof -ti:8000 | xargs kill -9

# Hoặc chạy trên port khác
python manage.py runserver 8080
```

### ❌ Lỗi Static Files

```bash
# Xóa static files cũ
rm -rf staticfiles/

# Collect lại
python manage.py collectstatic --noinput
```

### 🔍 Debug Mode

Để xem chi tiết lỗi, bật debug trong `.env`:

```env
DEBUG=True
```

**LƯU Ý**: Không bật DEBUG=True trên production!

### 📞 Yêu Cầu Hỗ Trợ

Nếu gặp lỗi không giải quyết được, cung cấp thông tin:
1. Thông báo lỗi đầy đủ (screenshot hoặc copy text)
2. Phiên bản Python: `python --version`
3. Phiên bản ODBC Driver đã cài
4. File `.env` (ẩn password)
5. Output của `pip list`

## 📄 License

[Thêm thông tin license của bạn ở đây]

## 👥 Contributors

[Thêm thông tin về nhóm phát triển]

## 📞 Liên Hệ

[Thêm thông tin liên hệ]
