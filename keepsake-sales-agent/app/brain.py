"""The LLM layer. Three jobs only: classify inbound intent, draft messages
within policy, and QC-check every draft. State transitions and permissions
live outside this file; the model proposes, the policy layer disposes."""
import json
import re
import time
import requests
from . import config

API = "https://api.anthropic.com/v1/messages"
HEADERS = {
    "x-api-key": config.ANTHROPIC_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}
RETRYABLE = {429, 500, 502, 503, 529}


def _mock_answer(prompt: str) -> str:
    """DRY_RUN stand-in for the model. Deterministic, keyed off prompt markers,
    shaped exactly like real output so the whole pipeline downstream is exercised."""
    if "intent classifier" in prompt:
        # the inbound message sits inside triple quotes right after the marker;
        # don't scan past it or the prompt's own rules text pollutes the match
        tail = prompt.split("NEW INBOUND MESSAGE:")[-1]
        parts = tail.split('"""')
        inbound = (parts[1] if len(parts) > 1 else tail).lower()
        if any(w in inbound for w in ("price", "cost", "how much", "budget", "discount")):
            intent, hint = "PRICING", "Founder handles pricing; hold warmly and push the call."
        elif any(w in inbound for w in ("call", "yes", "interested", "sounds good", "tell me more")):
            intent, hint = "INTERESTED", "They're warm; propose the call and share the link."
        else:
            intent, hint = "QUESTION", "Answer plainly, then one clear next step."
        return json.dumps({"intent": intent, "confidence": 0.9,
                           "extracted": {"phone": None, "whatsapp_optin": False,
                                         "proposed_times": [], "new_facts": []},
                           "summary_update": f"[dry-run] classified as {intent}.",
                           "reply_hint": hint})
    if "QC editor" in prompt:
        return json.dumps({"ok": True, "violations": [], "fixed_body": None})
    if "Score this prospect" in prompt:
        return json.dumps({"score": 72, "fit": "[dry-run] plausible ICP from research text.", "flags": []})
    if "handoff brief" in prompt:
        return json.dumps({"brief": "WHO: dry-run lead. WHAT THEY WANT: pilot gifting run. "
                                    "AGREED NEXT STEP: intro call. WATCH OUT FOR: none."})
    if "Compress this" in prompt:
        return json.dumps({"summary": "[dry-run] compressed summary."})
    # default: a draft. Must satisfy the policy wall and the critic checklist.
    body = ("Hi — saw your recent season of Himalayan treks and thought a personalised "
            "route poster could make a memorable finisher gift for your clients. "
            f"Worth a 20-minute call with our founder SK? {config.CAL_LINK}\n\n"
            "Reply 'no thanks' and I won't write again.\n\n" + config.SIGNATURE)
    return json.dumps({"channel": "email", "subject": "A finisher gift your trekkers keep", "body": body})


def _ask(prompt: str, max_tokens: int = 900) -> str:
    if config.DRY_RUN:
        return _mock_answer(prompt)
    last_err = None
    for attempt in range(4):
        try:
            resp = requests.post(API, headers=HEADERS, timeout=60, json={
                "model": config.MODEL,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            })
            if resp.status_code in RETRYABLE:
                wait = float(resp.headers.get("retry-after") or 2 ** (attempt + 1))
                time.sleep(min(wait, 30))
                last_err = f"http {resp.status_code}"
                continue
            resp.raise_for_status()
            data = resp.json()
            return "\n".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        except requests.exceptions.ConnectionError as e:
            last_err = str(e)
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"anthropic API unavailable after retries: {last_err}")


def _extract_json(text: str) -> dict:
    cleaned = re.sub(r"```json|```", "", text).strip()
    start = cleaned.find("{")
    if start < 0:
        raise ValueError("no JSON in model output")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
            continue
        if ch == '"': in_str = True
        elif ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(cleaned[start:i + 1])
    raise ValueError("unbalanced JSON")


