"""End-to-end dry run. Exercises the whole machine against a real Postgres with
DRY_RUN=true: no email, no WhatsApp, no LLM spend — sends are printed, the model
is a deterministic mock. Run:

    DRY_RUN=true DATABASE_URL=postgresql://... python -m scripts.dry_run

Walks: source -> score -> review-approve -> queued -> opener (Level 0 approval,
one verbatim + one edited) -> interested reply -> booking push -> pricing reply
-> escalation -> SK instruction -> opt-out -> suppression -> Cal.com booking ->
handoff packet -> follow-up job -> webhook retry dedupe. Asserts at every step;
exits non-zero on the first broken invariant."""
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

if os.environ.get("DRY_RUN", "").lower() != "true":
    sys.exit("Refusing: set DRY_RUN=true (this script must never touch real channels)")

from fastapi.testclient import TestClient

from app import config, db, policy, orchestrator
from app.main import app
from app.models import State

# Pin the clock inside send hours so the walk is deterministic at any hour.
policy._now = lambda: datetime(2026, 7, 10, 11, 0, tzinfo=ZoneInfo(config.TZ))

client = TestClient(app)
SEC = {"secret": config.WEBHOOK_SECRET}
PASSED = []


def step(name, cond, detail=""):
    mark = "✓" if cond else "✗"
    print(f"  {mark} {name}" + (f" — {detail}" if detail else ""))
    PASSED.append(bool(cond))
    if not cond:
        sys.exit(f"DRY RUN FAILED at: {name}")


def section(t):
    print(f"\n━━ {t} " + "━" * max(0, 60 - len(t)))


def cleanup():
    db.execute("DELETE FROM suppressions WHERE value LIKE %s", ("%@dryrun.test",))
    db.execute("DELETE FROM leads WHERE email LIKE %s OR phone LIKE %s", ("%@dryrun.test", "+9990000%"))
    db.execute("DELETE FROM raw_events WHERE dedupe_key LIKE %s OR dedupe_key LIKE %s",
               ("%dryrun%", "cal:cal-dry%"))
    db.set_setting("paused", False)
    db.set_setting("autonomy_level", 0)


def lead_of(email):
    return db.find_lead_by_email(email)


def pending_for(lead_id):
    return db.q1("SELECT * FROM messages WHERE lead_id=%s AND status='pending_approval' "
                 "ORDER BY created_at DESC LIMIT 1", (lead_id,))


cleanup()
print(f"Keepsake Sales Agent · dry run · autonomy L0 · {config.MODEL} (mocked)")

# ---------- 1. sourcing ----------
section("1 · Source & score (no one is contacted)")
for i, (name, email) in enumerate([("Priya Nair", "priya@dryrun.test"),
                                   ("Arjun Mehta", "arjun@dryrun.test")]):
    db.insert_lead(segment="trek_operator", name=name, company=f"Summit Treks {i}",
                   role="Founder", email=email, phone=None, source="csv",
                   score=50, facts={"research": "Runs guided Himalayan treks, ~400 clients/season, "
                                                "strong Google reviews, finisher certificates today."},
                   state=State.SOURCED)
from app import brain                                    # noqa: E402
for email in ("priya@dryrun.test", "arjun@dryrun.test"):
    ld = lead_of(email)
    s = brain.score_lead(ld["segment"], ld)
    db.update_lead(ld["id"], score=int(s["score"]))
    step(f"scored {email}", 0 <= s["score"] <= 100, f"score={s['score']} fit={s['fit'][:50]}")
step("both parked as SOURCED, nothing sent",
     all(lead_of(e)["state"] == State.SOURCED for e in ("priya@dryrun.test", "arjun@dryrun.test")))

# ---------- 2. review -> queue -> opener ----------
section("2 · Operator approves leads · worker fires openers")
for email in ("priya@dryrun.test", "arjun@dryrun.test"):
    r = client.post(f"/leads/{lead_of(email)['id']}/queue", params=SEC)
    step(f"review-approved {email} -> QUEUED", r.status_code == 200)
