"""
Core agent implementation
"""
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai import types as genai_types
import asyncio
import os
from typing import Optional

from ..tools import get_system_briefing
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
            tools=[get_system_briefing]
        )

        # Redis-backed session service with InMemory fallback
        redis_url = os.environ.get("REDIS_URL", "redis://192.168.50.88:6379/1")
        self._session_service = RedisSessionService(redis_url=redis_url)
        self._created_sessions = set()

        logger.info(f"Agent initialized: {self.config.agent.name}")

    def _get_instruction(self) -> str:
        """Get agent instruction"""
        return """You are MaSoVa Customer Support Assistant.

PROTOCOL:
1. When the user identifies themselves (e.g., as 'Soura' or 'Soura Vamseekar'),
   call 'get_system_briefing' with their name.
2. IMPORTANT: You MUST output the exact text returned by the tool.
3. Do not add extra commentary. Present the briefing clearly.
4. After the briefing, you may assist with order inquiries, menu questions,
   and customer support.

BEHAVIOR:
- Be professional and courteous
- Provide clear, concise responses
- Always verify user identity before discussing orders
- If user is not in database, politely inform them
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
