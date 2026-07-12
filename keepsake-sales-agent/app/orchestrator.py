"""The orchestrator. One pipeline for everything the agent does:
  event -> classify -> route via state machine -> draft -> policy -> critic
        -> approval gate -> send -> schedule next -> (handoff | escalate)
Every step writes to the messages/audit trail, so any complaint is reconstructable."""
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from . import config, db, brain, policy, channels
from .models import State, Intent, INTENT_ROUTES


def approval_token(msg_id: str) -> str:
    return hmac.new(config.WEBHOOK_SECRET.encode(), str(msg_id).encode(), hashlib.sha256).hexdigest()[:24]


def _is_cold(purpose: str) -> bool:
    """Cold-sequence touches (subject to touch caps and Level-1 auto-send)."""
    return purpose in ("opener", "revive") or purpose.startswith("follow_up")


# =============== outbound pipeline ===============
def dispatch(lead, purpose: str, extra: str = "") -> dict:
    """Draft -> critic -> policy -> approval/send. Returns the message row."""
    msgs = db.recent_messages(lead["id"])
    d = brain.draft(lead, msgs, purpose, extra)
    channel = d.get("channel") or "email"
    if channel == "whatsapp" and not lead.get("wa_opt_in"):
        channel = "email"                                   # brain proposed, policy disposes
    body, subject = (d.get("body") or "").strip(), d.get("subject")

    # QC critic: every outbound message, no exceptions
    c = brain.critic(lead, body, purpose)
    if not c.get("ok", False):
        body = (c.get("fixed_body") or "").strip()
        if not body or not policy.check_content(body).ok:
            row = db.add_message(lead["id"], "out", channel, body or d.get("body", ""), subject,
                                 status="blocked", meta={"critic": c, "purpose": purpose})
            db.add_escalation(lead["id"], "qc_block",
                              f"Critic blocked a {purpose}: {c.get('violations')}", d.get("body"))
            channels.notify_sk(f"QC blocked a {purpose} to {lead.get('company')}. Check dashboard.")
            return row

    is_cold = _is_cold(purpose)
    p = policy.pre_send(lead, channel, body, is_cold_opener=is_cold, purpose=purpose)
    if not p.ok:
        if p.defer_until:                                   # quiet hours / min-gap -> reschedule
            row = db.add_message(lead["id"], "out", channel, body, subject, status="draft",
                                 meta={"purpose": purpose, "deferred": p.reasons})
            db.schedule("send_draft", p.defer_until, {"lead_id": str(lead["id"]), "msg_id": str(row["id"])})
            return row
        return db.add_message(lead["id"], "out", channel, body, subject, status="blocked",
                              meta={"purpose": purpose, "policy": p.reasons})

    row = db.add_message(lead["id"], "out", channel, body, subject, status="draft",
                         meta={"purpose": purpose, "critic": c})
    level = db.autonomy()
    needs_approval = level == 0 or (level == 1 and not is_cold)
    if needs_approval:
        tok = approval_token(row["id"])
        db.update_message(row["id"], status="pending_approval", meta={**row["meta"], "token": tok})
        channels.notify_sk(
            f"APPROVE? {purpose} -> {lead.get('name') or lead.get('company')}\n"
            f"{body[:350]}\n"
            f"Yes: {config.BASE_URL}/approve/{row['id']}?t={tok}\n"
            f"No:  {config.BASE_URL}/reject/{row['id']}?t={tok}")
        return db.q1("SELECT * FROM messages WHERE id=%s", (row["id"],))
    return transmit(row["id"])


