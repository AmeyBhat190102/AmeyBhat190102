from datetime import datetime
from zoneinfo import ZoneInfo
import pytest

from app import config, policy
from app.models import State


# ---------------- content wall ----------------
@pytest.mark.parametrize("body", [
    "It costs ₹ 4500 per frame.",
    "Around $ 120 for the first run.",
    "We can do 20 % off for a pilot.",
    "Happy to offer a discount on volume.",
    "Roughly 300 per poster all-in.",
    "Here's a quote for 50 units.",
])
def test_pricing_language_blocked(body):
    assert not policy.check_content(body).ok


@pytest.mark.parametrize("body", [
    "SK covers pricing on a short call — worth 20 minutes?",
    "Every detail comes from what the customer tells us.",
    "Drafts are typically ready within 24 hours.",
])
def test_clean_copy_passes(body):
    assert policy.check_content(body).ok


def test_overclaims_blocked():
    assert not policy.check_content("This is guaranteed ROI, risk-free.").ok


def test_too_long_blocked():
    assert not policy.check_content("x" * 1801).ok


# ---------------- opt-out detection ----------------
@pytest.mark.parametrize("text", [
    "STOP", "stop.", "Please stop", "please stop emailing me",
    "Stop messaging me on this address", "unsubscribe", "Unsubscribe me please",
    "remove me from your list", "don't contact me again", "do not contact us",
    "I want to opt out of these emails",
])
def test_opt_out_detected(text):
    assert policy.detect_opt_out(text)


@pytest.mark.parametrize("text", [
    "We stop running treks in June, ping me after monsoon.",
    "Can't stop thinking about this idea — tell me more.",
    "Our last stop is Manali before the summit push.",
    "What does onboarding look like?",
])
def test_normal_prose_not_opt_out(text):
    assert not policy.detect_opt_out(text)


# ---------------- pre_send gauntlet ----------------
def _lead(**over):
    lead = {"id": "00000000-0000-0000-0000-000000000001", "segment": "trek_operator",
            "email": "a@b.co", "phone": None, "wa_opt_in": False,
            "state": State.CONTACTED, "sequence_step": 1}
    lead.update(over)
    return lead


@pytest.fixture
def open_gates(monkeypatch):
    """DB answers that let a send through; time pinned inside send hours."""
    from app import db
    monkeypatch.setattr(db, "is_paused", lambda: False)
    monkeypatch.setattr(db, "is_suppressed", lambda **kw: False)
    monkeypatch.setattr(db, "outbound_count_today", lambda lead_id=None: 0)
    monkeypatch.setattr(db, "last_outbound_at", lambda lead_id: None)
    monkeypatch.setattr(policy, "_now",
                        lambda: datetime(2026, 7, 10, 11, 0, tzinfo=ZoneInfo(config.TZ)))


BODY = "Worth a quick call with SK?"


def test_pre_send_ok(open_gates):
    assert policy.pre_send(_lead(), "email", BODY, is_cold_opener=True).ok


def test_kill_switch(open_gates, monkeypatch):
    from app import db
    monkeypatch.setattr(db, "is_paused", lambda: True)
    r = policy.pre_send(_lead(), "email", BODY, is_cold_opener=False)
    assert not r.ok and "kill_switch_on" in r.reasons


def test_cold_whatsapp_never(open_gates):
    r = policy.pre_send(_lead(phone="+911234567890"), "whatsapp", BODY, is_cold_opener=True)
    assert not r.ok and "whatsapp_requires_opt_in" in r.reasons


def test_inbound_only_segment_gets_no_cold_email(open_gates):
    r = policy.pre_send(_lead(segment="d2c_inbound"), "email", BODY, is_cold_opener=True)
    assert not r.ok and "segment_is_inbound_only" in r.reasons


def test_terminal_states_blocked(open_gates):
    for st in (State.OPTED_OUT, State.LOST, State.HANDED_OFF):
        assert not policy.pre_send(_lead(state=st), "email", BODY, is_cold_opener=False).ok


def test_quiet_hours_defer_not_block(open_gates, monkeypatch):
    monkeypatch.setattr(policy, "_now",
                        lambda: datetime(2026, 7, 10, 23, 0, tzinfo=ZoneInfo(config.TZ)))
    r = policy.pre_send(_lead(), "email", BODY, is_cold_opener=False)
    assert not r.ok and r.defer_until is not None
    assert r.defer_until.hour == config.QUIET_HOURS[1]


def test_touch_cap(open_gates):
    r = policy.pre_send(_lead(sequence_step=config.MAX_TOUCHES), "email", BODY, is_cold_opener=True)
    assert not r.ok and "max_touches_reached" in r.reasons


def test_global_daily_cap(open_gates, monkeypatch):
    from app import db
    monkeypatch.setattr(db, "outbound_count_today", lambda lead_id=None: config.GLOBAL_DAILY_CAP)
    assert not policy.pre_send(_lead(), "email", BODY, is_cold_opener=False).ok


def test_min_gap_defers_cold_touches(open_gates, monkeypatch):
    from app import db
    from datetime import timezone, timedelta
    monkeypatch.setattr(db, "last_outbound_at",
                        lambda lead_id: datetime.now(timezone.utc) - timedelta(hours=1))
    r = policy.pre_send(_lead(), "email", BODY, is_cold_opener=True)
    assert not r.ok and r.defer_until is not None


def test_replies_are_not_paced_by_min_gap(open_gates, monkeypatch):
    """A prospect who just replied must be answered promptly; per-lead pacing
    exists for unsolicited touches only."""
    from app import db
    from datetime import timezone, timedelta
    monkeypatch.setattr(db, "last_outbound_at",
                        lambda lead_id: datetime.now(timezone.utc) - timedelta(hours=1))
    monkeypatch.setattr(db, "outbound_count_today",
                        lambda lead_id=None: config.PER_LEAD_DAILY_CAP if lead_id else 0)
    assert policy.pre_send(_lead(state=State.ENGAGED), "email", BODY, is_cold_opener=False).ok


def test_booking_confirmation_allowed_after_handoff(open_gates):
    r = policy.pre_send(_lead(state=State.HANDED_OFF), "email", BODY,
                        is_cold_opener=False, purpose="booking_confirmation")
    assert r.ok


def test_pricing_in_body_blocked_at_send(open_gates):
    r = policy.pre_send(_lead(), "email", "It's ₹ 4000 per unit.", is_cold_opener=False)
    assert not r.ok and any("pricing_language" in x for x in r.reasons)
