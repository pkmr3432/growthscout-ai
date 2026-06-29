# service/api/routers/sessions.py
"""
FastAPI router mapping HTTP request actions to ExecutionService.
"""

import asyncio
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status, Request
from service.api.schemas.v1.session import (
    SessionCreateRequest,
    SessionResponse,
    FeedbackSubmitRequest
)
from service.api.schemas.v1.error import StandardErrorResponse
from service.api.dependencies import verify_api_key, get_execution_service
from service.application.execution_service import ExecutionService

router = APIRouter(
    prefix="/sessions",
    tags=["Sessions Operations"],
    dependencies=[Depends(verify_api_key)]
)

@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createSession",
    summary="Create a new workflow session",
    description="Initializes a new workflow execution session and validates its initial state transitions.",
    responses={
        400: {"model": StandardErrorResponse, "description": "Bad Request - Schema validation failed"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized - Missing or invalid API key"},
        403: {"model": StandardErrorResponse, "description": "Forbidden - Insufficient authentication scopes"},
        413: {"model": StandardErrorResponse, "description": "Payload Too Large - Request body exceeds limit"},
        429: {"model": StandardErrorResponse, "description": "Too Many Requests - Rate limit exceeded"},
        500: {"model": StandardErrorResponse, "description": "Internal Server Error - Unexpected failure"}
    }
)
async def create_session(
    payload: SessionCreateRequest,
    service: ExecutionService = Depends(get_execution_service)
):
    doc = await service.create_session(
        niche=payload.niche,
        location=payload.location,
        max_leads=payload.max_leads
    )
    return SessionResponse(**doc)

@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    operation_id="getSession",
    summary="Retrieve session checkpoint state",
    description="Loads the persisted checkpoint document and execution context for the specified session ID.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Unauthorized - Missing or invalid API key"},
        404: {"model": StandardErrorResponse, "description": "Session Not Found - The specified ID does not exist"},
        429: {"model": StandardErrorResponse, "description": "Too Many Requests - Rate limit exceeded"},
        500: {"model": StandardErrorResponse, "description": "Internal Server Error"}
    }
)
async def get_session(
    session_id: str,
    service: ExecutionService = Depends(get_execution_service)
):
    doc = await service.get_session(session_id)
    return SessionResponse(**doc)

@router.post(
    "/{session_id}/run",
    response_model=SessionResponse,
    operation_id="runSession",
    summary="Execute session workflow",
    description="Triggers the background execution runner loop for the session. Verifies locks and transitions state to RUNNING.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Unauthorized - Missing or invalid API key"},
        404: {"model": StandardErrorResponse, "description": "Session Not Found - The specified ID does not exist"},
        409: {"model": StandardErrorResponse, "description": "Conflict - Session is currently locked by another active run"},
        429: {"model": StandardErrorResponse, "description": "Too Many Requests - Rate limit exceeded"},
        500: {"model": StandardErrorResponse, "description": "Internal Server Error"}
    }
)
async def run_session(
    session_id: str,
    request: Request,
    service: ExecutionService = Depends(get_execution_service)
):
    request_id = getattr(request.state, "request_id", "unknown")
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    doc = await service.run_session(session_id, request_id, correlation_id)
    return SessionResponse(**doc)

@router.post(
    "/{session_id}/feedback",
    response_model=SessionResponse,
    operation_id="submitFeedback",
    summary="Submit HITL review feedback",
    description="Submits human reviewer approval or modification notes, advancing the workflow run from its review gate.",
    responses={
        400: {"model": StandardErrorResponse, "description": "Bad Request - Schema validation failed"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized - Missing or invalid API key"},
        404: {"model": StandardErrorResponse, "description": "Session Not Found - The specified ID does not exist"},
        409: {"model": StandardErrorResponse, "description": "Conflict - Session is currently locked by another active run"},
        429: {"model": StandardErrorResponse, "description": "Too Many Requests - Rate limit exceeded"},
        500: {"model": StandardErrorResponse, "description": "Internal Server Error"}
    }
)
async def submit_feedback(
    session_id: str,
    payload: FeedbackSubmitRequest,
    request: Request,
    service: ExecutionService = Depends(get_execution_service)
):
    request_id = getattr(request.state, "request_id", "unknown")
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    doc = await service.submit_feedback(
        session_id=session_id,
        approved=payload.approved,
        feedback_notes=payload.feedback_notes,
        adjusted_data=payload.adjusted_data,
        request_id=request_id,
        correlation_id=correlation_id
    )
    return SessionResponse(**doc)

@router.post(
    "/{session_id}/cancel",
    response_model=SessionResponse,
    operation_id="cancelSession",
    summary="Cancel active workflow execution",
    description="Cooperatively cancels any running background tasks for the session and releases locks and resources.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Unauthorized - Missing or invalid API key"},
        404: {"model": StandardErrorResponse, "description": "Session Not Found - The specified ID does not exist"},
        429: {"model": StandardErrorResponse, "description": "Too Many Requests - Rate limit exceeded"},
        500: {"model": StandardErrorResponse, "description": "Internal Server Error"}
    }
)
async def cancel_session(
    session_id: str,
    service: ExecutionService = Depends(get_execution_service)
):
    doc = await service.cancel_session(session_id)
    return SessionResponse(**doc)

@router.get(
    "/{session_id}/stream",
    operation_id="streamSession",
    summary="Stream session events (SSE)",
    description="Establishes a persistent Server-Sent Events (SSE) stream yielding real-time execution events for the session. Supports Last-Event-ID parameter.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Unauthorized - Missing or invalid API key"},
        404: {"model": StandardErrorResponse, "description": "Session Not Found - The specified ID does not exist"},
        429: {"model": StandardErrorResponse, "description": "Too Many Requests - Rate limit exceeded"},
        500: {"model": StandardErrorResponse, "description": "Internal Server Error"}
    }
)
async def stream_session(
    session_id: str,
    request: Request,
    service: ExecutionService = Depends(get_execution_service)
):
    from fastapi.responses import StreamingResponse
    from service.infrastructure.registry import registry

    # Validate session exists before opening stream
    await service.get_session(session_id)

    # Parse Last-Event-ID for replay support
    last_event_id_raw = request.headers.get("Last-Event-ID")
    last_event_id: Optional[int] = None
    if last_event_id_raw is not None:
        try:
            last_event_id = int(last_event_id_raw)
        except (ValueError, TypeError):
            last_event_id = None

    publisher = registry.event_publisher

    async def sse_generator():
        """Async generator yielding SSE-formatted event strings."""
        try:
            async for envelope in publisher.subscribe(session_id, last_event_id=last_event_id):
                yield envelope.to_sse_format()
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )
