"""
MaSoVa Customer Support Agent
"""

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
import asyncio
import json
import logging
import os
import redis as redis_lib
from dotenv import load_dotenv

from .tools.backend_tools import (
    get_order_status,
    get_menu_items,
    get_store_hours,
    submit_complaint,
    request_refund,
    get_loyalty_points,
    get_store_wait_time,
    cancel_order,
)

load_dotenv()
logger = logging.getLogger(__name__)

_session_service = InMemorySessionService()
_created_sessions: dict[str, str] = {}  # session_key -> actual session_id


# ---------------------------------------------------------------------------
# Redis session persistence helpers
# ---------------------------------------------------------------------------

_redis_client = None


def _get_redis() -> redis_lib.Redis | None:
    """Return Redis client, or None if Redis is unavailable (graceful degradation)."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    url = os.getenv("REDIS_URL", "redis://localhost:6379/1")
    try:
        client = redis_lib.from_url(url, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        _redis_client = client
        return client
    except Exception:
        return None


CHAT_SESSION_TTL = 3600  # 1 hour


def save_session_to_redis(session_key: str, messages: list[dict]) -> None:
    r = _get_redis()
    if r:
        try:
            r.setex(f"chat:{session_key}", CHAT_SESSION_TTL, json.dumps(messages))
        except Exception:
            pass  # graceful degradation


def load_session_from_redis(session_key: str) -> list[dict]:
    r = _get_redis()
    if r:
        try:
            data = r.get(f"chat:{session_key}")
            return json.loads(data) if data else []
        except Exception:
            pass
    return []

root_agent = LlmAgent(
    name="MaSoVa_Support",
    model="gemini-2.0-flash",
    instruction="""You are MaSoVa's friendly and efficient customer support assistant.

MaSoVa is a multi-branch restaurant chain in Hyderabad, India, serving South Indian,
North Indian, Indo-Chinese, Italian, American, Continental, and Beverage menus.

Your capabilities:
- Check order status: get_order_status
- Browse menu items: get_menu_items
- Check store hours: get_store_hours
- Submit complaints: submit_complaint
- Process refund requests: request_refund
- Check loyalty points and tier: get_loyalty_points
- Check kitchen wait time at a store: get_store_wait_time
- Cancel an order (PENDING/RECEIVED only): cancel_order

Guidelines:
1. Be warm, concise, and helpful.
2. For order inquiries, ask for the order ID if not provided, then call get_order_status.
3. For menu questions, ask which store or assume store-1 if unclear.
4. Confirm details before submitting complaints or refund requests.
5. For cancellations, always check the order status first using cancel_order — it validates cancellability.
6. If a tool fails, offer alternatives (phone: 1800-MASOVA, email: support@masova.com).
7. Keep responses under 150 words unless listing menu items.
""",
    tools=[
        get_order_status,
        get_menu_items,
        get_store_hours,
        submit_complaint,
        request_refund,
        get_loyalty_points,
        get_store_wait_time,
        cancel_order,
    ],
)

# ADK expects these names
agent = root_agent
app = root_agent


async def _ensure_session(user_id: str, session_id: str) -> str:
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
    for event in runner.run(
        user_id=user_id,
        session_id=actual_session_id,
        new_message=user_content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_text += part.text
    return response_text.strip()


def send_message(
    message: str,
    user_id: str = "anonymous",
    session_id: str = "default",
) -> str:
    """Synchronous wrapper for CLI use."""
    return asyncio.run(send_message_async(message, user_id, session_id))
