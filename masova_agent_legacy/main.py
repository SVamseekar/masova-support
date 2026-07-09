"""
MaSoVa Support Agent — REST API entry point.

Exposes POST /agent/chat for embedding in web and mobile apps.
Also supports the original CLI chat mode.

Run:
    uvicorn masova_agent.main:app_api --host 0.0.0.0 --port 8000 --reload
"""

import asyncio
import logging
import os
import uuid
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent import send_message_async, save_session_to_redis, load_session_from_redis

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app_api = FastAPI(
    title="MaSoVa Support Agent",
    description="AI-powered customer support for MaSoVa restaurant chain.",
    version="0.2.0",
)

# Allow requests from web frontend and mobile (adjust origins for production)
_allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:8080",
).split(",")

app_api.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    sessionId: Optional[str] = None   # client-managed; generated if omitted
    customerId: Optional[str] = None  # authenticated customer's MongoDB _id


class ChatResponse(BaseModel):
    reply: str
    sessionId: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app_api.get("/health")
def health():
    return {"status": "ok", "service": "masova-support-agent"}


@app_api.post("/agent/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to the MaSoVa support agent and receive a response.

    - `message`: the user's text
    - `sessionId`: pass the same value across turns to maintain conversation history
    - `customerId`: optional; used as the stable user_id for session isolation
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")

    session_id = request.sessionId or str(uuid.uuid4())
    user_id = request.customerId or f"anon-{session_id}"

    try:
        reply = await send_message_async(
            message=request.message.strip(),
            user_id=user_id,
            session_id=session_id,
        )
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Agent unavailable. Please try again.")

    # Persist turn to Redis (last 10 turns, 1h TTL)
    session_key = f"{user_id}:{session_id}"
    history = load_session_from_redis(session_key)
    history.append({"user": request.message.strip(), "assistant": reply})
    if len(history) > 10:
        history = history[-10:]
    save_session_to_redis(session_key, history)

    return ChatResponse(reply=reply, sessionId=session_id)


# ---------------------------------------------------------------------------
# CLI chat mode (python -m masova_agent.main)
# ---------------------------------------------------------------------------

def _cli():
    from .agent import send_message  # sync wrapper

    print("=" * 50)
    print("   MaSoVa Support — Interactive Session")
    print("=" * 50)
    print("Type 'exit' or 'quit' to end.\n")

    session_id = "cli-session"
    user_id = "cli-user"

    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() in ("exit", "quit"):
                print("\nGoodbye!")
                break
            if not user_input.strip():
                continue
            response = send_message(user_input, user_id=user_id, session_id=session_id)
            print(f"\nMaSoVa: {response}")
        except KeyboardInterrupt:
            print("\n\nSession interrupted. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            print(f"\nError: {e}\nPlease try again.")


if __name__ == "__main__":
    _cli()
