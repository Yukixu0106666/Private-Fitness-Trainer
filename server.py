import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.abspath(__file__))
MAX_BODY = 18 * 1024 * 1024
DB_PATH = os.path.join(ROOT, "fitness.db")
SESSION_DAYS = 30
MAX_AGENT_STEPS = 4
MAX_TOOL_ERRORS = 2
VECTOR_CANDIDATES = 20
VECTOR_RESULTS = 5
EMBEDDING_BATCH_SIZE = 32


def env_float(name):
    value = os.environ.get(name)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError as error:
        raise RuntimeError(f"{name} 必须是数字") from error


def embedding_dimensions():
    try:
        dimensions = int(os.environ.get("EMBEDDING_DIMENSIONS", "1536"))
    except ValueError as error:
        raise RuntimeError("EMBEDDING_DIMENSIONS 必须是整数") from error
    if not 1 <= dimensions <= 2000:
        raise RuntimeError("EMBEDDING_DIMENSIONS 必须位于 1-2000，才能建立 pgvector HNSW 索引")
    return dimensions


def vector_store_enabled():
    return is_postgres() and bool(os.environ.get("EMBEDDING_API_KEY"))


def estimate_cost(prompt_tokens=0, completion_tokens=0, input_rate=None, output_rate=None):
    if input_rate is None and output_rate is None:
        return None
    input_rate = input_rate or 0.0
    output_rate = output_rate or 0.0
    return round((prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000, 8)


class TraceRecorder:
    def __init__(self, user_id, date, phase):
        self.trace_id = uuid.uuid4().hex
        self.user_id = user_id
        self.date = date
        self.phase = phase
        self.started_at = now().isoformat()
        self.started_clock = time.perf_counter()
        self.events = []
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.embedding_tokens = 0
        self.estimated_cost_usd = 0.0
        self.cost_known = True
        self.model = ""
        self.status = "running"
        self.error = None

    @contextmanager
    def span(self, name, **attributes):
        started = time.perf_counter()
        try:
            yield
        except Exception as error:
            self.event(name, started, "error", {**attributes, "errorType": type(error).__name__})
            raise
        else:
            self.event(name, started, "ok", attributes)

    def event(self, name, started, status="ok", attributes=None):
        self.events.append({
            "name": name,
            "status": status,
            "durationMs": round((time.perf_counter() - started) * 1000, 2),
            "attributes": attributes or {},
        })

    def record_model_call(self, model, started, usage):
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        has_usage = "prompt_tokens" in usage or "completion_tokens" in usage
        cost = estimate_cost(
            prompt, completion,
            env_float("MODEL_INPUT_COST_PER_1M"),
            env_float("MODEL_OUTPUT_COST_PER_1M"),
        ) if has_usage else None
        self.model = model
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        if cost is None:
            self.cost_known = False
        else:
            self.estimated_cost_usd += cost
        self.event("llm.chat", started, attributes={
            "model": model, "promptTokens": prompt,
            "completionTokens": completion, "estimatedCostUsd": cost,
        })

    def record_embedding_call(self, model, started, usage, input_count):
        tokens = int(usage.get("prompt_tokens") or usage.get("total_tokens") or 0)
        has_usage = "prompt_tokens" in usage or "total_tokens" in usage
        cost = estimate_cost(tokens, 0, env_float("EMBEDDING_COST_PER_1M"), 0.0) if has_usage else None
        self.embedding_tokens += tokens
        if cost is None:
            self.cost_known = False
        else:
            self.estimated_cost_usd += cost
        self.event("llm.embedding", started, attributes={
            "model": model, "inputCount": input_count,
            "tokens": tokens, "estimatedCostUsd": cost,
        })

    def finish(self, status, error=None):
        self.status = status
        self.error = error

    def summary(self):
        return {
            "traceId": self.trace_id,
            "durationMs": round((time.perf_counter() - self.started_clock) * 1000, 2),
            "promptTokens": self.prompt_tokens,
            "completionTokens": self.completion_tokens,
            "embeddingTokens": self.embedding_tokens,
            "estimatedCostUsd": round(self.estimated_cost_usd, 8) if self.cost_known else None,
        }


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
            connection.execute("SET search_path TO public, extensions")
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
                """CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    profile_json TEXT NOT NULL, updated_at TEXT NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS coach_outputs (
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    date TEXT NOT NULL, phase TEXT NOT NULL, output_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL, model TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, PRIMARY KEY (user_id, date, phase))""",
                """CREATE TABLE IF NOT EXISTS request_traces (
                    trace_id TEXT PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    date TEXT NOT NULL, phase TEXT NOT NULL, status TEXT NOT NULL,
                    duration_ms DOUBLE PRECISION NOT NULL, model TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL, completion_tokens INTEGER NOT NULL,
                    embedding_tokens INTEGER NOT NULL, estimated_cost_usd DOUBLE PRECISION,
                    events_json TEXT NOT NULL, error_text TEXT, created_at TEXT NOT NULL)""",
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
                """CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id INTEGER PRIMARY KEY, profile_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS coach_outputs (
                    user_id INTEGER NOT NULL, date TEXT NOT NULL, phase TEXT NOT NULL,
                    output_json TEXT NOT NULL, metadata_json TEXT NOT NULL,
                    model TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, date, phase))""",
                """CREATE TABLE IF NOT EXISTS request_traces (
                    trace_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
                    date TEXT NOT NULL, phase TEXT NOT NULL, status TEXT NOT NULL,
                    duration_ms REAL NOT NULL, model TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL, completion_tokens INTEGER NOT NULL,
                    embedding_tokens INTEGER NOT NULL, estimated_cost_usd REAL,
                    events_json TEXT NOT NULL, error_text TEXT, created_at TEXT NOT NULL)""",
            ]
        for statement in statements:
            query(connection, statement)
        query(connection, """CREATE INDEX IF NOT EXISTS request_traces_user_created
            ON request_traces (user_id, created_at DESC)""")
        if vector_store_enabled():
            dimensions = embedding_dimensions()
            query(connection, "CREATE EXTENSION IF NOT EXISTS vector")
            query(connection, f"""CREATE TABLE IF NOT EXISTS fitness_memory_chunks (
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                date TEXT NOT NULL, chunk_type TEXT NOT NULL, content TEXT NOT NULL,
                content_hash TEXT NOT NULL, metadata_json TEXT NOT NULL,
                embedding_model TEXT NOT NULL, embedding vector({dimensions}) NOT NULL,
                updated_at TEXT NOT NULL, PRIMARY KEY (user_id, date, chunk_type))""")
            query(connection, """CREATE INDEX IF NOT EXISTS fitness_memory_chunks_embedding_hnsw
                ON fitness_memory_chunks USING hnsw (embedding vector_cosine_ops)""")
            query(connection, """CREATE INDEX IF NOT EXISTS fitness_memory_chunks_user_date
                ON fitness_memory_chunks (user_id, date DESC)""")
    migrate_legacy_memory()


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


