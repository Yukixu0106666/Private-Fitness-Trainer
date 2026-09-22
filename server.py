import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.abspath(__file__))
MAX_BODY = 18 * 1024 * 1024
DB_PATH = os.path.join(ROOT, "fitness.db")
SESSION_DAYS = 30


def load_env():
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def is_postgres():
    return bool(os.environ.get("DATABASE_URL"))


@contextmanager
def db():
    if is_postgres():
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError("使用 DATABASE_URL 需要安装 psycopg[binary]") from error
        connection = psycopg.connect(os.environ["DATABASE_URL"])
        try:
            yield connection, "%s"
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    else:
        connection = sqlite3.connect(DB_PATH)
        try:
            yield connection, "?"
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def query(connection, sql, params=()):
    return connection.execute(sql, params)


def init_db():
    with db() as (connection, placeholder):
        if not is_postgres():
            existing = query(connection, "SELECT name FROM sqlite_master WHERE type='table' AND name='records'").fetchone()
            if existing:
                columns = {row[1] for row in query(connection, "PRAGMA table_info(records)").fetchall()}
                if "user_id" not in columns:
                    query(connection, "ALTER TABLE records RENAME TO records_legacy")
        if is_postgres():
            statements = [
                """CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL, created_at TEXT NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at TEXT NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS records (
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    date TEXT NOT NULL, record_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, PRIMARY KEY (user_id, date))""",
            ]
        else:
            statements = [
                """CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL, created_at TEXT NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at TEXT NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS records (
                    user_id INTEGER NOT NULL, date TEXT NOT NULL, record_json TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, date))""",
            ]
        for statement in statements:
            query(connection, statement)


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260000)
    return f"pbkdf2_sha256$260000${salt.hex()}${digest.hex()}"


def verify_password(password, encoded):
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return algorithm == "pbkdf2_sha256" and hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def now():
    return datetime.now(timezone.utc)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    with db() as (connection, placeholder):
        query(connection, f"INSERT INTO sessions (token_hash, user_id, expires_at) VALUES ({placeholder}, {placeholder}, {placeholder})",
              (token_hash(token), user_id, (now() + timedelta(days=SESSION_DAYS)).isoformat()))
    return token


def user_from_token(token):
    if not token:
        return None
    with db() as (connection, placeholder):
        row = query(connection, f"SELECT users.id, users.email FROM sessions JOIN users ON users.id=sessions.user_id WHERE token_hash={placeholder} AND expires_at>{placeholder}",
                    (token_hash(token), now().isoformat())).fetchone()
    return {"id": row[0], "email": row[1]} if row else None


def delete_session(token):
    if token:
        with db() as (connection, placeholder):
            query(connection, f"DELETE FROM sessions WHERE token_hash={placeholder}", (token_hash(token),))


def list_records(user_id):
    with db() as (connection, placeholder):
        rows = query(connection, f"SELECT record_json FROM records WHERE user_id={placeholder} ORDER BY date DESC", (user_id,)).fetchall()
    return [json.loads(row[0]) for row in rows]


def save_record(user_id, record):
    date = record.get("date")
    if not isinstance(date, str) or not date or not isinstance(record.get("plan"), dict):
        raise ValueError("记录缺少有效日期或教练计划")
    timestamp = now().isoformat()
    serialized = json.dumps(record, ensure_ascii=False)
    with db() as (connection, placeholder):
        if is_postgres():
            sql = """INSERT INTO records (user_id,date,record_json,created_at,updated_at)
                     VALUES (%s,%s,%s,%s,%s) ON CONFLICT (user_id,date)
                     DO UPDATE SET record_json=EXCLUDED.record_json, updated_at=EXCLUDED.updated_at"""
        else:
            sql = """INSERT INTO records (user_id,date,record_json,created_at,updated_at)
                     VALUES (?,?,?,?,?) ON CONFLICT(user_id,date)
                     DO UPDATE SET record_json=excluded.record_json, updated_at=excluded.updated_at"""
        query(connection, sql, (user_id, date, serialized, timestamp, timestamp))


def call_model(payload):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("服务端未配置 OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "qwen/qwen3.8-27b")
    if api_key.startswith("gsk_") and base_url == "https://api.openai.com/v1":
        base_url, model = "https://api.groq.com/openai/v1", model
    request = Request(f"{base_url}/chat/completions", data=json.dumps(
        {"model": model, "temperature": 0.3, "response_format": {"type": "json_object"}, "messages": payload}).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "User-Agent": "fitness-coach/1.0"}, method="POST")
    try:
        with urlopen(request, timeout=90) as response:
            result = json.loads(response.read().decode())
    except HTTPError as error:
        raise RuntimeError(f"模型服务返回 {error.code}: {error.read().decode(errors='replace')[:500]}") from error
    except URLError as error:
        raise RuntimeError(f"无法连接模型服务：{error.reason}") from error
    return json.loads(result["choices"][0]["message"]["content"])


