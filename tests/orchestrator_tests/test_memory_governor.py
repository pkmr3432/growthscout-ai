# tests/orchestrator_tests/test_memory_governor.py
"""
Tests: MemoryGovernor advisory access control.

Validates:
  - Authorised writes return allowed=True
  - Unauthorised agent writes return allowed=False with denied_reason
  - audit_history write without append_only_immutable policy is denied
  - audit_history write with correct policy is allowed
  - Unknown domains return allowed=False
  - Read access control mirrors write access control
  - MemoryGovernor never raises for any authorization failure
"""
import pytest

from agents.orchestrator_agent.state_machine.memory_governor import (
    MemoryGovernor,
    MemoryDecision,
)


class TestMemoryGovernorWrites:
    def test_orchestrator_can_write_session_memory(self):
        mg = MemoryGovernor()
        decision = mg.evaluate_write("orchestrator_agent", "session_memory")
        assert decision.allowed is True
        assert decision.denied_reason is None

    def test_discovery_agent_can_write_business_profiles(self):
        mg = MemoryGovernor()
        decision = mg.evaluate_write("business_discovery_agent", "business_profiles")
        assert decision.allowed is True

    def test_analysis_agent_can_write_audit_history_with_correct_policy(self):
        mg = MemoryGovernor()
        decision = mg.evaluate_write(
            "website_analysis_agent", "audit_history", policy="append_only_immutable"
        )
        assert decision.allowed is True

    def test_analysis_agent_cannot_write_audit_history_with_overwrite_policy(self):
        mg = MemoryGovernor()
        decision = mg.evaluate_write(
            "website_analysis_agent", "audit_history", policy="overwrite"
        )
        assert decision.allowed is False
        assert decision.denied_reason is not None
        assert "append_only_immutable" in decision.denied_reason

    def test_orchestrator_cannot_write_business_profiles(self):
        mg = MemoryGovernor()
        decision = mg.evaluate_write("orchestrator_agent", "business_profiles")
        assert decision.allowed is False
        assert decision.denied_reason is not None

    def test_discovery_agent_cannot_write_audit_history(self):
        mg = MemoryGovernor()
        decision = mg.evaluate_write(
            "business_discovery_agent", "audit_history", policy="append_only_immutable"
        )
        assert decision.allowed is False

    def test_opportunity_agent_can_write_opportunity_history(self):
        mg = MemoryGovernor()
        decision = mg.evaluate_write("opportunity_agent", "opportunity_history")
        assert decision.allowed is True

    def test_growth_agent_can_write_growth_reports(self):
        mg = MemoryGovernor()
        decision = mg.evaluate_write("growth_intelligence_agent", "growth_reports")
        assert decision.allowed is True

    def test_unknown_domain_denied(self):
        mg = MemoryGovernor()
        decision = mg.evaluate_write("orchestrator_agent", "unknown_domain")
        assert decision.allowed is False

    def test_unknown_agent_denied(self):
        mg = MemoryGovernor()
        decision = mg.evaluate_write("rogue_agent", "session_memory")
        assert decision.allowed is False


class TestMemoryGovernorReads:
    def test_orchestrator_can_read_session_memory(self):
        mg = MemoryGovernor()
        decision = mg.evaluate_read("orchestrator_agent", "session_memory")
        assert decision.allowed is True

    def test_analysis_agent_can_read_business_profiles(self):
        mg = MemoryGovernor()
        decision = mg.evaluate_read("website_analysis_agent", "business_profiles")
        assert decision.allowed is True

    def test_discovery_agent_cannot_read_audit_history(self):
        """Discovery agent has no read access to audit_history."""
        mg = MemoryGovernor()
        decision = mg.evaluate_read("business_discovery_agent", "audit_history")
        assert decision.allowed is False

    def test_unknown_domain_read_denied(self):
        mg = MemoryGovernor()
        decision = mg.evaluate_read("orchestrator_agent", "ghost_domain")
        assert decision.allowed is False


class TestMemoryGovernorNeverRaises:
    def test_no_exception_on_denied_write(self):
        mg = MemoryGovernor()
        # Must return MemoryDecision, not raise
        decision = mg.evaluate_write("rogue_agent", "growth_reports")
        assert isinstance(decision, MemoryDecision)
        assert decision.allowed is False

    def test_no_exception_on_denied_read(self):
        mg = MemoryGovernor()
        decision = mg.evaluate_read("rogue_agent", "session_memory")
        assert isinstance(decision, MemoryDecision)
        assert decision.allowed is False


class TestMemoryGovernorHelpers:
    def test_get_authorised_write_domains_for_orchestrator(self):
        mg = MemoryGovernor()
        domains = mg.get_authorised_write_domains("orchestrator_agent")
        assert "session_memory" in domains

    def test_get_authorised_read_domains_for_opportunity_agent(self):
        mg = MemoryGovernor()
        domains = mg.get_authorised_read_domains("opportunity_agent")
        assert "audit_history" in domains
        assert "competitor_snapshots" in domains


class TestMemoryDecisionModel:
    def test_allowed_decision_has_no_denied_reason(self):
        mg = MemoryGovernor()
        d = mg.evaluate_write("orchestrator_agent", "session_memory")
        assert d.allowed is True
        assert d.denied_reason is None

    def test_denied_decision_has_denied_reason(self):
        mg = MemoryGovernor()
        d = mg.evaluate_write("rogue_agent", "session_memory")
        assert d.allowed is False
        assert d.denied_reason is not None
        assert len(d.denied_reason) > 0

    def test_governance_notes_present(self):
        mg = MemoryGovernor()
        d = mg.evaluate_write("orchestrator_agent", "session_memory")
        assert isinstance(d.governance_notes, list)
