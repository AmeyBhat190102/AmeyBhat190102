# Keepsake Sales Agent

An autonomous sales agent for Keepsake Press. It sources nothing on its own authority: you feed it leads, it works them over email (cold) and WhatsApp (warm, opt-in only), books a call with SK, hands off, and stops. Pricing never leaves the founder's hands.

## What "closed" means here
Firm yes + call booked with SK. That's the terminal state. The agent then sends you a handoff packet (who, what they want, agreed next step, watch-outs, full thread) and freezes the lead.

## Architecture

```
Apollo / Apify / CSV        Website form / CTWA ads
        |                            |
     [SOURCED] --queue--> [QUEUED]   |
        \                            v
         `--> orchestrator <--- webhooks (Smartlead reply, WhatsApp, Cal.com)
                   |
     classify -> route (state machine) -> draft (LLM)
                   |                          |
             policy engine  <----------  QC critic
             (deterministic)              (every message)
                   |
        approval gate (autonomy 0/1/2)
                   |
        Smartlead (email) / WhatsApp Cloud API
                   |
     CALL_BOOKED -> handoff packet -> SK (WhatsApp)
```

Layers:
- **State machine** (`models.py`): SOURCED → QUEUED → CONTACTED → ENGAGED → BOOKING → CALL_BOOKED → HANDED_OFF, plus ESCALATED / NOT_NOW / LOST / OPTED_OUT. The LLM emits an intent; the routing table picks the transition. The LLM never picks a state.
- **Policy engine** (`policy.py`): kill switch, suppression list, WhatsApp opt-in requirement, quiet hours (IST), per-lead and global rate caps, touch caps, and a hard regex wall against any pricing language. Deterministic; runs before every send; the LLM cannot override it.
- **Brain** (`brain.py`): three jobs. Classify inbound intent. Draft within an approved-claims whitelist. Critic-check every draft (prices, invented facts, overclaims) with auto-fix or block.
- **Memory** (`db.py`): Postgres is the source of truth. Verbatim messages, a rolling per-lead summary, extracted facts. Context per turn = playbook + claims + facts + summary + last 12 messages.
- **Events** (`main.py`): webhooks for Smartlead replies, WhatsApp inbound, Cal.com bookings, website leads. Every raw payload is logged, every outcome reconstructable.
- **Scheduler** (`worker.py` + `jobs` table): follow-ups at day 3/4/5, one revival after 45 days, paced outreach batches every 20 minutes inside send hours. A reply cancels the drip instantly.

## Escalation triggers (always page SK, at any autonomy level)
Pricing or discount asks · requests for a human · anger · prospect proposes their own call times · referrals · QC blocks. The agent drafts a holding reply for one-tap approval and freezes the lead until you resolve.

## Setup runbook

1. **Postgres**: `createdb keepsake && psql $DATABASE_URL -f schema.sql`
2. **Env** (see all in `app/config.py`):
   `DATABASE_URL, ANTHROPIC_API_KEY, WEBHOOK_SECRET, BASE_URL, SK_WHATSAPP, CAL_LINK,`
   `SMARTLEAD_API_KEY, SMARTLEAD_CAMPAIGN_ID, WA_PHONE_ID, WA_TOKEN, WA_VERIFY_TOKEN`
3. **Email infra (do this first, it gates everything)**: buy 3 secondary domains (brand variants, .com/.in/.co; never your primary domain), 2-3 mailboxes each, SPF/DKIM/DMARC, connect to Smartlead, run warmup for 30 days before the first cold send, and keep warmup running forever. Create one Smartlead campaign whose step 1 body is exactly `{{agent_body}}` with subject `{{agent_subject}}`; point its reply webhook at `POST {BASE_URL}/webhooks/smartlead?secret=...`.
4. **WhatsApp**: complete Meta Business Verification, register a number on the Cloud API, and get two templates approved: `keepsake_intro` (marketing, 1 body param) and `owner_alert` (utility, 1 body param, used to page you). Point the webhook at `/webhooks/whatsapp`. WhatsApp is never used cold; the agent only moves there after a prospect shares a number and agrees.
5. **Run**: `pip install -r requirements.txt` then `uvicorn app.main:app --port 8000` and `python -m app.worker` (two processes).
6. **Leads**: `python -m scripts.leads import leads.csv trek_operator` then `python -m scripts.leads queue_all trek_operator 20`. Verify emails before import; bounces above 2% burn domains.

## Graduated autonomy (do not skip)
- **Level 0 (weeks 1-2)**: every message pings your WhatsApp with approve/reject links. You are the send button.
- **Level 1**: cold openers auto-send; replies to humans still need your tap.
- **Level 2**: full auto; only escalation triggers stop it.
Change at runtime: `POST /admin/autonomy/1?secret=...`. Kill switch: `POST /admin/pause?secret=...`. Daily digest: hit `GET /digest?secret=...` from a cron.

## Compliance stance (why the design looks like this)
- WhatsApp requires explicit opt-in; cold WhatsApp is prohibited and enforced hard (frequency caps, tier cuts, bans). Email carries the cold motion; WhatsApp closes warm.
- Every email ends with a working opt-out line; any stop request suppresses email + phone permanently and sends one final confirmation.
- The agent discloses it's an AI concierge in its signature (`DISCLOSE_AI=true`). Keep it on. It costs nothing before the call and protects trust at handoff.
- The agent can only assert facts from `CLAIMS` in `config.py`. Edit that list; nothing else it says about the company is permitted to exist.

## What v1 deliberately does not do
Scrape leads autonomously (you curate lists), see your calendar (Cal.com link + webhook instead), talk prices (ever), or send on LinkedIn/Instagram. Each is an add-on once the core loop proves itself at Level 0.
