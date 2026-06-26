# tests/orchestrator_tests/test_audit_trail.py
"""
Tests: AuditTrailWriter immutable append-only trail.

Validates:
  - All 10 AuditEventType values are accepted
  - append() works for new entries
  - append() with duplicate entry_id raises ImmutabilityViolationError
  - read_trail() returns entries in insertion order
  - find_by_event_type() filters correctly
  - count() returns correct total
  - Different sessions are isolated from each other
"""
import pytest
from datetime import datetime, timezone

from agents.orchestrator_agent.hooks.audit_trail import (
    AuditTrailWriter,
    AuditTrailEntry,
    AuditEventType,
)
from agents.orchestrator_agent.state_machine.states import WorkflowState
from agents.orchestrator_agent.exceptions import ImmutabilityViolationError


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _make_entry(
    entry_id: str = "evt_abcd1234",
    session_id: str = "sess_abcd1234",
    event_type: AuditEventType = AuditEventType.STATE_ENTERED,
) -> AuditTrailEntry:
    return AuditTrailEntry(
        entry_id=entry_id,
        session_id=session_id,
        workflow_id="wf_abcd1234",
        event_type=event_type,
        workflow_state=WorkflowState.IDLE,
        acting_agent="orchestrator_agent",
        timestamp=_now(),
        transition_reason="test entry",
    )


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestAuditEventTypeEnum:
    def test_all_event_types_present(self):
        expected = {
            "STATE_ENTERED", "STATE_EXITED",
            "WORKER_STARTED", "WORKER_COMPLETED", "WORKER_FAILED",
            "MEMORY_WRITE", "MEMORY_READ",
            "CHECKPOINT_CREATED",
            "WORKFLOW_RESUMED",
            "VALIDATION_FAILED",
            "VALIDATION_STARTED",
            "SCHEMA_VALIDATION_FAILED",
            "BUSINESS_VALIDATION_FAILED",
            "OUTPUT_NORMALIZED",
            "VALIDATION_SUCCEEDED",
            "RETRY_STARTED",
            "RETRY_COMPLETED",
            "CIRCUIT_OPENED",
            "CIRCUIT_HALF_OPEN",
            "CIRCUIT_CLOSED",
            "TIMEOUT_OCCURRED",
            "WORKFLOW_RECOVERY_FAILED",
        }
        actual = {e.value for e in AuditEventType}
        assert actual == expected

    def test_event_type_count(self):
        assert len(list(AuditEventType)) == 22


class TestAuditTrailEntry:
    def test_valid_entry_id_pattern(self):
        entry = _make_entry(entry_id="evt_deadbeef")
        assert entry.entry_id == "evt_deadbeef"

    def test_invalid_entry_id_raises(self):
        with pytest.raises(Exception):
            _make_entry(entry_id="bad_id")

    def test_entry_is_frozen(self):
        """AuditTrailEntry must be immutable."""
        entry = _make_entry()
        with pytest.raises(Exception):
            entry.transition_reason = "mutated"  # type: ignore


class TestAuditTrailWriterAppend:
    def test_append_new_entry(self):
        writer = AuditTrailWriter()
        entry = _make_entry()
        writer.append(entry)
        assert writer.count("sess_abcd1234") == 1

    def test_duplicate_entry_id_raises_immutability_error(self):
        writer = AuditTrailWriter()
        entry = _make_entry(entry_id="evt_abcd1234")
        writer.append(entry)
        duplicate = _make_entry(entry_id="evt_abcd1234")  # same ID, same session
        with pytest.raises(ImmutabilityViolationError):
            writer.append(duplicate)

    def test_different_sessions_do_not_conflict(self):
        """Same entry_id in different sessions must NOT raise."""
        writer = AuditTrailWriter()
        writer.append(_make_entry(entry_id="evt_abcd1234", session_id="sess_aaaa0001"))
        writer.append(_make_entry(entry_id="evt_abcd1234", session_id="sess_bbbb0002"))
        assert writer.count("sess_aaaa0001") == 1
        assert writer.count("sess_bbbb0002") == 1


class TestAuditTrailWriterRead:
    def test_read_trail_returns_entries_in_insertion_order(self):
        writer = AuditTrailWriter()
        for i in range(3):
            writer.append(_make_entry(entry_id=f"evt_000000{i:02d}"))
        trail = writer.read_trail("sess_abcd1234")
        assert len(trail) == 3
        assert [e.entry_id for e in trail] == ["evt_00000000", "evt_00000001", "evt_00000002"]

    def test_read_trail_empty_session_returns_empty_list(self):
        writer = AuditTrailWriter()
        assert writer.read_trail("sess_nonexist") == []

    def test_read_trail_returns_copy(self):
        """Modifying the returned list must not affect the internal store."""
        writer = AuditTrailWriter()
        writer.append(_make_entry())
        trail = writer.read_trail("sess_abcd1234")
        trail.clear()
        assert writer.count("sess_abcd1234") == 1


class TestAuditTrailWriterFilter:
    def test_find_by_event_type(self):
        writer = AuditTrailWriter()
        writer.append(_make_entry(entry_id="evt_00000001", event_type=AuditEventType.STATE_ENTERED))
        writer.append(_make_entry(entry_id="evt_00000002", event_type=AuditEventType.STATE_EXITED))
        writer.append(_make_entry(entry_id="evt_00000003", event_type=AuditEventType.STATE_ENTERED))

        entered = writer.find_by_event_type("sess_abcd1234", AuditEventType.STATE_ENTERED)
        assert len(entered) == 2

        exited = writer.find_by_event_type("sess_abcd1234", AuditEventType.STATE_EXITED)
        assert len(exited) == 1

    def test_find_by_event_type_returns_empty_when_none_match(self):
        writer = AuditTrailWriter()
        writer.append(_make_entry(entry_id="evt_00000001", event_type=AuditEventType.STATE_ENTERED))
        result = writer.find_by_event_type("sess_abcd1234", AuditEventType.CHECKPOINT_CREATED)
        assert result == []


class TestAuditTrailAllEventTypes:
    def test_all_event_types_accepted(self):
        """Every AuditEventType must be accepted by append() without error."""
        writer = AuditTrailWriter()
        for i, event_type in enumerate(AuditEventType):
            entry = _make_entry(
                entry_id=f"evt_{i:08x}",
                event_type=event_type,
            )
            writer.append(entry)  # Must not raise
        assert writer.count("sess_abcd1234") == 22
