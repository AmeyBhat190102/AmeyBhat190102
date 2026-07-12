"""Lead sourcing utilities.
CSV import:   python -m scripts.leads import path/to/leads.csv trek_operator
Apollo fetch: python -m scripts.leads apollo "adventure travel" IN 25 trek_operator

CSV columns (header row required): name,company,role,email,phone,research
`research` is free text (their treks, IG bio, review counts); the drafter uses
it for grounded personalisation. Verify emails (bounce risk < 2%) BEFORE import."""
import csv
import os
import sys
import requests
from app import db
from app.models import State


def import_csv(path: str, segment: str):
    added = 0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            email, phone = (row.get("email") or "").strip() or None, (row.get("phone") or "").strip() or None
            if not email and not phone:
                continue
            if db.is_suppressed(email=email, phone=phone):
                continue
            lead = db.insert_lead(
                segment=segment, name=(row.get("name") or "").strip() or None,
                company=(row.get("company") or "").strip() or None,
                role=(row.get("role") or "").strip() or None,
                email=email, phone=phone, source="csv", score=55,
                facts={"research": (row.get("research") or "").strip()},
                state=State.SOURCED)
            if lead:
                added += 1
    print(f"imported {added} leads as {segment} (state=SOURCED). "
          f"Queue them via POST /leads/{{id}}/queue or `queue_all` below.")


def queue_all(segment: str, limit: int = 50):
    rows = db.qall("UPDATE leads SET state='QUEUED' WHERE state='SOURCED' AND segment=%s "
                   "AND id IN (SELECT id FROM leads WHERE state='SOURCED' AND segment=%s "
                   "ORDER BY score DESC LIMIT %s) RETURNING id", (segment, segment, limit))
    print(f"queued {len(rows)} {segment} leads")


def apollo(keywords: str, country: str = "IN", n: int = 25, segment: str = "trek_operator"):
    """Pull people from Apollo.io's search API into SOURCED leads."""
    key = os.environ.get("APOLLO_API_KEY")
    if not key:
        sys.exit("set APOLLO_API_KEY")
    r = requests.post("https://api.apollo.io/api/v1/mixed_people/search",
                      headers={"X-Api-Key": key},
                      json={"q_keywords": keywords, "person_locations": [country],
                            "page": 1, "per_page": min(n, 100)}, timeout=30)
    r.raise_for_status()
    added = 0
    for p in r.json().get("people", []):
        email = p.get("email")
        if not email or "email_not_unlocked" in email:
            continue
        org = p.get("organization") or {}
        lead = db.insert_lead(segment=segment, name=p.get("name"), company=org.get("name"),
                              role=p.get("title"), email=email, phone=None, source="apollo",
                              score=60, facts={"research": (org.get("short_description") or "")[:600]},
                              state=State.SOURCED)
        if lead:
            added += 1
    print(f"apollo: imported {added} leads")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "import":
        import_csv(sys.argv[2], sys.argv[3])
    elif cmd == "queue_all":
        queue_all(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 50)
    elif cmd == "apollo":
        apollo(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "IN",
               int(sys.argv[4]) if len(sys.argv) > 4 else 25,
               sys.argv[5] if len(sys.argv) > 5 else "trek_operator")
    else:
        print(__doc__)
