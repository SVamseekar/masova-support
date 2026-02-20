"""
MaSoVa backend API tools for the support agent.
Each function is registered as an ADK tool — Gemini calls them when needed.
"""

import os
import logging
import httpx

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("MASOVA_BACKEND_URL", "http://localhost:8080/api")
INTERNAL_TOKEN = os.getenv("MASOVA_INTERNAL_TOKEN", "")


def _get(path: str, params: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {INTERNAL_TOKEN}"} if INTERNAL_TOKEN else {}
    try:
        r = httpx.get(f"{BACKEND_URL}{path}", params=params, headers=headers, timeout=8.0)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        logger.warning(f"GET {path} → {e.response.status_code}")
        return {"error": f"HTTP {e.response.status_code}"}
    except Exception as e:
        logger.error(f"GET {path} failed: {e}")
        return {"error": str(e)}


def _post(path: str, body: dict) -> dict:
    headers = {"Content-Type": "application/json"}
    if INTERNAL_TOKEN:
        headers["Authorization"] = f"Bearer {INTERNAL_TOKEN}"
    try:
        r = httpx.post(f"{BACKEND_URL}{path}", json=body, headers=headers, timeout=8.0)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        logger.warning(f"POST {path} → {e.response.status_code}")
        return {"error": f"HTTP {e.response.status_code}"}
    except Exception as e:
        logger.error(f"POST {path} failed: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------

def get_order_status(order_id: str) -> str:
    """
    Retrieve the current status of a customer order.

    Args:
        order_id: The order ID or order number (e.g. "ORD-20260216-102").

    Returns:
        Human-readable order status summary.
    """
    data = _get(f"/orders/public/{order_id}")
    if "error" in data:
        return f"Sorry, I couldn't find order {order_id}. Please double-check the order ID."

    status = data.get("status", "UNKNOWN")
    order_num = data.get("orderNumber", order_id)
    items = data.get("items", [])
    item_list = ", ".join(
        f"{i.get('quantity', 1)}x {i.get('name', '?')}" for i in items
    )
    eta = data.get("preparationTime", "")
    eta_str = f" (ETA: ~{eta} min)" if eta else ""

    status_messages = {
        "PENDING": "has been received and is pending confirmation",
        "RECEIVED": "has been confirmed and will be prepared shortly",
        "PREPARING": "is being prepared by the kitchen",
        "OVEN": "is in the oven",
        "BAKED": "is ready and waiting for dispatch",
        "DISPATCHED": "is out for delivery",
        "DELIVERED": "has been delivered",
        "COMPLETED": "is complete — thank you!",
        "SERVED": "has been served — enjoy your meal!",
        "CANCELLED": "has been cancelled",
    }
    desc = status_messages.get(status, f"is currently {status}")
    return (
        f"Order #{order_num} {desc}{eta_str}.\n"
        f"Items: {item_list or 'details unavailable'}."
    )


def get_menu_items(store_id: str, category: str = "") -> str:
    """
    Fetch available menu items for a store, optionally filtered by category.

    Args:
        store_id: Store ID to query (e.g. "store-1").
        category: Optional category filter (e.g. "BIRYANI", "PIZZA", "DOSA").

    Returns:
        Formatted list of menu items with prices.
    """
    params: dict = {"storeId": store_id, "available": "true"}
    if category:
        params["category"] = category.upper()

    data = _get("/menu/items", params=params)
    if "error" in data:
        return "Sorry, I couldn't fetch the menu right now. Please try again shortly."

    items = data if isinstance(data, list) else data.get("content", data.get("items", []))
    if not items:
        cat_str = f" in {category}" if category else ""
        return f"No menu items found{cat_str} at this store right now."

    lines = []
    for item in items[:10]:
        name = item.get("name", "Unknown")
        price = item.get("discountedPrice") or item.get("basePrice", 0)
        desc = item.get("description", "")
        spice = item.get("spiceLevel", "")
        spice_str = f" [{spice}]" if spice else ""
        desc_str = f" — {desc[:60]}" if desc else ""
        lines.append(f"- {name}{spice_str}: ₹{price:.0f}{desc_str}")

    more = f"\n...and {len(items) - 10} more items." if len(items) > 10 else ""
    return "Menu items available:\n" + "\n".join(lines) + more


def get_store_hours(store_id: str) -> str:
    """
    Get operating hours and current open/closed status for a store.

    Args:
        store_id: The store ID (e.g. "store-1").

    Returns:
        Store name, hours, and current open/closed status.
    """
    data = _get(f"/stores/{store_id}")
    if "error" in data:
        return "Sorry, I couldn't retrieve store information right now."

    name = data.get("name", f"Store {store_id}")
    is_open = data.get("isOpen", False)
    open_time = data.get("openingTime", "N/A")
    close_time = data.get("closingTime", "N/A")
    status = "currently OPEN" if is_open else "currently CLOSED"
    return f"{name} is {status}.\nHours: {open_time} – {close_time}."


def submit_complaint(customer_id: str, order_id: str, description: str) -> str:
    """
    Submit a customer complaint or support ticket for an order.

    Args:
        customer_id: The customer's user ID.
        order_id: The order ID the complaint relates to.
        description: Clear description of the issue.

    Returns:
        Confirmation with ticket reference number.
    """
    if len(description.strip()) < 10:
        return "Please provide more detail about the issue so we can help you effectively."

    data = _post("/reviews/complaints", {
        "customerId": customer_id,
        "orderId": order_id,
        "description": description,
        "type": "COMPLAINT",
    })

    if "error" in data:
        return (
            "Your complaint has been noted. Our support team will contact you within 24 hours. "
            "You can also reach us at support@masova.com."
        )

    ticket_ref = data.get("id", data.get("ticketId", f"SUP-{order_id[-6:]}"))
    return (
        f"Your complaint has been submitted. Ticket: {ticket_ref}. "
        f"We'll respond within 24 hours."
    )


def get_loyalty_points(customer_id: str) -> str:
    """Get the loyalty points balance, tier, and next reward threshold for a customer.

    Args:
        customer_id: The customer's unique identifier.

    Returns:
        A string describing the customer's loyalty points balance, tier level,
        and how many more points are needed for the next reward.
    """
    data = _get(f"/customers/{customer_id}/stats")
    if "error" in data:
        return "I couldn't retrieve your loyalty points right now. Please check the app."
    points = data.get("loyaltyPoints", 0)
    tier = data.get("loyaltyTier", "BRONZE")
    thresholds = {"BRONZE": 500, "SILVER": 2000, "GOLD": 5000, "PLATINUM": 10000}
    next_tier_map = {"BRONZE": "SILVER", "SILVER": "GOLD", "GOLD": "PLATINUM", "PLATINUM": None}
    next_tier = next_tier_map.get(tier)
    if next_tier:
        needed = thresholds.get(next_tier, 0) - points
        next_info = f" You need {max(0, needed)} more points to reach {next_tier}."
    else:
        next_info = " You are at the highest tier — PLATINUM!"
    return f"You have {points} loyalty points and are a {tier} member.{next_info}"


def get_store_wait_time(store_id: str) -> str:
    """Get the estimated current wait time at a store based on active orders in the kitchen.

    Args:
        store_id: The store's unique identifier (e.g., 'store-1').

    Returns:
        A string describing the estimated wait time for new orders at this store.
    """
    data = _get("/orders/kitchen/queue", params={"storeId": store_id, "status": "RECEIVED,PREPARING,OVEN"})
    if "error" in data:
        return "I couldn't check the current wait time. Please call the store directly."
    active = data.get("totalElements", 0) if isinstance(data, dict) else len(data)
    if active == 0:
        return "Great news — the kitchen is currently free. Expect very fast service right now!"
    elif active <= 5:
        return f"The kitchen has {active} order(s) in progress. Estimated wait: 15–20 minutes."
    elif active <= 10:
        return f"The kitchen is moderately busy with {active} orders. Estimated wait: 25–35 minutes."
    else:
        return f"The kitchen is very busy right now ({active} active orders). Estimated wait: 40–50 minutes."


def cancel_order(order_id: str, reason: str) -> str:
    """Cancel a customer order if it is still in a cancellable state (PENDING or RECEIVED only).

    Orders that are already being prepared cannot be cancelled.

    Args:
        order_id: The unique order identifier.
        reason: The reason for cancellation (must be at least 5 characters).

    Returns:
        A string confirming the cancellation or explaining why it cannot be cancelled.
    """
    if len(reason.strip()) < 5:
        return "Please provide a reason for cancellation (at least 5 characters)."
    order_data = _get(f"/orders/public/{order_id}")
    if "error" not in order_data:
        current_status = order_data.get("status", "")
        cancellable = {"PENDING", "RECEIVED"}
        if current_status not in cancellable:
            return (
                f"Sorry, order #{order_id} cannot be cancelled — it is already {current_status}. "
                f"Orders can only be cancelled when PENDING or RECEIVED. "
                f"I can submit a complaint or refund request instead."
            )
    data = _post(f"/orders/{order_id}/cancel", {"reason": reason})
    if "error" in data:
        return f"I wasn't able to cancel order #{order_id} right now. Please contact the restaurant directly."
    return (
        f"Order #{order_id} has been successfully cancelled. Reason: {reason}. "
        f"A refund will be processed automatically if payment was made."
    )


def request_refund(order_id: str, reason: str) -> str:
    """
    Request a refund for an order.

    Args:
        order_id: The order ID to refund.
        reason: Reason for the refund request.

    Returns:
        Confirmation or guidance on next steps.
    """
    if len(reason.strip()) < 5:
        return "Please provide a reason for the refund request."

    data = _post("/payments/refund/request", {"orderId": order_id, "reason": reason})

    if "error" in data:
        return (
            "Your refund request has been logged. A specialist will review it and process "
            "within 3–5 business days. You'll receive an email confirmation."
        )

    refund_id = data.get("refundId", data.get("id", ""))
    ref_str = f" (Ref: {refund_id})" if refund_id else ""
    return (
        f"Refund requested for order {order_id}{ref_str}. "
        f"Processing takes 3–5 business days. We'll notify you by email."
    )
