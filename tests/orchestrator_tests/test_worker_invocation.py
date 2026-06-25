# tests/orchestrator_tests/test_worker_invocation.py
"""
Tests: WorkerRegistry and invocation contracts.

Validates:
  - All 4 worker names are registered
  - WorkerNotFoundError raised for unknown names
  - WorkerInvocationRequest validates fields correctly
  - WorkerInvocationResult fields validate correctly
  - Workers cannot be cross-referenced (isolation)
  - RetryPolicy enum members are present
"""
import pytest
from datetime import datetime, timezone

from agents.orchestrator_agent.interfaces.worker_invocation import (
    WorkerRegistry,
    WorkerInvocationRequest,
    WorkerInvocationResult,
    RetryPolicy,
)
from agents.orchestrator_agent.exceptions import WorkerNotFoundError
from agents.shared.schemas import DiscoveryLeadsSchema


# ─── RetryPolicy ──────────────────────────────────────────────────────────────

class TestRetryPolicyEnum:
    def test_all_policies_present(self):
        expected = {"NONE", "FIXED_DELAY", "EXPONENTIAL_BACKOFF"}
        actual = {p.value for p in RetryPolicy}
        assert actual == expected


# ─── WorkerRegistry ───────────────────────────────────────────────────────────

class TestWorkerRegistry:
    def test_registered_names_contains_all_workers(self):
        registry = WorkerRegistry()
        names = registry.registered_names()
        expected = {
            "business_discovery_agent",
            "website_analysis_agent",
            "opportunity_agent",
            "growth_intelligence_agent",
        }
        assert set(names) == expected

    def test_is_registered_true_for_known_worker(self):
        registry = WorkerRegistry()
        assert registry.is_registered("business_discovery_agent") is True

    def test_is_registered_false_for_unknown(self):
        registry = WorkerRegistry()
        assert registry.is_registered("nonexistent_agent") is False

    def test_get_unknown_raises_worker_not_found_error(self):
        registry = WorkerRegistry()
        with pytest.raises(WorkerNotFoundError) as exc_info:
            registry.get("rogue_agent")
        assert "rogue_agent" in str(exc_info.value)

    def test_worker_not_found_error_is_not_key_error(self):
        """Must raise WorkerNotFoundError, not generic KeyError."""
        registry = WorkerRegistry()
        with pytest.raises(WorkerNotFoundError):
            registry.get("unknown")

    def test_worker_isolation_no_cross_reference(self):
        """Each worker can only be retrieved by its own name."""
        registry = WorkerRegistry()
        # Can retrieve individual workers
        for name in registry.registered_names():
            assert registry.is_registered(name)
        # Cannot combine names
        assert not registry.is_registered("business_discovery_agent+website_analysis_agent")


class TestWorkerInvocationRequest:
    def _make_request(self, **overrides) -> WorkerInvocationRequest:
        return WorkerInvocationRequest(
            worker_name=overrides.get("worker_name", "business_discovery_agent"),
            input_payload=overrides.get(
                "input_payload",
                DiscoveryLeadsSchema(leads=[], competitor_candidates=[]),
            ),
            expected_output_schema=overrides.get("expected_output_schema", "DiscoveryLeadsSchema"),
            correlation_id=overrides.get("correlation_id", "corr-test-001"),
            timeout=overrides.get("timeout", 60.0),
            retry_limit=overrides.get("retry_limit", 2),
            execution_deadline=overrides.get("execution_deadline", None),
        )

    def test_valid_request_construction(self):
        req = self._make_request()
        assert req.worker_name == "business_discovery_agent"
        assert req.timeout == 60.0
        assert req.retry_limit == 2
        assert req.retry_policy == RetryPolicy.EXPONENTIAL_BACKOFF

    def test_request_is_frozen(self):
        req = self._make_request()
        with pytest.raises(Exception):
            req.worker_name = "other"  # type: ignore

    def test_timeout_must_be_positive(self):
        with pytest.raises(Exception):
            self._make_request(timeout=0.0)

    def test_retry_limit_cannot_be_negative(self):
        with pytest.raises(Exception):
            self._make_request(retry_limit=-1)

    def test_execution_deadline_optional(self):
        req = self._make_request()
        assert req.execution_deadline is None

    def test_execution_deadline_can_be_set(self):
        req = self._make_request(execution_deadline=datetime.now(timezone.utc))
        assert req.execution_deadline is not None


class TestWorkerInvocationResult:
    def test_successful_result(self):
        result = WorkerInvocationResult(
            worker_name="business_discovery_agent",
            correlation_id="corr-001",
            success=True,
            output=DiscoveryLeadsSchema(leads=[], competitor_candidates=[]),
            error_message=None,
            execution_duration_ms=250.0,
            retries_attempted=0,
        )
        assert result.success is True
        assert result.output is not None
        assert result.error_message is None

    def test_failed_result(self):
        result = WorkerInvocationResult(
            worker_name="website_analysis_agent",
            correlation_id="corr-002",
            success=False,
            output=None,
            error_message="Timeout after 60 seconds.",
            execution_duration_ms=60000.0,
            retries_attempted=2,
        )
        assert result.success is False
        assert result.output is None
        assert "Timeout" in result.error_message

    def test_result_is_frozen(self):
        result = WorkerInvocationResult(
            worker_name="opportunity_agent",
            correlation_id="corr-003",
            success=True,
            output=None,
            error_message=None,
            execution_duration_ms=100.0,
            retries_attempted=0,
        )
        with pytest.raises(Exception):
            result.worker_name = "mutated"  # type: ignore

    def test_duration_cannot_be_negative(self):
        with pytest.raises(Exception):
            WorkerInvocationResult(
                worker_name="opportunity_agent",
                correlation_id="corr-003",
                success=True,
                output=None,
                error_message=None,
                execution_duration_ms=-1.0,
                retries_attempted=0,
            )
