"""Lead generation. One entry point, run(), triggered from the dashboard button,
POST /leadgen/run, or the CLI. Sources from Apollo, dedupes against the DB,
scores each lead with the LLM against the segment playbook, and stores them as
SOURCED so SK can review before anything is contacted. Sourcing never sends."""
import os
import requests
from . import config, db, brain
from .models import State

APOLLO_URL = "https://api.apollo.io/api/v1/mixed_people/search"


def run(segment: str, n: int = 25, keywords: str | None = None, country: str = "IN") -> dict:
    pb = config.PLAYBOOKS.get(segment)
    if not pb:
        return {"error": f"unknown segment '{segment}'"}
    if not pb.get("outbound"):
        return {"error": "d2c_inbound is inbound-only; leads arrive via the website form or CTWA ads"}
    key = os.environ.get("APOLLO_API_KEY", "")
    if not key:
        return {"error": "APOLLO_API_KEY not set. Either set it, or import a CSV: "
                         "python -m scripts.leads import leads.csv " + segment}

    kw = (keywords or pb.get("apollo_keywords") or segment.replace("_", " ")).strip()
    try:
        r = requests.post(APOLLO_URL, headers={"X-Api-Key": key}, timeout=40, json={
            "q_keywords": kw, "person_locations": [country],
            "page": 1, "per_page": max(1, min(n, 100)),
        })
        r.raise_for_status()
        people = r.json().get("people", [])
    except Exception as e:
        return {"error": f"apollo: {str(e)[:200]}"}

    fetched, added, dupes, scored = len(people), 0, 0, 0
    for p in people:
        email = p.get("email")
        if not email or "email_not_unlocked" in email:
            continue
        if db.is_suppressed(email=email):
            continue
        org = p.get("organization") or {}
        research = " · ".join(x for x in [
            org.get("short_description"), org.get("website_url"),
            f"employees ~{org.get('estimated_num_employees')}" if org.get("estimated_num_employees") else None,
        ] if x)[:700]
        lead = db.insert_lead(segment=segment, name=p.get("name"), company=org.get("name"),
                              role=p.get("title"), email=email, phone=None, source="apollo",
                              score=50, facts={"research": research, "keywords": kw},
                              state=State.SOURCED)
        if not lead:
            dupes += 1
            continue
        added += 1
        try:
            s = brain.score_lead(segment, lead)
            facts = dict(lead["facts"])
            facts["fit"] = s.get("fit", "")
            facts["flags"] = s.get("flags", [])
            db.update_lead(lead["id"], score=int(s.get("score", 50)), facts=facts)
            scored += 1
        except Exception:
            pass  # unscored leads keep the default 50; still reviewable
    return {"segment": segment, "keywords": kw, "fetched": fetched,
            "added": added, "duplicates": dupes, "scored": scored}