def call_json(prompt: str, max_tokens: int = 900) -> dict:
    try:
        return _extract_json(_ask(prompt, max_tokens))
    except Exception as e:
        retry = prompt + f"\n\nIMPORTANT: your previous output failed to parse ({str(e)[:80]}). " \
                         "Respond with ONLY one valid JSON object."
        return _extract_json(_ask(retry, max_tokens))


def _ctx(lead, messages) -> str:
    pb = config.PLAYBOOKS[lead["segment"]]
    thread = "\n".join(
        f"[{m['channel']}] {'THEM' if m['direction'] == 'in' else 'AGENT'}: {m['body'][:600]}"
        for m in messages
    )
    return (f"LEAD: {lead.get('name') or 'unknown'} | {lead.get('role') or ''} at {lead.get('company') or 'unknown'} "
            f"| segment {lead['segment']} | state {lead['state']}\n"
            f"RESEARCH/FACTS: {json.dumps(lead.get('facts') or {})[:900]}\n"
            f"ROLLING SUMMARY: {lead.get('summary') or '(none)'}\n"
            f"PLAYBOOK GOAL: {pb['goal']}\nVALUE PROP: {pb['value_prop']}\n"
            f"RECENT THREAD:\n{thread or '(no messages yet)'}")


# ---------------- 1. classify ----------------
INTENTS = ("INTERESTED QUESTION PRICING OBJECTION BOOKING_ACCEPT TIMES_PROPOSED NOT_NOW "
           "NOT_INTERESTED OPT_OUT WRONG_PERSON REFERRAL HUMAN_REQUEST ANGRY AUTOREPLY UNCLEAR")

def classify(lead, messages, inbound_text: str) -> dict:
    prompt = f"""You are the intent classifier for a B2B sales agent at Keepsake Press (personalised keepsake posters).
{_ctx(lead, messages)}

NEW INBOUND MESSAGE:
\"\"\"{inbound_text[:2000]}\"\"\"

Classify it. Respond with ONLY one JSON object:
{{
 "intent": one of [{INTENTS}],
 "confidence": 0.0-1.0,
 "extracted": {{
   "phone": "E.164 phone if they shared one, else null",
   "whatsapp_optin": true only if they clearly agreed to chat on WhatsApp, else false,
   "proposed_times": ["any specific call times they offered"],
   "new_facts": ["concrete business facts worth remembering, their words tightened"]
 }},
 "summary_update": "1-2 sentences to append to the rolling summary",
 "reply_hint": "one line on what the ideal next message should do"
}}

Rules:
- PRICING covers any ask about cost, rates, discounts or budgets.
- BOOKING_ACCEPT means a clear yes to a call (or they say they booked via the link).
- TIMES_PROPOSED means they offered their own slots instead of using the link.
- HUMAN_REQUEST means they asked for a person, founder, or 'someone real'.
- OPT_OUT for any request to stop being contacted.
- AUTOREPLY for out-of-office and automated responses.
- If genuinely mixed (e.g. interested AND asking price), PRICING wins; it must reach the founder.
- confidence below 0.5 means you should have picked UNCLEAR."""
    return call_json(prompt)


