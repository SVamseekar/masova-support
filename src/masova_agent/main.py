"""
MaSoVa Support Agent — FastAPI REST entry point.

Run:
    uvicorn src.masova_agent.main:app --host 0.0.0.0 --port 8000 --reload
"""

import asyncio
import base64
import binascii
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Body, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, AliasChoices, model_validator

from .agent import send_message_async, _session_service
from .auth import (
    AgentIdentity,
    bind_identity,
    reset_identity,
    verify_customer_jwt,
)
from .runtime.identity import require_scope
from .scheduler.scheduler import scheduler, register_jobs
from .utils.env_check import check_environment

load_dotenv()
check_environment(strict=True)
logger = logging.getLogger(__name__)


async def _start_review_consumer():
    """Consume review.created events from RabbitMQ for Agent 5."""
    try:
        import aio_pika
        from .agents.review_response_agent import draft_review_response

        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        connection = await aio_pika.connect_robust(rabbitmq_url)
        channel = await connection.channel()
        queue = await channel.declare_queue("masova.agent.reviews", durable=True)
        exchange = await channel.declare_exchange(
            "masova.reviews.exchange", aio_pika.ExchangeType.TOPIC, durable=True
        )
        await queue.bind(exchange, "review.created")

        logger.info("RabbitMQ review consumer started")

        async for message in queue:
            async with message.process():
                review_data = json.loads(message.body)
                if review_data.get("rating", 5) <= 3:
                    await draft_review_response(review_data)
    except Exception as e:
        logger.warning("RabbitMQ consumer not started (%s) — review response agent disabled", e)


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # Reload config to pick up any .env changes made after module import
    from .utils.config import reload_config

    reload_config()

    # Start scheduler
    scheduler.start()
    register_jobs()
    logger.info("APScheduler started with %d jobs", len(scheduler.get_jobs()))

    # Start RabbitMQ consumer; hold reference so it is not GC'd
    _review_task = asyncio.create_task(_start_review_consumer())

    yield

    # Shutdown
    _review_task.cancel()
    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")


app = FastAPI(
    title="MaSoVa Support Agent",
    description="AI-powered customer support for MaSoVa restaurant chain.",
    version="0.3.0",
    lifespan=lifespan,
)

_console_dir = Path(__file__).parent / "static"
app.mount("/console-assets", StaticFiles(directory=_console_dir), name="console-assets")


@app.exception_handler(RequestValidationError)
async def validation_errors(request: Request, exc: RequestValidationError):
    if request.url.path == "/agent/manager/chat":
        # Default validation errors echo the input; recordings must remain transient.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
                    for error in exc.errors()
                ]
            },
        )
    return await request_validation_exception_handler(request, exc)


@app.get("/console", include_in_schema=False)
async def console():
    return FileResponse(_console_dir / "console.html")


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


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    from .runtime.rate_limit import check_rate_limit, classify_route_tier

    tier = classify_route_tier(request.url.path, request.method)
    client_host = request.client.host if request.client else "unknown"
    key = request.headers.get("X-Agent-Api-Key") or request.headers.get(
        "X-Customer-Token", client_host
    )
    if not check_rate_limit(key, tier):
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
    return await call_next(request)


# ---------------------------------------------------------------------------
# Chat endpoint (Agent 1)
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    sessionId: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    sessionId: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "masova-support-agent"}