OUTPUT_FIELDS = {"morning": "plan", "midday": "stretch", "evening": "eveningReview"}


def fact_records(user_id, limit=None, before_or_on=None):
    conditions = ["user_id={placeholder}"]
    params = [user_id]
    with db() as (connection, placeholder):
        conditions = [item.format(placeholder=placeholder) for item in conditions]
        if before_or_on:
            conditions.append(f"date<={placeholder}")
            params.append(before_or_on)
        sql = f"SELECT record_json FROM records WHERE {' AND '.join(conditions)} ORDER BY date DESC"
        if limit is not None:
            sql += f" LIMIT {placeholder}"
            params.append(int(limit))
        rows = query(connection, sql, tuple(params)).fetchall()
    return [json.loads(row[0]) for row in rows]


def coach_outputs(user_id, date=None):
    with db() as (connection, placeholder):
        params = [user_id]
        sql = f"SELECT date,phase,output_json,metadata_json,model,updated_at FROM coach_outputs WHERE user_id={placeholder}"
        if date:
            sql += f" AND date={placeholder}"
            params.append(date)
        rows = query(connection, sql, tuple(params)).fetchall()
    return [{
        "date": row[0], "phase": row[1], "output": json.loads(row[2]),
        "metadata": json.loads(row[3]), "model": row[4], "updatedAt": row[5],
    } for row in rows]


def merge_outputs(records, outputs):
    by_date = {record.get("date"): dict(record) for record in records}
    for output in outputs:
        record = by_date.get(output["date"])
        field = OUTPUT_FIELDS.get(output["phase"])
        if record is not None and field:
            record[field] = output["output"]
            record.setdefault("coachMetadata", {})[output["phase"]] = output["metadata"]
    return list(by_date.values())


def list_records(user_id):
    records = fact_records(user_id)
    return merge_outputs(records, coach_outputs(user_id))


def record_by_date(user_id, date, include_outputs=True):
    with db() as (connection, placeholder):
        row = query(connection, f"SELECT record_json FROM records WHERE user_id={placeholder} AND date={placeholder}", (user_id, date)).fetchone()
    if not row:
        return None
    record = json.loads(row[0])
    if include_outputs:
        record = merge_outputs([record], coach_outputs(user_id, date))[0]
    return record


def load_profile(user_id):
    with db() as (connection, placeholder):
        row = query(connection, f"SELECT profile_json,updated_at FROM user_profiles WHERE user_id={placeholder}", (user_id,)).fetchone()
    if not row:
        return {"confirmed": {}, "updatedAt": None}
    return {"confirmed": json.loads(row[0]), "updatedAt": row[1]}


def update_profile(user_id, values, allow_clear=False):
    supported = ("height", "goal", "equipment", "dietaryPreferences", "constraints")
    supplied = {key: values.get(key) for key in supported if key in values}
    if not supplied:
        return
    current = load_profile(user_id)["confirmed"]
    for key, value in supplied.items():
        if value in (None, "", []):
            if allow_clear:
                current.pop(key, None)
        else:
            current[key] = value
    timestamp = now().isoformat()
    serialized = json.dumps(current, ensure_ascii=False)
    with db() as (connection, placeholder):
        if is_postgres():
            sql = """INSERT INTO user_profiles (user_id,profile_json,updated_at) VALUES (%s,%s,%s)
                     ON CONFLICT (user_id) DO UPDATE SET profile_json=EXCLUDED.profile_json,updated_at=EXCLUDED.updated_at"""
        else:
            sql = """INSERT INTO user_profiles (user_id,profile_json,updated_at) VALUES (?,?,?)
                     ON CONFLICT(user_id) DO UPDATE SET profile_json=excluded.profile_json,updated_at=excluded.updated_at"""
        query(connection, sql, (user_id, serialized, timestamp))


def save_record(user_id, record):
    if not isinstance(record, dict):
        raise ValueError("记录格式无效")
    date = record.get("date")
    if not isinstance(date, str):
        raise ValueError("记录格式无效")
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError("记录缺少有效日期") from error
    timestamp = now().isoformat()
    profile_update = record.get("_profile") if isinstance(record.get("_profile"), dict) else {}
    invalidate_phase = record.get("_invalidatePhase")
    facts = {key: value for key, value in record.items() if key not in set(OUTPUT_FIELDS.values()) | {"coachMetadata", "_profile", "_invalidatePhase"}}
    serialized = json.dumps(facts, ensure_ascii=False)
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
        if invalidate_phase in OUTPUT_FIELDS:
            query(connection, f"DELETE FROM coach_outputs WHERE user_id={placeholder} AND date={placeholder} AND phase={placeholder}",
                  (user_id, date, invalidate_phase))
    update_profile(user_id, facts)
    update_profile(user_id, profile_update, allow_clear=True)


