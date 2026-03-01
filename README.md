# Order Tracking Hub

Hệ thống theo dõi đơn hàng tự động với khả năng tích hợp nhiều nhà vận chuyển và thông báo qua Telegram.

## 📋 Mô tả

Order Tracking Hub là một ứng dụng web Flask cho phép người dùng theo dõi trạng thái đơn hàng từ nhiều đơn vị vận chuyển khác nhau. Hệ thống tự động kiểm tra cập nhật trạng thái đơn hàng theo định kỳ và gửi thông báo qua Telegram khi có thay đổi.

## ✨ Tính năng

- 🔐 **Xác thực người dùng**: Đăng ký, đăng nhập với Firebase Authentication
- 📦 **Theo dõi đơn hàng**: Thêm và quản lý mã vận đơn từ nhiều nhà vận chuyển
- 🔄 **Cập nhật tự động**: Scheduler tự động kiểm tra trạng thái đơn hàng theo định kỳ
- 📱 **Thông báo Telegram**: Nhận thông báo tức thời khi đơn hàng có cập nhật
- 🚚 **Hỗ trợ nhiều nhà vận chuyển**: 
  - Shopee Express VN (SPXVN)
  - Dễ dàng mở rộng với các nhà vận chuyển khác
- 📊 **Dashboard trực quan**: Xem danh sách và chi tiết đơn hàng
- ⚙️ **Cài đặt cá nhân**: Quản lý tài khoản và cấu hình thông báo

## 🛠 Công nghệ sử dụng

- **Backend**: Flask 3.0.0
- **Database**: Firebase Firestore
- **Authentication**: Firebase Admin SDK
- **Scheduler**: APScheduler 3.10.4
- **Forms**: Flask-WTF 1.2.1
- **Notifications**: Telegram Bot API
- **HTTP Client**: Requests 2.31.0

## 📦 Yêu cầu

- Python 3.8+
- Firebase Project với Admin SDK credentials
- Telegram Bot Token (tùy chọn, để sử dụng tính năng thông báo)

## 🚀 Cài đặt

### 1. Clone repository

```bash
git clone https://github.com/nguyenngocdantruong/TrackingOrder.git
cd OrderTracking
```

### 2. Tạo môi trường ảo

```bash
python -m venv .venv
```

### 3. Kích hoạt môi trường ảo

**Windows:**
```bash
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
source .venv/bin/activate
```

### 4. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 5. Cấu hình Firebase

