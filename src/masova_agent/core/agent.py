"""
Core agent implementation
"""
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai import types as genai_types
import asyncio
import os
from typing import Optional

from ..tools import (
    get_system_briefing,
    get_order_status,
    get_menu_items,
    get_store_hours,
    submit_complaint,
    request_refund,
    get_loyalty_points,
    get_store_wait_time,
    cancel_order,
)
from ..utils import get_config, get_logger, setup_logging
from ..exceptions import AgentError
from .redis_session_service import RedisSessionService

logger = get_logger(__name__)


class MaSoVaAgent:
    """MaSoVa Customer Support Agent"""

    def __init__(self):
        """Initialize agent"""
        self.config = get_config()
        setup_logging(level=self.config.logging.level)

        # Create ADK agent
        self.llm_agent = LlmAgent(
            name=self.config.agent.name,
            model=self.config.agent.model,
            instruction=self._get_instruction(),
            tools=[
                get_system_briefing,
                get_order_status,
                get_menu_items,
                get_store_hours,
                submit_complaint,
                request_refund,
                get_loyalty_points,
                get_store_wait_time,
                cancel_order,
            ]
        )

        # Redis-backed session service with InMemory fallback
        redis_url = os.environ.get("REDIS_URL", "redis://192.168.50.88:6379/1")
        self._session_service = RedisSessionService(redis_url=redis_url)
        self._created_sessions = set()

        logger.info(f"Agent initialized: {self.config.agent.name}")

    def _get_instruction(self) -> str:
        """Get agent instruction"""
        return """You are MaSoVa Customer Support Assistant.

CAPABILITIES:
- Check order status: ask for order number or customer email
- Show menu items: ask what cuisine or category they want
- Store hours: tell customers when the store is open
- Submit complaints: log customer complaints with category and description
- Request refunds: initiate refunds for valid complaints
- Check loyalty points: tell customers their points balance and how to redeem
- Store wait time: current estimated wait for new orders
- Cancel order: cancel if status allows (RECEIVED only)

PROTOCOL:
1. Greet the customer warmly
2. Ask what you can help with
3. Use the appropriate tool to get real data — never make up order numbers, times, or points
4. If a tool fails, apologize and suggest contacting the store directly

TONE: Professional, helpful, brief. Maximum 3 sentences per response.
"""

    async def _create_session_if_needed(
        self,
        user_id: str,
        session_id: str
    ) -> str:
        """Create session if it doesn't exist"""
        session_key = f"{user_id}:{session_id}"

        if session_key not in self._created_sessions:
            session = await self._session_service.create_session(
                app_name=self.config.agent.app_name,
                user_id=user_id
            )
            self._created_sessions.add(session_key)
            logger.info(f"Created session: {session.id} for user: {user_id}")
            return session.id

        return session_id

    async def _send_async(
        self,
        message: str,
        user_id: str = "default_user",
        session_id: str = "default_session"
    ) -> str:
        """
        Send message to agent (async)

        Args:
            message: User message
            user_id: User identifier
            session_id: Session identifier

        Returns:
            Agent response text

        Raises:
            AgentError: If agent encounters an error
        """
        try:
            # Ensure session exists
            actual_session_id = await self._create_session_if_needed(user_id, session_id)

            # Create runner
            runner = Runner(
                agent=self.llm_agent,
                app_name=self.config.agent.app_name,
                session_service=self._session_service
            )

            # Create user message
            user_message = genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=message)]
            )

            # Execute agent
            response_text = ""
            event_stream = runner.run(
                user_id=user_id,
                session_id=actual_session_id,
                new_message=user_message
            )

            for event in event_stream:
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            response_text += part.text

            # Give async thread time to complete
            await asyncio.sleep(0.5)

            logger.info(f"Response generated for user: {user_id}")
            return response_text.strip()

        except Exception as e:
            logger.error(f"Agent error: {e}", exc_info=True)
            raise AgentError(f"Failed to process message: {str(e)}")

    def send_message(
        self,
        message: str,
        user_id: str = "default_user",
        session_id: str = "default_session"
    ) -> str:
        """
        Send message to agent (synchronous)

        Args:
            message: User message
            user_id: User identifier
            session_id: Session identifier

        Returns:
            Agent response text
        """
        return asyncio.run(self._send_async(message, user_id, session_id))


# Global agent instance
_agent: Optional[MaSoVaAgent] = None


def get_agent() -> MaSoVaAgent:
    """Get global agent instance"""
    global _agent
    if _agent is None:
        _agent = MaSoVaAgent()
    return _agent


def send_message(
    message: str,
    user_id: str = "default_user",
    session_id: str = "default_session"
) -> str:
    """
    Send message to agent (convenience function)

    Args:
        message: User message
        user_id: User identifier
        session_id: Session identifier

    Returns:
        Agent response text
    """
    agent = get_agent()
    return agent.send_message(message, user_id, session_id)


# Export for ADK discovery
root_agent = get_agent().llm_agent
agent = root_agent
app = root_agent
