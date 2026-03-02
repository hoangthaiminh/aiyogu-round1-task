# ⬡ HomeworkAI — Chấm bài thông minh

Hệ thống nộp bài học sinh và nhận phản hồi AI như giáo viên Việt Nam, xây dựng bằng Flask + SQLite + Gemini API.

![Tech](https://img.shields.io/badge/Flask-3.0-cyan) ![Python](https://img.shields.io/badge/Python-3.10+-blue) ![AI](https://img.shields.io/badge/Gemini-1.5--flash-green)

## ✦ Tính năng

- **Auth**: Đăng ký / Đăng nhập / Đổi mật khẩu
- **Nộp bài**: Text + ảnh đính kèm (JPG/PNG/WebP, tối đa 5MB)
- **Nộp lại bài** — chỉnh sửa và chấm lại với phản hồi mới
- **Xóa bài làm** — xóa cả dữ liệu DB lẫn ảnh đính kèm, có xác nhận 2 bước
- **Xuất CSV** — xuất toàn bộ bài làm ra file CSV UTF-8 BOM (mở đúng tiếng Việt trên Excel)
- **Hồ sơ cá nhân** — avatar, tên hiển thị (Unicode/emoji), đổi mật khẩu
- **Chấm AI**: Điểm 0-10, tiêu chí, điểm mạnh/yếu, sửa lỗi, gợi ý
- **Profile**: Sửa tên, email, mật khẩu
- **Dark/Light mode**
- **Responsive** mobile/desktop

## ⚡ Cài đặt & Chạy

### 1. Clone và cài dependencies
```bash
git clone <repo>
cd homework_helper
pip install -r requirements.txt
```

### 2. Cấu hình .env
```bash
cp .env.example .env
# Mở .env và điền API key
```

### 3. Lấy Gemini API key miễn phí
1. Vào https://aistudio.google.com/app/apikey
2. Tạo API key (miễn phí, không cần thẻ credit)
3. Điền vào `.env`:
   ```
   AI_API_KEY=AIza...
   ```

### 4. Chạy ứng dụng
```bash
python app.py
```
Mở trình duyệt: **http://localhost:5000**

## 🧪 Demo Mode (không cần API key)

Nếu không điền `AI_API_KEY`, ứng dụng tự động dùng **dummy feedback** để test toàn bộ luồng. Rất tiện để phát triển UI.

## 📁 Cấu trúc project

```
homework_helper/
├── app.py                  # Flask app chính
├── data.db                 # SQLite DB (tự tạo)
├── requirements.txt
├── .env.example
├── README.md
├── uploads/                # Ảnh upload (gitignore)
├── templates/
│   ├── base.html           # Layout + navbar + OpenGraph
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── submit.html
│   ├── detail.html
│   ├── profile.html
│   └── error.html
└── static/
    ├── css/style.css       # Dark neon IT-cool theme
    ├── js/main.js          # Theme toggle, mobile menu
    └── favicon.svg
```

## 🔧 Thay đổi AI Provider

Trong `app.py`, hàm `call_ai_api()` xử lý toàn bộ việc gọi AI:

- **Gemini** (mặc định): Dùng `AI_API_URL` trong `.env`
- **Thay model**: Đổi URL trong `.env`, vd: `gemini-2.0-flash-exp`
- **Provider khác**: Sửa phần build `payload` trong `call_ai_api()` theo spec provider

## 🔒 Bảo mật

- Password hash với `werkzeug.security`
- Upload: validate kích thước + MIME type thực (Pillow)
- `secure_filename` + random hex prefix
- API key chỉ server biết, client không bao giờ gọi trực tiếp
- User chỉ xem/sửa dữ liệu của chính họ
- Ảnh upload chỉ accessible khi login và là chủ sở hữu