r = client.post("/outreach/run", params={**SEC, "limit": 5})
step("outreach batch dispatched", r.json()["dispatched"] == 2, "2 openers drafted")
p1, p2 = pending_for(lead_of("priya@dryrun.test")["id"]), pending_for(lead_of("arjun@dryrun.test")["id"])
step("Level 0: both openers wait for approval", p1 is not None and p2 is not None)
step("critic ran on the drafts", "critic" in p1["meta"])

# ---------- 3. approvals: one verbatim, one edited ----------
section("3 · SK approves — one unchanged, one edited (tracked)")
r = client.post(f"/approve/{p1['id']}", params=SEC, json={"body": p1["body"]})
step("verbatim approval sends", r.json()["status"] == "sent" and not r.json()["edited"])
r = client.post(f"/approve/{p2['id']}", params=SEC, json={"body": p2["body"] + "\n\nP.S. Loved the Roopkund route."})
step("edited approval sends and is flagged", r.json()["status"] == "sent" and r.json()["edited"])
step("follow-up drip scheduled (day 3)",
     db.q1("SELECT count(*) c FROM jobs WHERE kind='follow_up' AND status='pending' "
           "AND payload->>'lead_id'=%s", (str(lead_of("priya@dryrun.test")["id"]),))["c"] == 1)
step("leads now CONTACTED", lead_of("priya@dryrun.test")["state"] == State.CONTACTED)

# ---------- 4. interested reply ----------
section("4 · Prospect replies interested · agent pushes the call")
sl = {"event_type": "EMAIL_REPLY", "to_email": "priya@dryrun.test",
      "reply_body_plain": "This sounds interesting — happy to do a quick call.",
      "email_stats_id": "st-1", "message_id": "<m1@dryrun>", "campaign_id": "c-1"}
r = client.post("/webhooks/smartlead", params=SEC, json=sl)
step("reply webhook accepted", r.json().get("ok") is True)
r = client.post("/webhooks/smartlead", params=SEC, json=sl)
step("retry of same delivery deduped", r.json().get("ignored") == "duplicate delivery")
ld = lead_of("priya@dryrun.test")
step("drip cancelled on reply",
     db.q1("SELECT count(*) c FROM jobs WHERE kind='follow_up' AND status='pending' "
           "AND payload->>'lead_id'=%s", (str(ld["id"]),))["c"] == 0)
step("intent classified INTERESTED",
     db.q1("SELECT intent FROM messages WHERE lead_id=%s AND direction='in' "
           "ORDER BY created_at DESC LIMIT 1", (ld["id"],))["intent"] == "INTERESTED")
rep = pending_for(ld["id"])
step("reply drafted, awaiting approval, includes calendar link",
     rep is not None and config.CAL_LINK in rep["body"])
step("state moved to BOOKING", lead_of("priya@dryrun.test")["state"] == State.BOOKING)
client.get(f"/approve/{rep['id']}", params=SEC)
step("booking push sent", db.q1("SELECT status FROM messages WHERE id=%s", (rep["id"],))["status"] == "sent")

# ---------- 5. pricing -> escalation ----------
section("5 · Pricing question · wall holds · SK is paged")
r = client.post("/webhooks/smartlead", params=SEC, json={
    "event_type": "EMAIL_REPLY", "to_email": "arjun@dryrun.test",
    "reply_body_plain": "Before we talk, what's the cost per poster roughly?",
    "email_stats_id": "st-2", "message_id": "<m2@dryrun>", "campaign_id": "c-1"})
ld = lead_of("arjun@dryrun.test")
step("lead frozen as ESCALATED", ld["state"] == State.ESCALATED)
esc = db.q1("SELECT * FROM escalations WHERE lead_id=%s AND status='open'", (ld["id"],))
step("escalation opened with a suggested holding reply", esc is not None and esc["suggestion"])
r = client.post(f"/escalations/{esc['id']}/resolve", params=SEC,
                json={"instruction": "Confirm SK will cover pricing on the call, offer Tue/Wed."})
step("SK's instruction dispatched as a draft", r.json()["message_status"] == "pending_approval")
hold = pending_for(ld["id"])
step("holding reply contains no pricing language", policy.check_content(hold["body"]).ok)
client.get(f"/approve/{hold['id']}", params=SEC)

