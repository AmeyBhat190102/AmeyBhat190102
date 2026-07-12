"""Thin Postgres layer. psycopg2 with a connection pool; dict rows; JSONB handled."""
import json
from contextlib import contextmanager
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor, Json
from . import config

_pool = None


def _get_pool():
    """Lazy init so importing this module never requires a live database."""
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(minconn=1, maxconn=8, dsn=config.DATABASE_URL)
    return _pool


@contextmanager
def cur():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as c:
                yield c
    finally:
        pool.putconn(conn)


def q1(sql, params=()):
    with cur() as c:
        c.execute(sql, params)
        return c.fetchone()


def qall(sql, params=()):
    with cur() as c:
        c.execute(sql, params)
        return c.fetchall()


def execute(sql, params=()):
    with cur() as c:
        c.execute(sql, params)
        return c.rowcount


# ---------------- settings ----------------
def get_setting(key, default=None):
    row = q1("SELECT value FROM settings WHERE key=%s", (key,))
    return row["value"] if row else default


def set_setting(key, value):
    execute("INSERT INTO settings (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", (key, Json(value)))


def is_paused() -> bool:
    return bool(get_setting("paused", False))


def autonomy() -> int:
    return int(get_setting("autonomy_level", config.DEFAULT_AUTONOMY))


# ---------------- leads ----------------
def get_lead(lead_id):
    return q1("SELECT * FROM leads WHERE id=%s", (lead_id,))


def find_lead_by_email(email):
    return q1("SELECT * FROM leads WHERE lower(email)=lower(%s)", (email,)) if email else None


def find_lead_by_phone(phone):
    return q1("SELECT * FROM leads WHERE phone=%s", (phone,)) if phone else None


def insert_lead(**kw):
    keys = ["segment", "name", "company", "role", "email", "phone", "source", "score", "facts", "state"]
    vals = [kw.get(k) for k in keys]
    vals[8] = Json(kw.get("facts") or {})
    vals[9] = kw.get("state", "SOURCED")
    return q1(f"INSERT INTO leads ({','.join(keys)}) VALUES ({','.join(['%s']*len(keys))}) "
              "ON CONFLICT DO NOTHING RETURNING *", vals)


LEAD_COLS = {"segment", "name", "company", "role", "email", "phone", "wa_opt_in",
             "wa_last_inbound_at", "state", "sequence_step", "score", "source",
             "summary", "facts", "handoff", "lost_reason", "next_action_at"}
MESSAGE_COLS = {"subject", "body", "status", "intent", "provider_id", "meta", "sent_at"}


def update_lead(lead_id, **fields):
    bad = set(fields) - LEAD_COLS
    if bad:
        raise ValueError(f"unknown lead columns: {bad}")
    if "facts" in fields:
        fields["facts"] = Json(fields["facts"])
    if "handoff" in fields:
        fields["handoff"] = Json(fields["handoff"])
    sets = ", ".join(f"{k}=%s" for k in fields) + ", updated_at=now()"
    execute(f"UPDATE leads SET {sets} WHERE id=%s", list(fields.values()) + [lead_id])
    return get_lead(lead_id)


def leads_in_state(state, limit=50):
    return qall("SELECT * FROM leads WHERE state=%s ORDER BY score DESC, created_at LIMIT %s", (state, limit))


# ---------------- messages ----------------
def add_message(lead_id, direction, channel, body, subject=None, status="draft",
                intent=None, provider_id=None, meta=None):
    return q1("INSERT INTO messages (lead_id, direction, channel, subject, body, status, intent, provider_id, meta) "
              "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
              (lead_id, direction, channel, subject, body, status, intent, provider_id, Json(meta or {})))


def update_message(msg_id, **fields):
    bad = set(fields) - MESSAGE_COLS
    if bad:
        raise ValueError(f"unknown message columns: {bad}")
    if "meta" in fields:
        fields["meta"] = Json(fields["meta"])
    sets = ", ".join(f"{k}=%s" for k in fields)
    execute(f"UPDATE messages SET {sets} WHERE id=%s", list(fields.values()) + [msg_id])
    return q1("SELECT * FROM messages WHERE id=%s", (msg_id,))