def prompt_for(body):
    check_in, history, images = body.get("checkIn", {}), body.get("history", [])[:14], body.get("images", [])
    language = "English" if body.get("language") == "en" else "Chinese"
    content = [{"type": "text", "text": json.dumps({"今日反馈": check_in, "最近14天历史": history,
        "任务": f"结合饮食、排便、体重趋势和恢复情况生成明天安全具体的训练饮食建议。部分饮食记录不要推断全天营养，不要诊断疾病。Use {language} for every user-facing JSON value."}, ensure_ascii=False)}]
    for image in images[:4]:
        if isinstance(image, str) and image.startswith("data:image/"):
            content.append({"type": "image_url", "image_url": {"url": image, "detail": "low"}})
    system = """你是一名谨慎的健身教练。Output all user-facing text in {language}. 输出严格 JSON，不要 Markdown，字段必须为：
{"title":"不超过20字","summary":"2句以内","training":{"loadLabel":"不超过8字","items":["4-6条具体动作、组数、时间"]},"nutrition":{"analysis":"饮食结构分析","estimatedCalories":"可选范围或未知","nextDayTip":"明日饮食建议"},"recovery":"恢复和安全提醒","disclaimer":"固定提示"}""".replace("{language}", language)
    return [{"role": "system", "content": system}, {"role": "user", "content": content}]


class Handler(SimpleHTTPRequestHandler):
    def request_path(self):
        return self.path.split("?", 1)[0]

    def token(self):
        cookies = SimpleCookie(self.headers.get("Cookie", ""))
        return cookies["session"].value if "session" in cookies else None

    def current_user(self):
        return user_from_token(self.token())

    def do_GET(self):
        path = self.request_path()
        if path == "/api/me":
            self.send_json(200, {"user": self.current_user()})
        elif path == "/api/records":
            user = self.current_user()
            if not user:
                self.send_json(401, {"error": "请先登录"})
            else:
                self.send_json(200, {"records": list_records(user["id"])})
        else:
            super().do_GET()

    def do_POST(self):
        path = self.request_path()
        if path not in ("/api/register", "/api/login", "/api/logout", "/api/coach", "/api/records"):
            self.send_error(404)
            return
        if path == "/api/logout":
            delete_session(self.token())
            self.send_json(200, {"ok": True}, clear_cookie=True)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY:
                self.send_json(413, {"error": "请求过大"})
                return
            body = json.loads(self.rfile.read(length))
            if path in ("/api/register", "/api/login"):
                email, password = str(body.get("email", "")).strip().lower(), str(body.get("password", ""))
                if len(email) < 5 or "@" not in email or len(password) < 8:
                    self.send_json(400, {"error": "请输入有效邮箱和至少 8 位密码"})
                    return
                with db() as (connection, placeholder):
                    row = query(connection, f"SELECT id,password_hash FROM users WHERE email={placeholder}", (email,)).fetchone()
                    if path == "/api/register":
                        if row:
                            self.send_json(409, {"error": "该邮箱已注册"})
                            return
                        cur = query(connection, f"INSERT INTO users (email,password_hash,created_at) VALUES ({placeholder},{placeholder},{placeholder}) RETURNING id",
                                    (email, hash_password(password), now().isoformat()))
                        user_id = cur.fetchone()[0]
                    elif not row or not verify_password(password, row[1]):
                        self.send_json(401, {"error": "邮箱或密码错误"})
                        return
                    else:
                        user_id = row[0]
                self.send_json(200, {"user": {"id": user_id, "email": email}}, cookie=create_session(user_id))
                return
            user = self.current_user()
            if not user:
                self.send_json(401, {"error": "请先登录"})
                return
            if path == "/api/records":
                save_record(user["id"], body)
                self.send_json(201, {"ok": True})
            else:
                self.send_json(200, {"plan": call_model(prompt_for(body))})
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
        except (OSError, RuntimeError) as error:
            self.send_json(502, {"error": str(error)})

    def send_json(self, status, payload, cookie=None, clear_cookie=False):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "http://localhost:8000"))
        self.send_header("Access-Control-Allow-Credentials", "true")
        if cookie or clear_cookie:
            value = "" if clear_cookie else cookie
            max_age = 0 if clear_cookie else SESSION_DAYS * 86400
            secure = "; Secure" if os.environ.get("COOKIE_SECURE", "").lower() == "true" or self.headers.get("X-Forwarded-Proto") == "https" else ""
            self.send_header("Set-Cookie", f"session={value}; Max-Age={max_age}; Path=/; HttpOnly; SameSite=Lax{secure}")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "http://localhost:8000"))
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


if __name__ == "__main__":
    load_env()
    init_db()
    os.chdir(ROOT)
    print("健身教练已启动：http://localhost:8000")
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8000"))), Handler).serve_forever()
