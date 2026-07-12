"""Central configuration. Everything SK tunes lives here or in env vars."""
import os

# ---------- dry run ----------
# DRY_RUN=true: nothing leaves the box. Channel sends are logged and return a
# dryrun: provider ref; the LLM layer answers with deterministic canned JSON.
# The full pipeline (policy, critic, approvals, jobs) still runs against the DB.
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

# ---------- infrastructure ----------
DATABASE_URL   = os.environ["DATABASE_URL"]
ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "") if DRY_RUN else os.environ["ANTHROPIC_API_KEY"]
MODEL          = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

SMARTLEAD_KEY            = os.environ.get("SMARTLEAD_API_KEY", "")
SMARTLEAD_CAMPAIGN_ID    = os.environ.get("SMARTLEAD_CAMPAIGN_ID", "")   # campaign the agent replies through
WEBHOOK_SECRET           = os.environ.get("WEBHOOK_SECRET", "change-me") # shared secret for inbound webhooks + approval links

WA_PHONE_ID     = os.environ.get("WA_PHONE_ID", "")      # WhatsApp Cloud API phone number id
WA_TOKEN        = os.environ.get("WA_TOKEN", "")
WA_VERIFY_TOKEN = os.environ.get("WA_VERIFY_TOKEN", "verify-me")
WA_APP_SECRET   = os.environ.get("WA_APP_SECRET", "")    # Meta app secret; when set, X-Hub-Signature-256 is enforced
WA_INTRO_TEMPLATE = os.environ.get("WA_INTRO_TEMPLATE", "keepsake_intro")   # approved marketing template (1 body param)
WA_OWNER_TEMPLATE = os.environ.get("WA_OWNER_TEMPLATE", "owner_alert")      # approved utility template to notify SK (1 body param)

SK_WHATSAPP = os.environ.get("SK_WHATSAPP", "")          # SK's number in E.164
BASE_URL    = os.environ.get("BASE_URL", "http://localhost:8000")  # public URL for approval links
CAL_LINK    = os.environ.get("CAL_LINK", "https://cal.com/sk/keepsake-intro")
AGENT_NAME  = os.environ.get("AGENT_NAME", "Asha")
TZ          = os.environ.get("TZ", "Asia/Kolkata")

# ---------- autonomy ----------
# 0 = every outbound message needs SK approval (weeks 1-2)
# 1 = cold openers auto-send; replies to humans need approval
# 2 = full auto; only escalation triggers stop the agent
# Stored in DB settings so it can be changed at runtime; env is the initial default.
DEFAULT_AUTONOMY = int(os.environ.get("AUTONOMY_LEVEL", "0"))

# ---------- hard policy ----------
QUIET_HOURS = (21, 9)            # no outbound between 21:00 and 09:00 IST
MAX_TOUCHES = 4                  # opener + 3 follow-ups, then NOT_NOW
FOLLOW_UP_DAYS = [3, 4, 5]       # spacing between touches
REVIVE_AFTER_DAYS = 45           # one revival attempt after NOT_NOW
MIN_GAP_HOURS = 20               # never message the same lead twice within this gap
GLOBAL_DAILY_CAP = 120           # total outbound/day across channels (raise as domains warm)
PER_LEAD_DAILY_CAP = 2

# Pricing wall: the agent NEVER states or negotiates prices. If SK later wants a
# public anchor line, set it here verbatim; only this exact sentence is permitted.
PUBLIC_PRICE_ANCHOR: str | None = None
PRICE_BLOCK_PATTERNS = [r"₹\s?\d", r"\$\s?\d", r"\d+\s?%\s?(off|discount)", r"\bdiscount\b",
                        r"\bper (unit|piece|poster)\b", r"\bquote\b.{0,20}\d"]

OPT_OUT_WORDS = ["stop", "unsubscribe", "remove me", "don't contact", "do not contact", "opt out"]

# ---------- claim whitelist ----------
# The agent may only assert facts from this list. Anything else gets stripped by the critic.
CLAIMS = [
    "Keepsake Press turns real memories into designed keepsake posters, printed and framed.",
    "Every detail on a poster comes from what the customer tells us; nothing is invented.",
    "Customers approve a draft before anything is printed.",
    "Posters are print-grade at 300 DPI.",
    "We offer a white-label gifting programme for partners such as trek operators, wedding planners and HR teams.",
    "Partners can gift clients a personalised poster of their trek, wedding or milestone.",
    "Drafts are typically ready within 24 hours.",
    "We are based in India and ship across India.",
    "Pricing depends on volume and format; SK covers it on a short call.",
]

# ---------- playbooks ----------
PLAYBOOKS = {
    "trek_operator": {
        "outbound": True,
        "apollo_keywords": "trekking adventure travel operator himalaya",
        "value_prop": "A personalised trek poster (route, dates, stats, their photo) as a finisher gift boosts reviews, referrals and repeat bookings.",
        "opener_angle": "Reference their specific treks and seasons. One idea, one question. Under 90 words.",
        "goal": "Book a 20-minute call with SK to design a pilot gifting run.",
    },
    "wedding_planner": {
        "outbound": True,
        "apollo_keywords": "wedding planner events india",
        "value_prop": "A keepsake poster of the wedding weekend is a high-margin add-on and a memorable planner signature gift.",
        "opener_angle": "Reference their portfolio style. Position as their branded farewell gift. Under 90 words.",
        "goal": "Book a 20-minute call with SK to see samples and pilot pricing.",
    },
    "corporate_gifting": {
        "outbound": True,
        "apollo_keywords": "hr people operations employee experience gifting",
        "value_prop": "Personalised milestone posters (work anniversaries, offsites, launches) beat generic hampers on cost and sentiment.",
        "opener_angle": "Reference their company scale or a recent event. Under 90 words.",
        "goal": "Book a 20-minute call with SK for a pilot for their next occasion.",
    },
    "d2c_inbound": {
        "outbound": False,   # never cold; only replies to inbound enquiries (site, Click-to-WhatsApp ads)
        "value_prop": "Your memory, set in print. You describe it, approve the draft, we print and frame it.",
        "opener_angle": "Warm, personal, zero pressure. Ask what memory they want to keep.",
        "goal": "Get their memory brief started, then book a call with SK only if it's a bulk or custom order.",
    },
}

# AI disclosure. Keep this on. It protects trust at handoff and keeps you clean.
DISCLOSE_AI = os.environ.get("DISCLOSE_AI", "true").lower() == "true"
SIGNATURE = f"{AGENT_NAME} · Keepsake Press" + (" (AI concierge; a human reviews every order)" if DISCLOSE_AI else "")