def recent_messages(lead_id, n=12):
    rows = qall("SELECT * FROM messages WHERE lead_id=%s AND status IN ('sent','received') "
                "ORDER BY created_at DESC LIMIT %s", (lead_id, n))
    return list(reversed(rows))


def outbound_count_today(lead_id=None):
    if lead_id:
        row = q1("SELECT count(*) c FROM messages WHERE lead_id=%s AND direction='out' AND status='sent' "
                 "AND sent_at > now() - interval '24 hours'", (lead_id,))
    else:
        row = q1("SELECT count(*) c FROM messages WHERE direction='out' AND status='sent' "
                 "AND sent_at > now() - interval '24 hours'")
    return row["c"]


def last_outbound_at(lead_id):
    row = q1("SELECT max(sent_at) t FROM messages WHERE lead_id=%s AND direction='out' AND status='sent'", (lead_id,))
    return row["t"]


# ---------------- jobs ----------------
def schedule(kind, run_at, payload):
    return q1("INSERT INTO jobs (kind, run_at, payload) VALUES (%s,%s,%s) RETURNING *",
              (kind, run_at, Json(payload)))


def cancel_jobs(lead_id, kinds=("follow_up", "revive")):
    execute("UPDATE jobs SET status='cancelled' WHERE status='pending' AND kind = ANY(%s) "
            "AND payload->>'lead_id'=%s", (list(kinds), str(lead_id)))


def due_jobs(limit=20):
    """Claim due jobs as 'running'; the worker marks them done/failed afterwards.
    A crash mid-job leaves it 'running' so it shows up as stuck instead of lost."""
    return qall("UPDATE jobs SET status='running', attempts=attempts+1 WHERE id IN ("
                "  SELECT id FROM jobs WHERE status='pending' AND run_at <= now() "
                "  ORDER BY run_at LIMIT %s FOR UPDATE SKIP LOCKED) RETURNING *", (limit,))


def mark_job(job_id, status):
    execute("UPDATE jobs SET status=%s WHERE id=%s", (status, job_id))


