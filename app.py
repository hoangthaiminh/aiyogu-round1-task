"""
Homework Helper & Auto-feedback - Flask App
Hệ thống nộp bài và nhận phản hồi AI như giáo viên Việt Nam
Sử dụng sqlite3 thuần (không cần SQLAlchemy)
"""

import os
import io
import re
import json
import base64
import sqlite3
import secrets
import unicodedata
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, abort, send_from_directory)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import requests as http_requests

# Load .env nếu có python-dotenv, không thì bỏ qua
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024  # 30MB – server sẽ nén lại

# Cấu hình AI — lấy từ .env
AI_API_KEY = os.getenv('AI_API_KEY', '')
# AI_API_URL: Thay đổi URL này để dùng model/provider khác
# Mặc định: Gemini 1.5 Flash (miễn phí, không cần thẻ credit)
# Lấy key tại: https://aistudio.google.com/app/apikey
AI_API_URL = os.getenv(
    'AI_API_URL',
    'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'
)

DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')
MAX_IMAGE_SIZE = 5 * 1024 * 1024   # 5 MB
IMAGE_MAX_DIM = 1024                # resize nếu lớn hơn px này
UPLOAD_MAX_RAW = 25 * 1024 * 1024  # Giới hạn file thô đầu vào (25MB)

# ─── USERNAME / DISPLAY NAME VALIDATION ──────────────────────────────────────
# username: chỉ a-z, A-Z, 0-9, dấu _ ; 3–30 ký tự
USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,30}$')


def validate_username(username: str):
    """Trả (True, None) nếu hợp lệ, (False, msg) nếu không."""
    if not username:
        return False, 'Tên đăng nhập không được để trống.'
    if not USERNAME_RE.match(username):
        return False, ('Tên đăng nhập chỉ dùng chữ cái a–z, A–Z, số 0–9 và dấu gạch dưới (_), '
                       'từ 3 đến 30 ký tự, không dấu cách.')
    return True, None


def sanitize_display_name(name: str) -> str:
    """
    Cho phép mọi ký tự Unicode hiển thị được (kể cả emoji, tiếng Việt…).
    Loại bỏ ký tự điều khiển (category C*) và normalize NFKC.
    Tối đa 60 ký tự sau khi trim.
    """
    if not name:
        return ''
    # Loại bỏ ký tự điều khiển (Cc, Cf…) nhưng giữ khoảng trắng thường
    cleaned = ''.join(
        c for c in name
        if unicodedata.category(c)[0] != 'C' or c == ' '
    )
    cleaned = unicodedata.normalize('NFKC', cleaned).strip()
    return cleaned[:60]


# ─── DATABASE ─────────────────────────────────────────────────────────────────

