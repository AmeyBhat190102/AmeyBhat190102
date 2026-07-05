"""Analyst-agent tools: lightweight analytics over the order data."""

from __future__ import annotations

import json
from collections import Counter

from langchain_core.tools import tool

from atlas import data


@tool
def customer_spend_summary(customer_id: str) -> str:
    """Summarize a customer's total spend, order count, and status breakdown."""
    orders = data.orders_for_customer(customer_id)
    if not orders:
        return f"No orders on file for customer {customer_id!r}."
    total = sum(o["amount"] for o in orders)
    statuses = Counter(o["status"] for o in orders)
    return json.dumps(
        {
            "customer_id": customer_id,
            "order_count": len(orders),
            "total_spend": round(total, 2),
            "average_order_value": round(total / len(orders), 2),
            "status_breakdown": dict(statuses),
        }
    )


@tool
def top_products() -> str:
    """Rank products by revenue across all customers."""
    revenue: Counter = Counter()
    for order in data.ORDERS.values():
        revenue[order["item"]] += order["amount"]
    ranked = [{"item": item, "revenue": round(amt, 2)} for item, amt in revenue.most_common()]
    return json.dumps(ranked)


ANALYST_TOOLS = [customer_spend_summary, top_products]