# ---------------- suppressions / escalations / events ----------------
def suppress(kind, value, reason):
    if value:
        execute("INSERT INTO suppressions (kind, value, reason) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                (kind, value.lower(), reason))


def is_suppressed(email=None, phone=None):
    if email and q1("SELECT 1 FROM suppressions WHERE kind='email' AND value=lower(%s)", (email,)):
        return True
    if email and "@" in email and q1("SELECT 1 FROM suppressions WHERE kind='domain' AND value=lower(%s)",
                                     (email.split("@")[1],)):
        return True
    if phone and q1("SELECT 1 FROM suppressions WHERE kind='phone' AND value=%s", (phone.lower(),)):
        return True
    return False


def add_escalation(lead_id, reason, context, suggestion=None):
    return q1("INSERT INTO escalations (lead_id, reason, context, suggestion) VALUES (%s,%s,%s,%s) RETURNING *",
              (lead_id, reason, context, suggestion))


def open_escalations():
    return qall("SELECT e.*, l.name, l.company FROM escalations e JOIN leads l ON l.id=e.lead_id "
                "WHERE e.status='open' ORDER BY e.created_at")


def log_event(source, payload, error=None, dedupe_key=None) -> bool:
    """Log a raw event. With a dedupe_key, returns False if the same provider
    event was already seen (webhook retry) so the caller can skip processing."""
    if dedupe_key:
        row = q1("INSERT INTO raw_events (source, payload, processed, error, dedupe_key) "
                 "VALUES (%s,%s,%s,%s,%s) "
                 "ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING RETURNING id",
                 (source, Json(payload), error is None, error, dedupe_key))
        return row is not None
    execute("INSERT INTO raw_events (source, payload, processed, error) VALUES (%s,%s,%s,%s)",
            (source, Json(payload), error is None, error))
    return True


# ---------------- dashboard / metrics ----------------
def leads_list(state=None, segment=None, limit=100):
    where, params = [], []
    if state:
        where.append("state=%s"); params.append(state)
    if segment:
        where.append("segment=%s"); params.append(segment)
    w = ("WHERE " + " AND ".join(where)) if where else ""
    return qall(f"SELECT id, segment, name, company, role, email, phone, state, score, "
                f"sequence_step, facts, summary, updated_at FROM leads {w} "
                f"ORDER BY score DESC, updated_at DESC LIMIT %s", params + [limit])


def pending_approvals():
    return qall("SELECT m.id, m.lead_id, m.channel, m.subject, m.body, m.created_at, "
                "m.meta->>'purpose' AS purpose, m.meta->>'token' AS token, l.name, l.company "
                "FROM messages m JOIN leads l ON l.id=m.lead_id "
                "WHERE m.status='pending_approval' ORDER BY m.created_at")


def metrics():
    states = {r["state"]: r["c"] for r in qall("SELECT state, count(*) c FROM leads GROUP BY state")}
    m24 = q1("SELECT "
             "count(*) FILTER (WHERE direction='out' AND status='sent' AND sent_at > now()-interval '24 hours') sent24, "
             "count(*) FILTER (WHERE direction='in' AND created_at > now()-interval '24 hours') recv24, "
             "count(*) FILTER (WHERE status='failed' AND created_at > now()-interval '24 hours') failed24, "
             "count(*) FILTER (WHERE status='blocked' AND created_at > now()-interval '24 hours') blocked24 "
             "FROM messages")
    wk = q1("SELECT "
            "count(DISTINCT lead_id) FILTER (WHERE direction='out' AND status='sent' AND sent_at > now()-interval '7 days') contacted7, "
            "count(DISTINCT lead_id) FILTER (WHERE direction='in' AND created_at > now()-interval '7 days') replied7, "
            "count(*) FILTER (WHERE meta ? 'token' AND status='sent' AND (meta->>'edited') IS DISTINCT FROM 'true' "
            "                 AND created_at > now()-interval '7 days') approved7, "
            "count(*) FILTER (WHERE meta->>'edited'='true' AND status='sent' AND created_at > now()-interval '7 days') edited7, "
            "count(*) FILTER (WHERE meta->>'rejected'='true' AND created_at > now()-interval '7 days') rejected7, "
            "count(*) FILTER (WHERE status='blocked' AND meta ? 'critic' AND created_at > now()-interval '7 days') qc_blocked7 "
            "FROM messages")
    jobs = q1("SELECT count(*) FILTER (WHERE status='failed') failed, "
              "count(*) FILTER (WHERE status='pending' AND run_at < now()-interval '5 minutes') overdue FROM jobs")
    events = {r["source"]: r["t"].isoformat() for r in
              qall("SELECT source, max(created_at) t FROM raw_events GROUP BY source")}
    esc = q1("SELECT count(*) c FROM escalations WHERE status='open'")
    appr = q1("SELECT count(*) c FROM messages WHERE status='pending_approval'")
    hb = get_setting("worker_heartbeat")
    contacted, replied = wk["contacted7"] or 0, wk["replied7"] or 0
    a_ok, a_ed, a_no = wk["approved7"] or 0, wk["edited7"] or 0, wk["rejected7"] or 0
    decided = a_ok + a_ed + a_no
    return {
        "paused": is_paused(), "autonomy": autonomy(), "states": states,
        "sent_24h": m24["sent24"], "replies_24h": m24["recv24"],
        "failed_24h": m24["failed24"], "blocked_24h": m24["blocked24"],
        "contacted_7d": contacted, "replied_7d": replied,
        "reply_rate_7d": round(100.0 * replied / contacted, 1) if contacted else None,
        # approved *unchanged* over all decided drafts; edits count against promotion
        "approval_rate_7d": round(100.0 * a_ok / decided, 1) if decided else None,
        "edited_7d": a_ed,
        "qc_blocked_7d": wk["qc_blocked7"],
        "pending_approvals": appr["c"], "open_escalations": esc["c"],
        "jobs_failed": jobs["failed"], "jobs_overdue": jobs["overdue"],
        "worker_heartbeat": hb, "last_webhook": events,
        "booked_total": (states.get("CALL_BOOKED", 0) + states.get("HANDED_OFF", 0)),
    }
