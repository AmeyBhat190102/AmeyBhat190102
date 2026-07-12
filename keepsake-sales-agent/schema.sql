-- Keepsake Sales Agent · Postgres schema
-- psql $DATABASE_URL -f schema.sql

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS leads (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  segment       TEXT NOT NULL,                 -- trek_operator | wedding_planner | corporate_gifting | d2c_inbound
  name          TEXT,
  company       TEXT,
  role          TEXT,
  email         TEXT,
  phone         TEXT,                          -- E.164, e.g. +9198xxxxxxx
  wa_opt_in     BOOLEAN NOT NULL DEFAULT FALSE,
  wa_last_inbound_at TIMESTAMPTZ,              -- controls 24h session window
  state         TEXT NOT NULL DEFAULT 'SOURCED',
  sequence_step INT  NOT NULL DEFAULT 0,       -- outreach touches sent
  score         INT  NOT NULL DEFAULT 50,
  source        TEXT,                          -- apollo | apify_maps | csv | inbound_web | ctwa
  summary       TEXT NOT NULL DEFAULT '',      -- rolling conversation memory
  facts         JSONB NOT NULL DEFAULT '{}',   -- research + extracted commitments
  handoff       JSONB,                         -- final packet once CALL_BOOKED
  lost_reason   TEXT,
  next_action_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS leads_state_idx ON leads(state);
CREATE UNIQUE INDEX IF NOT EXISTS leads_email_uq ON leads(lower(email)) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS leads_phone_uq ON leads(phone) WHERE phone IS NOT NULL;

CREATE TABLE IF NOT EXISTS messages (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id     UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  direction   TEXT NOT NULL,                   -- in | out
  channel     TEXT NOT NULL,                   -- email | whatsapp | system
  subject     TEXT,
  body        TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'draft',   -- draft | pending_approval | approved | sent | blocked | failed | received
  intent      TEXT,                            -- classifier output for inbound
  provider_id TEXT,                            -- smartlead / wamid reference
  meta        JSONB NOT NULL DEFAULT '{}',     -- critic report, policy log, approval token
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS messages_lead_idx ON messages(lead_id, created_at);
CREATE INDEX IF NOT EXISTS messages_status_idx ON messages(status);

CREATE TABLE IF NOT EXISTS jobs (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_at    TIMESTAMPTZ NOT NULL,
  kind      TEXT NOT NULL,                     -- follow_up | revive | digest
  payload   JSONB NOT NULL DEFAULT '{}',
  status    TEXT NOT NULL DEFAULT 'pending',   -- pending | running | done | failed | cancelled
  attempts  INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS jobs_due_idx ON jobs(status, run_at);

CREATE TABLE IF NOT EXISTS escalations (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id    UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  reason     TEXT NOT NULL,                    -- pricing | human_request | angry | ambiguous | legal | times_proposed
  context    TEXT NOT NULL,
  suggestion TEXT,                             -- agent's suggested reply, awaiting SK
  status     TEXT NOT NULL DEFAULT 'open',     -- open | resolved | dismissed
  resolution TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS suppressions (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  kind      TEXT NOT NULL,                     -- email | phone | domain
  value     TEXT NOT NULL,
  reason    TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (kind, value)
);

CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value JSONB NOT NULL
);
INSERT INTO settings (key, value) VALUES ('paused', 'false') ON CONFLICT (key) DO NOTHING;
INSERT INTO settings (key, value) VALUES ('autonomy_level', '0') ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS raw_events (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source     TEXT NOT NULL,                    -- smartlead | whatsapp | cal | web
  payload    JSONB NOT NULL,
  processed  BOOLEAN NOT NULL DEFAULT FALSE,
  error      TEXT,
  dedupe_key TEXT,                             -- provider message id; blocks webhook-retry double processing
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS raw_events_dedupe_uq ON raw_events(dedupe_key) WHERE dedupe_key IS NOT NULL;
