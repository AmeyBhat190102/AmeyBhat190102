"""Support-agent tools.

The interesting one is `issue_refund`: it calls `interrupt()` from *inside a
tool*, pausing the whole graph mid-run until a human approves or rejects the
refund. Because interrupts re-execute the interrupted node from its start on
resume, all side effects (actually recording the refund) happen strictly
*after* the interrupt call.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool
from langgraph.config import get_store, get_stream_writer
from langgraph.types import interrupt

from atlas import data


@tool
def lookup_order(order_id: str) -> str:
    """Look up a single order by its id (e.g. 'ord_1001')."""
    order = data.ORDERS.get(order_id)
    if not order:
        return f"No order found with id {order_id!r}."
    return json.dumps({"order_id": order_id, **order})


@tool
def list_orders(customer_id: str) -> str:
    """List all orders for a customer id (e.g. 'cus_001')."""
    orders = data.orders_for_customer(customer_id)
    if not orders:
        return f"No orders on file for customer {customer_id!r}."
    return json.dumps(orders)


@tool
def check_refund_eligibility(order_id: str) -> str:
    """Check whether an order is eligible for a refund under the return policy."""
    order = data.ORDERS.get(order_id)
    if not order:
        return f"No order found with id {order_id!r}."
    if order["status"] != "delivered":
        return json.dumps({"eligible": False, "reason": "Order not delivered yet."})
    age = data.days_since_delivery(order)
    window = data.REFUND_POLICY["window_days"]
    if age is not None and age > window:
        return json.dumps(
            {"eligible": False, "reason": f"Delivered {age} days ago; window is {window} days."}
        )
    return json.dumps(
        {
            "eligible": True,
            "amount": order["amount"],
            "requires_human_approval": order["amount"] >= data.REFUND_POLICY["auto_approve_below"],
            "policy": data.REFUND_POLICY["notes"],
        }
    )


@tool
def issue_refund(order_id: str, reason: str) -> str:
    """Issue a refund for an order. Large refunds pause for human approval."""
    order = data.ORDERS.get(order_id)
    if not order:
        return f"No order found with id {order_id!r}."

    amount = order["amount"]
    writer = get_stream_writer()

    if amount >= data.REFUND_POLICY["auto_approve_below"]:
        # ---- HUMAN-IN-THE-LOOP: pause the entire run right here. ------------
        decision = interrupt(
            {
                "kind": "refund_approval",
                "order_id": order_id,
                "item": order["item"],
                "amount": amount,
                "reason": reason,
                "question": f"Approve refund of ${amount:.2f} for {order['item']}?",
            }
        )
        # Everything below runs only after Command(resume=...) arrives.
        if not (isinstance(decision, dict) and decision.get("approved")):
            note = (decision or {}).get("note", "") if isinstance(decision, dict) else ""
            return f"Refund REJECTED by a human reviewer. Note: {note or 'no note provided'}."

    # Side effect after the interrupt → runs exactly once.
    data.ORDERS[order_id]["status"] = "refunded"
    writer({"event": "refund_issued", "order_id": order_id, "amount": amount})
    return f"Refund of ${amount:.2f} issued for order {order_id} ({order['item']})."


@tool
def remember_preference(customer_id: str, preference: str) -> str:
    """Save a lasting customer preference (e.g. 'prefers email follow-ups') to long-term memory."""
    store = get_store()
    existing = store.get(("preferences", customer_id), "profile")
    prefs: list[str] = list(existing.value["items"]) if existing else []
    if preference not in prefs:
        prefs.append(preference)
    store.put(("preferences", customer_id), "profile", {"items": prefs})
    return f"Saved. Known preferences for {customer_id}: {prefs}"


SUPPORT_TOOLS = [lookup_order, list_orders, check_refund_eligibility, issue_refund, remember_preference]