def persist_check_in(user_id, check_in):
    if not isinstance(check_in, dict):
        raise ValueError("打卡格式无效")
    phase = check_in.get("phase", "morning")
    if phase not in OUTPUT_FIELDS:
        raise ValueError("未知教练阶段")
    date = str(check_in.get("date", ""))
    record = record_by_date(user_id, date, include_outputs=False) or {"date": date}
    phase_facts = {key: value for key, value in check_in.items() if key != "phase"}
    record[phase] = phase_facts
    for key in ("goal", "height"):
        if phase_facts.get(key) not in (None, ""):
            record[key] = phase_facts[key]
    record["_invalidatePhase"] = phase
    save_record(user_id, record)


def save_coach_output(user_id, date, phase, output, metadata, model):
    if phase not in OUTPUT_FIELDS:
        raise ValueError("未知教练阶段")
    timestamp = now().isoformat()
    serialized_output = json.dumps(output, ensure_ascii=False)
    serialized_metadata = json.dumps(metadata, ensure_ascii=False)
    with db() as (connection, placeholder):
        if is_postgres():
            sql = """INSERT INTO coach_outputs (user_id,date,phase,output_json,metadata_json,model,created_at,updated_at)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (user_id,date,phase)
                     DO UPDATE SET output_json=EXCLUDED.output_json,metadata_json=EXCLUDED.metadata_json,
                     model=EXCLUDED.model,updated_at=EXCLUDED.updated_at"""
        else:
            sql = """INSERT INTO coach_outputs (user_id,date,phase,output_json,metadata_json,model,created_at,updated_at)
                     VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(user_id,date,phase)
                     DO UPDATE SET output_json=excluded.output_json,metadata_json=excluded.metadata_json,
                     model=excluded.model,updated_at=excluded.updated_at"""
        query(connection, sql, (user_id, date, phase, serialized_output, serialized_metadata, model, timestamp, timestamp))


def migrate_legacy_memory():
    with db() as (connection, placeholder):
        rows = query(connection, "SELECT user_id,date,record_json FROM records ORDER BY date").fetchall()
        profile_users = {row[0] for row in query(connection, "SELECT user_id FROM user_profiles").fetchall()}
    profile_seeds = {}
    for user_id, date, serialized in rows:
        record = json.loads(serialized)
        legacy_metadata = record.get("coachMetadata") or {}
        moved = False
        for phase, field in OUTPUT_FIELDS.items():
            output = record.get(field)
            if not isinstance(output, dict):
                continue
            metadata = legacy_metadata.get(phase) or {
                "dataStatus": "legacy",
                "sources": [{"id": f"record:{date}", "type": "legacy_record", "date": date}],
                "missingData": [],
                "migrated": True,
            }
            save_coach_output(user_id, date, phase, output, metadata, "legacy-unknown")
            moved = True
        facts = {key: value for key, value in record.items() if key not in set(OUTPUT_FIELDS.values()) | {"coachMetadata"}}
        if moved or facts != record:
            with db() as (connection, placeholder):
                query(connection, f"UPDATE records SET record_json={placeholder},updated_at={placeholder} WHERE user_id={placeholder} AND date={placeholder}",
                      (json.dumps(facts, ensure_ascii=False), now().isoformat(), user_id, date))
        if user_id not in profile_users:
            profile_seeds[user_id] = facts
    for user_id, facts in profile_seeds.items():
        update_profile(user_id, facts)


FUNCTION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_fitness_record_by_date",
            "description": "读取当前登录用户某一天已保存的早间计划、实际训练和晚间复盘。比较计划与实际完成情况时使用。",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {"date": {"type": "string", "description": "YYYY-MM-DD 日期"}},
                "required": ["date"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_fitness_records",
            "description": "读取当前登录用户最近几天的精简健身记录，用于判断睡眠、恢复、训练和饮食趋势。",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 14}},
                "required": ["days"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_weight_trend",
            "description": "计算当前登录用户最近几天有效晨起体重的平均值和变化量，不对体重变化做医学诊断。",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "minimum": 2, "maximum": 14}},
                "required": ["days"],
                "additionalProperties": False,
            },
        },
    },
]


def compact_record(record):
    morning = record.get("morning") or {key: record.get(key) for key in ("weight", "sleep", "energy", "soreness", "notes")}
    midday = record.get("midday") or ({"workout": record.get("workout")} if record.get("workout") else None)
    evening = record.get("evening")
    plan = record.get("plan") or {}
    compact = {
        "date": record.get("date"), "goal": record.get("goal"),
        "morning": morning, "midday": midday, "evening": evening,
        "assignedTraining": (plan.get("training") or {}).get("items", []),
    }
    if isinstance(evening, dict) and isinstance(evening.get("food"), str):
        compact["evening"] = {**evening, "food": evening["food"][:600]}
    return compact


def numeric(value):
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def derived_stats(records):
    chronological = list(reversed(records))
    weight_samples = []
    sleep_values = []
    energy_values = []
    workout_days = 0
    workout_minutes = 0
    for record in chronological:
        morning = record.get("morning") or record
        weight = numeric(morning.get("weight"))
        sleep = numeric(morning.get("sleep"))
        energy = numeric(morning.get("energy"))
        if weight is not None:
            weight_samples.append({"date": record.get("date"), "weightKg": round(weight, 2)})
        if sleep is not None:
            sleep_values.append(sleep)
        if energy is not None:
            energy_values.append(energy)
        midday = record.get("midday") or {}
        exercises = midday.get("exercises") or []
        minutes = numeric(midday.get("totalDuration"))
        if exercises or (minutes is not None and minutes > 0):
            workout_days += 1
        if minutes is not None and minutes > 0:
            workout_minutes += round(minutes)
    weights = [sample["weightKg"] for sample in weight_samples]
    dates = [record.get("date") for record in chronological if record.get("date")]
    return {
        "period": {"from": dates[0] if dates else None, "to": dates[-1] if dates else None},
        "recordCount": len(records),
        "weight": {
            "sampleCount": len(weights), "samples": weight_samples,
            "averageKg": round(sum(weights) / len(weights), 2) if weights else None,
            "changeKg": round(weights[-1] - weights[0], 2) if len(weights) > 1 else None,
        },
        "averageSleepHours": round(sum(sleep_values) / len(sleep_values), 2) if sleep_values else None,
        "averageEnergy": round(sum(energy_values) / len(energy_values), 2) if energy_values else None,
        "workoutDays": workout_days,
        "workoutMinutes": workout_minutes,
    }