def get_db():
    """Kết nối SQLite, trả về Row objects"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Khởi tạo bảng nếu chưa có"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            email TEXT DEFAULT '',
            avatar_path TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content_text TEXT DEFAULT '',
            image_path TEXT DEFAULT '',
            ai_feedback_json TEXT DEFAULT '{}',
            score REAL DEFAULT 0.0,
            submitted_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()


# ─── AUTH HELPERS ─────────────────────────────────────────────────────────────

def login_required(f):
    """Decorator yêu cầu đăng nhập"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Vui lòng đăng nhập để tiếp tục.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    """Lấy user hiện tại từ session"""
    if 'user_id' not in session:
        return None
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return user


# ─── FILE UPLOAD HELPERS ──────────────────────────────────────────────────────

def validate_image_format(file) -> tuple:
    """
    Chỉ kiểm tra định dạng file (MIME thực qua Pillow).
    KHÔNG từ chối theo kích thước — server sẽ tự nén.
    Trả (True, img_format) hoặc (False, error_msg).
    """
    try:
        img = Image.open(file)
        fmt = (img.format or '').lower()
        file.seek(0)
        if fmt not in ('jpeg', 'png', 'webp', 'gif'):
            return False, f'Chỉ chấp nhận JPG, PNG, WebP hoặc GIF (nhận: {fmt or "unknown"})'
    except Exception:
        file.seek(0)
        return False, 'File không phải ảnh hợp lệ'
    file.seek(0)
    return True, fmt


# Alias cũ để không phải sửa caller
def validate_image(file):
    ok, val = validate_image_format(file)
    if ok:
        return True, None
    return False, val


def save_and_compress_image(file, original_filename: str) -> str:
    """
    Smart server-side compression:
    - Thử nén từ chất lượng cao → thấp dần cho đến khi <= MAX_IMAGE_SIZE.
    - Nếu vẫn vượt ngưỡng → raise ValueError (caller sẽ flash lỗi).
    - GIF: giữ nguyên (lossless copy); nếu vượt ngưỡng → báo lỗi.
    - PNG: lossless resize dần; PNG nặng hơn JPEG nên chuyển JPEG nếu cần.
    - JPEG / WebP: giảm quality + shrink dimension dần.

    Luôn trả filename (không có đường dẫn đầy đủ).
    """
    file.seek(0, 2)
    raw_size = file.tell()
    file.seek(0)

    if raw_size > UPLOAD_MAX_RAW:
        raise ValueError(f'File quá lớn (tối đa {UPLOAD_MAX_RAW // 1024 // 1024}MB cho phép upload).')

    safe_name = secure_filename(original_filename)
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
        ext = '.jpg'

    # ── GIF: copy thô, không nén (giữ animation) ──
    if ext == '.gif':
        if raw_size <= MAX_IMAGE_SIZE:
            import shutil
            final_name = f"{secrets.token_hex(10)}.gif"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], final_name)
            file.seek(0)
            with open(save_path, 'wb') as out:
                shutil.copyfileobj(file, out)
            return final_name
        raise ValueError(f'GIF quá lớn ({raw_size / 1024 / 1024:.1f}MB). GIF không thể nén — vui lòng dùng ảnh JPG/PNG/WebP.')

    img = Image.open(file)

    # ── Chuẩn hoá mode theo format đầu ra ──
    def prepare(image, target_ext):
        if target_ext in ('.jpg', '.jpeg'):
            if image.mode in ('RGBA', 'LA', 'PA'):
                bg = Image.new('RGB', image.size, (255, 255, 255))
                mask = image.split()[-1] if image.mode in ('RGBA', 'LA') else None
                bg.paste(image.convert('RGBA') if image.mode == 'PA' else image,
                         mask=mask)
                return bg
            if image.mode != 'RGB':
                return image.convert('RGB')
        elif target_ext == '.webp':
            if image.mode not in ('RGB', 'RGBA'):
                return image.convert('RGBA' if 'A' in image.mode else 'RGB')
        elif target_ext == '.png':
            if image.mode not in ('RGB', 'RGBA', 'L', 'LA', 'P'):
                return image.convert('RGBA')
        return image

    def try_save(image, target_ext, max_dim, quality):
        """Trả bytes nếu <= MAX_IMAGE_SIZE, ngược lại None."""
        work = image.copy()
        if max(work.size) > max_dim:
            work.thumbnail((max_dim, max_dim), Image.LANCZOS)
        work = prepare(work, target_ext)
        buf = io.BytesIO()
        if target_ext in ('.jpg', '.jpeg'):
            work.save(buf, format='JPEG', quality=quality, optimize=True)
        elif target_ext == '.webp':
            work.save(buf, format='WEBP', quality=quality, method=4)
        elif target_ext == '.png':
            work.save(buf, format='PNG', optimize=True, compress_level=9)
        size = buf.tell()
        return buf if size <= MAX_IMAGE_SIZE else None

    # ── Danh sách attempts: (max_dim, quality) từ tốt → thấp ──
    # Với JPEG/WebP: giảm quality dần
    # Với PNG: resize dần, nếu vẫn to → chuyển sang JPEG
    attempts_lossy = [
        (3000, 95), (2400, 92), (2000, 90), (1600, 88),
        (1280, 85), (1024, 82), (900, 78), (800, 74),
        (700, 70), (600, 65), (512, 60), (480, 55),
        (400, 50), (360, 45), (320, 40),
    ]

    result_buf = None
    out_ext = ext

    if ext == '.png':
        # Thử PNG lossless trước (resize dần)
        png_dims = [4096, 2048, 1600, 1200, 1024, 800, 640, 512, 400, 320]
        for dim in png_dims:
            buf = try_save(img, '.png', dim, None)
            if buf:
                result_buf = buf
                out_ext = '.png'
                break
        # Nếu PNG vẫn to → chuyển JPEG
        if not result_buf:
            for max_dim, quality in attempts_lossy:
                buf = try_save(img, '.jpg', max_dim, quality)
                if buf:
                    result_buf = buf
                    out_ext = '.jpg'
                    break
    else:
        for max_dim, quality in attempts_lossy:
            buf = try_save(img, ext, max_dim, quality)
            if buf:
                result_buf = buf
                out_ext = ext
                break

    if result_buf is None:
        raise ValueError(
            f'Ảnh quá lớn, không thể nén xuống dưới {MAX_IMAGE_SIZE // 1024 // 1024}MB. '
            f'Vui lòng dùng ảnh nhỏ hơn.'
        )

    final_name = f"{secrets.token_hex(10)}{out_ext}"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], final_name)
    result_buf.seek(0)
    with open(save_path, 'wb') as f:
        f.write(result_buf.read())

    app.logger.info(f'Image saved: {final_name} (raw {raw_size//1024}KB → {os.path.getsize(save_path)//1024}KB)')
    return final_name


# Alias để không sửa mọi caller
def save_and_resize_image(file, original_filename):
    return save_and_compress_image(file, original_filename)

# ─── AI API CALL ──────────────────────────────────────────────────────────────
#
# Chiến lược tránh JSON bị cắt ngắn (Unterminated string):
#
# 1. STRUCTURED OUTPUT (Gemini native): dùng responseMimeType="application/json"
#    + responseSchema (type UPPERCASE) → model bị ràng buộc ở decoder level,
#    KHÔNG THỂ sinh ra JSON không hợp lệ dù bị timeout hay token limit.
#
# 2. INPUT TRIMMING: cắt bài làm tối đa MAX_TEXT_CHARS ký tự trước khi gửi.
#    Tránh prompt quá dài → response cần dài theo → dễ bị truncate.
#
# 3. TÁCH PROMPT + DATA: prompt ngắn gọn, không nhắc lại schema dài trong text,
#    để token budget dành cho output có ý nghĩa.
#
# 4. JSON REPAIR fallback: nếu provider khác (không hỗ trợ structured output)
#    trả về JSON cụt, hàm _repair_json() cố tự vá trước khi báo lỗi.
#
# ── Để đổi provider ──
# Thay AI_API_URL trong .env. Nếu provider không hỗ trợ response_schema,
# xóa responseMimeType + responseSchema khỏi generationConfig
# → fallback về _repair_json() + parse thông thường.

MAX_TEXT_CHARS = 4000   # Cắt bài làm nếu quá dài, tránh prompt bloat

# Schema mô tả JSON mong muốn — dùng cho Gemini Structured Output
# LƯU Ý: Gemini Schema API yêu cầu type viết HOA (STRING, NUMBER, OBJECT, ARRAY)
# và dùng camelCase cho config keys (responseMimeType, responseSchema).
# Tham khảo: https://ai.google.dev/api/generate-content#v1beta.Schema
_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "score": {"type": "NUMBER"},
        "criteria": {
            "type": "OBJECT",
            "properties": {
                "content":   {"type": "NUMBER"},
                "language":  {"type": "NUMBER"},
                "structure": {"type": "NUMBER"}
            },
            "required": ["content", "language", "structure"]
        },
        "strengths":  {"type": "ARRAY", "items": {"type": "STRING"}},
        "weaknesses": {"type": "ARRAY", "items": {"type": "STRING"}},
        "corrections": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "original":    {"type": "STRING"},
                    "corrected":   {"type": "STRING"},
                    "explanation": {"type": "STRING"}
                },
                "required": ["original", "corrected", "explanation"]
            }
        },
        "suggestions":       {"type": "ARRAY", "items": {"type": "STRING"}},
        "detailed_feedback": {"type": "STRING"}
    }
}


def _repair_json(raw: str) -> dict:
    """
    Cố sửa JSON bị cắt nửa chừng (Unterminated string / missing brackets).
    Dùng làm fallback khi provider KHÔNG hỗ trợ Structured Output.
    Thuật toán v2: phân tích stack bracket/quote để đóng đúng thứ tự.
    """
    s = raw.strip()
    if s.startswith('```'):
        s = s.split('\n', 1)[-1].rsplit('```', 1)[0].strip()

    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # Phân tích stack để tìm đúng ký tự cần đóng
    stack = []
    in_string = False
    escape_next = False
    for ch in s:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            if in_string:
                in_string = False
                if stack and stack[-1] == '"':
                    stack.pop()
            else:
                in_string = True
                stack.append('"')
        elif not in_string:
            if ch in ('{', '['):
                stack.append(ch)
            elif ch == '}' and stack and stack[-1] == '{':
                stack.pop()
            elif ch == ']' and stack and stack[-1] == '[':
                stack.pop()

    closing = []
    for token in reversed(stack):
        if token == '"':
            closing.append('"')
        elif token == '{':
            closing.append('}')
        elif token == '[':
            closing.append(']')

    attempt = s + ''.join(closing)
    try:
        return json.loads(attempt)
    except json.JSONDecodeError:
        pass

    # Brute-force fallback
    for _ in range(8):
        for ch in ['"', ']', '}']:
            try:
                return json.loads(attempt + ch)
            except json.JSONDecodeError:
                pass
        attempt += '}'

    raise ValueError("Không thể tự sửa JSON bị cắt")


def call_ai_api(text, image_path=None):
    """
    Gọi Gemini API để chấm bài, trả dict feedback.
    Nếu không có AI_API_KEY → dummy feedback (demo mode).
    """
    if not AI_API_KEY:
        return _dummy_feedback(text)

    # ── 1. Cắt bài làm nếu quá dài (tránh prompt bloat) ──
    text_for_ai = text[:MAX_TEXT_CHARS]
    if len(text) > MAX_TEXT_CHARS:
        text_for_ai += f"\n\n[... Bài bị cắt tại {MAX_TEXT_CHARS} ký tự do giới hạn hệ thống ...]"

    # ── 2. Prompt ngắn gọn — KHÔNG nhắc lại schema dài trong text ──
    prompt = (
        "Bạn là giáo viên Việt Nam chấm bài học sinh. "
        "Hãy đọc bài làm dưới đây và chấm điểm theo các tiêu chí: "
        "nội dung (content), ngôn ngữ (language), cấu trúc (structure). "
        "Cho điểm từng tiêu chí từ 0–10, tính điểm tổng (score) là trung bình cộng. "
        "Nêu 2–3 điểm mạnh (strengths), 2–3 điểm yếu (weaknesses), "
        "tối đa 3 lỗi cụ thể cần sửa (corrections), "
        "2–3 gợi ý cải thiện (suggestions), "
        "và một đoạn nhận xét tổng quan ngắn gọn (detailed_feedback, tối đa 3 câu). "
        "Trả lời HOÀN TOÀN bằng tiếng Việt.\n\n"
        f"BÀI LÀM:\n{text_for_ai}"
    )

    try:
        # ── 3. Auto-correct URL: v1/ → v1beta/ (responseSchema chỉ hỗ trợ v1beta) ──
        api_url = AI_API_URL
        import re as _re
                # Auto-correct /v1/ → /v1beta/ (responseSchema chỉ hoạt động trên v1beta)
        if '/v1/models/' in api_url:
            api_url = api_url.replace('/v1/models/', '/v1beta/models/')

        # ── 4. Build payload ──
        parts = [{"text": prompt}]

        if image_path:
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], image_path)
            if os.path.exists(full_path):
                with open(full_path, 'rb') as f:
                    img_b64 = base64.b64encode(f.read()).decode('utf-8')
                ext = os.path.splitext(image_path)[1].lower()
                mime = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                        '.png': 'image/png', '.webp': 'image/webp',
                        '.gif': 'image/gif'}.get(ext, 'image/jpeg')
                parts.append({"inline_data": {"mime_type": mime, "data": img_b64}})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.3,
                # maxOutputTokens đủ cho feedback ngắn gọn (không cần 2048)
                # Với structured output, Gemini tự đảm bảo JSON hợp lệ trước khi cắt
                "maxOutputTokens": 2048,
                # ── KEY FIX: Structured Output ──
                # Buộc Gemini dùng constrained decoding → JSON luôn hợp lệ,
                # không bao giờ bị Unterminated string dù token limit bị chạm.
                "responseMimeType": "application/json",
                "responseSchema": _RESPONSE_SCHEMA
            }
        }

        resp = http_requests.post(
            f"{api_url}?key={AI_API_KEY}",
            json=payload,
            timeout=45,
            headers={"Content-Type": "application/json"}
        )
        if not resp.ok:
            try:
                err_body = resp.json()
                err_msg = err_body.get('error', {}).get('message', resp.text[:300])
            except Exception:
                err_msg = resp.text[:300]
            app.logger.error(f'Gemini API {resp.status_code}: {err_msg}')
            raise Exception(f'Gemini API lỗi {resp.status_code}: {err_msg}')
        resp.raise_for_status()
        data = resp.json()

        # Kiểm tra finish_reason để log cảnh báo nếu bị cắt
        candidate = data['candidates'][0]
        finish_reason = candidate.get('finishReason', '')
        if finish_reason not in ('STOP', 'MAX_TOKENS', ''):
            app.logger.warning(f'Gemini finish_reason={finish_reason}')

        raw = candidate['content']['parts'][0]['text'].strip()

        # Với structured output, json.loads() thường thành công ngay.
        # Nếu không (provider khác), dùng _repair_json() làm safety net.
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            app.logger.warning('json.loads failed, trying _repair_json()')
            return _repair_json(raw)

    except http_requests.exceptions.Timeout:
        app.logger.error('AI API timeout')
        return _dummy_feedback(text, error='Timeout kết nối AI (>45s)')
    except Exception as e:
        app.logger.error(f'AI API error: {e}')
        return _dummy_feedback(text, error=str(e))

def _dummy_feedback(text, error=None):
    """Phản hồi mẫu khi demo mode hoặc lỗi"""
    note = f' [Lỗi: {error}]' if error else ' [DEMO MODE — Không có API Key]'
    return {
        "score": 7.5,
        "criteria": {"content": 7, "language": 8, "structure": 7},
        "strengths": [
            "Bài viết có nội dung rõ ràng, dễ theo dõi",
            "Cấu trúc câu mạch lạc, đúng ngữ pháp"
        ],
        "weaknesses": [
            "Cần bổ sung thêm dẫn chứng cụ thể",
            "Một số đoạn cần khai triển ý sâu hơn"
        ],
        "corrections": [
            {
                "original": "(Đây là lỗi mẫu demo)",
                "corrected": "(Đây là cách sửa mẫu)",
                "explanation": "Nhận xét mẫu từ hệ thống demo — thêm AI_API_KEY để có phản hồi thật"
            }
        ],
        "suggestions": [
            "Đọc thêm tài liệu tham khảo để làm phong phú nội dung",
            "Luyện tập viết đoạn văn mỗi ngày"
        ],
        "detailed_feedback": (
            f"Đây là phản hồi demo.{note} "
            "Bài làm của em có chất lượng trung bình khá. "
            "Em đã nắm được cấu trúc cơ bản, nhưng cần cố gắng hơn "
            "trong việc lập luận và dẫn chứng."
        )
    }


# ─── TEMPLATE FILTER ──────────────────────────────────────────────────────────

@app.template_filter('score_color')
def score_color(score):
    """Trả về class CSS neon theo mức điểm"""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return 'neon-red'
    if s >= 8:
        return 'neon-green'
    elif s >= 6:
        return 'neon-yellow'
    elif s >= 4:
        return 'neon-orange'
    return 'neon-red'


@app.context_processor
def inject_globals():
    user = get_current_user()
    avatar_url = None
    if user and user['avatar_path']:
        avatar_url = url_for('uploaded_file', filename=user['avatar_path'])
    return dict(current_user=user, avatar_url=avatar_url)


# ─── ROUTES: AUTH ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        display_name = request.form.get('display_name', '').strip()
        email = request.form.get('email', '').strip()

        # Validate username (server-side, chặt)
        ok, msg = validate_username(username)
        if not ok:
            flash(msg, 'error')
            return render_template('register.html')

        if not password:
            flash('Mật khẩu không được để trống.', 'error')
            return render_template('register.html')
        if len(password) < 6:
            flash('Mật khẩu phải có ít nhất 6 ký tự.', 'error')
            return render_template('register.html')

        # Sanitize display_name
        clean_display = sanitize_display_name(display_name) or username

        conn = get_db()
        try:
            conn.execute(
                'INSERT INTO users (username, password_hash, display_name, email) VALUES (?, ?, ?, ?)',
                (username, generate_password_hash(password), clean_display, email)
            )
            conn.commit()
            flash('Đăng ký thành công! Vui lòng đăng nhập.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Tên đăng nhập đã tồn tại.', 'error')
        finally:
            conn.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f"Chào mừng, {user['display_name'] or user['username']}!", 'success')
            return redirect(url_for('dashboard'))

        flash('Sai tên đăng nhập hoặc mật khẩu.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Đã đăng xuất.', 'info')
    return redirect(url_for('login'))


# ─── ROUTES: PROFILE ──────────────────────────────────────────────────────────

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = get_current_user()
    if request.method == 'POST':
        display_name = sanitize_display_name(request.form.get('display_name', '').strip())
        email = request.form.get('email', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        conn = get_db()

        # Xử lý avatar upload
        new_avatar_path = user['avatar_path'] if user['avatar_path'] else ''
        if 'avatar' in request.files:
            avatar_file = request.files['avatar']
            if avatar_file and avatar_file.filename:
                valid, msg = validate_image(avatar_file)
                if not valid:
                    flash(f'Lỗi ảnh đại diện: {msg}', 'error')
                    conn.close()
                    return render_template('profile.html', user=user)
                try:
                    # Xóa avatar cũ nếu có
                    if user['avatar_path']:
                        old_path = os.path.join(app.config['UPLOAD_FOLDER'], user['avatar_path'])
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    new_avatar_path = save_and_resize_image(avatar_file, avatar_file.filename)
                except ValueError as e:
                    flash(str(e), 'error')
                except Exception as e:
                    app.logger.error(f'Avatar save error: {e}')
                    flash('Không thể lưu ảnh đại diện, vui lòng thử lại.', 'error')
                    conn.close()
                    return render_template('profile.html', user=user)

        if new_password:
            if new_password != confirm_password:
                flash('Mật khẩu mới không khớp.', 'error')
                conn.close()
                return render_template('profile.html', user=user)
            if len(new_password) < 6:
                flash('Mật khẩu mới phải có ít nhất 6 ký tự.', 'error')
                conn.close()
                return render_template('profile.html', user=user)
            conn.execute(
                'UPDATE users SET display_name=?, email=?, avatar_path=?, password_hash=? WHERE id=?',
                (display_name, email, new_avatar_path, generate_password_hash(new_password), session['user_id'])
            )
        else:
            conn.execute(
                'UPDATE users SET display_name=?, email=?, avatar_path=? WHERE id=?',
                (display_name, email, new_avatar_path, session['user_id'])
            )
        conn.commit()
        conn.close()
        flash('Thông tin đã được cập nhật!', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html', user=user)


# ─── ROUTES: DASHBOARD ────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    conn = get_db()
    submissions = conn.execute(
        'SELECT * FROM submissions WHERE user_id = ? ORDER BY submitted_at DESC',
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return render_template('dashboard.html', user=user, submissions=submissions)


# ─── ROUTES: SUBMIT ───────────────────────────────────────────────────────────

@app.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    user = get_current_user()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content_text = request.form.get('content_text', '').strip()

        if not title or not content_text:
            flash('Tiêu đề và nội dung bài làm không được để trống.', 'error')
            return render_template('submit.html', user=user)

        image_path = ''
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                # Server-side validation — không tin client
                valid, msg = validate_image(file)
                if not valid:
                    flash(f'Lỗi ảnh: {msg}', 'error')
                    return render_template('submit.html', user=user)
                try:
                    image_path = save_and_resize_image(file, file.filename)
                except ValueError as e:
                    # ValueError = ảnh quá lớn sau khi nén hết mức
                    flash(str(e), 'error')
                    return render_template('submit.html', user=user)
                except Exception as e:
                    app.logger.error(f'Image save error: {e}')
                    flash('Không thể lưu ảnh, vui lòng thử lại.', 'error')
                    return render_template('submit.html', user=user)

        # ── AI chấm bài ──
        # Kết quả AI được lưu nguyên vào DB trước khi redirect.
        # Route detail sẽ load từ DB và parse — không bao giờ render trực tiếp từ response.
        feedback = call_ai_api(content_text, image_path if image_path else None)
        score = float(feedback.get('score', 0))

        conn = get_db()
        cursor = conn.execute(
            '''INSERT INTO submissions
               (user_id, title, content_text, image_path, ai_feedback_json, score)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (session['user_id'], title, content_text, image_path,
             json.dumps(feedback, ensure_ascii=False), score)
        )
        sub_id = cursor.lastrowid
        conn.commit()
        conn.close()

        flash('Nộp bài thành công! AI đã chấm xong.', 'success')
        return redirect(url_for('detail', submission_id=sub_id))

    return render_template('submit.html', user=user)


# ─── ROUTES: DETAIL ───────────────────────────────────────────────────────────

@app.route('/submission/<int:submission_id>')
@login_required
def detail(submission_id):
    conn = get_db()
    sub = conn.execute('SELECT * FROM submissions WHERE id = ?', (submission_id,)).fetchone()
    conn.close()

    if not sub:
        abort(404)
    if sub['user_id'] != session['user_id']:
        abort(403)

    feedback = {}
    try:
        feedback = json.loads(sub['ai_feedback_json'])
    except Exception:
        pass

    user = get_current_user()
    return render_template('detail.html', user=user, sub=sub, feedback=feedback)


# ─── SERVE UPLOADS (bảo mật: chỉ chủ sở hữu xem được) ─────────────────────

@app.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    conn = get_db()
    # Cho phép xem: submission của user hiện tại HOẶC avatar của bất kỳ user nào
    sub = conn.execute(
        'SELECT id FROM submissions WHERE image_path = ? AND user_id = ?',
        (filename, session['user_id'])
    ).fetchone()
    avatar_owner = conn.execute(
        'SELECT id FROM users WHERE avatar_path = ?', (filename,)
    ).fetchone()
    conn.close()
    if not sub and not avatar_owner:
        abort(403)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)



# ─── ROUTES: DELETE SUBMISSION ────────────────────────────────────────────────

@app.route('/submission/<int:submission_id>/delete', methods=['POST'])
@login_required
def delete_submission(submission_id):
    conn = get_db()
    sub = conn.execute(
        'SELECT * FROM submissions WHERE id = ? AND user_id = ?',
        (submission_id, session['user_id'])
    ).fetchone()

    if not sub:
        conn.close()
        abort(404)

    # Xóa file ảnh đính kèm nếu có
    if sub['image_path']:
        img_file = os.path.join(app.config['UPLOAD_FOLDER'], sub['image_path'])
        if os.path.exists(img_file):
            try:
                os.remove(img_file)
            except Exception as e:
                app.logger.error(f'Delete image error: {e}')

    conn.execute('DELETE FROM submissions WHERE id = ?', (submission_id,))
    conn.commit()
    conn.close()

    flash('Đã xóa bài làm thành công.', 'success')
    return redirect(url_for('dashboard'))


# ─── ROUTES: RESUBMIT ─────────────────────────────────────────────────────────

@app.route('/submission/<int:submission_id>/resubmit', methods=['GET', 'POST'])
@login_required
def resubmit(submission_id):
    conn = get_db()
    sub = conn.execute(
        'SELECT * FROM submissions WHERE id = ? AND user_id = ?',
        (submission_id, session['user_id'])
    ).fetchone()
    conn.close()

    if not sub:
        abort(404)

    user = get_current_user()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content_text = request.form.get('content_text', '').strip()

        if not title or not content_text:
            flash('Tiêu đề và nội dung bài làm không được để trống.', 'error')
            return render_template('resubmit.html', user=user, sub=sub)

        # Xử lý ảnh: giữ ảnh cũ nếu không upload mới
        image_path = sub['image_path']
        remove_image = request.form.get('remove_image') == '1'

        if remove_image:
            if image_path:
                old_file = os.path.join(app.config['UPLOAD_FOLDER'], image_path)
                if os.path.exists(old_file):
                    try:
                        os.remove(old_file)
                    except Exception:
                        pass
            image_path = ''

        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                valid, msg = validate_image(file)
                if not valid:
                    flash(f'Lỗi ảnh: {msg}', 'error')
                    return render_template('resubmit.html', user=user, sub=sub)
                try:
                    if image_path:
                        old_file = os.path.join(app.config['UPLOAD_FOLDER'], image_path)
                        if os.path.exists(old_file):
                            os.remove(old_file)
                    image_path = save_and_resize_image(file, file.filename)
                except ValueError as e:
                    flash(str(e), 'error')
                    return render_template('resubmit.html', user=user, sub=sub)
                except Exception as e:
                    app.logger.error(f'Image save error: {e}')
                    flash('Không thể lưu ảnh, vui lòng thử lại.', 'error')
                    return render_template('resubmit.html', user=user, sub=sub)

        feedback = call_ai_api(content_text, image_path if image_path else None)
        score = float(feedback.get('score', 0))

        conn = get_db()
        update_sql = (
            "UPDATE submissions "
            "SET title=?, content_text=?, image_path=?, ai_feedback_json=?, "
            "score=?, submitted_at=datetime('now') "
            "WHERE id=?"
        )
        conn.execute(update_sql,
            (title, content_text, image_path,
             json.dumps(feedback, ensure_ascii=False), score, submission_id))
        conn.commit()
        conn.close()

        flash('Đã nộp lại bài thành công! AI đã chấm xong.', 'success')
        return redirect(url_for('detail', submission_id=submission_id))

    return render_template('resubmit.html', user=user, sub=sub)


# ─── ROUTES: EXPORT CSV ───────────────────────────────────────────────────────

import csv
import io

@app.route('/export/csv')
@login_required
def export_csv():
    conn = get_db()
    submissions = conn.execute(
        'SELECT * FROM submissions WHERE user_id = ? ORDER BY submitted_at DESC',
        (session['user_id'],)
    ).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)

    writer.writerow([
        'STT', 'Tiêu đề', 'Nội dung bài làm',
        'Điểm tổng', 'Điểm nội dung', 'Điểm ngôn ngữ', 'Điểm cấu trúc',
        'Điểm mạnh', 'Điểm yếu', 'Gợi ý cải thiện',
        'Nhận xét tổng quan', 'Ảnh đính kèm (URL)',
        'Thời gian nộp'
    ])

    base_url = request.host_url.rstrip('/')

    for i, sub in enumerate(submissions, 1):
        feedback = {}
        try:
            feedback = json.loads(sub['ai_feedback_json'])
        except Exception:
            pass

        criteria = feedback.get('criteria', {})
        strengths = ' | '.join(feedback.get('strengths', []))
        weaknesses = ' | '.join(feedback.get('weaknesses', []))
        suggestions = ' | '.join(feedback.get('suggestions', []))

        image_url = ''
        if sub['image_path']:
            image_url = f"{base_url}/uploads/{sub['image_path']}"

        writer.writerow([
            i,
            sub['title'],
            sub['content_text'],
            sub['score'],
            criteria.get('content', ''),
            criteria.get('language', ''),
            criteria.get('structure', ''),
            strengths,
            weaknesses,
            suggestions,
            feedback.get('detailed_feedback', ''),
            image_url,
            sub['submitted_at']
        ])

    # UTF-8 BOM for Excel Vietnamese support
    csv_bytes = ('\ufeff' + output.getvalue()).encode('utf-8')

    from flask import Response
    return Response(
        csv_bytes,
        mimetype='text/csv; charset=utf-8',
        headers={
            'Content-Disposition': 'attachment; filename="bai_lam_cua_toi.csv"'
        }
    )



# ─── ERROR HANDLERS ───────────────────────────────────────────────────────────

@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', code=403, msg='Bạn không có quyền truy cập.'), 403

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404, msg='Trang không tồn tại.'), 404

@app.errorhandler(413)
def too_large(e):
    return render_template('error.html', code=413, msg='File quá lớn (tối đa 5MB).'), 413


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db()
    app.run(debug=True, port=5000)

# placeholder - will be replaced
