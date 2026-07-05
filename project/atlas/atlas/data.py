"""Mock data layer: orders, customers, and a small product knowledge base.

In a real deployment these would be database / search-index calls. Keeping them
in-process makes the project runnable anywhere while preserving realistic shapes.
"""

from __future__ import annotations

from datetime import date

CUSTOMERS: dict[str, dict] = {
    "cus_001": {"name": "Priya Sharma", "tier": "gold", "email": "priya@example.com"},
    "cus_002": {"name": "Marco Ruiz", "tier": "standard", "email": "marco@example.com"},
    "guest": {"name": "Guest", "tier": "standard", "email": None},
}

ORDERS: dict[str, dict] = {
    "ord_1001": {
        "customer_id": "cus_001",
        "item": "Nimbus X1 Wireless Headphones",
        "amount": 249.00,
        "status": "delivered",
        "ordered_on": "2026-06-02",
        "delivered_on": "2026-06-06",
    },
    "ord_1002": {
        "customer_id": "cus_001",
        "item": "Nimbus Charging Dock",
        "amount": 59.00,
        "status": "in_transit",
        "ordered_on": "2026-06-28",
        "delivered_on": None,
    },
    "ord_2001": {
        "customer_id": "cus_002",
        "item": "Aero Mechanical Keyboard",
        "amount": 129.00,
        "status": "delivered",
        "ordered_on": "2026-05-15",
        "delivered_on": "2026-05-19",
    },
}

REFUND_POLICY = {
    "window_days": 30,
    "auto_approve_below": 50.00,
    "notes": "Refunds within 30 days of delivery. Amounts >= $50 require human approval.",
}

# A tiny knowledge base the researcher agent searches over.
KNOWLEDGE_BASE: list[dict] = [
    {
        "id": "kb_01",
        "title": "Nimbus X1 battery troubleshooting",
        "body": (
            "The Nimbus X1 provides 40h playback. Rapid battery drain is usually caused by "
            "firmware < 2.3 keeping the ANC processor awake. Update via the Nimbus app; a "
            "full charge cycle after updating recalibrates the battery gauge."
        ),
        "tags": ["nimbus", "battery", "firmware", "troubleshooting"],
    },
    {
        "id": "kb_02",
        "title": "Nimbus X1 pairing and multipoint",
        "body": (
            "The X1 supports multipoint with two devices. Pairing failures after firmware "
            "updates are fixed by clearing the pairing list (hold both volume keys 5s)."
        ),
        "tags": ["nimbus", "bluetooth", "pairing"],
    },
    {
        "id": "kb_03",
        "title": "Return & refund process",
        "body": (
            "Refunds are issued to the original payment method within 5-7 business days "
            "after approval. Items must be within the 30-day window from delivery."
        ),
        "tags": ["refund", "policy", "returns"],
    },
    {
        "id": "kb_04",
        "title": "Aero keyboard firmware & key chatter",
        "body": (
            "Key chatter on the Aero keyboard is resolved by firmware 1.8 which adds "
            "configurable debounce (default 5ms). Use the Aero configurator to update."
        ),
        "tags": ["aero", "keyboard", "firmware"],
    },
    {
        "id": "kb_05",
        "title": "Warranty coverage",
        "body": (
            "All devices carry a 24-month limited warranty covering manufacturing defects. "
            "Water damage and drops are excluded. Gold-tier customers get advance replacement."
        ),
        "tags": ["warranty", "policy"],
    },
]


def search_kb(query: str, limit: int = 3) -> list[dict]:
    """Naive keyword scoring over the knowledge base."""
    terms = [t for t in query.lower().split() if len(t) > 2]
    scored = []
    for doc in KNOWLEDGE_BASE:
        haystack = (doc["title"] + " " + doc["body"] + " " + " ".join(doc["tags"])).lower()
        score = sum(haystack.count(t) for t in terms)
        if score:
            scored.append((score, doc))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [doc for _, doc in scored[:limit]]


def orders_for_customer(customer_id: str) -> list[dict]:
    return [
        {"order_id": oid, **o} for oid, o in ORDERS.items() if o["customer_id"] == customer_id
    ]


def days_since_delivery(order: dict) -> int | None:
    if not order.get("delivered_on"):
        return None
    delivered = date.fromisoformat(order["delivered_on"])
    return (date.today() - delivered).days