- Tạo project trên [Firebase Console](https://console.firebase.google.com/)
- Tải về Service Account Key (JSON file)
- Đổi tên file thành `trackingorderhub-firebase-adminsdk-fbsvc-0de65e1b75.json` hoặc cập nhật đường dẫn trong code
- Đặt file vào thư mục gốc của project

### 6. Cấu hình ứng dụng

Tạo/chỉnh sửa file `config.conf`:

```properties
PORT_APP=8084
LISTEN_PORT=0.0.0.0
DEBUG=0
SCHEDULER_ENABLED=1
POLL_INTERVAL_SECONDS=600
```

**Các tham số:**
- `PORT_APP`: Cổng chạy ứng dụng (mặc định: 5000)
- `LISTEN_PORT`: Địa chỉ lắng nghe (0.0.0.0 cho tất cả interfaces, 127.0.0.1 cho localhost)
- `DEBUG`: Chế độ debug (0: tắt, 1: bật)
- `SCHEDULER_ENABLED`: Bật/tắt scheduler tự động kiểm tra đơn hàng (0: tắt, 1: bật)
- `POLL_INTERVAL_SECONDS`: Khoảng thời gian giữa các lần kiểm tra (giây)

### 7. Cấu hình biến môi trường (tùy chọn)

Tạo file `.env` để cấu hình các biến môi trường bổ sung:

```env
SECRET_KEY=your-secret-key-here
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
FIREBASE_CREDENTIALS_PATH=trackingorderhub-firebase-adminsdk-fbsvc-0de65e1b75.json
```

## 🎮 Sử dụng

### Chạy ứng dụng

```bash
python run.py
```

Ứng dụng sẽ chạy tại `http://localhost:8084` (hoặc cổng đã cấu hình)

### Chạy với tunnel (cho phát triển)

```bash
run_tunnel.bat
```

### Sử dụng web interface

1. Truy cập `http://localhost:8084`
2. Đăng ký tài khoản mới hoặc đăng nhập
3. Thêm mã vận đơn cần theo dõi
4. Xem dashboard để theo dõi trạng thái
5. Cấu hình Telegram bot trong phần Settings để nhận thông báo

### Sử dụng Telegram chat bot

Sau khi đã cấu hình Telegram Chat ID trong Settings, bạn có thể chat trực tiếp với bot để thao tác nhanh:

- `/add <mã vận đơn> [tên gợi nhớ]`: thêm đơn hàng mới
- `/providers`: xem danh sách đơn vị vận chuyển đang hỗ trợ
- `/list`: xem danh sách đơn hàng (`#<mã vận đơn> - <trạng thái hiện tại>`)
- `/help`: hướng dẫn sử dụng
- `/author`: thông tin tác giả

Nếu user chat lần đầu mà chưa có tài khoản website, hệ thống sẽ tự tạo **tài khoản tạm theo Telegram ID** để vẫn lưu lịch sử tracking. Bot sẽ hiển thị nút **Liên kết tài khoản** mở endpoint `/link` để user nhập username/password và chuyển tài khoản tạm thành tài khoản website chính thức.

## 📁 Cấu trúc dự án

```
OrderTracking/
├── app/
│   ├── __init__.py              # Khởi tạo Flask app
│   ├── config.py                # Cấu hình ứng dụng
│   ├── firebase.py              # Khởi tạo Firebase
│   ├── scheduler.py             # APScheduler cho background tasks
│   ├── auth/                    # Module xác thực
│   │   ├── forms.py
│   │   └── routes.py
│   ├── notifications/           # Module thông báo
│   │   └── telegram.py
│   ├── providers/               # Module nhà vận chuyển
│   │   ├── base.py             # Base class cho providers
│   │   ├── registry.py         # Registry quản lý providers
│   │   ├── spx_vn_provider.py  # Shopee Express VN provider
│   │   └── fixtures/
│   ├── repos/                   # Data repositories
│   │   ├── trackings_repo.py
│   │   └── users_repo.py
│   ├── settings/                # Module cài đặt
│   │   ├── forms.py
│   │   └── routes.py
│   ├── static/                  # CSS, JS, images
│   ├── templates/               # HTML templates
│   │   ├── auth/
│   │   ├── settings/
│   │   └── tracking/
│   └── tracking/                # Module theo dõi đơn hàng
│       ├── forms.py
│       ├── routes.py
│       └── services.py
├── config.conf                  # File cấu hình
├── requirements.txt             # Python dependencies
├── run.py                       # Entry point
└── README.md                    # Documentation
```

## 🔌 Thêm nhà vận chuyển mới

Để thêm hỗ trợ cho nhà vận chuyển mới:

1. Tạo file provider mới trong `app/providers/`
2. Kế thừa từ `CarrierProvider` base class
3. Implement các phương thức: `id`, `displayName`, `supports()`, `track()`
4. Đăng ký provider trong `registry.py`

Ví dụ:

```python
from app.providers.base import CarrierProvider, TrackingResult

class NewCarrierProvider(CarrierProvider):
    @property
    def id(self) -> str:
        return "new_carrier"
    
    @property
    def displayName(self) -> str:
        return "New Carrier"
    
    def supports(self, tracking_number: str) -> bool:
        return tracking_number.startswith("NC")
    
    def track(self, tracking_number: str) -> TrackingResult:
        # Implement tracking logic
        pass
```

## 👥 Đóng góp

Mọi đóng góp đều được hoan nghênh! Vui lòng tạo issue hoặc pull request.

## 📧 Liên hệ

https://www.facebook.com/dantruong.2025/
