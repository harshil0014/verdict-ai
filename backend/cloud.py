"""Optional private Supabase snapshot mirror. SQLite is the primary store.

The durable outbox survives network failure; no cloud success is inferred.
Only operator snapshots are mirrored, not ephemeral demo workspaces.
"""

import os, json, httpx
from store import connect, now, enqueue


def configured():
    return os.getenv("VERDICT_SUPABASE_MIRROR") == "true" and bool(
        os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SECRET_KEY")
    )


def seed_outbox():
    if not configured():
        return
    with connect() as c:
        for row in c.execute(
            "SELECT body FROM cases WHERE tenant='operator'"
        ).fetchall():
            body = json.loads(row["body"])
            done = c.execute(
                "SELECT revision FROM cloud_sync WHERE case_id=?", (body["id"],)
            ).fetchone()
            if not done or done["revision"] < body["revision"]:
                enqueue(c, "operator", body)
        c.commit()


def flush_one():
    if not configured():
        return
    with connect() as c:
        row = c.execute("SELECT * FROM cloud_outbox ORDER BY rowid LIMIT 1").fetchone()
    if not row:
        return
    try:
        r = httpx.post(
            os.environ["SUPABASE_URL"].rstrip("/")
            + "/rest/v1/verdict_snapshots?on_conflict=case_id",
            headers={
                "apikey": os.environ["SUPABASE_SECRET_KEY"],
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            json=json.loads(row["payload"]),
            timeout=12,
        )
        if r.status_code not in (200, 201, 204):
            raise RuntimeError("Supabase HTTP " + str(r.status_code))
        with connect() as c:
            c.execute(
                "INSERT OR REPLACE INTO cloud_sync VALUES(?,?,?)",
                (row["case_id"], row["revision"], now()),
            )
            c.execute(
                "DELETE FROM cloud_outbox WHERE case_id=? AND revision=?",
                (row["case_id"], row["revision"]),
            )
            c.commit()
    except Exception as e:
        message = str(e) if isinstance(e, RuntimeError) else "Network unavailable"
        with connect() as c:
            c.execute(
                "UPDATE cloud_outbox SET error=? WHERE case_id=?",
                (message, row["case_id"]),
            )
            c.commit()


def status():
    with connect() as c:
        pending = c.execute("SELECT count(*) FROM cloud_outbox").fetchone()[0]
        synced = c.execute("SELECT count(*) FROM cloud_sync").fetchone()[0]
        error = c.execute(
            "SELECT error FROM cloud_outbox WHERE error IS NOT NULL LIMIT 1"
        ).fetchone()
    return {
        "configured": configured(),
        "pending": pending,
        "synced_cases": synced,
        "last_error": error["error"] if error else None,
        "primary": "SQLite private server disk",
        "mirror": "Supabase private PostgreSQL snapshots",
    }