# ---------------- 2. draft ----------------
def draft(lead, messages, purpose: str, extra_instruction: str = "") -> dict:
    """purpose: opener | follow_up_N | reply | booking_push | revive"""
    pb = config.PLAYBOOKS[lead["segment"]]
    claims = "\n".join(f"- {c}" for c in config.CLAIMS)
    anchor = f'\n- If pricing must be acknowledged, you may use ONLY this exact sentence: "{config.PUBLIC_PRICE_ANCHOR}"' \
        if config.PUBLIC_PRICE_ANCHOR else ""
    prompt = f"""You are {config.AGENT_NAME}, the sales concierge at Keepsake Press. Write the next {purpose} message.
{_ctx(lead, messages)}

APPROVED CLAIMS (you may state ONLY these facts about us):
{claims}{anchor}

HARD RULES:
1. Never state, estimate or negotiate any price, number with a currency, or discount. If they asked about pricing, say the founder covers pricing on a short call and push the call.
2. Never invent facts about them or us. Personalisation must come from RESEARCH/FACTS or the thread.
3. Booking is the goal: a 20-minute call with SK (the founder). Calendar link: {config.CAL_LINK}
4. Voice: warm, direct, short sentences. No hype words, no "revolutionary", no exclamation spam. Under 110 words for email, under 60 for WhatsApp.
5. {pb['opener_angle'] if purpose == 'opener' else 'Answer what they actually said first. One clear next step.'}
6. Sign off exactly as: {config.SIGNATURE}
7. Emails must include a one-line opt-out ("Reply 'no thanks' and I won't write again."). WhatsApp replies don't need it.
{('8. ' + extra_instruction) if extra_instruction else ''}

Respond with ONLY one JSON object:
{{ "channel": "email" | "whatsapp", "subject": "email subject or null", "body": "the message" }}
Choose whatsapp only if wa_opt_in is true in the lead facts/state and the thread is already there; otherwise email."""
    return call_json(prompt)


# ---------------- 3. critic ----------------
def critic(lead, body: str, purpose: str) -> dict:
    claims = "\n".join(f"- {c}" for c in config.CLAIMS)
    prompt = f"""You are the QC editor for an outbound sales agent. A draft is about to be sent to a real prospect.
Approved claims about the company:
{claims}

Draft ({purpose}) to {lead.get('name')} at {lead.get('company')}:
\"\"\"{body}\"\"\"

Check ONLY for real violations:
- any price, currency amount, percentage discount, or negotiation of cost
- any factual claim about the company not in the approved list
- any invented fact about the prospect
- promises of outcomes ("will double your reviews") or delivery commitments not in the claims
- disrespect, pressure tactics, or fake urgency
- missing sign-off or (for email) missing opt-out line

Respond with ONLY one JSON object:
{{ "ok": true|false, "violations": ["short reasons"], "fixed_body": "corrected full message, or null if ok" }}
If violations exist, fixed_body MUST be the full corrected message with problems removed, same voice, same length class."""
    return call_json(prompt)


# ---------------- 5. lead scoring ----------------
def score_lead(segment: str, lead: dict) -> dict:
    pb = config.PLAYBOOKS[segment]
    prompt = f"""Score this prospect for Keepsake Press's {segment} gifting programme.
Value prop: {pb['value_prop']}
Prospect: {lead.get('name')} | {lead.get('role')} at {lead.get('company')}
Research: {json.dumps((lead.get('facts') or {}).get('research', ''))[:800]}

Judge fit ONLY from the given research; do not invent facts. Consider: does the business
have end-clients with emotional milestones to gift? Is this person likely a decision maker?
Any red flags (aggregator, defunct, irrelevant, too tiny)?

Respond with ONLY one JSON object:
{{ "score": 0-100, "fit": "one line on why this score", "flags": ["red flags, if any"] }}
Scoring: 80+ ideal ICP, 60-79 worth contacting, 40-59 marginal, <40 skip."""
    return call_json(prompt, 300)


# ---------------- 4. summaries / digests ----------------
def merge_summary(old: str, update: str) -> str:
    merged = (old + " " + (update or "")).strip()
    if len(merged) <= 900:
        return merged
    out = call_json(
        "Compress this sales-lead summary to under 120 words, keeping commitments, "
        "objections, and next steps. Respond ONLY as {\"summary\": \"...\"}\n\n" + merged, 400)
    return out.get("summary", merged[:900])


def handoff_brief(lead, messages) -> str:
    out = call_json(f"""Write a founder handoff brief for this closed lead. 120 words max, plain text,
sections: WHO, WHAT THEY WANT, AGREED NEXT STEP, WATCH OUT FOR. Only use facts from the context.
{_ctx(lead, messages)}
Respond ONLY as {{"brief": "..."}}""", 500)
    return out.get("brief", "Brief unavailable; see thread.")