@app.post("/agent/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, identity: AgentIdentity = Depends(verify_customer_jwt)):
    """Send a message to the support agent as the caller's verified identity."""
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")

    session_id = request.sessionId or str(uuid.uuid4())
    user_id = identity.user_id

    # Bind the verified identity for the duration of this request so tool
    # functions (submit_complaint, cancel_order, etc.) act on the real
    # authenticated customer rather than any LLM-parsed argument.
    token = bind_identity(identity)
    try:
        reply, actual_session_id = await send_message_async(
            message=request.message.strip(),
            user_id=user_id,
            session_id=session_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Agent error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Agent unavailable. Please try again.")
    finally:
        reset_identity(token)

    await _session_service.append_turn(actual_session_id, "user", request.message.strip())
    await _session_service.append_turn(actual_session_id, "assistant", reply)

    return ChatResponse(reply=reply, sessionId=session_id)


# ---------------------------------------------------------------------------
# Agent trigger endpoints (internal/ops — scheduler or manager triggered).
# Gated by a static service API key, not a customer JWT: there is no single
# customer identity to bind these to.
# ---------------------------------------------------------------------------


@app.post(
    "/agents/demand-forecast/trigger",
    dependencies=[Depends(require_scope("trigger:demand_forecast"))],
)
async def trigger_demand_forecast():
    from .agents.demand_forecasting_agent import run_demand_forecast

    return await run_demand_forecast()


@app.post(
    "/agents/inventory-reorder/trigger",
    dependencies=[Depends(require_scope("trigger:inventory_reorder"))],
)
async def trigger_inventory_reorder():
    from .agents.inventory_reorder_agent import run_inventory_reorder

    return await run_inventory_reorder()


@app.post(
    "/agents/churn-prevention/trigger",
    dependencies=[Depends(require_scope("trigger:churn_prevention"))],
)
async def trigger_churn_prevention():
    from .agents.churn_prevention_agent import run_churn_prevention

    return await run_churn_prevention()


@app.post(
    "/agents/review-response/trigger",
    dependencies=[Depends(require_scope("trigger:review_response"))],
)
async def trigger_review_response(review_data: dict = Body(...)):
    from .agents.review_response_agent import draft_review_response

    return await draft_review_response(review_data)


@app.post(
    "/agents/shift-optimisation/trigger",
    dependencies=[Depends(require_scope("trigger:shift_optimisation"))],
)
async def trigger_shift_opt():
    from .agents.shift_optimisation_agent import run_shift_optimisation

    return await run_shift_optimisation()


@app.post(
    "/agents/kitchen-coach/trigger",
    dependencies=[Depends(require_scope("trigger:kitchen_coach"))],
)
async def trigger_kitchen_coach():
    from .agents.kitchen_coach_agent import run_kitchen_coach

    return await run_kitchen_coach()


@app.post(
    "/agents/dynamic-pricing/trigger",
    dependencies=[Depends(require_scope("trigger:dynamic_pricing"))],
)
async def trigger_dynamic_pricing():
    from .agents.dynamic_pricing_agent import run_dynamic_pricing

    return await run_dynamic_pricing()


# ---------------------------------------------------------------------------
# ActionProposal list / resolve (manager outcome recording — not final execute)
# ---------------------------------------------------------------------------


class ResolveProposalBody(BaseModel):
    status: str  # APPROVED | REJECTED
    note: Optional[str] = Field(default=None, max_length=2000)


@app.get("/agent/proposals", dependencies=[Depends(require_scope("read:proposals"))])
async def list_action_proposals(
    storeId: Optional[str] = None,
    status: Optional[str] = None,
    agent: Optional[str] = None,
    limit: int = 100,
):
    """
    List ActionProposals stored by this service.

    Final business execute still happens in platform UI/backend after a manager
    approves there; this endpoint records local audit outcomes.
    """
    from .runtime import proposal_store

    return {
        "proposals": proposal_store.list_proposals(
            store_id=storeId, status=status, agent=agent, limit=limit
        )
    }


@app.post(
    "/agent/proposals/{proposal_id}/resolve",
    dependencies=[Depends(require_scope("resolve:proposals"))],
)
async def resolve_action_proposal(proposal_id: str, body: ResolveProposalBody):
    from .runtime import proposal_store

    if body.status.upper() not in ("APPROVED", "REJECTED"):
        raise HTTPException(status_code=400, detail="Only APPROVED or REJECTED may be recorded")
    try:
        rec = proposal_store.resolve_proposal(proposal_id, body.status, note=body.note or "")
    except proposal_store.ProposalConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not rec:
        raise HTTPException(status_code=404, detail="proposal not found")
    return rec


class ManagerChatRequest(BaseModel):
    message: str = Field(default="", max_length=8000)
    session_id: Optional[str] = Field(
        default="default", max_length=128, validation_alias=AliasChoices("session_id", "sessionId")
    )
    store_id: Optional[str] = Field(
        default=None, max_length=128, validation_alias=AliasChoices("store_id", "storeId")
    )
    audio_base64: Optional[str] = Field(
        default=None,
        max_length=5592408,
        validation_alias=AliasChoices("audio_base64", "audioBase64"),
    )
    mime_type: str = Field(
        default="audio/webm", validation_alias=AliasChoices("mime_type", "mimeType")
    )

    @model_validator(mode="before")
    @classmethod
    def unambiguous_aliases(cls, value):
        if isinstance(value, dict):
            for snake, camel in [
                ("session_id", "sessionId"),
                ("store_id", "storeId"),
                ("audio_base64", "audioBase64"),
                ("mime_type", "mimeType"),
            ]:
                if snake in value and camel in value and value[snake] != value[camel]:
                    raise ValueError(f"Conflicting {snake}/{camel} values")
        return value

    @model_validator(mode="after")
    def valid_input(self):
        from .agents.manager_audio import AUDIO_MIME_TYPES, MAX_AUDIO_BYTES

        self.message = self.message.strip()
        if not self.message and not self.audio_base64:
            raise ValueError("Provide a non-empty message or audio recording")
        if self.audio_base64:
            if self.mime_type not in AUDIO_MIME_TYPES:
                raise ValueError("Unsupported audio MIME type")
            try:
                audio = base64.b64decode(self.audio_base64, validate=True)
            except (ValueError, binascii.Error):
                raise ValueError("Invalid base64 audio")
            if not audio or len(audio) > MAX_AUDIO_BYTES:
                raise ValueError("Audio must be between 1 byte and 4 MiB")
        return self


@app.post("/agent/manager/chat")
async def manager_chat(body: ManagerChatRequest, _=Depends(require_scope("chat:manager"))):
    from .agents.manager_chat_agent import run_manager_chat

    try:
        return await run_manager_chat(
            body.message,
            body.session_id or "default",
            body.store_id,
            audio_base64=body.audio_base64,
            mime_type=body.mime_type,
            scopes=_.get("scopes") or [],
            principal=_.get("key") or "manager",
        )
    except Exception:
        raise HTTPException(
            status_code=502, detail="Manager speech unavailable. Retry or type a message."
        )


@app.get("/agent/manager/conversations")
async def manager_conversations(
    storeId: Optional[str] = Query(default=None, max_length=128),
    limit: int = Query(default=50, ge=1, le=128),
    identity=Depends(require_scope("chat:manager")),
):
    from .runtime import conversation_store

    try:
        rows = await asyncio.to_thread(
            conversation_store.list_conversations, identity["key"], storeId, limit
        )
    except conversation_store.HistoryUnavailable:
        raise HTTPException(
            status_code=503, detail="Conversation history unavailable. Retry later."
        )
    return {"conversations": rows, "storeId": storeId or None}


@app.get("/agent/manager/conversations/{session_id}")
async def manager_conversation(
    session_id: str,
    storeId: Optional[str] = Query(default=None, max_length=128),
    identity=Depends(require_scope("chat:manager")),
):
    from .runtime import conversation_store

    if not session_id or len(session_id) > 128:
        raise HTTPException(status_code=422, detail="Invalid conversation ID")
    try:
        record = await asyncio.to_thread(
            conversation_store.get_conversation, identity["key"], storeId, session_id
        )
    except conversation_store.HistoryUnavailable:
        raise HTTPException(
            status_code=503, detail="Conversation history unavailable. Retry later."
        )
    if record is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"conversation": record}


@app.get("/agent/manager/stores")
async def manager_stores(_=Depends(require_scope("read:registry"))):
    from .tools.ops_tools import list_stores

    import httpx

    try:
        return await list_stores()
    except httpx.RequestError as ex:
        raise HTTPException(
            status_code=503,
            detail="Store lookup unavailable. Retry when the backend reconnects.",
        ) from ex


@app.get("/agent/console")
async def console_catalog(identity=Depends(require_scope("read:registry"))):
    from .runtime.console_catalog import SPECIALISTS

    return {
        "specialists": SPECIALISTS,
        "scopes": identity.get("scopes") or [],
        "decision_execution": "record_only",
    }


@app.get("/agents")
async def list_agents(_=Depends(require_scope("read:registry"))):
    from .runtime.wrap import AGENT_ALLOWLISTS

    return [{"name": name, "tool_count": len(tools)} for name, tools in AGENT_ALLOWLISTS.items()]


@app.get("/agent/runs")
async def get_runs(
    limit: int = Query(default=100, ge=1, le=500),
    agent: Optional[str] = None,
    storeId: Optional[str] = None,
    _=Depends(require_scope("read:runs")),
):
    from .runtime import run_store

    return run_store.list_runs(limit=limit, agent=agent, store_id=storeId)


@app.get("/agent/runs/{run_id}")
async def get_run_by_id(run_id: str, _=Depends(require_scope("read:runs"))):
    from .runtime import run_store

    run = run_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
