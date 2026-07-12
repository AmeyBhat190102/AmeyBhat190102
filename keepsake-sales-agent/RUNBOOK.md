# Keepsake Sales Agent · Operator Runbook

This is your manual. Ten minutes a day runs the whole machine. Everything below is visible live at `{BASE_URL}/dashboard?secret=YOUR_WEBHOOK_SECRET`.

---

## 1. Running it

Two processes, always both:

```
uvicorn app.main:app --host 0.0.0.0 --port 8000     # API + webhooks + dashboard
python -m app.worker                                 # follow-ups, paced outreach, heartbeat
```

First-run checklist (once):
1. `psql $DATABASE_URL -f schema.sql`
2. All env vars set (see `app/config.py`); `WEBHOOK_SECRET` is also your dashboard password.
3. Smartlead: campaign created with step 1 = `{{agent_body}}` / subject `{{agent_subject}}`; reply webhook pointed at `/webhooks/smartlead?secret=...`; domains warmed 30 days.
4. WhatsApp: Meta verification done, `keepsake_intro` and `owner_alert` templates approved, webhook at `/webhooks/whatsapp`.
5. Cal.com: booking webhook at `/webhooks/cal?secret=...` so a booked call auto-triggers handoff.
6. Autonomy at Level 0. Open the dashboard. You should see the worker heartbeat go green within 90 seconds.

Stop everything instantly: the Pause button, or `POST /admin/pause?secret=...`. Nothing sends while paused; inbound still gets logged.

## 2. Your daily loop (morning, 10 minutes)

1. Open the dashboard. Glance at the health strip; anything red, jump to section 6.
2. Clear **Awaiting your approval**. At Level 0 this is every message. Approve unchanged when it's good; reject when it's not. Your approve/reject pattern is itself the key quality metric.
3. Clear **Escalations**. Pricing asks and proposed call times land here with a suggested reply; edit the instruction if needed and send.
4. Skim **Review queue** if you sourced leads yesterday; approve or reject them (section 5).
5. Check **calls booked**. That number is the business.

## 3. How to judge if it's running properly

Three layers can fail independently: the plumbing, the deliverability, and the selling. Judge each on its own signals.

### Layer 1 · Plumbing (is it alive)
| Signal | Green | Red | Meaning |
|---|---|---|---|
| Worker heartbeat | under 90s | older / missing | worker process died; restart `python -m app.worker` |
| Jobs | 0 failed, 0 overdue | any failed or overdue >5 min | scheduler stalled; check worker logs |
| Failed sends 24h | 0 | 3+ | Smartlead/WA credentials or template problem |
| Replies webhook | replies arriving while sends happen | sends > 20 but zero inbound events in 48h | webhook broken; you're talking into the void. Fix before anything else, silent replies are lost deals |

### Layer 2 · Deliverability (are emails landing)
Watch these inside Smartlead and Meta Business Manager, not the dashboard:
- Bounce rate under 2% and spam complaints under 0.1%; cross either and pause the campaign, fix the list.
- Reply rate 7d on the dashboard: 2%+ green, 1-2% yellow, under 1% after ~50 contacted means list or copy problem; industry average for cold B2B sits around 3.4%.
- WhatsApp quality rating stays green in Meta Business Manager. Error 131049 on sends means users hit their marketing frequency cap; back off, it is not a bug.

### Layer 3 · Selling quality (is the brain good)
- **Draft approval rate 7d** (dashboard): the share of drafts you approve unchanged at Level 0. This is the same first-draft-approval thesis as the poster product. 80%+ for two straight weeks earns Level 1. Below 60%, the playbooks or claims need editing, not the model.
- **QC blocks 7d**: 0-1 is normal. Rising means the drafter keeps reaching for claims that aren't whitelisted; either expand `CLAIMS` in config or read the blocked drafts to see what it wants to say.
- **Escalation mix**: pricing escalations are good news (buying signals). Angry escalations above ~2% of replies means the copy or targeting is off; pause and read threads.
- **Funnel math** per 100 contacted, healthy cold B2B: 3-6 replies, 1-2 calls booked. 150+ contacted with zero booked: stop, read every reply thread, fix before scaling.

Weekly ritual (Friday, 20 min): read 5 full threads end to end in the drawer, note where the agent felt robotic, edit playbook angles, review autonomy level.

## 4. Triggering lead generation

Sourcing never contacts anyone. It fetches, dedupes, scores, and parks leads as SOURCED for your review.

**Dashboard**: Generate leads card → pick segment, count, optional keywords → *Source & score*.

**API**:
```
curl -X POST "$BASE_URL/leadgen/run?secret=$SECRET&segment=trek_operator&n=25"
curl -X POST "$BASE_URL/leadgen/run?secret=$SECRET&segment=wedding_planner&n=25&keywords=destination%20wedding%20goa"
```

**CSV** (your own scraped/curated lists, e.g. Apify Google Maps exports):
```
python -m scripts.leads import leads.csv trek_operator
```
Columns: `name,company,role,email,phone,research`. Fill `research` well; it is the only raw material for personalisation and scoring. Verify emails before import; bounces burn domains.

Requires `APOLLO_API_KEY` for the Apollo path. Each sourced lead gets an LLM fit score (0-100), a one-line reason, and red flags, judged strictly from the research text; the scorer is told to never invent facts.

## 5. Evaluating the leads it created

The review queue shows score, reason, and flags. Your rubric:

- **Approve (→ queue)** when: the business clearly has end-clients with emotional milestones (trekkers, couples, employees), the person plausibly decides on gifting or marketing, and the research text is specific enough to personalise from.
- **Reject** when: aggregator or marketplace rather than an operator, defunct or unverifiable, generic role at a giant company, empty research, or any flag you can't dismiss in 10 seconds.
- Scores calibrate you, they don't decide: 80+ should almost always be approved, under 40 almost always rejected. The 50-70 band is where your judgment earns its keep.
- Track your own acceptance rate. If you reject more than half of a batch, the keywords are wrong; change them in the next run rather than grinding through bad batches.
- Approving moves a lead to QUEUED. The worker then drips openers in small batches (3 every 20 minutes) inside send hours, respecting all caps. You can also force a batch: `POST /outreach/run?secret=...&limit=10`.

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Heartbeat red | worker not running | restart worker; check DB connectivity |
| Sends fail with smartlead 4xx | API key / campaign id | verify `SMARTLEAD_API_KEY`, `SMARTLEAD_CAMPAIGN_ID` |
| WA sends fail 401/403 | token expired | regenerate permanent token in Meta, update `WA_TOKEN` |
| Sent > 0 but zero replies ever | reply webhook not wired | re-add webhook URLs in Smartlead / Meta app; test with a reply from your own inbox |
| Everything stuck in pending_approval | that's Level 0 working | approve from dashboard or WhatsApp links; raise autonomy when earned |
| Leadgen returns error | `APOLLO_API_KEY` missing | set it, or use the CSV path |
| Message blocked, reason `pricing_language` | draft contained a price | correct behaviour; the wall held. If it was your own approved anchor, set `PUBLIC_PRICE_ANCHOR` |
| Lead says stop but keeps getting drafts | should never happen; if it does, pause + check `suppressions` table | file it as a bug immediately |

## 7. Promotion criteria (autonomy)

- Level 0 → 1: two consecutive weeks with draft approval ≥80%, zero compliance incidents, webhooks proven live.
- Level 1 → 2: two more weeks at ≥85% approval on replies, escalations handled cleanly, at least 3 calls booked.
- Any week with an angry-rate spike, a deliverability breach, or a pricing leak: drop one level, read threads, fix, re-earn it.
