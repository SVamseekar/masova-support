"""
MaSoVa Customer Support Agent
"""

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai import types as genai_types
import asyncio
import logging
import os
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
from .core.redis_session_service import RedisSessionService

load_dotenv()
logger = logging.getLogger(__name__)

# Redis-backed session service with InMemory fallback
_redis_url = os.getenv("REDIS_URL", "redis://192.168.50.88:6379/1")
_session_service = RedisSessionService(redis_url=_redis_url)
_created_sessions: dict[str, str] = {}  # session_key -> actual session_id

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
) -> tuple[str, str]:
    """Returns (reply_text, actual_session_id) so callers can persist turns correctly."""
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
    return response_text.strip(), actual_session_id


def send_message(
    message: str,
    user_id: str = "anonymous",
    session_id: str = "default",
) -> str:
    """Synchronous wrapper for CLI use."""
    return asyncio.run(send_message_async(message, user_id, session_id))
