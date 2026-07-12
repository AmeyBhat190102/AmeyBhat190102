# Keepsake Sales Agent — Product Assessment & Extension Plan

*Based on a full read of the v1 codebase (`keepsakesalesagent.zip`, ~2,000 LOC) and the operator RUNBOOK. Date: 2026-07-12.*

---

## 1. What the product is

An **autonomous B2B sales agent for Keepsake Press** (personalised keepsake posters, India). It runs the entire top-of-funnel motion — source leads, send cold email, handle replies, move warm conversations to WhatsApp, book a call with SK (the founder) — and then stops. "Closed" = call booked + handoff packet delivered. Pricing never leaves the founder's hands.

**Core design thesis** (and it's a good one): *the LLM proposes, deterministic code disposes.*

- **State machine** (`models.py`) — 11 lead states; the LLM emits an *intent*, a static routing table picks the transition. The LLM never picks a state.
- **Policy engine** (`policy.py`) — deterministic pre-send wall: kill switch, suppression list, WhatsApp opt-in requirement, quiet hours (IST 21:00–09:00), per-lead/global rate caps, touch caps, regex pricing wall. Runs before *every* send; re-runs at transmit time.
- **Brain** (`brain.py`) — exactly three LLM jobs: classify intent, draft within a claims whitelist, critic-check every draft. Plus lead scoring and handoff briefs.
- **Graduated autonomy** — Level 0 (approve everything) → 1 (openers auto) → 2 (full auto), earned via approval-rate thresholds defined in the RUNBOOK.
- **Channels** (`channels.py`) — Smartlead for cold email (owns warmup/deliverability), WhatsApp Cloud API for warm/opt-in only, correct 24h-session vs template handling.
- **Memory** — Postgres as source of truth: verbatim messages, rolling per-lead summary, extracted facts, full raw-event log. Every outcome reconstructable.
- **Ops surface** — single-file dashboard (approvals, review queue, escalations, pipeline, leadgen trigger, pause, autonomy), worker heartbeat, daily digest.

Segments: `trek_operator`, `wedding_planner`, `corporate_gifting` (outbound) and `d2c_inbound` (inbound-only, via website form / Click-to-WhatsApp ads).

---

## 2. Requirements audit — is v1 complete?

### ✅ Met (verified in code)

| Requirement (README/RUNBOOK) | Where | Verdict |
|---|---|---|
| State machine, LLM never picks states | `models.py`, `orchestrator._route` | ✅ Clean |
| Pricing wall (regex + critic + escalation) | `policy.check_content`, `brain.critic`, `PRICING` intent | ✅ Triple-layered |
| WhatsApp opt-in enforcement, no cold WA | `policy.pre_send` step 2 | ✅ Hard-coded |
| Quiet hours defer (not block) | `policy.pre_send` step 4 + `next_send_window` | ✅ |
| Rate caps (global 120/day, 2/lead/day, 20h min gap) | `policy.pre_send` step 3 | ✅ |
| Touch cap (4) + follow-ups day 3/4/5 + one 45-day revival | `orchestrator.transmit`, `run_job` | ✅ |
| Reply cancels the drip instantly | `handle_inbound` → `db.cancel_jobs` first line | ✅ |
| Approval gate by autonomy level, WhatsApp approve/reject links | `dispatch`, HMAC token per message | ✅ |
| Escalation triggers (pricing, human, angry, times-proposed, referral, QC block) | `ESCALATE_INTENTS`, `_route` | ✅ |
| Handoff packet + freeze on CALL_BOOKED | `orchestrator.handoff` | ✅ |
| Opt-out → permanent suppression + one confirmation | `_route` suppress + `_confirm_opt_out` | ✅ |
| Claims whitelist + critic strips anything else | `config.CLAIMS`, `brain.critic` | ✅ |
| AI disclosure in signature | `config.SIGNATURE` | ✅ |
| Sourcing never contacts anyone (SOURCED → review → QUEUED) | `leadgen.run`, dashboard review queue | ✅ |
| LLM lead scoring, "never invent facts" | `brain.score_lead` | ✅ |
| Paced outreach (3 per 20 min inside send hours) | `worker.loop` | ✅ |
| Full audit trail (raw events, message meta, critic reports) | `db.log_event`, message `meta` | ✅ |
| Dashboard: health strip, approvals, review queue, escalations, pipeline, drawer, leadgen card | `dashboard.html` | ✅ All present |
| Metrics the RUNBOOK references (reply rate 7d, approval rate 7d, QC blocks 7d, heartbeat, booked) | `db.metrics` | ✅ |

**Verdict: v1's stated scope is genuinely implemented.** The RUNBOOK is honest — everything it tells the operator to look at exists. The deliberate non-goals (autonomous scraping, calendar access, pricing, LinkedIn/IG) are cleanly excluded rather than half-built.

### ⚠️ Gaps and real bugs found (fix before scaling)

**Security / compliance**

1. **WhatsApp webhook has no signature verification.** `POST /webhooks/whatsapp` accepts any payload — no `X-Hub-Signature-256` check, no secret. An attacker (or a misconfigured retry) can forge inbound messages, flip `wa_opt_in=True` on any lead, create junk D2C leads, and burn LLM spend. Meta signs every delivery; verify it.
2. **No webhook idempotency.** Smartlead and Meta both retry deliveries. A retried reply is processed twice → duplicate classify → duplicate outbound draft. Dedupe on provider message id (`wamid`, `stats_id`+`message_id`) in `raw_events`.
3. **Approval token compared with `!=`** — use `hmac.compare_digest`. Also secrets ride in URL query params (logged by proxies); acceptable for v1, should move to header/cookie.

**Correctness**

4. **WhatsApp template sends will 400 outside the 24h window.** `wa_send` stuffs the full drafted body (with newlines and signature) into a template body parameter — Meta rejects params containing newlines/tabs. Any first-touch WA message after opt-in but outside a session will fail. Params must be single-line, or the template flow needs a dedicated short param.
5. **`detect_opt_out` matches substrings.** `"stop" in text` fires on "can't stop thinking about this" or "we stop running treks in June" → an interested lead gets permanently suppressed. Use word-boundary regex and require it to be the dominant signal (or route low-confidence cases through the classifier, which already has an OPT_OUT intent).
6. **The BOOKING state is effectively unreachable.** In `_route`, the intent routing sets state to ENGAGED *before* the `booked_state == State.BOOKING` check, so `booking_push` never fires. And `CAL_LINK in row["body"]` → BOOKING only runs when `status == "sent"`, which is never true at Level 0 (status is `pending_approval`). State drift between what the machine models and what actually happens.
7. **Existing lead re-enquiring via website form is silently dropped.** `insert_lead` uses `ON CONFLICT DO NOTHING RETURNING *` → returns `None` for a duplicate; `/webhooks/inbound_lead` doesn't re-fetch (the WA hook does), so the message is lost.
8. **Webhook handlers do LLM work inline.** The FastAPI handlers are `async` but call the synchronous orchestrator, which makes up to three blocking Anthropic calls (60s timeout each). Meta expects a fast 200; slow responses → retries → duplicate processing (compounds bug #2). The event loop is also blocked for every other request. Webhooks should persist + ack immediately and let the worker process inbound.
9. **Jobs are marked `done` before they run** (`due_jobs` UPDATE…RETURNING). A worker crash mid-job silently loses a follow-up. Should be `running` → `done`/`failed`, with retry-on-crash semantics.
10. **No approve-with-edit.** The RUNBOOK's whole quality metric is "approved *unchanged*", but the only options are approve verbatim or reject-and-lose-it. Operators will approve mediocre drafts out of friction. An edit box on the approval card (and tracking edited vs unchanged separately) makes Level-promotion data honest.

**Engineering hygiene**

11. **Zero tests, no CI, no lint config, no Dockerfile, no migrations** (schema.sql only), no `.env.example`. The policy engine and state routing are pure functions begging for a test suite — this is the highest-value 200 lines of test code available.
12. **Raw `requests` to the Anthropic API** — no retry/backoff on 429/529, no structured outputs (hand-rolled JSON brace-parser with one retry). The official SDK + tool-forced JSON removes a whole failure class.
13. **`db.py` interpolates field names into SQL** in `update_lead`/`update_message`. Callers are all internal today, so not exploitable, but one careless future caller makes it injectable. Whitelist columns.

---

## 3. Extension plan

Ordered so that each phase is shippable alone and de-risks the next. **Phase 0 is not optional** — everything after it multiplies volume, and the bugs above multiply with it.

### Phase 0 — Harden the core (1–2 weeks)

Fix the audit items: WA signature verification + webhook idempotency, template-param bug, opt-out word boundaries, BOOKING state repair, duplicate-lead re-enquiry, async ack-then-process for webhooks, job `running` state, approve-with-edit, constant-time tokens. Add pytest suite for `policy.py` + `models.py` routing + `_extract_json`, a Dockerfile + docker-compose (Postgres included), `.env.example`, GitHub Actions (lint + tests), and switch `brain.py` to the Anthropic SDK with retries and structured outputs.

### Phase 1 — Product functionality (the selling gets smarter)

These deepen the existing loop without widening the surface:

1. **Approve-with-edit + edit-distance tracking.** The operator's edits are free RLHF. Store the diff; a weekly job summarises what SK keeps changing and proposes playbook/claims edits. This directly serves the RUNBOOK's promotion criteria.
2. **Per-segment analytics.** `metrics()` is global; the funnel math in RUNBOOK §3 (replies per 100 contacted, calls per 100) should be per segment and per keyword batch, so bad lists are caught at the segment level, not blended away. Add a `sourcing_batches` table so each leadgen run's acceptance rate is trackable (RUNBOOK §5 asks the operator to track this by hand today).
3. **A/B opener angles.** `PLAYBOOKS` holds one `opener_angle` per segment. Make it a weighted list; tag each message with its angle; report reply rate per angle. Smallest possible experimentation loop, no new infra.
4. **Objection/FAQ memory.** Recurring questions (turnaround, shipping, samples) land as fresh LLM drafts every time. Add a curated `snippets` table (SK-approved answers, versioned) injected into the draft context — tightens voice, cuts tokens, and gives the critic firmer ground.
5. **Bounce/complaint handling as a first-class intent.** Smartlead emits bounce webhooks; today only replies are parsed. Auto-suppress hard bounces and count them — the RUNBOOK's 2% bounce threshold currently has to be checked inside Smartlead by hand.
6. **Timezone-aware quiet hours per lead** once any non-IN targeting starts (config already carries `country` in leadgen).
7. **Weekly auto-review pack.** The RUNBOOK's Friday ritual (read 5 threads, note robotic moments) can be pre-chewed: a scheduled job picks the 5 most-edited/escalated threads and drafts the "where it felt robotic" notes for SK to confirm. Keep the human in the ritual; remove the archaeology.

### Phase 2 — Integrations (widen the funnel, keep the wall)

In rough order of leverage:

1. **Cal.com deeper integration** *(explicitly deferred from v1)*. Read available slots via API so `TIMES_PROPOSED` escalations arrive with "these of their proposed times are actually free" — SK one-taps instead of calendar-cross-checking. Booking-cancelled/rescheduled webhooks should un-handoff or re-alert; today a cancellation leaves a HANDED_OFF ghost.
2. **Email verification API** (ZeroBounce/NeverBounce) in the leadgen path. The RUNBOOK pleads "verify emails before import"; make it automatic — verify on source, park failures as flagged, protect the domains.
3. **Apify Google Maps actor** as a second sourcing path (the CSV columns and `apify_maps` source enum already anticipate it). Trek operators and wedding planners are Maps-native businesses that Apollo misses.
4. **Payments/deposit link at handoff** (Razorpay): optional "pilot deposit" link SK can attach when resolving a pricing escalation — the agent still never talks numbers; it delivers SK's link verbatim. Keeps the pricing wall intact while shortening close time.
5. **LinkedIn as a *research* integration, not a sending channel.** Enrich `facts.research` at source time (recent posts, company size) for better personalisation and scoring. Sending on LinkedIn stays out — automation there is ToS-hostile and the deliverability story doesn't transfer.
6. **CRM export webhook** (generic outbound webhook or HubSpot/Sheets): fire the handoff packet into wherever SK tracks revenue, so "calls booked" can be joined to "orders won" — the one metric the system can't see today.
7. **Instagram DMs via Meta Graph** — same policy engine, same session-window logic as WA. Only after Level 2 is earned; it's the same compliance shape as WhatsApp so the code slot exists.

### Phase 3 — Code structure (earn the ability to move fast)

The current layering (`models → policy → brain → orchestrator → channels → db`) is genuinely good for 2k LOC. Restructure *incrementally*, in this order:

1. **Split the HTTP surface from processing.** Webhooks write to `raw_events` and return 200; the worker consumes unprocessed events through the same `handle_inbound` path. This fixes bug #8, makes retries idempotent (with #2's dedupe), and means the API process no longer needs LLM credentials at all.
2. **Channel adapters behind a formal interface.** `channels.py` already has `send()`; extract a `ChannelAdapter` protocol (`send`, `parse_webhook`, `verify_signature`) with `EmailChannel` and `WhatsAppChannel` classes — Instagram/SMS then become new files, not edits to a shared module.
3. **Repository layer over raw SQL.** `db.py` is 40 functions on one module; group into `LeadsRepo`, `MessagesRepo`, `JobsRepo`, `SettingsRepo` with typed returns (Pydantic models — FastAPI is already there). Kills the f-string SQL risk and gives the test suite seams.
4. **Config → Pydantic Settings.** `config.py` crashes on import if `DATABASE_URL` is missing and mixes secrets with tunables. `pydantic-settings` gives validation, `.env` support, and lets playbooks/claims move to the DB (editable from the dashboard — the RUNBOOK already tells operators to "edit playbook angles" weekly; today that's a code deploy).
5. **Alembic migrations** so schema changes stop being "re-run schema.sql and hope IF NOT EXISTS covers it".
6. **Observability**: structured logging (structlog), Sentry, and a `/metrics` Prometheus endpoint. The dashboard is the operator's view; the builder needs one too.
7. **What *not* to do yet:** no microservices, no Celery/Redis (the Postgres job queue with `FOR UPDATE SKIP LOCKED` is correct at this scale), no framework rewrite. The two-process shape (API + worker) is right until well past 10k leads.

### Suggested sequencing

| Phase | Duration | Gate to next |
|---|---|---|
| 0 · Harden | 1–2 wks | Tests green in CI; webhooks verified + idempotent; approve-with-edit live |
| 1 · Product | 2–4 wks (parallel with Level 0→1 operation) | Approval rate ≥80% two weeks (RUNBOOK criterion) |
| 2 · Integrations | staged, one at a time | Each integration behind a config flag; funnel math stays green |
| 3 · Structure | continuous, piggybacked on Phases 1–2 | Each refactor lands with the feature that needs it |

The deepest strategic point: **this codebase's moat is the policy engine and the audit trail, not the prompts.** Every extension should route through `policy.pre_send` and land in `messages`/`raw_events`, or it doesn't ship. That discipline is what lets autonomy Level 2 ever be safe.
