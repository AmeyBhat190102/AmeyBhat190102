"""HTTP surface. Webhooks in, SK's control panel endpoints out.
Run: uvicorn app.main:app --host 0.0.0.0 --port 8000

Webhooks ack immediately and process in the background: providers (Meta
especially) treat slow responses as failures and retry, and inbound processing
makes multiple LLM calls. Retries are deduped on provider message ids."""
import hashlib
import hmac
import os
from fastapi import BackgroundTasks, FastAPI, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse, HTMLResponse
from datetime import datetime, timezone
from . import config, db, channels, orchestrator, brain, leadgen
from .models import State

app = FastAPI(title="Keepsake Sales Agent")


def _auth(secret: str):
    if not hmac.compare_digest(secret, config.WEBHOOK_SECRET):
        raise HTTPException(401, "bad secret")


def _process_inbound(lead_id, channel, text, meta=None):
    """Background-task wrapper: never let processing errors vanish silently."""
    try:
        lead = db.get_lead(lead_id)
        if lead:
            orchestrator.handle_inbound(lead, channel, text, meta)
    except Exception as e:
        db.log_event("process_error", {"lead_id": str(lead_id), "channel": channel,
                                       "text": text[:500]}, error=str(e)[:500])


@app.get("/health")
def health():
    return {"ok": True, "paused": db.is_paused(), "autonomy": db.autonomy(),
            "dry_run": config.DRY_RUN}


# ---------------- inbound: email (Smartlead) ----------------
@app.post("/webhooks/smartlead")
async def smartlead_hook(req: Request, tasks: BackgroundTasks, secret: str = Query("")):
    _auth(secret)
    payload = await req.json()
    norm = channels.parse_smartlead_webhook(payload)
    key = None
    if norm and (norm["meta"].get("message_id") or norm["meta"].get("stats_id")):
        key = f"sl:{norm['meta'].get('message_id')}:{norm['meta'].get('stats_id')}"
    if not db.log_event("smartlead", payload, dedupe_key=key):
        return {"ignored": "duplicate delivery"}
    if not norm or not norm["email"]:
        return {"ignored": True}
    lead = db.find_lead_by_email(norm["email"])
    if not lead:
        return {"ignored": "unknown lead"}
    tasks.add_task(_process_inbound, lead["id"], "email", norm["text"], norm["meta"])
    return {"ok": True}


# ---------------- inbound: WhatsApp Cloud API ----------------
@app.get("/webhooks/whatsapp")
def wa_verify(hub_mode: str = Query("", alias="hub.mode"),
              hub_token: str = Query("", alias="hub.verify_token"),
              hub_challenge: str = Query("", alias="hub.challenge")):
    if hub_mode == "subscribe" and hub_token == config.WA_VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(403, "verification failed")


@app.post("/webhooks/whatsapp")
async def wa_hook(req: Request, tasks: BackgroundTasks):
    raw = await req.body()
    if config.WA_APP_SECRET:                    # Meta signs every delivery; verify it
        sig = req.headers.get("x-hub-signature-256", "")
        want = "sha256=" + hmac.new(config.WA_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, want):
            raise HTTPException(403, "bad signature")
    payload = await req.json()
    messages = channels.parse_wa_webhook(payload)
    key = f"wa:{messages[0]['wamid']}" if messages and messages[0].get("wamid") else None
    if not db.log_event("whatsapp", payload, dedupe_key=key):
        return {"ignored": "duplicate delivery"}
    for m in messages:
        lead = db.find_lead_by_phone(m["phone"])
        if not lead:
            # Inbound stranger on WhatsApp = D2C enquiry (CTWA ad or shared number).
            lead = db.insert_lead(segment="d2c_inbound", name=m.get("name"), phone=m["phone"],
                                  source="ctwa", state=State.ENGAGED, score=60, facts={})
            if not lead:
                lead = db.find_lead_by_phone(m["phone"])
        tasks.add_task(_process_inbound, lead["id"], "whatsapp", m["text"])
    return {"ok": True}


