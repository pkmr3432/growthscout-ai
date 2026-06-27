# service/application/execution_service.py
"""
Execution service coordinating workflow runs, locks, states, checkpoint store,
and event publishing for real-time SSE streaming.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import HTTPException, status

from service.application.states import SessionState, validate_transition, InvalidStateTransitionError
from service.infrastructure.registry import registry
from service.infrastructure.config import settings

from agents.orchestrator_agent.state_machine.workflow_context import (
    WorkflowContext,
    WorkflowMetadata,
    ExecutionMetadata,
    WorkflowTimestamps
)
from agents.orchestrator_agent.state_machine.states import WorkflowState

logger = logging.getLogger("growthscout.execution_service")

class ExecutionService:
    """
    Coordinates workflow creation, async running loops, resuming HITL approvals,
    lock acquisition, checkpoint persistence, and event publication to SSE subscribers.
    """
    def __init__(self) -> None:
        self.lock_manager = registry.lock_manager
        self.scheduler = registry.task_scheduler
        self.store = registry.checkpoint_store
        self.publisher = registry.event_publisher

    async def _emit_event(
        self,
        session_id: str,
        event_name: str,
        data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Safely publishes an event via the EventPublisher, catching exceptions to
        prevent event emission failures from disrupting workflow execution.
        """
        try:
            await self.publisher.publish(
                session_id=session_id,
                event_name=event_name,
                data=data,
                correlation_id=correlation_id
            )
        except Exception as e:
            logger.warning(f"Event emission failed for session {session_id}: {e}")

    async def create_session(self, niche: str, location: str, max_leads: int) -> Dict[str, Any]:
        """
        Creates a session database record, validates initial states, and saves checkpoint.
        """
        import uuid
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        doc = {
            "session_id": session_id,
            "workflow_id": workflow_id,
            "current_state": SessionState.CREATED.value,
            "niche": niche,
            "location": location,
            "max_leads": max_leads,
            "revision_count": 0,
            "created_at": now,
            "updated_at": now,
            "status": "idle",
            "context_data": None
        }

        # Validate transition: CREATED -> IDLE
        validate_transition(SessionState.CREATED, SessionState.IDLE)
        doc["current_state"] = SessionState.IDLE.value
        
        await self.store.save_checkpoint(session_id, doc)
        return doc

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Loads the session state document from the CheckpointStore.
        Raises HTTP 404 if missing.
        """
        doc = await self.store.load_checkpoint(session_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "SESSION_NOT_FOUND",
                        "message": f"No session found matching identifier '{session_id}'."
                    }
                }
            )
        return doc

    async def run_session(self, session_id: str, request_id: str, correlation_id: str) -> Dict[str, Any]:
        """
        Triggers execution run for a session ID. Checks locks and schedules background tasks.
        Emits execution_started event on successful scheduling.
        """
        doc = await self.get_session(session_id)
        
        # 1. Check Session Locks
        if await self.lock_manager.is_locked(session_id) or await self.scheduler.is_task_running(session_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "SESSION_LOCKED",
                        "message": f"Session '{session_id}' is currently running an active background task."
                    }
                }
            )

        # 2. Acquire Session Lock
        acquired = await self.lock_manager.acquire(session_id)
        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "SESSION_LOCKED",
                        "message": f"Failed to acquire session lock for '{session_id}'."
                    }
                }
            )

        # 3. Validate state machine transition
        current_state = SessionState(doc["current_state"])
        try:
            validate_transition(current_state, SessionState.RUNNING)
        except InvalidStateTransitionError as e:
            await self.lock_manager.release(session_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_TRANSITION",
                        "message": str(e)
                    }
                }
            )

        doc["current_state"] = SessionState.RUNNING.value
        doc["status"] = "running"
        doc["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        await self.store.save_checkpoint(session_id, doc)

        # Emit execution_started event
        await self._emit_event(
            session_id=session_id,
            event_name="execution_started",
            data={
                "previous_state": current_state.value,
                "new_state": SessionState.RUNNING.value,
                "niche": doc["niche"],
                "location": doc["location"]
            },
            correlation_id=correlation_id
        )

        # 4. Schedule background runner
        run_coro = self._run_workflow_loop(session_id, request_id, correlation_id)
        # Timeout derived from config (default 1800 seconds)
        scheduled = await self.scheduler.schedule_task(
            session_id=session_id,
            coro=run_coro,
            timeout_seconds=float(settings.mcp.timeout_seconds * 60) # converting to minutes scope if needed, let's use 1800
        )
        
        if not scheduled:
            await self.lock_manager.release(session_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": {
                        "code": "SCHEDULER_FAILED",
                        "message": "Failed to schedule background execution task."
                    }
                }
            )

        return doc

    async def submit_feedback(
        self,
        session_id: str,
        approved: bool,
        feedback_notes: Optional[str],
        adjusted_data: Optional[Dict[str, Any]],
        request_id: str,
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Submits feedback to a session waiting for feedback, resuming background runs.
        """
        doc = await self.get_session(session_id)

        # 1. Verify Locks
        if await self.lock_manager.is_locked(session_id) or await self.scheduler.is_task_running(session_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "SESSION_LOCKED",
                        "message": f"Session '{session_id}' is locked by active runner."
                    }
                }
            )

        # 2. Acquire lock
        acquired = await self.lock_manager.acquire(session_id)
        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "SESSION_LOCKED",
                        "message": "Lock acquisition failed."
                    }
                }
            )

        # 3. Transition verification: WAITING_FOR_FEEDBACK -> RESUMING
        current_state = SessionState(doc["current_state"])
        try:
            validate_transition(current_state, SessionState.RESUMING)
            # Intermediate state transition
            doc["current_state"] = SessionState.RESUMING.value
            doc["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            await self.store.save_checkpoint(session_id, doc)

            # Emit state_changed event for RESUMING
            await self._emit_event(
                session_id=session_id,
                event_name="state_changed",
                data={
                    "previous_state": current_state.value,
                    "new_state": SessionState.RESUMING.value,
                    "approved": approved
                },
                correlation_id=correlation_id
            )

            # Transition: RESUMING -> RUNNING
            validate_transition(SessionState.RESUMING, SessionState.RUNNING)
            doc["current_state"] = SessionState.RUNNING.value
            doc["status"] = "running"
            doc["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            await self.store.save_checkpoint(session_id, doc)

            # Emit execution_started event for resume
            await self._emit_event(
                session_id=session_id,
                event_name="execution_started",
                data={
                    "previous_state": SessionState.RESUMING.value,
                    "new_state": SessionState.RUNNING.value,
                    "resumed": True,
                    "approved": approved
                },
                correlation_id=correlation_id
            )
        except InvalidStateTransitionError as e:
            await self.lock_manager.release(session_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_TRANSITION",
                        "message": str(e)
                    }
                }
            )

        # 4. Schedule resume workflow loop
        run_coro = self._run_workflow_loop(
            session_id=session_id,
            request_id=request_id,
            correlation_id=correlation_id,
            resume=True,
            approved=approved,
            feedback_notes=feedback_notes,
            adjusted_data=adjusted_data
        )
        await self.scheduler.schedule_task(
            session_id=session_id,
            coro=run_coro,
            timeout_seconds=1800.0
        )

        return doc

    async def cancel_session(self, session_id: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Cooperatively cancels active execution, updates state to CANCELLED, and releases lock.
        Emits execution_cancelled event.
        """
        doc = await self.get_session(session_id)
        
        # Trigger Task Cancellation
        cancelled = await self.scheduler.cancel_task(session_id)
        
        # State transition: validate transition current_state -> CANCELLED
        current_state = SessionState(doc["current_state"])
        try:
            validate_transition(current_state, SessionState.CANCELLED)
        except InvalidStateTransitionError as e:
            # Even if transition fails, we release the lock and cancel scheduler
            await self.lock_manager.release(session_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_TRANSITION",
                        "message": str(e)
                    }
                }
            )

        doc["current_state"] = SessionState.CANCELLED.value
        doc["status"] = "idle"
        doc["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        await self.store.save_checkpoint(session_id, doc)

        # Emit execution_cancelled event
        await self._emit_event(
            session_id=session_id,
            event_name="execution_cancelled",
            data={
                "previous_state": current_state.value,
                "new_state": SessionState.CANCELLED.value
            },
            correlation_id=correlation_id
        )

        # Close publisher stream for this session
        await self.publisher.close_session(session_id)
        
        # Ensure lock release
        await self.lock_manager.release(session_id)
        return doc

    async def _run_workflow_loop(
        self,
        session_id: str,
        request_id: str,
        correlation_id: str,
        resume: bool = False,
        approved: bool = True,
        feedback_notes: Optional[str] = None,
        adjusted_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Async worker loop executing WorkflowExecutor.
        Emits step_completed, gate_reached, execution_completed, and execution_failed events.
        """
        try:
            doc = await self.store.load_checkpoint(session_id)
            if not doc:
                return

            context_data = doc.get("context_data")
            if context_data:
                context = WorkflowContext.model_validate(context_data)
            else:
                # Build context
                from agents.orchestrator_agent.run_budget import WorkflowRunBudget
                metadata = WorkflowMetadata(
                    niche=doc["niche"],
                    location=doc["location"],
                    max_leads=doc["max_leads"]
                )
                exec_meta = ExecutionMetadata(
                    orchestrator_version="4.0",
                    adk_version="2.3.0",
                    correlation_id=correlation_id
                )
                ts = WorkflowTimestamps(
                    created_at=datetime.fromisoformat(doc["created_at"]) if isinstance(doc["created_at"], str) else doc["created_at"],
                    updated_at=datetime.now(timezone.utc),
                    state_entered_at=datetime.now(timezone.utc)
                )
                budget = WorkflowRunBudget(
                    max_seconds=1800,
                    max_tokens=500000,
                    max_cost=5.0
                )
                context = WorkflowContext(
                    session_id=session_id,
                    workflow_id=doc["workflow_id"],
                    current_state=WorkflowState.IDLE,
                    execution_metadata=exec_meta,
                    workflow_metadata=metadata,
                    timestamps=ts,
                    budget=budget
                )

            if resume:
                # Incorporate feedback variables into context
                context = context.with_incremented_revision(datetime.now(timezone.utc))
                next_state = WorkflowState.COMPLETED if approved else WorkflowState.REPORT_GENERATION
                context = context.with_state(next_state, datetime.now(timezone.utc))

            # Execute loop
            import os
            mock_eval = os.environ.get("GROWTHSCOUT_MOCK_EVAL") == "true" or settings.app.env == "development"
            
            previous_state = context.current_state.value if hasattr(context.current_state, 'value') else str(context.current_state)

            if mock_eval:
                # Simulate background runner execution trace
                await asyncio.sleep(1.0)
                if context.current_state == WorkflowState.IDLE:
                    context = context.with_state(WorkflowState.AWAITING_APPROVAL, datetime.now(timezone.utc))
                elif context.current_state == WorkflowState.REPORT_GENERATION:
                    context = context.with_state(WorkflowState.AWAITING_APPROVAL, datetime.now(timezone.utc))
                elif context.current_state == WorkflowState.COMPLETED:
                    context = context.with_state(WorkflowState.COMPLETED, datetime.now(timezone.utc))
            else:
                from agents.orchestrator_agent.workflow_executor import WorkflowExecutor
                executor = WorkflowExecutor()
                context = await executor.execute_to_gate(context)

            # Emit step_completed event
            new_state_value = context.current_state.value if hasattr(context.current_state, 'value') else str(context.current_state)
            await self._emit_event(
                session_id=session_id,
                event_name="step_completed",
                data={
                    "previous_state": previous_state,
                    "new_state": new_state_value,
                    "revision_count": context.revision_count
                },
                correlation_id=correlation_id
            )

            # Map context outcome state to SessionState
            session_state = SessionState.RUNNING
            status_val = "running"

            if context.current_state == WorkflowState.AWAITING_APPROVAL:
                session_state = SessionState.WAITING_FOR_FEEDBACK
                status_val = "paused_on_gate"
                # Emit gate_reached event
                await self._emit_event(
                    session_id=session_id,
                    event_name="gate_reached",
                    data={
                        "gate_type": "human_approval",
                        "state": session_state.value,
                        "revision_count": context.revision_count
                    },
                    correlation_id=correlation_id
                )
            elif context.current_state in [WorkflowState.COMPLETED, WorkflowState.NO_LEADS_FOUND]:
                session_state = SessionState.COMPLETED
                status_val = "completed"
                # Emit execution_completed event
                await self._emit_event(
                    session_id=session_id,
                    event_name="execution_completed",
                    data={
                        "state": session_state.value,
                        "revision_count": context.revision_count,
                        "terminal": True
                    },
                    correlation_id=correlation_id
                )
                # Close publisher stream for completed sessions
                await self.publisher.close_session(session_id)
            elif context.current_state == WorkflowState.FAILED:
                session_state = SessionState.FAILED
                status_val = "failed"
                # Emit execution_failed event
                await self._emit_event(
                    session_id=session_id,
                    event_name="execution_failed",
                    data={
                        "state": session_state.value,
                        "reason": "Workflow execution encountered a failure"
                    },
                    correlation_id=correlation_id
                )
                await self.publisher.close_session(session_id)
            elif context.current_state == WorkflowState.CANCELLED:
                session_state = SessionState.CANCELLED
                status_val = "cancelled"

            # Reload document to ensure no overrides
            doc = await self.store.load_checkpoint(session_id)
            if doc:
                doc["current_state"] = session_state.value
                doc["status"] = status_val
                doc["revision_count"] = context.revision_count
                doc["context_data"] = context.model_dump(mode="json")
                doc["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                await self.store.save_checkpoint(session_id, doc)

        except asyncio.CancelledError:
            logger.info(f"Task execution for session {session_id} cancelled.")
            doc = await self.store.load_checkpoint(session_id)
            if doc:
                doc["current_state"] = SessionState.CANCELLED.value
                doc["status"] = "idle"
                doc["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                await self.store.save_checkpoint(session_id, doc)
            raise
        except Exception as e:
            logger.error(f"Background task failure on session {session_id}: {e}")
            # Emit execution_failed event
            await self._emit_event(
                session_id=session_id,
                event_name="execution_failed",
                data={
                    "state": SessionState.FAILED.value,
                    "reason": str(e)
                },
                correlation_id=correlation_id
            )
            doc = await self.store.load_checkpoint(session_id)
            if doc:
                doc["current_state"] = SessionState.FAILED.value
                doc["status"] = "failed"
                doc["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                await self.store.save_checkpoint(session_id, doc)
        finally:
            # Release locking state
            await self.lock_manager.release(session_id)