def record_embedding_document(record):
    compact = compact_record(record)
    return json.dumps(compact, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def request_embeddings(texts, trace=None):
    if not texts:
        return []
    api_key = os.environ.get("EMBEDDING_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 EMBEDDING_API_KEY")
    base_url = os.environ.get("EMBEDDING_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
    payload = {"model": model, "input": texts, "dimensions": embedding_dimensions()}
    request = Request(
        f"{base_url}/embeddings",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "fitness-coach/1.0",
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode())
    except HTTPError as error:
        detail = error.read().decode(errors="replace")[:500]
        if trace:
            trace.event("llm.embedding", started, "error", {"model": model, "httpStatus": error.code})
        raise RuntimeError(f"Embedding 服务返回 {error.code}: {detail}") from error
    except URLError as error:
        if trace:
            trace.event("llm.embedding", started, "error", {"model": model, "errorType": "URLError"})
        raise RuntimeError(f"无法连接 Embedding 服务：{error.reason}") from error
    ordered = sorted(result.get("data") or [], key=lambda item: item.get("index", 0))
    embeddings = [item.get("embedding") for item in ordered]
    if len(embeddings) != len(texts) or any(not isinstance(item, list) for item in embeddings):
        raise RuntimeError("Embedding 服务返回数量不匹配")
    dimensions = embedding_dimensions()
    if any(len(item) != dimensions for item in embeddings):
        raise RuntimeError(f"Embedding 向量维度必须为 {dimensions}")
    if trace:
        trace.record_embedding_call(model, started, result.get("usage") or {}, len(texts))
    return embeddings


def vector_literal(values):
    return "[" + ",".join(format(float(value), ".10g") for value in values) + "]"


def ensure_record_embeddings(user_id, records, trace=None):
    if not vector_store_enabled() or not records:
        return {"enabled": False, "indexed": 0}
    model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
    pending = []
    with db() as (connection, placeholder):
        for record in records:
            date = record.get("date")
            if not date:
                continue
            content = record_embedding_document(record)
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            row = query(connection, f"""SELECT content_hash,embedding_model
                FROM fitness_memory_chunks WHERE user_id={placeholder} AND date={placeholder}
                AND chunk_type='daily_facts'""", (user_id, date)).fetchone()
            if not row or row[0] != content_hash or row[1] != model:
                pending.append((date, content, content_hash, {
                    "date": date,
                    "hasMorning": bool(record.get("morning")),
                    "hasMidday": bool(record.get("midday")),
                    "hasEvening": bool(record.get("evening")),
                }))
    if not pending:
        return {"enabled": True, "indexed": 0}
    embeddings = []
    for start in range(0, len(pending), EMBEDDING_BATCH_SIZE):
        batch = pending[start:start + EMBEDDING_BATCH_SIZE]
        embeddings.extend(request_embeddings([item[1] for item in batch], trace=trace))
    with db() as (connection, _):
        for (date, content, content_hash, metadata), embedding in zip(pending, embeddings):
            query(connection, """INSERT INTO fitness_memory_chunks
                (user_id,date,chunk_type,content,content_hash,metadata_json,embedding_model,embedding,updated_at)
                VALUES (%s,%s,'daily_facts',%s,%s,%s,%s,%s::vector,%s)
                ON CONFLICT (user_id,date,chunk_type) DO UPDATE SET
                content=EXCLUDED.content,content_hash=EXCLUDED.content_hash,
                metadata_json=EXCLUDED.metadata_json,embedding_model=EXCLUDED.embedding_model,
                embedding=EXCLUDED.embedding,updated_at=EXCLUDED.updated_at""", (
                    user_id, date, content, content_hash,
                    json.dumps(metadata, ensure_ascii=False), model,
                    vector_literal(embedding), now().isoformat(),
                ))
    return {"enabled": True, "indexed": len(pending)}


def keyword_overlap(query_text, content):
    pattern = r"[a-zA-Z0-9]+|[\u4e00-\u9fff]"
    query_terms = set(re.findall(pattern, query_text.lower()))
    content_terms = set(re.findall(pattern, content.lower()))
    return len(query_terms & content_terms) / len(query_terms) if query_terms else 0.0


def rerank_candidates(candidates, query_text, reference_date, limit=VECTOR_RESULTS):
    try:
        reference = datetime.strptime(reference_date, "%Y-%m-%d")
    except ValueError:
        reference = None
    ranked = []
    for candidate in candidates:
        similarity = max(0.0, min(1.0, float(candidate.get("similarity") or 0.0)))
        recency = 0.0
        if reference:
            try:
                age = max(0, (reference - datetime.strptime(candidate["date"], "%Y-%m-%d")).days)
                recency = 1 / (1 + age)
            except (KeyError, ValueError):
                pass
        lexical = keyword_overlap(query_text, candidate.get("content", ""))
        score = 0.75 * similarity + 0.15 * recency + 0.10 * lexical
        ranked.append({**candidate, "rerankScore": round(score, 6), "lexicalScore": round(lexical, 6)})
    return sorted(ranked, key=lambda item: (item["rerankScore"], item.get("date", "")), reverse=True)[:limit]


def hybrid_vector_retrieve(user_id, query_text, before_or_on, trace=None, limit=VECTOR_RESULTS):
    if not vector_store_enabled() or not query_text.strip():
        return []
    embedding = request_embeddings([query_text], trace=trace)[0]
    vector = vector_literal(embedding)
    model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
    with db() as (connection, _):
        rows = query(connection, """SELECT date,content,metadata_json,
            1 - (embedding <=> %s::vector) AS similarity
            FROM fitness_memory_chunks
            WHERE user_id=%s AND date<=%s AND embedding_model=%s
            ORDER BY embedding <=> %s::vector LIMIT %s""", (
                vector, user_id, before_or_on, model, vector, VECTOR_CANDIDATES,
            )).fetchall()
    candidates = [{
        "date": row[0], "content": row[1],
        "metadata": json.loads(row[2]), "similarity": float(row[3]),
    } for row in rows]
    return rerank_candidates(candidates, query_text, before_or_on, limit=limit)


def persist_trace(trace):
    summary = trace.summary()
    with db() as (connection, placeholder):
        query(connection, f"""INSERT INTO request_traces
            (trace_id,user_id,date,phase,status,duration_ms,model,prompt_tokens,
             completion_tokens,embedding_tokens,estimated_cost_usd,events_json,error_text,created_at)
            VALUES ({','.join([placeholder] * 14)})""", (
                trace.trace_id, trace.user_id, trace.date, trace.phase, trace.status,
                summary["durationMs"], trace.model, summary["promptTokens"],
                summary["completionTokens"], summary["embeddingTokens"],
                summary["estimatedCostUsd"], json.dumps(trace.events, ensure_ascii=False),
                trace.error, trace.started_at,
            ))


def safe_persist_trace(trace):
    try:
        persist_trace(trace)
        return True
    except Exception:
        return False


def percentile(values, percent):
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    index = max(0, math.ceil(percent / 100 * len(ordered)) - 1)
    return round(ordered[index], 2)


def trace_metrics(user_id, limit=100):
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 100
    limit = max(1, min(1000, limit))
    with db() as (connection, placeholder):
        rows = query(connection, f"""SELECT duration_ms,estimated_cost_usd,prompt_tokens,
            completion_tokens,embedding_tokens,status FROM request_traces
            WHERE user_id={placeholder} ORDER BY created_at DESC LIMIT {placeholder}""",
            (user_id, limit)).fetchall()
    durations = [row[0] for row in rows]
    costs = [row[1] for row in rows if row[1] is not None]
    return {
        "requestCount": len(rows),
        "p50LatencyMs": percentile(durations, 50),
        "p95LatencyMs": percentile(durations, 95),
        "averageCostUsd": round(sum(costs) / len(costs), 8) if costs else None,
        "totalCostUsd": round(sum(costs), 8) if costs else None,
        "costedRequestCount": len(costs),
        "promptTokens": sum(row[2] for row in rows),
        "completionTokens": sum(row[3] for row in rows),
        "embeddingTokens": sum(row[4] for row in rows),
        "successRate": round(sum(row[5] == "ok" for row in rows) / len(rows), 4) if rows else None,
    }


def recent_traces(user_id, limit=20):
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 20
    limit = max(1, min(100, limit))
    with db() as (connection, placeholder):
        rows = query(connection, f"""SELECT trace_id,date,phase,status,duration_ms,model,
            prompt_tokens,completion_tokens,embedding_tokens,estimated_cost_usd,
            events_json,error_text,created_at FROM request_traces
            WHERE user_id={placeholder} ORDER BY created_at DESC LIMIT {placeholder}""",
            (user_id, limit)).fetchall()
    return [{
        "traceId": row[0], "date": row[1], "phase": row[2], "status": row[3],
        "durationMs": row[4], "model": row[5], "promptTokens": row[6],
        "completionTokens": row[7], "embeddingTokens": row[8],
        "estimatedCostUsd": row[9], "events": json.loads(row[10]),
        "error": row[11], "createdAt": row[12],
    } for row in rows]


def previous_date(date):
    return (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")


def build_memory_context(user_id, check_in, trace=None):
    date = str(check_in.get("date", ""))
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError("打卡日期必须为 YYYY-MM-DD") from error
    phase = check_in.get("phase", "morning")
    profile = load_profile(user_id)
    current = record_by_date(user_id, date)
    recent_facts = fact_records(user_id, limit=14, before_or_on=date)
    stats = derived_stats(recent_facts)
    prior = record_by_date(user_id, previous_date(date)) if phase == "morning" else None
    semantic_matches = []
    vector_status = {"enabled": vector_store_enabled(), "indexed": 0, "retrieved": 0}
    if vector_store_enabled():
        started = time.perf_counter()
        try:
            vector_facts = fact_records(user_id, before_or_on=date)
            index_status = ensure_record_embeddings(user_id, vector_facts, trace=trace)
            query_text = json.dumps(check_in, ensure_ascii=False, sort_keys=True)
            semantic_matches = hybrid_vector_retrieve(user_id, query_text, date, trace=trace)
            vector_status.update(index_status)
            vector_status["retrieved"] = len(semantic_matches)
            if trace:
                trace.event("retrieval.hybrid_pgvector", started, attributes=vector_status)
        except Exception as error:
            vector_status["error"] = type(error).__name__
            if trace:
                trace.event("retrieval.hybrid_pgvector", started, "error", vector_status)
    sources = []
    if profile["updatedAt"]:
        sources.append({"id": "profile:confirmed", "type": "confirmed_profile", "updatedAt": profile["updatedAt"]})
    if current:
        sources.append({"id": f"record:{date}", "type": "daily_record", "date": date})
        if current.get("plan"):
            sources.append({"id": f"coach_output:{date}:morning", "type": "coach_output", "date": date, "phase": "morning"})
    if prior:
        sources.append({"id": f"record:{prior['date']}", "type": "daily_record", "date": prior["date"]})
        if prior.get("plan"):
            sources.append({"id": f"coach_output:{prior['date']}:morning", "type": "coach_output", "date": prior["date"], "phase": "morning"})
    if stats["recordCount"]:
        sources.append({
            "id": f"derived:recent14:{stats['period']['from']}:{stats['period']['to']}",
            "type": "server_derived_stats", "period": stats["period"],
            "recordCount": stats["recordCount"],
        })
    if semantic_matches:
        sources.append({
            "id": f"hybrid_pgvector:{date}",
            "type": "hybrid_pgvector_reranked",
            "dates": [item["date"] for item in semantic_matches],
            "resultCount": len(semantic_matches),
        })
    missing = []
    confirmed = profile["confirmed"]
    for key in ("goal", "height"):
        if confirmed.get(key) in (None, ""):
            missing.append(f"profile.{key}")
    if not current:
        missing.append("currentDay")
    if phase == "morning" and not prior:
        missing.append("previousDay")
    if phase == "midday":
        if not current or not current.get("morning"):
            missing.append("currentDay.morning")
        if not current or not current.get("plan"):
            missing.append("currentDay.morningPlan")
    if phase == "evening":
        if not current or not current.get("morning"):
            missing.append("currentDay.morning")
        if not current or not current.get("midday"):
            missing.append("currentDay.midday")
    data_status = "complete" if not missing else "minimal" if not current else "partial"
    provenance = {
        "dataStatus": data_status,
        "sources": sources,
        "missingData": missing,
        "retrievedAt": now().isoformat(),
    }
    memory = {
        "confirmedProfile": confirmed,
        "currentDay": compact_record(current) if current else None,
        "previousDay": compact_record(prior) if prior else None,
        "recent14DayStats": stats,
        "semanticMatches": [json.loads(item["content"]) for item in semantic_matches],
        "vectorRetrieval": vector_status,
        "provenance": provenance,
    }
    return memory, provenance


def execute_function(user_id, name, arguments):
    if name == "get_fitness_record_by_date":
        date = str(arguments.get("date", ""))
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError as error:
            raise ValueError("工具参数 date 必须为 YYYY-MM-DD") from error
        record = record_by_date(user_id, date)
        return {"found": bool(record), "record": compact_record(record) if record else None}
    if name == "get_recent_fitness_records":
        days = max(1, min(14, int(arguments.get("days", 7))))
        records = fact_records(user_id, limit=days)
        return {"days": days, "records": [compact_record(item) for item in records]}
    if name == "calculate_weight_trend":
        days = max(2, min(14, int(arguments.get("days", 7))))
        trend = derived_stats(fact_records(user_id, limit=days))["weight"]
        return {"days": days, **trend}
    raise ValueError(f"不允许的工具：{name}")


def request_model(base_url, api_key, model, messages, tools_enabled=True, require_tool=False, trace=None):
    request_body = {
        "model": model,
        "temperature": 0.3,
        "messages": messages,
    }
    if tools_enabled:
        request_body.update({
            "tools": FUNCTION_TOOLS,
            "tool_choice": "required" if require_tool else "auto",
            "parallel_tool_calls": False,
        })
    else:
        request_body["response_format"] = {"type": "json_object"}
    request = Request(f"{base_url}/chat/completions", data=json.dumps(request_body).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "User-Agent": "fitness-coach/1.0"}, method="POST")
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=90) as response:
            result = json.loads(response.read().decode())
    except HTTPError as error:
        detail = error.read().decode(errors="replace")[:500]
        if trace:
            trace.event("llm.chat", started, "error", {"model": model, "httpStatus": error.code})
        raise RuntimeError(f"模型服务返回 {error.code}: {detail}") from error
    except URLError as error:
        if trace:
            trace.event("llm.chat", started, "error", {"model": model, "errorType": "URLError"})
        raise RuntimeError(f"无法连接模型服务：{error.reason}") from error
    if trace:
        trace.record_model_call(model, started, result.get("usage") or {})
    return result["choices"][0]["message"]


def tool_error(code, message, retryable):
    return {"ok": False, "error": {"code": code, "message": message, "retryable": retryable}}


def tool_source(name, arguments, output):
    if name == "get_fitness_record_by_date" and output.get("found"):
        date = arguments.get("date")
        return {"id": f"tool:record:{date}", "type": "tool_daily_record", "date": date}
    if name == "get_recent_fitness_records":
        dates = [record.get("date") for record in output.get("records", []) if record.get("date")]
        return {"id": f"tool:recent:{':'.join(dates)}", "type": "tool_recent_records", "dates": dates}
    if name == "calculate_weight_trend":
        dates = [sample.get("date") for sample in output.get("samples", []) if sample.get("date")]
        return {"id": f"tool:weight:{':'.join(dates)}", "type": "tool_derived_weight_trend", "dates": dates}
    return None


def parse_model_content(message):
    if not message.get("content"):
        raise RuntimeError("模型没有返回计划内容")
    return json.loads(message["content"])


def call_model(payload, user_id, trace=None):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("服务端未配置 OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "qwen/qwen3.8-27b")
    if api_key.startswith("gsk_") and base_url == "https://api.openai.com/v1":
        base_url, model = "https://api.groq.com/openai/v1", model
    messages = list(payload)
    used_tools = []
    tool_sources = []
    seen_calls = set()
    tool_errors = 0
    duplicate_calls = 0
    forced_reason = None
    allowed_tools = {tool["function"]["name"] for tool in FUNCTION_TOOLS}
    for step in range(MAX_AGENT_STEPS):
        message = request_model(base_url, api_key, model, messages, tools_enabled=True, require_tool=False, trace=trace)
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return parse_model_content(message), used_tools, {
                "forcedFinish": False, "toolErrors": tool_errors, "duplicateCalls": duplicate_calls,
                "model": model, "toolSources": tool_sources,
            }
        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": tool_calls})
        for tool_call in tool_calls:
            tool_started = time.perf_counter()
            tool_name = (tool_call.get("function") or {}).get("name", "")
            arguments = None
            try:
                arguments = json.loads((tool_call.get("function") or {}).get("arguments") or "{}")
                if not isinstance(arguments, dict):
                    raise ValueError("工具参数必须是 JSON 对象")
                fingerprint = f"{tool_name}:{json.dumps(arguments, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"
            except (json.JSONDecodeError, ValueError) as error:
                tool_errors += 1
                output = tool_error("INVALID_ARGUMENT", f"工具参数无效：{error}", True)
            else:
                if fingerprint in seen_calls:
                    duplicate_calls += 1
                    output = tool_error("DUPLICATE_CALL", "相同工具和参数已经调用过。请使用之前的结果直接完成回答，不要再次调用。", False)
                    forced_reason = "duplicate_tool_call"
                else:
                    seen_calls.add(fingerprint)
                    try:
                        if tool_name not in allowed_tools:
                            raise KeyError(tool_name)
                        output = execute_function(user_id, tool_name, arguments)
                        used_tools.append(tool_name)
                        source = tool_source(tool_name, arguments, output)
                        if source:
                            tool_sources.append(source)
                    except KeyError:
                        tool_errors += 1
                        output = tool_error("UNKNOWN_TOOL", "请求的工具不可用，请使用已有信息完成回答。", False)
                    except (ValueError, TypeError) as error:
                        tool_errors += 1
                        output = tool_error("INVALID_ARGUMENT", str(error), True)
                    except Exception:
                        tool_errors += 1
                        output = tool_error("TOOL_UNAVAILABLE", "历史记录工具暂时不可用，请使用本次输入提供保守建议。", False)
            if trace:
                trace.event("agent.tool", tool_started,
                    "error" if output.get("ok") is False else "ok", {
                        "tool": tool_name,
                        "arguments": arguments if isinstance(arguments, dict) else None,
                        "errorCode": (output.get("error") or {}).get("code"),
                    })
            messages.append({"role": "tool", "tool_call_id": tool_call["id"], "content": json.dumps(output, ensure_ascii=False)})
        if duplicate_calls:
            break
        if tool_errors >= MAX_TOOL_ERRORS:
            forced_reason = "tool_error_budget"
            break
    if forced_reason is None:
        forced_reason = "step_budget"
    messages.append({
        "role": "user",
        "content": "工具调用现已结束。请立即输出任务要求的最终 JSON，不得再调用工具。只能使用服务端固定记忆、本次输入和已经成功返回的工具结果；不得声称使用了固定 provenance 或成功工具结果之外的数据；若 fixedMemory.previousDay 为空，previousDayEvaluation.score 必须为 null。",
    })
    final_message = request_model(base_url, api_key, model, messages, tools_enabled=False, trace=trace)
    return parse_model_content(final_message), used_tools, {
        "forcedFinish": True, "reason": forced_reason,
        "toolErrors": tool_errors, "duplicateCalls": duplicate_calls,
        "model": model, "toolSources": tool_sources,
    }


def prompt_for(body, memory):
    check_in, images = body.get("checkIn", {}), body.get("images", [])
    phase = check_in.get("phase", "morning")
    language = "English" if body.get("language") == "en" else "Chinese"
    phase_tasks = {
        "morning": """这是早间教练。根据今早体重、睡眠、精力、酸痛、可用时间、最近14天趋势和前一天完整记录，制定今天三餐与运动计划。若有前一天记录，用模型综合完成度、运动量、饮食结构、排便、恢复和目标给前一天打0-100分；评分必须解释依据，不得因为减重越多就机械加分。若没有前一天记录，score必须为null。输出严格JSON：
{"title":"今日重点，不超过20字","summary":"两句以内","previousDayEvaluation":{"date":"被评分日期或空字符串","score":null,"summary":"评分说明","wins":["优点"],"improve":["改进点"]},"meals":{"breakfast":"具体早餐","lunch":"具体午餐","dinner":"具体晚餐","principles":"份量、蛋白质和饮水原则"},"training":{"loadLabel":"训练强度","items":["4-6条含动作、组数或时间的安排"]},"recovery":"安全和恢复提醒"}""",
        "midday": """这是训练后教练。比较早间训练建议与用户实际运动、运动量、主观强度和完成程度；每项运动的 amount 是数值，unit 为 minutes（分钟）或 reps（个），totalDuration 只统计按分钟记录的项目。立即生成针对实际使用肌群的拉伸和冷身建议。疼痛时不得建议强行拉伸。输出严格JSON：
{"title":"训练后重点，不超过20字","summary":"对本次完成情况的简短反馈","stretch":{"duration":"总拉伸时长","items":["4-6条含部位、动作和保持时间的拉伸"],"safety":"安全提醒"}}""",
        "evening": """这是晚间复盘教练。结合今天早间状态与计划、实际运动、全天饮食、排便和用户感受做简短复盘，不提前给出最终分数；说明明早模型评分会参考哪些实际数据。不要诊断疾病或精确估算无法确认的热量。输出严格JSON：
{"title":"今日复盘，不超过20字","summary":"两句以内","wins":["1-3条今天做得好的地方"],"tomorrowScoreFactors":["2-4条明早评分会参考的因素"],"tonightTip":"今晚可执行的恢复建议"}""",
    }
    task = phase_tasks.get(phase, phase_tasks["morning"]) + f"\nEvery user-facing JSON value must be written in {language}."
    content = [{"type": "text", "text": json.dumps({"本次阶段": phase, "本次反馈": check_in, "fixedMemory": memory, "任务": task}, ensure_ascii=False)}]
    for image in images[:4]:
        if isinstance(image, str) and image.startswith("data:image/"):
            content.append({"type": "image_url", "image_url": {"url": image, "detail": "low"}})
    system = f"""你是一名谨慎的健身教练 Agent。服务端已按阶段提供 fixedMemory，其中 confirmedProfile 是用户确认信息；currentDay 和 previousDay 的 morning、midday、evening 是用户事实，assignedTraining 是单独保存的 AI 计划，只能用于比较而不能视为实际完成；recent14DayStats 是服务端确定性计算结果；semanticMatches 是经过用户隔离、日期过滤、向量召回与重排的历史事实；provenance 列出固定检索来源。不得猜测固定来源或成功工具结果中没有的数据。工具只用于可选补充，无需为了回答而调用。必须只输出任务指定结构的有效 JSON，不要 Markdown。所有面向用户的JSON值必须使用{language}。建议应具体、温和、可执行；不得诊断疾病。评分属于基于历史记录的模型估计而非医学结论，并应避免体重数字偏见。"""
    return [{"role": "system", "content": system}, {"role": "user", "content": content}]


def require_object(value, path):
    if not isinstance(value, dict):
        raise ValueError(f"模型返回的 {path} 必须是对象")
    return value


def require_text(value, path):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"模型返回的 {path} 必须是非空文本")


def require_text_list(value, path):
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"模型返回的 {path} 必须是文本数组")


