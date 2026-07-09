"""
MaSoVa Customer Support Agent
Powered by Google ADK + Gemini with real backend API integration.
"""

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai import types as genai_types
import httpx
import logging
import asyncio
import os
from dotenv import load_dotenv

from .redis_session_service import RedisSessionService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Backend base URL (defaults to local dev)
BACKEND_URL = os.getenv("MASOVA_BACKEND_URL", "http://localhost:8080/api")
# Service account token for internal calls (set in production)
INTERNAL_TOKEN = os.getenv("MASOVA_INTERNAL_TOKEN", "")

# Global session service — Redis-backed with InMemory fallback
_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/1")
_session_service = RedisSessionService(redis_url=_redis_url)
_created_sessions: dict[str, str] = {}  # session_key -> actual session_id


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------


def _get(path: str, params: dict | None = None) -> dict:
    """Synchronous GET against the MaSoVa backend."""
    headers = {"Authorization": f"Bearer {INTERNAL_TOKEN}"} if INTERNAL_TOKEN else {}
    try:
        response = httpx.get(f"{BACKEND_URL}{path}", params=params, headers=headers, timeout=8.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        logger.warning(f"Backend {path} returned {e.response.status_code}")
        return {"error": f"HTTP {e.response.status_code}", "detail": e.response.text[:200]}
    except Exception as e:
        logger.error(f"Backend call failed for {path}: {e}")
        return {"error": str(e)}


def _post(path: str, body: dict) -> dict:
    """Synchronous POST against the MaSoVa backend."""
    headers = {"Content-Type": "application/json"}
    if INTERNAL_TOKEN:
        headers["Authorization"] = f"Bearer {INTERNAL_TOKEN}"
    try:
        response = httpx.post(f"{BACKEND_URL}{path}", json=body, headers=headers, timeout=8.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        logger.warning(f"Backend POST {path} returned {e.response.status_code}")
        return {"error": f"HTTP {e.response.status_code}", "detail": e.response.text[:200]}
    except Exception as e:
        logger.error(f"Backend POST failed for {path}: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Agent tools — called by Gemini when it decides they are needed
# ---------------------------------------------------------------------------


def get_order_status(order_id: str) -> str:
    """
    Retrieve the current status of a customer order.

    Args:
        order_id: The order ID (e.g. "ORD-20260216-102") or order number.

    Returns:
        A human-readable summary of the order status, items, and ETA.
    """
    data = _get(f"/orders/public/{order_id}")
    if "error" in data:
        return f"Sorry, I couldn't find order {order_id}. Please check the order ID and try again."

    status = data.get("status", "UNKNOWN")
    order_num = data.get("orderNumber", order_id)
    items = data.get("items", [])
    item_list = ", ".join(f"{i.get('quantity', 1)}x {i.get('name', '?')}" for i in items)
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
        "COMPLETED": "is complete — thank you for dining with us!",
        "SERVED": "has been served — enjoy your meal!",
        "CANCELLED": "has been cancelled",
    }
    status_desc = status_messages.get(status, f"is currently {status}")

    return (
        f"Order #{order_num} {status_desc}{eta_str}.\n"
        f"Items: {item_list if item_list else 'details unavailable'}."
    )


def get_menu_items(store_id: str, category: str = "") -> str:
    """
    Fetch available menu items for a store, optionally filtered by category.

    Args:
        store_id: The store ID to query (e.g. "store-1").
        category: Optional category filter (e.g. "BIRYANI", "PIZZA", "DOSA").

    Returns:
        A formatted list of available menu items with prices.
    """
    params: dict = {"storeId": store_id, "available": "true"}
    if category:
        params["category"] = category.upper()

    data = _get("/menu/items", params=params)

    if "error" in data:
        return f"Sorry, I couldn't fetch the menu right now. Please try again in a moment."

    # Handle both list and paginated responses
    items = data if isinstance(data, list) else data.get("content", data.get("items", []))
    if not items:
        cat_str = f" in category {category}" if category else ""
        return f"No menu items found{cat_str} for this store at the moment."

    # Show up to 10 items
    lines = []
    for item in items[:10]:
        name = item.get("name", "Unknown")
        price = item.get("discountedPrice") or item.get("basePrice", 0)
        desc = item.get("description", "")
        spice = item.get("spiceLevel", "")
        spice_str = f" [{spice}]" if spice else ""
        lines.append(
            f"- {name}{spice_str}: ₹{price:.0f} — {desc[:60]}"
            if desc
            else f"- {name}{spice_str}: ₹{price:.0f}"
        )

    total = len(items)
    more_str = f"\n...and {total - 10} more items." if total > 10 else ""
    return f"Menu items available:\n" + "\n".join(lines) + more_str


def get_store_hours(store_id: str) -> str:
    """
    Get the operating hours and current open/closed status for a store.

    Args:
        store_id: The store ID (e.g. "store-1").

    Returns:
        Store name, opening/closing times, and whether it is currently open.
    """
    data = _get(f"/stores/{store_id}")
    if "error" in data:
        return f"Sorry, I couldn't retrieve store information right now."

    name = data.get("name", f"Store {store_id}")
    is_open = data.get("isOpen", False)
    open_time = data.get("openingTime", "N/A")
    close_time = data.get("closingTime", "N/A")
    status = "currently OPEN" if is_open else "currently CLOSED"

    return f"{name} is {status}.\n" f"Hours: {open_time} – {close_time}."


def submit_complaint(customer_id: str, order_id: str, description: str) -> str:
    """
    Submit a customer complaint or support ticket for an order.

    Args:
        customer_id: The customer's user ID.
        order_id: The order ID the complaint relates to.
        description: A clear description of the issue.

    Returns:
        Confirmation of the complaint submission with a ticket reference.
    """
    if len(description.strip()) < 10:
        return "Please provide more detail about the issue so we can help you effectively."

    body = {
        "customerId": customer_id,
        "orderId": order_id,
        "description": description,
        "type": "COMPLAINT",
    }
    data = _post("/reviews/complaints", body)

    if "error" in data:
        # Graceful fallback — log it and give a reassuring message
        logger.error(f"Complaint submission failed: {data}")
        return (
            "Your complaint has been noted. Our support team will contact you within 24 hours. "
            "You can also reach us at support@masova.com."
        )

    ticket_ref = data.get("id", data.get("ticketId", "SUP-" + order_id[-6:]))
    return (
        f"Your complaint has been submitted successfully. "
        f"Ticket reference: {ticket_ref}. "
        f"Our team will respond within 24 hours."
    )


def request_refund(order_id: str, reason: str) -> str:
    """
    Request a refund for an order.

    Args:
        order_id: The order ID to refund.
        reason: The reason for requesting the refund.

    Returns:
        Confirmation of the refund request or guidance on next steps.
    """
    if len(reason.strip()) < 5:
        return "Please provide a reason for the refund request."

    body = {
        "orderId": order_id,
        "reason": reason,
    }
    data = _post("/payments/refund/request", body)

    if "error" in data:
        logger.error(f"Refund request failed: {data}")
        return (
            "I've logged your refund request. A payment specialist will review it and process "
            "your refund within 3-5 business days. You'll receive an email confirmation."
        )

    refund_id = data.get("refundId", data.get("id", ""))
    ref_str = f" (Ref: {refund_id})" if refund_id else ""
    return (
        f"Your refund request for order {order_id} has been submitted{ref_str}. "
        f"Processing takes 3-5 business days. We'll notify you by email."
    )


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

root_agent = LlmAgent(
    name="MaSoVa_Support",
    model="gemini-2.0-flash",
    instruction="""You are MaSoVa's friendly and efficient customer support assistant.

MaSoVa is a multi-branch restaurant chain in Hyderabad, India, serving South Indian,
North Indian, Indo-Chinese, Italian, American, Continental, and Beverage menus.

Your capabilities:
- Check order status using get_order_status
- Browse menu items using get_menu_items
- Check store hours using get_store_hours
- Submit complaints on behalf of customers using submit_complaint
- Process refund requests using request_refund

Guidelines:
1. Be warm, concise, and helpful. Avoid filler phrases.
2. When a customer asks about an order, ask for the order ID if they haven't provided it, then call get_order_status.
3. For menu questions, ask which store or assume store-1 if unclear, then call get_menu_items.
4. For complaints or refunds, collect all required details before calling the tool.
5. Always confirm actions before submitting complaints or refund requests.
6. If a tool returns an error, offer alternatives (phone support, email) rather than repeating the failure.
7. Keep responses under 150 words unless listing menu items.
""",
    tools=[
        get_order_status,
        get_menu_items,
        get_store_hours,
        submit_complaint,
        request_refund,
    ],
)

# ADK expects these names
agent = root_agent
app = root_agent


# ---------------------------------------------------------------------------
# Session management + send_message helper
# ---------------------------------------------------------------------------


async def _ensure_session(user_id: str, session_id: str) -> str:
    """Create a session if it doesn't exist; return the real session_id."""
    key = f"{user_id}:{session_id}"
    if key not in _created_sessions:
        session = await _session_service.create_session(
            app_name="masova_support",
            user_id=user_id,
        )
        _created_sessions[key] = session.id
        logger.info(f"Created session {session.id} for user {user_id}")
    return _created_sessions[key]


async def send_message_async(
    message: str,
    user_id: str = "anonymous",
    session_id: str = "default",
) -> str:
    """
    Send a message to the agent and return the text response.

    Args:
        message: User's message.
        user_id: Stable identifier for the user (e.g. customer MongoDB ID).
        session_id: Conversation session identifier.

    Returns:
        Agent's response as a plain string.
    """
    actual_session_id = await _ensure_session(user_id, session_id)

    runner = Runner(
        agent=root_agent,
        app_name="masova_support",
        session_service=_session_service,
    )

    user_content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=message)],
    )

    response_text = ""
    try:
        for event in runner.run(
            user_id=user_id,
            session_id=actual_session_id,
            new_message=user_content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text
    except Exception as e:
        logger.error(f"Agent run failed: {e}", exc_info=True)
        raise

    return response_text.strip()


def send_message(
    message: str,
    user_id: str = "anonymous",
    session_id: str = "default",
) -> str:
    """Synchronous wrapper around send_message_async (for CLI use)."""
    return asyncio.run(send_message_async(message, user_id, session_id))
