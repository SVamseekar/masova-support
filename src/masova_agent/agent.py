"""
MaSoVa Customer Support Agent
"""

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
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
)

load_dotenv()
logger = logging.getLogger(__name__)

_session_service = InMemorySessionService()
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

Guidelines:
1. Be warm, concise, and helpful.
2. For order inquiries, ask for the order ID if not provided, then call get_order_status.
3. For menu questions, ask which store or assume store-1 if unclear.
4. Confirm details before submitting complaints or refund requests.
5. If a tool fails, offer alternatives (phone: 1800-MASOVA, email: support@masova.com).
6. Keep responses under 150 words unless listing menu items.
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