# ---------- 6. opt-out ----------
section("6 · Opt-out · permanent suppression")
client.post("/webhooks/smartlead", params=SEC, json={
    "event_type": "EMAIL_REPLY", "to_email": "arjun@dryrun.test",
    "reply_body_plain": "Actually please stop emailing me.",
    "email_stats_id": "st-3", "message_id": "<m3@dryrun>", "campaign_id": "c-1"})
ld = lead_of("arjun@dryrun.test")
step("state OPTED_OUT", ld["state"] == State.OPTED_OUT)
step("email suppressed forever", db.is_suppressed(email="arjun@dryrun.test"))
blocked = policy.pre_send(ld, "email", "hello again", is_cold_opener=False)
step("any future send is refused", not blocked.ok and "suppressed" in blocked.reasons)

# ---------- 7. booking -> handoff ----------
section("7 · Cal.com booking · handoff packet · agent stops")
r = client.post("/webhooks/cal", params=SEC, json={
    "triggerEvent": "BOOKING_CREATED",
    "payload": {"uid": "cal-dry-1", "attendees": [{"email": "priya@dryrun.test", "name": "Priya"}]}})
ld = lead_of("priya@dryrun.test")
step("lead HANDED_OFF", ld["state"] == State.HANDED_OFF)
step("handoff packet written", ld["handoff"] and "brief" in ld["handoff"])
conf = pending_for(ld["id"])
step("warm confirmation drafted for approval", conf is not None)
r = client.get(f"/approve/{conf['id']}", params=SEC)
step("confirmation sends despite HANDED_OFF (purpose-scoped exception)",
     db.q1("SELECT status FROM messages WHERE id=%s", (conf["id"],))["status"] == "sent")

# ---------- 8. worker & follow-up path ----------
section("8 · Worker job path (forced follow-up)")
db.insert_lead(segment="trek_operator", name="Silent Sam", company="Quiet Treks",
               role="Owner", email="sam@dryrun.test", phone=None, source="csv", score=70,
               facts={"research": "small operator, Sahyadri weekend treks"}, state=State.QUEUED)
client.post("/outreach/run", params={**SEC, "limit": 5})
sam = lead_of("sam@dryrun.test")
op = pending_for(sam["id"])
client.get(f"/approve/{op['id']}", params=SEC)
db.execute("UPDATE jobs SET run_at=now() WHERE kind='follow_up' AND payload->>'lead_id'=%s", (str(sam["id"]),))
jobs = db.due_jobs()
for j in jobs:
    orchestrator.run_job(j)
    db.mark_job(j["id"], "done")
step("due follow-up claimed and executed", any(j["kind"] == "follow_up" for j in jobs))
fu = db.q1("SELECT * FROM messages WHERE lead_id=%s AND meta->>'purpose'='follow_up_2' "
           "ORDER BY created_at DESC LIMIT 1", (sam["id"],))
step("follow_up_2 drafted after silence", fu is not None)
# we forced the job early, so the 20h min-gap correctly deferred it instead of sending
step("min-gap deferred the too-early touch (rescheduled, not blocked)",
     fu["status"] in ("draft", "pending_approval"),
     f"status={fu['status']}" + (" · send_draft job queued" if fu["status"] == "draft" else ""))

# ---------- 9. kill switch ----------
section("9 · Kill switch")
client.post("/admin/pause", params=SEC)
blocked = policy.pre_send(lead_of("sam@dryrun.test"), "email", "anything", is_cold_opener=False)
step("paused blocks every send", not blocked.ok and "kill_switch_on" in blocked.reasons)
client.post("/admin/resume", params=SEC)

# ---------- summary ----------
section("Result")
m = client.get("/metrics", params=SEC).json()
print(f"  states: " + ", ".join(f"{k}={v}" for k, v in sorted(m["states"].items())))
print(f"  sent 24h={m['sent_24h']} · pending={m['pending_approvals']} · escalations open={m['open_escalations']}"
      f" · approval rate 7d={m['approval_rate_7d']}% (edited={m['edited_7d']})")
print(f"\nDRY RUN PASSED — {len(PASSED)} checks, 0 external calls, 0 tokens spent.")