def transmit(msg_id) -> dict:
    """Actually send an approved/auto message. Re-runs policy at send time."""
    m = db.q1("SELECT * FROM messages WHERE id=%s", (msg_id,))
    lead = db.get_lead(m["lead_id"])
    p = policy.pre_send(lead, m["channel"], m["body"],
                        is_cold_opener=_is_cold(m["meta"].get("purpose", "")),
                        purpose=m["meta"].get("purpose", ""))
    if not p.ok:
        if p.defer_until:
            db.schedule("send_draft", p.defer_until, {"lead_id": str(lead["id"]), "msg_id": str(msg_id)})
            return m
        return db.update_message(msg_id, status="blocked", meta={**m["meta"], "policy": p.reasons})
    try:
        ref = channels.send(lead, m["channel"], m.get("subject"), m["body"])
    except channels.SendError as e:
        db.log_event("send_error", {"msg": str(e), "lead": str(lead["id"])}, error=str(e))
        return db.update_message(msg_id, status="failed", meta={**m["meta"], "error": str(e)})

    db.update_message(msg_id, status="sent", provider_id=ref, sent_at=datetime.now(timezone.utc))
    purpose = m["meta"].get("purpose", "")
    if _is_cold(purpose):
        step = lead["sequence_step"] + 1
        db.update_lead(lead["id"], state=State.CONTACTED, sequence_step=step)
        if step < config.MAX_TOUCHES:
            days = config.FOLLOW_UP_DAYS[min(step - 1, len(config.FOLLOW_UP_DAYS) - 1)]
            db.schedule("follow_up", datetime.now(timezone.utc) + timedelta(days=days),
                        {"lead_id": str(lead["id"]), "step": step})
    return db.q1("SELECT * FROM messages WHERE id=%s", (msg_id,))


# =============== inbound pipeline ===============
def handle_inbound(lead, channel: str, text: str, meta: dict | None = None):
    db.cancel_jobs(lead["id"])                              # a reply stops the drip immediately
    if channel == "whatsapp":
        lead = db.update_lead(lead["id"], wa_opt_in=True,
                              wa_last_inbound_at=datetime.now(timezone.utc))
    if meta and channel == "email":
        facts = dict(lead.get("facts") or {})
        facts["smartlead"] = {**facts.get("smartlead", {}), **meta}
        lead = db.update_lead(lead["id"], facts=facts)
    db.add_message(lead["id"], "in", channel, text, status="received")

    if policy.detect_opt_out(text):
        return _route(lead, Intent.OPT_OUT, {}, text)

    msgs = db.recent_messages(lead["id"])
    cls = brain.classify(lead, msgs, text)
    intent = Intent(cls.get("intent", "UNCLEAR")) if cls.get("intent") in Intent.__members__ else Intent.UNCLEAR
    if float(cls.get("confidence", 0)) < 0.5:
        intent = Intent.UNCLEAR

    ex = cls.get("extracted") or {}
    updates = {}
    facts = dict(lead.get("facts") or {})
    if ex.get("new_facts"):
        facts.setdefault("learned", []).extend(ex["new_facts"][:5])
    if ex.get("phone") and not lead.get("phone"):
        updates["phone"] = ex["phone"]
    if ex.get("whatsapp_optin"):
        updates["wa_opt_in"] = True
    updates["facts"] = facts
    updates["summary"] = brain.merge_summary(lead.get("summary", ""), cls.get("summary_update", ""))
    lead = db.update_lead(lead["id"], **updates)
    db.execute("UPDATE messages SET intent=%s WHERE id=(SELECT id FROM messages WHERE lead_id=%s "
               "AND direction='in' ORDER BY created_at DESC LIMIT 1)", (intent, lead["id"]))
    return _route(lead, intent, cls, text)