def validate_coach_output(output, phase, memory):
    plan = require_object(output, "根节点")
    adjustments = []
    require_text(plan.get("title"), "title")
    require_text(plan.get("summary"), "summary")
    if phase == "morning":
        evaluation = require_object(plan.get("previousDayEvaluation"), "previousDayEvaluation")
        meals = require_object(plan.get("meals"), "meals")
        training = require_object(plan.get("training"), "training")
        for key in ("breakfast", "lunch", "dinner", "principles"):
            require_text(meals.get(key), f"meals.{key}")
        require_text(training.get("loadLabel"), "training.loadLabel")
        require_text_list(training.get("items"), "training.items")
        require_text(plan.get("recovery"), "recovery")
        for key in ("summary",):
            require_text(evaluation.get(key), f"previousDayEvaluation.{key}")
        require_text_list(evaluation.get("wins"), "previousDayEvaluation.wins")
        require_text_list(evaluation.get("improve"), "previousDayEvaluation.improve")
        prior = memory.get("previousDay")
        if not prior:
            if evaluation.get("score") is not None or evaluation.get("date"):
                adjustments.append("cleared_unverified_previous_day_score")
            evaluation["date"] = ""
            evaluation["score"] = None
        else:
            expected_date = prior.get("date", "")
            if evaluation.get("date") != expected_date:
                evaluation["date"] = expected_date
                adjustments.append("corrected_previous_day_date")
            score = numeric(evaluation.get("score"))
            if score is None or not 0 <= score <= 100:
                evaluation["score"] = None
                adjustments.append("removed_invalid_score")
            else:
                evaluation["score"] = round(score)
    elif phase == "midday":
        stretch = require_object(plan.get("stretch"), "stretch")
        require_text(stretch.get("duration"), "stretch.duration")
        require_text_list(stretch.get("items"), "stretch.items")
        require_text(stretch.get("safety"), "stretch.safety")
    elif phase == "evening":
        require_text_list(plan.get("wins"), "wins")
        require_text_list(plan.get("tomorrowScoreFactors"), "tomorrowScoreFactors")
        require_text(plan.get("tonightTip"), "tonightTip")
    else:
        raise ValueError("未知教练阶段")
    return plan, {"passed": True, "adjustments": adjustments}


