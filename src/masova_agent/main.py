"""
MaSoVa Support Agent — FastAPI REST entry point.

Run:
    uvicorn src.masova_agent.main:app --host 0.0.0.0 --port 8000 --reload
"""

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
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MaSoVa Support Agent",
    description="AI-powered customer support for MaSoVa restaurant chain.",
    version="0.2.0",
)

_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:8080",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    sessionId: Optional[str] = None
    customerId: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    sessionId: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "masova-support-agent"}


@app.post("/agent/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to the MaSoVa support agent.

    Pass the same `sessionId` across turns to maintain conversation history.
    `customerId` is used as the stable user identity for session isolation.
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