def _route(lead, intent: Intent, cls: dict, text: str):
    prior_state = lead["state"]                 # before routing overwrites it
    new_state, action = INTENT_ROUTES[intent]
    if new_state:
        lead = db.update_lead(lead["id"], state=new_state)

    if action == "ignore":
        return
    if action == "suppress":
        db.suppress("email", lead.get("email"), "opt_out")
        db.suppress("phone", lead.get("phone"), "opt_out")
        _confirm_opt_out(lead)
        return
    if action == "close":
        db.update_lead(lead["id"], lost_reason=intent.value)
        return
    if action == "snooze":
        db.schedule("revive", datetime.now(timezone.utc) + timedelta(days=config.REVIVE_AFTER_DAYS),
                    {"lead_id": str(lead["id"])})
        dispatch(lead, "reply", "They said not now. Acknowledge gracefully in 2-3 sentences, "
                                "no pushback, leave the door open. Do not ask a question.")
        return
    if action == "escalate":
        suggestion = None
        if intent in (Intent.PRICING, Intent.TIMES_PROPOSED):
            d = brain.draft(lead, db.recent_messages(lead["id"]), "reply",
                            "Draft the holding reply for SK to approve: pricing/scheduling is his call. "
                            "Warmly confirm the founder will take it from here.")
            suggestion = d.get("body")
        esc = db.add_escalation(lead["id"], intent.value.lower(), text[:800], suggestion)
        channels.notify_sk(
            f"ESCALATION [{intent.value}] {lead.get('name')} · {lead.get('company')}\n"
            f"They said: {text[:280]}\n"
            f"Resolve: {config.BASE_URL}/escalations/{esc['id']}")
        return
    if action == "handoff":
        return handoff(lead)
    if action == "reply":
        hint = cls.get("reply_hint", "")
        purpose = "booking_push" if prior_state == State.BOOKING else "reply"
        extra = (hint + " If they show buying interest, propose the call and share the calendar link "
                        "once, naturally.").strip()
        row = dispatch(lead, purpose, extra)
        # pending_approval counts too: the link is in flight, the machine is in booking mode
        if row and row["status"] in ("sent", "pending_approval") and config.CAL_LINK in row["body"]:
            db.update_lead(lead["id"], state=State.BOOKING)
        return row


def _confirm_opt_out(lead):
    """One final compliance confirmation, then permanent silence."""
    try:
        body = ("Understood, and done. You won't hear from us again. "
                f"If you ever change your mind, we're at hello@keepsakepress.in.\n\n{config.SIGNATURE}")
        if policy.check_content(body).ok and not db.is_paused():
            channel = "whatsapp" if lead.get("wa_opt_in") and lead.get("phone") else "email"
            ref = channels.send(lead, channel, "You're opted out", body)
            db.add_message(lead["id"], "out", channel, body, status="sent", provider_id=ref)
    except Exception:
        pass


# =============== handoff ===============
def handoff(lead):
    msgs = db.recent_messages(lead["id"], 30)
    brief = brain.handoff_brief(lead, msgs)
    packet = {
        "lead_id": str(lead["id"]), "name": lead.get("name"), "company": lead.get("company"),
        "segment": lead["segment"], "email": lead.get("email"), "phone": lead.get("phone"),
        "brief": brief, "booked_at": str(datetime.now(timezone.utc)),
        "summary": lead.get("summary"),
    }
    db.update_lead(lead["id"], state=State.HANDED_OFF, handoff=packet)
    db.cancel_jobs(lead["id"])
    channels.notify_sk(
        f"CALL BOOKED ✓ {lead.get('name')} · {lead.get('company')} ({lead['segment']})\n{brief[:500]}\n"
        f"Thread: {config.BASE_URL}/leads/{lead['id']}")
    dispatch(lead, "booking_confirmation",
             "They booked the call. Send a short warm confirmation: looking forward, "
             "SK will meet them, nothing else to do. No links, no questions.")
    return packet


# =============== jobs ===============
def run_job(job):
    kind, payload = job["kind"], job["payload"]
    if kind == "send_draft":
        return transmit(payload["msg_id"])
    lead = db.get_lead(payload["lead_id"])
    if not lead:
        return
    if kind == "follow_up":
        if lead["state"] == State.CONTACTED and lead["sequence_step"] == payload["step"]:
            dispatch(lead, f"follow_up_{payload['step'] + 1}",
                     "This is a follow-up to silence. New angle, shorter than the last message, "
                     "no guilt-tripping. Reference one specific thing about them.")
    elif kind == "revive":
        if lead["state"] == State.NOT_NOW:
            db.update_lead(lead["id"], sequence_step=config.MAX_TOUCHES - 1)  # one touch only
            dispatch(lead, "revive", "They said 'not now' about six weeks ago. Check back in warmly "
                                     "with one fresh, concrete reason it's timely.")


def start_outreach_batch(limit=20):
    """Pull QUEUED leads and fire openers, respecting caps."""
    sent = 0
    for lead in db.leads_in_state(State.QUEUED, limit):
        if db.outbound_count_today() >= config.GLOBAL_DAILY_CAP:
            break
        row = dispatch(lead, "opener")
        if row and row["status"] in ("sent", "pending_approval"):
            sent += 1
    return sent