# ---------------- inbound: website / manual lead ----------------
@app.post("/webhooks/inbound_lead")
async def inbound_lead(req: Request, tasks: BackgroundTasks, secret: str = Query("")):
    _auth(secret)
    b = await req.json()
    lead = db.insert_lead(segment=b.get("segment", "d2c_inbound"), name=b.get("name"),
                          company=b.get("company"), role=b.get("role"), email=b.get("email"),
                          phone=b.get("phone"), source=b.get("source", "inbound_web"),
                          score=70, facts={"note": b.get("message", "")},
                          state=State.ENGAGED if b.get("message") else State.SOURCED)
    if not lead:
        # already known (unique email/phone): a repeat enquiry, not a no-op
        lead = db.find_lead_by_email(b.get("email")) or db.find_lead_by_phone(b.get("phone"))
    if lead and b.get("message"):
        tasks.add_task(_process_inbound, lead["id"],
                       "email" if lead.get("email") else "whatsapp", b["message"])
    return {"ok": True, "lead_id": str(lead["id"]) if lead else None}


# ---------------- inbound: Cal.com booking ----------------
@app.post("/webhooks/cal")
async def cal_hook(req: Request, tasks: BackgroundTasks, secret: str = Query("")):
    _auth(secret)
    payload = await req.json()
    inner = payload.get("payload") or {}
    key = f"cal:{inner['uid']}" if inner.get("uid") else None
    if not db.log_event("cal", payload, dedupe_key=key):
        return {"ignored": "duplicate delivery"}
    email = ((inner.get("attendees") or [{}])[0]).get("email")
    lead = db.find_lead_by_email(email) if email else None
    if lead and lead["state"] not in (State.HANDED_OFF,):
        db.update_lead(lead["id"], state=State.CALL_BOOKED)
        tasks.add_task(lambda lid: orchestrator.handoff(db.get_lead(lid)), lead["id"])
    return {"ok": True}


# ---------------- approvals ----------------
def _approval_auth(msg_id: str, t: str, secret: str):
    if not (hmac.compare_digest(t, orchestrator.approval_token(msg_id))
            or hmac.compare_digest(secret, config.WEBHOOK_SECRET)):
        raise HTTPException(401, "bad token")


def _do_approve(msg_id: str, edited_body: str | None = None):
    m = db.q1("SELECT * FROM messages WHERE id=%s", (msg_id,))
    if not m or m["status"] != "pending_approval":
        return None
    meta = dict(m["meta"])
    if edited_body is not None and edited_body.strip() and edited_body.strip() != m["body"].strip():
        meta.update(edited=True, original_body=m["body"])
        db.update_message(msg_id, status="approved", body=edited_body.strip(), meta=meta)
    else:
        db.update_message(msg_id, status="approved")
    return orchestrator.transmit(msg_id)


@app.get("/approve/{msg_id}")
def approve(msg_id: str, t: str = Query(""), secret: str = Query("")):
    """One-tap approval from the WhatsApp link. Sends the draft verbatim."""
    _approval_auth(msg_id, t, secret)
    sent = _do_approve(msg_id)
    if not sent:
        return PlainTextResponse("Nothing pending for this message.")
    return PlainTextResponse(f"Approved. Status: {sent['status']}.")


@app.post("/approve/{msg_id}")
async def approve_edited(msg_id: str, req: Request, t: str = Query(""), secret: str = Query("")):
    """Dashboard approval; body may carry {'body': edited text}. Edits are
    tracked separately — the promotion metric counts unchanged approvals only."""
    _approval_auth(msg_id, t, secret)
    b = await req.json() if (await req.body()) else {}
    sent = _do_approve(msg_id, b.get("body"))
    if not sent:
        raise HTTPException(404, "nothing pending for this message")
    return {"ok": True, "status": sent["status"], "edited": bool(sent["meta"].get("edited"))}


@app.get("/reject/{msg_id}")
def reject(msg_id: str, t: str = Query(""), secret: str = Query("")):
    _approval_auth(msg_id, t, secret)
    m = db.q1("SELECT * FROM messages WHERE id=%s", (msg_id,))
    if not m:
        raise HTTPException(404)
    db.update_message(msg_id, status="blocked", meta={**m["meta"], "rejected": True})
    return PlainTextResponse("Rejected. The agent will not send it.")


# ---------------- escalations ----------------
@app.get("/escalations")
def escalations(secret: str = Query("")):
    _auth(secret)
    return db.open_escalations()


@app.get("/escalations/{esc_id}")
def escalation(esc_id: str, secret: str = Query("")):
    _auth(secret)
    e = db.q1("SELECT * FROM escalations WHERE id=%s", (esc_id,))
    if not e:
        raise HTTPException(404)
    thread = db.recent_messages(e["lead_id"], 10)
    return {"escalation": e, "thread": [{"dir": m["direction"], "body": m["body"]} for m in thread]}