class Handler(SimpleHTTPRequestHandler):
    def request_path(self):
        return self.path.split("?", 1)[0]

    def end_headers(self):
        if self.request_path() in ("/", "/index.html", "/app.js", "/styles.css"):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def token(self):
        cookies = SimpleCookie(self.headers.get("Cookie", ""))
        return cookies["session"].value if "session" in cookies else None

    def current_user(self):
        return user_from_token(self.token())

    def do_GET(self):
        path = self.request_path()
        params = parse_qs(urlparse(self.path).query)
        if path == "/api/me":
            self.send_json(200, {"user": self.current_user()})
        elif path in ("/api/records", "/api/metrics", "/api/traces"):
            user = self.current_user()
            if not user:
                self.send_json(401, {"error": "请先登录"})
            elif path == "/api/metrics":
                self.send_json(200, trace_metrics(user["id"], params.get("limit", ["100"])[0]))
            elif path == "/api/traces":
                self.send_json(200, {"traces": recent_traces(user["id"], params.get("limit", ["20"])[0])})
            else:
                self.send_json(200, {"records": list_records(user["id"]), "profile": load_profile(user["id"])})
        else:
            super().do_GET()

    def do_POST(self):
        path = self.request_path()
        active_trace = None
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
                self.send_json(201, {"ok": True, "profile": load_profile(user["id"])})
            else:
                check_in = body.get("checkIn") or {}
                phase = check_in.get("phase", "morning")
                date = str(check_in.get("date", ""))
                active_trace = TraceRecorder(user["id"], date, phase)
                with active_trace.span("check_in.persist"):
                    persist_check_in(user["id"], check_in)
                with active_trace.span("memory.build"):
                    memory, provenance = build_memory_context(user["id"], check_in, trace=active_trace)
                with active_trace.span("agent.run"):
                    plan, tools_used, agent_status = call_model(prompt_for(body, memory), user["id"], trace=active_trace)
                source_ids = {source["id"] for source in provenance["sources"]}
                for source in agent_status.get("toolSources", []):
                    if source["id"] not in source_ids:
                        provenance["sources"].append(source)
                        source_ids.add(source["id"])
                with active_trace.span("output.validate"):
                    plan, validation = validate_coach_output(plan, phase, memory)
                metadata = {
                    **provenance,
                    "agent": agent_status,
                    "validation": validation,
                    "optionalToolsUsed": tools_used,
                }
                with active_trace.span("coach_output.persist"):
                    save_coach_output(user["id"], date, phase, plan, metadata, agent_status["model"])
                active_trace.finish("ok")
                observability = active_trace.summary()
                safe_persist_trace(active_trace)
                active_trace = None
                self.send_json(200, {
                    "plan": plan, "toolsUsed": tools_used, "agent": agent_status,
                    "provenance": provenance, "validation": validation,
                    "observability": observability,
                })
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            if active_trace:
                active_trace.finish("error", str(error)[:500])
                safe_persist_trace(active_trace)
            self.send_json(400, {"error": str(error)})
        except (OSError, RuntimeError) as error:
            if active_trace:
                active_trace.finish("error", str(error)[:500])
                safe_persist_trace(active_trace)
            self.send_json(502, {"error": str(error)})
        except Exception as error:
            if active_trace:
                active_trace.finish("error", type(error).__name__)
                safe_persist_trace(active_trace)
            self.send_json(500, {"error": "服务器内部错误"})

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
