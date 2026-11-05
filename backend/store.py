import os, json, sqlite3, hashlib, uuid
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path(os.getenv("VERDICT_DATA_DIR", str(ROOT / "runtime")))
RUNTIME.mkdir(parents=True, exist_ok=True)
DB = RUNTIME / "verdict.sqlite3"


def now():
    return datetime.now(timezone.utc).isoformat()


def uid(prefix=""):
    return prefix + uuid.uuid4().hex[:16]


def canon(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(x):
    return hashlib.sha256(
        (x if isinstance(x, bytes) else canon(x).encode())
    ).hexdigest()


@contextmanager
def connect():
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
    finally:
        c.close()


def init():
    with connect() as c:
        c.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,tenant TEXT NOT NULL,revision INTEGER NOT NULL,body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT,case_id TEXT,at TEXT,kind TEXT,data TEXT,previous TEXT,hash TEXT);
        CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,tenant TEXT,role TEXT,expires REAL);
        CREATE TABLE IF NOT EXISTS requests(hash TEXT PRIMARY KEY,case_id TEXT,tenant TEXT,body TEXT,expires REAL,completed INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY,case_id TEXT,tenant TEXT,content BLOB,mime TEXT,name TEXT);
        CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY,case_id TEXT,tenant TEXT,digest TEXT,body TEXT,status TEXT,expires REAL);
        CREATE TABLE IF NOT EXISTS webhooks(id TEXT PRIMARY KEY,status TEXT);
        CREATE TABLE IF NOT EXISTS cloud_outbox(case_id TEXT PRIMARY KEY,revision INTEGER,payload TEXT,error TEXT);
        CREATE TABLE IF NOT EXISTS cloud_sync(case_id TEXT PRIMARY KEY,revision INTEGER,at TEXT);
        """)


def audit(c, case_id, kind, data):
    prior = c.execute(
        "SELECT hash FROM audit WHERE case_id=? ORDER BY seq DESC LIMIT 1", (case_id,)
    ).fetchone()
    record = {
        "case_id": case_id,
        "at": now(),
        "kind": kind,
        "data": data,
        "previous": prior["hash"] if prior else "",
    }
    h = digest(record)
    c.execute(
        "INSERT INTO audit(case_id,at,kind,data,previous,hash) VALUES(?,?,?,?,?,?)",
        (case_id, record["at"], kind, canon(data), record["previous"], h),
    )


def enqueue(c, tenant, body):
    if os.getenv("VERDICT_SUPABASE_MIRROR") != "true" or tenant != "operator":
        return
    rows = c.execute(
        "SELECT * FROM audit WHERE case_id=? ORDER BY seq", (body["id"],)
    ).fetchall()
    history = [{**dict(r), "data": json.loads(r["data"])} for r in rows]
    payload = {
        "case_id": body["id"],
        "tenant": tenant,
        "revision": body["revision"],
        "body": body,
        "audit": history,
        "snapshot_sha256": digest({"body": body, "audit": history}),
        "updated_at": now(),
    }
    c.execute(
        "INSERT OR REPLACE INTO cloud_outbox VALUES(?,?,?,NULL)",
        (body["id"], body["revision"], canon(payload)),
    )


def create(tenant, body):
    body = {
        **body,
        "id": body.get("id", uid("V-")),
        "created_at": now(),
        "updated_at": now(),
        "revision": 1,
        "evidence": body.get("evidence", []),
        "requests": [],
        "analysis": None,
    }
    with connect() as c:
        c.execute(
            "INSERT INTO cases VALUES(?,?,?,?)", (body["id"], tenant, 1, canon(body))
        )
        audit(
            c,
            body["id"],
            "case_created",
            {"mode": body["mode"], "title": body["title"]},
        )
        enqueue(c, tenant, body)
        c.commit()
    return body


def get(case_id, tenant):
    with connect() as c:
        r = c.execute(
            "SELECT body FROM cases WHERE id=? AND tenant=?", (case_id, tenant)
        ).fetchone()
    if not r:
        raise KeyError("Case not found")
    return json.loads(r["body"])


def listing(tenant):
    with connect() as c:
        rows = c.execute(
            "SELECT body FROM cases WHERE tenant=? ORDER BY rowid DESC", (tenant,)
        ).fetchall()
    return [json.loads(r["body"]) for r in rows]


def save(body, tenant, kind, data, expected=None, extra=None):
    expected = body["revision"] if expected is None else expected
    body = {**body, "revision": expected + 1, "updated_at": now()}
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        r = c.execute(
            "UPDATE cases SET revision=?,body=? WHERE id=? AND tenant=? AND revision=?",
            (body["revision"], canon(body), body["id"], tenant, expected),
        )
        if r.rowcount != 1:
            raise ValueError("Case changed. Refresh and review the newest evidence.")
        if extra:
            extra(c)
        audit(c, body["id"], kind, data)
        enqueue(c, tenant, body)
        c.commit()
    return body


def timeline(case_id):
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM audit WHERE case_id=? ORDER BY seq", (case_id,)
        ).fetchall()
    return [{**dict(r), "data": json.loads(r["data"])} for r in rows]


def verify_timeline(rows):
    previous = ""
    for r in rows:
        rec = {k: r[k] for k in ["case_id", "at", "kind", "data", "previous"]}
        if r["previous"] != previous or digest(rec) != r["hash"]:
            return False
        previous = r["hash"]
    return True
