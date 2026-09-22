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
    phase = check_in.get("phase", "morning")
    phase_tasks = {
        "morning": """这是早间教练。根据今早体重、睡眠、精力、酸痛、可用时间、最近14天趋势和前一天完整记录，制定今天三餐与运动计划。若有前一天记录，用模型综合完成度、运动量、饮食结构、排便、恢复和目标给前一天打0-100分；评分必须解释依据，不得因为减重越多就机械加分。若没有前一天记录，score必须为null。输出严格JSON：
{"title":"今日重点，不超过20字","summary":"两句以内","previousDayEvaluation":{"date":"被评分日期或空字符串","score":null,"summary":"评分说明","wins":["优点"],"improve":["改进点"]},"meals":{"breakfast":"具体早餐","lunch":"具体午餐","dinner":"具体晚餐","principles":"份量、蛋白质和饮水原则"},"training":{"loadLabel":"训练强度","items":["4-6条含动作、组数或时间的安排"]},"recovery":"安全和恢复提醒"}""",
        "midday": """这是训练后教练。比较早间训练建议与用户实际运动、时长、主观强度和完成程度，立即生成针对实际使用肌群的拉伸和冷身建议。疼痛时不得建议强行拉伸。输出严格JSON：
{"title":"训练后重点，不超过20字","summary":"对本次完成情况的简短反馈","stretch":{"duration":"总拉伸时长","items":["4-6条含部位、动作和保持时间的拉伸"],"safety":"安全提醒"}}""",
        "evening": """这是晚间复盘教练。结合今天早间状态与计划、实际运动、全天饮食、排便和用户感受做简短复盘，不提前给出最终分数；说明明早模型评分会参考哪些实际数据。不要诊断疾病或精确估算无法确认的热量。输出严格JSON：
{"title":"今日复盘，不超过20字","summary":"两句以内","wins":["1-3条今天做得好的地方"],"tomorrowScoreFactors":["2-4条明早评分会参考的因素"],"tonightTip":"今晚可执行的恢复建议"}""",
    }
    task = phase_tasks.get(phase, phase_tasks["morning"])
    content = [{"type": "text", "text": json.dumps({"本次阶段": phase, "本次反馈": check_in, "最近14天历史": history, "任务": task}, ensure_ascii=False)}]
    for image in images[:4]:
        if isinstance(image, str) and image.startswith("data:image/"):
            content.append({"type": "image_url", "image_url": {"url": image, "detail": "low"}})
    system = """你是一名谨慎的中文健身教练 Agent。你通过一天中早间、训练后、晚间三个阶段连续工作。必须只输出任务指定结构的有效 JSON，不要 Markdown。建议应具体、温和、可执行；不得诊断疾病。评分属于基于历史记录的模型估计而非医学结论，并应避免体重数字偏见。"""
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