@app.post("/escalations/{esc_id}/resolve")
async def resolve(esc_id: str, req: Request, secret: str = Query("")):
    _auth(secret)
    b = await req.json()               # {"instruction": "...", "dismiss": false}
    e = db.q1("SELECT * FROM escalations WHERE id=%s", (esc_id,))
    if not e:
        raise HTTPException(404)
    db.execute("UPDATE escalations SET status=%s, resolution=%s, resolved_at=now() WHERE id=%s",
               ("dismissed" if b.get("dismiss") else "resolved", b.get("instruction", ""), esc_id))
    lead = db.get_lead(e["lead_id"])
    if b.get("dismiss"):
        db.update_lead(lead["id"], state=State.ENGAGED)
        return {"ok": True}
    db.update_lead(lead["id"], state=State.ENGAGED)
    row = orchestrator.dispatch(db.get_lead(lead["id"]), "reply",
                                f"SK's instruction for this reply, follow it exactly within policy: "
                                f"{b.get('instruction','')[:600]}")
    return {"ok": True, "message_status": row["status"] if row else None}


# ---------------- leads & ops ----------------
@app.get("/leads")
def leads(state: str = Query(None), segment: str = Query(None),
          limit: int = Query(100), secret: str = Query("")):
    _auth(secret)
    return db.leads_list(state, segment, min(limit, 300))


@app.get("/leads/{lead_id}")
def lead_view(lead_id: str, secret: str = Query("")):
    _auth(secret)
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404)
    return {"lead": lead, "thread": db.recent_messages(lead_id, 40)}


@app.post("/leads/{lead_id}/reject")
def reject_lead(lead_id: str, secret: str = Query("")):
    _auth(secret)
    return db.update_lead(lead_id, state=State.LOST, lost_reason="rejected_in_review")


@app.get("/approvals")
def approvals(secret: str = Query("")):
    _auth(secret)
    return db.pending_approvals()


@app.get("/metrics")
def metrics(secret: str = Query("")):
    _auth(secret)
    return db.metrics()


@app.post("/leadgen/run")
def leadgen_run(secret: str = Query(""), segment: str = Query("trek_operator"),
                n: int = Query(25), keywords: str = Query(None), country: str = Query("IN")):
    _auth(secret)
    return leadgen.run(segment, n, keywords, country)


@app.get("/dashboard")
def dashboard(secret: str = Query("")):
    _auth(secret)
    path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    with open(path, encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.post("/leads/{lead_id}/queue")
def queue_lead(lead_id: str, secret: str = Query("")):
    _auth(secret)
    lead = db.get_lead(lead_id)
    pb = config.PLAYBOOKS.get(lead["segment"], {})
    if not pb.get("outbound"):
        raise HTTPException(400, "segment is inbound-only")
    return db.update_lead(lead_id, state=State.QUEUED)


@app.post("/outreach/run")
def run_outreach(secret: str = Query(""), limit: int = 10):
    _auth(secret)
    return {"dispatched": orchestrator.start_outreach_batch(limit)}


@app.post("/admin/pause")
def pause(secret: str = Query("")):
    _auth(secret); db.set_setting("paused", True)
    channels.notify_sk("Agent PAUSED. No messages will send until resume.")
    return {"paused": True}


@app.post("/admin/resume")
def resume(secret: str = Query("")):
    _auth(secret); db.set_setting("paused", False)
    return {"paused": False}


@app.post("/admin/autonomy/{level}")
def set_autonomy(level: int, secret: str = Query("")):
    _auth(secret)
    if level not in (0, 1, 2):
        raise HTTPException(400, "level must be 0, 1 or 2")
    db.set_setting("autonomy_level", level)
    return {"autonomy": level}


@app.get("/digest")
def digest(secret: str = Query("")):
    _auth(secret)
    counts = db.qall("SELECT state, count(*) c FROM leads GROUP BY state ORDER BY c DESC")
    sent = db.q1("SELECT count(*) c FROM messages WHERE direction='out' AND status='sent' "
                 "AND sent_at > now() - interval '24 hours'")
    got = db.q1("SELECT count(*) c FROM messages WHERE direction='in' "
                "AND created_at > now() - interval '24 hours'")
    esc = db.open_escalations()
    text = (f"Daily digest · sent {sent['c']} · replies {got['c']} · open escalations {len(esc)}\n"
            + " | ".join(f"{r['state']}:{r['c']}" for r in counts))
    channels.notify_sk(text)
    return {"digest": text, "escalations": len(esc),
            "generated_at": str(datetime.now(timezone.utc))}
