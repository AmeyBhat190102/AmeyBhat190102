# Deployment · How this runs on a server & where the leads come from

## 1. Topology

Everything fits on one small VM (2 vCPU / 2 GB — a ₹800-1500/mo droplet/Lightsail box) or any container platform (Railway, Render, Fly.io):

```
                         ┌──────────────────────── your server ───────────────────────┐
 Smartlead  ─webhook─▶   │                                                            │
 Meta/WhatsApp ─webhook─▶│  Caddy/nginx (TLS :443) ──▶ uvicorn app.main:app (:8000)   │
 Cal.com    ─webhook─▶   │                                    │        ▲              │
 Website form ─POST─▶    │                                    ▼        │              │
                         │                              Postgres 16 ◀──┤              │
 SK's phone ◀─approvals──│                                    ▲        │              │
 (WhatsApp)              │                python -m app.worker┘  (30s poll loop)      │
                         └────────────────────────────────────────────────────────────┘
                                   outbound: Smartlead API · WhatsApp Cloud API ·
                                             Anthropic API · Apollo API
```

Two long-running processes, one database:

| Process | Command | Job |
|---|---|---|
| **API** | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | receives webhooks (replies, bookings, form fills), serves the dashboard and approval links, exposes admin endpoints. Webhooks ack instantly and process in the background. |
| **Worker** | `python -m app.worker` | polls the `jobs` table every 30s: fires due follow-ups/revivals, paces cold openers (3 per 20 min inside 09:00–21:00 IST), writes the heartbeat the dashboard watches. |

Neither process keeps state in memory — Postgres is the only truth — so either can be restarted at any moment without losing a conversation. `restart: unless-stopped` (compose) or systemd `Restart=always` covers crashes.

### Quick start (docker compose)

```bash
cp .env.example .env        # fill in keys
docker compose up -d --build
docker compose exec -T db psql -U keepsake keepsake < schema.sql
# open https://your-host/dashboard?secret=$WEBHOOK_SECRET
```

### Bare-metal alternative (systemd)

Two units, both `After=postgresql.service`, `ExecStart` as in the table above, `EnvironmentFile=/etc/keepsake.env`. Put Caddy in front: `agent.yourdomain.in { reverse_proxy :8000 }` — Caddy handles TLS automatically, and the webhook providers require HTTPS.

### One-time wiring after deploy

1. `psql -f schema.sql` (idempotent).
2. Smartlead campaign → reply webhook → `https://.../webhooks/smartlead?secret=...`
3. Meta app → WhatsApp webhook → `https://.../webhooks/whatsapp` (verify token = `WA_VERIFY_TOKEN`; set `WA_APP_SECRET` so signatures are enforced).
4. Cal.com → booking-created webhook → `https://.../webhooks/cal?secret=...`
5. Cron for the daily digest: `curl -X POST https://.../digest?secret=...` at 08:30 IST.
6. Watch the dashboard heartbeat turn green; keep autonomy at Level 0.

## 2. Where the "users" come from — nobody is messaged by discovery

The agent **never finds someone and immediately messages them**. Contact lists are built and gated in four stages; sending is a separate, human-approved act.

### Stage 1 · Sourcing (builds the list, sends nothing)

Three feeder paths, all landing in the `leads` table as `state=SOURCED`:

| Path | Trigger | What happens |
|---|---|---|
| **Apollo.io search** | Dashboard "Source & score" button, or `POST /leadgen/run?segment=trek_operator&n=25` | The playbook's keywords (e.g. *"trekking adventure travel operator himalaya"*) query Apollo's people-search API for matching decision-makers in India. Each person arrives with name, role, company, email and a research blurb. |
| **CSV import** | `python -m scripts.leads import leads.csv trek_operator` | Your own curated/scraped lists (e.g. Apify Google Maps exports). The `research` column is the raw material for personalisation. |
| **Inbound** | Website form → `POST /webhooks/inbound_lead`; strangers messaging the WhatsApp number (CTWA ads) | These skip cold outreach entirely — they arrive `ENGAGED` and only ever get *replies*. |

Every sourced lead is deduped against the DB (unique email/phone) and checked against the suppression list, then **scored 0–100 by the LLM strictly from the research text**, with a one-line reason and red flags.

### Stage 2 · Human review (the gate)

Sourced leads sit in the dashboard **Review queue** showing score, fit reason and flags. SK approves (→ `QUEUED`) or rejects each one. Nothing in `SOURCED` can ever be contacted — the policy engine refuses cold sends to inbound-only segments and the worker only pulls from `QUEUED`.

### Stage 3 · Paced dispatch (the drip)

The worker picks the highest-scoring `QUEUED` leads, **3 at a time, at most every 20 minutes, only between 09:00 and 21:00 IST**, max 120 sends/day globally, max 2/lead/day, never twice within 20 hours. For each lead it drafts a personalised opener from the research text, runs the QC critic and the policy wall, and then — at Level 0 — pings SK's WhatsApp with the draft and approve/reject links. Only on approval does the email actually leave, via the Smartlead campaign (which owns mailbox rotation, warmup and deliverability). Silence gets follow-ups on day 3/4/5 (4 touches max), then `NOT_NOW` and one revival after 45 days.

### Stage 4 · Replies flow back

Replies hit the webhooks, are classified for intent, and either get a drafted response (again approval-gated), escalate to SK (pricing, anger, human request, proposed times), or terminate the lead (opt-out → permanent suppression). A booked Cal.com call ends the loop with a handoff packet to SK's WhatsApp.

**WhatsApp is never used cold.** The agent only messages a prospect there after they shared their number and agreed — enforced in `policy.pre_send`, not in the prompt.

## 3. Verifying a box before going live

```bash
DRY_RUN=true python -m scripts.dry_run      # full funnel offline: no sends, no tokens
python -m pytest                            # policy wall, state machine, parsers
curl https://.../health                     # {"ok": true, "paused": false, "autonomy": 0}
```

`DRY_RUN=true` in the env makes every channel print instead of send and replaces the LLM with a deterministic mock — safe to run against the production DB schema on a fresh box.
