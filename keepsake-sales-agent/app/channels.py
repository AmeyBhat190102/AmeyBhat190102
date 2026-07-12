"""Channel adapters. Email goes through Smartlead (which owns warmup, rotation
and deliverability). WhatsApp goes through the Cloud API with correct session
vs template handling. Both are behind one send() interface."""
from datetime import datetime, timezone, timedelta
import requests
from . import config, db

SL_BASE = "https://server.smartlead.ai/api/v1"
WA_BASE = f"https://graph.facebook.com/v20.0/{config.WA_PHONE_ID}/messages"


class SendError(Exception):
    pass


def _dry_run(channel: str, to: str, body: str) -> str:
    print(f"[DRY-RUN {channel}] -> {to}: {body[:200]!r}")
    return f"dryrun:{channel}"


def tpl_param(text: str, limit: int = 900) -> str:
    """Meta rejects template body parameters containing newlines, tabs or 4+
    consecutive spaces. Collapse all whitespace to single spaces and truncate."""
    return " ".join(text.split())[:limit]


# ---------------- email via Smartlead ----------------
def email_send(lead, subject: str, body: str) -> str:
    """Reply within the lead's Smartlead thread if one exists, else send as a
    new message through the campaign. Returns a provider reference."""
    if config.DRY_RUN:
        return _dry_run("email", lead.get("email", "?"), f"{subject or ''} | {body}")
    if not config.SMARTLEAD_KEY:
        raise SendError("SMARTLEAD_API_KEY not configured")
    stats = (lead.get("facts") or {}).get("smartlead", {})
    params = {"api_key": config.SMARTLEAD_KEY}
    if stats.get("message_id"):
        # reply in-thread to the prospect's last email
        url = f"{SL_BASE}/campaigns/{stats.get('campaign_id', config.SMARTLEAD_CAMPAIGN_ID)}/reply-email-thread"
        payload = {
            "email_stats_id": stats.get("stats_id"),
            "email_body": body.replace("\n", "<br>"),
            "reply_message_id": stats["message_id"],
            "reply_email_body": stats.get("last_body", ""),
        }
    else:
        # first touch: add lead to campaign; Smartlead's sequence slot 1 carries our body
        url = f"{SL_BASE}/campaigns/{config.SMARTLEAD_CAMPAIGN_ID}/leads"
        payload = {"lead_list": [{
            "email": lead["email"], "first_name": lead.get("name") or "",
            "company_name": lead.get("company") or "",
            "custom_fields": {"agent_subject": subject or "", "agent_body": body},
        }]}
    r = requests.post(url, params=params, json=payload, timeout=30)
    if r.status_code >= 300:
        raise SendError(f"smartlead {r.status_code}: {r.text[:200]}")
    return f"smartlead:{r.json().get('id', 'ok')}"


def parse_smartlead_webhook(payload: dict) -> dict | None:
    """Normalise a Smartlead EMAIL_REPLY webhook into {email, text, meta}."""
    ev = (payload.get("event_type") or payload.get("webhook_type") or "").upper()
    if "REPLY" not in ev:
        return None
    email = (payload.get("to_email") or payload.get("lead_email") or
             (payload.get("lead") or {}).get("email"))
    text = payload.get("reply_body_plain") or payload.get("reply_body") or payload.get("email_body") or ""
    return {
        "email": email,
        "text": text.strip(),
        "meta": {
            "stats_id": payload.get("email_stats_id") or payload.get("stats_id"),
            "message_id": payload.get("message_id") or payload.get("reply_message_id"),
            "campaign_id": payload.get("campaign_id"),
            "last_body": text[:1500],
        },
    }


# ---------------- WhatsApp Cloud API ----------------
def _wa_session_open(lead) -> bool:
    t = lead.get("wa_last_inbound_at")
    if not t:
        return False
    if isinstance(t, str):
        t = datetime.fromisoformat(t)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - t < timedelta(hours=24)


def wa_send(lead, body: str) -> str:
    """Session message inside the 24h window; approved template outside it.
    Caller has already verified wa_opt_in via the policy engine."""
    if config.DRY_RUN:
        return _dry_run("whatsapp", lead.get("phone", "?"), body)
    if not (config.WA_TOKEN and config.WA_PHONE_ID):
        raise SendError("WhatsApp Cloud API not configured")
    headers = {"Authorization": f"Bearer {config.WA_TOKEN}"}
    if _wa_session_open(lead):
        payload = {"messaging_product": "whatsapp", "to": lead["phone"],
                   "type": "text", "text": {"body": body[:3500]}}
    else:
        payload = {"messaging_product": "whatsapp", "to": lead["phone"], "type": "template",
                   "template": {"name": config.WA_INTRO_TEMPLATE, "language": {"code": "en"},
                                "components": [{"type": "body",
                                                "parameters": [{"type": "text", "text": tpl_param(body)}]}]}}
    r = requests.post(WA_BASE, headers=headers, json=payload, timeout=30)
    if r.status_code >= 300:
        raise SendError(f"whatsapp {r.status_code}: {r.text[:200]}")
    return "wa:" + (r.json().get("messages") or [{}])[0].get("id", "ok")


def notify_sk(text: str):
    """Page SK on WhatsApp via an approved utility template. Never raises."""
    try:
        if config.DRY_RUN or not (config.WA_TOKEN and config.SK_WHATSAPP):
            print("[NOTIFY-SK]", text[:500])
            return
        headers = {"Authorization": f"Bearer {config.WA_TOKEN}"}
        payload = {"messaging_product": "whatsapp", "to": config.SK_WHATSAPP, "type": "template",
                   "template": {"name": config.WA_OWNER_TEMPLATE, "language": {"code": "en"},
                                "components": [{"type": "body",
                                                "parameters": [{"type": "text", "text": tpl_param(text)}]}]}}
        requests.post(WA_BASE, headers=headers, json=payload, timeout=20)
    except Exception as e:
        print("[NOTIFY-SK failed]", e, "|", text[:300])


def parse_wa_webhook(payload: dict) -> list[dict]:
    """Normalise inbound WhatsApp messages into [{phone, text, name}]."""
    out = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name")
                     for c in value.get("contacts", [])}
            for m in value.get("messages", []):
                if m.get("type") != "text":
                    continue
                out.append({"phone": "+" + m["from"].lstrip("+"),
                            "text": m["text"]["body"],
                            "name": names.get(m["from"]),
                            "wamid": m.get("id")})           # provider id, used for retry dedupe
    return out


# ---------------- unified send ----------------
def send(lead, channel: str, subject: str | None, body: str) -> str:
    if channel == "email":
        if not lead.get("email"):
            raise SendError("lead has no email")
        return email_send(lead, subject, body)
    if channel == "whatsapp":
        if not lead.get("phone"):
            raise SendError("lead has no phone")
        return wa_send(lead, body)
    raise SendError(f"unknown channel {channel}")
