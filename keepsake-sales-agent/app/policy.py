"""The policy engine. Deterministic. Runs before every send. The LLM cannot
override anything here; if a check fails, the message is blocked or deferred
and the reason is logged on the message row."""
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from . import config, db
from .models import State

PRICE_RES = [re.compile(p, re.I) for p in config.PRICE_BLOCK_PATTERNS]

# Whole-word/phrase matches only: "unsubscribe" is unambiguous anywhere, but a
# bare "stop" is not ("we stop running treks in June"). "stop" only counts when
# it IS the message or is aimed at the contact itself ("stop emailing me").
OPT_OUT_RES = [re.compile(r"\b" + r"\s+".join(map(re.escape, w.split())) + r"\b", re.I)
               for w in config.OPT_OUT_WORDS if w != "stop"]
STOP_RE = re.compile(r"^\s*(?:please\s+)?stop\b[.!\s]*$"
                     r"|\bstop\s+(?:email|mail|messag|contact|send|writ|text|spam)\w*", re.I)


class PolicyResult:
    def __init__(self, ok=True, defer_until=None, reasons=None):
        self.ok = ok
        self.defer_until = defer_until      # datetime -> reschedule instead of block
        self.reasons = reasons or []

    def fail(self, reason):
        self.ok = False
        self.reasons.append(reason)
        return self


def _now():
    return datetime.now(ZoneInfo(config.TZ))


def next_send_window():
    """Next moment inside allowed hours."""
    n = _now()
    start_quiet, end_quiet = config.QUIET_HOURS
    if n.hour >= start_quiet:
        n = (n + timedelta(days=1)).replace(hour=end_quiet, minute=5, second=0)
    elif n.hour < end_quiet:
        n = n.replace(hour=end_quiet, minute=5, second=0)
    return n


def pre_send(lead, channel: str, body: str, is_cold_opener: bool, purpose: str = "") -> PolicyResult:
    r = PolicyResult()

    # 0. Kill switch
    if db.is_paused():
        return r.fail("kill_switch_on")

    # 1. Suppression / opt-out
    if db.is_suppressed(email=lead.get("email"), phone=lead.get("phone")):
        return r.fail("suppressed")
    # HANDED_OFF still allows the one warm "call booked" confirmation, which may
    # be approved (Level 0) after the state has already flipped.
    terminal = ((State.OPTED_OUT, State.LOST) if purpose == "booking_confirmation"
                else (State.OPTED_OUT, State.LOST, State.HANDED_OFF))
    if lead["state"] in terminal:
        return r.fail(f"terminal_state:{lead['state']}")

    # 2. Channel compliance
    if channel == "whatsapp":
        if not lead.get("wa_opt_in"):
            return r.fail("whatsapp_requires_opt_in")   # cold WhatsApp is never allowed
        # session vs template handled at send time; policy only guarantees opt-in exists
    if channel == "email" and is_cold_opener:
        pb = config.PLAYBOOKS.get(lead["segment"], {})
        if not pb.get("outbound", False):
            return r.fail("segment_is_inbound_only")    # e.g. d2c_inbound never gets cold email

    # 3. Rate caps. The global cap covers everything; per-lead pacing (daily cap,
    # min gap) protects against unsolicited hammering, so it applies to cold
    # touches only — a prospect who just replied gets answered promptly.
    if db.outbound_count_today() >= config.GLOBAL_DAILY_CAP:
        return r.fail("global_daily_cap")
    if is_cold_opener:
        if db.outbound_count_today(lead["id"]) >= config.PER_LEAD_DAILY_CAP:
            return r.fail("per_lead_daily_cap")
        last = db.last_outbound_at(lead["id"])
        if last:
            gap_ok_at = last + timedelta(hours=config.MIN_GAP_HOURS)
            if gap_ok_at > datetime.now(gap_ok_at.tzinfo):
                r.defer_until = gap_ok_at
                return r.fail("min_gap_not_elapsed")

    # 4. Quiet hours -> defer, not block
    h = _now().hour
    start_quiet, end_quiet = config.QUIET_HOURS
    if h >= start_quiet or h < end_quiet:
        r.defer_until = next_send_window()
        return r.fail("quiet_hours")

    # 5. Touch cap for cold sequences
    if is_cold_opener and lead["sequence_step"] >= config.MAX_TOUCHES:
        return r.fail("max_touches_reached")

    # 6. Content guards (belt and braces; the critic also checks these)
    return check_content(body, r)


def check_content(body: str, r: PolicyResult | None = None) -> PolicyResult:
    r = r or PolicyResult()
    low = body.lower()
    anchor = (config.PUBLIC_PRICE_ANCHOR or "").lower()
    stripped = low.replace(anchor, "") if anchor else low
    for rex in PRICE_RES:
        if rex.search(stripped):
            return r.fail(f"pricing_language:{rex.pattern}")
    for word in ["guarantee", "guaranteed roi", "risk-free"]:
        if word in low:
            return r.fail(f"overclaim:{word}")
    if len(body) > 1800:
        return r.fail("too_long")
    return r


def detect_opt_out(text: str) -> bool:
    """Deterministic opt-out fast path. Ambiguous prose falls through to the
    classifier, which has its own OPT_OUT intent as a second net."""
    return bool(STOP_RE.search(text)) or any(rex.search(text) for rex in OPT_OUT_RES)
