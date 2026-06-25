# tests/orchestrator_tests/test_state_machine.py
"""
Tests: Workflow state topology (states.py).

Validates:
  - WorkflowState enum completeness (11 states)
  - StateType enum members
  - EvidenceRequirement enum members (5 tokens)
  - WORKFLOW_TOPOLOGY covers every WorkflowState
  - TERMINAL_STATES and ACTIVE_STATES are disjoint and complete
  - Terminal states have no allowed_transitions
  - Active states have at least one allowed_transition
  - StateNode fields are fully populated
"""
import pytest

from agents.orchestrator_agent.state_machine.states import (
    WorkflowState,
    StateType,
    EvidenceRequirement,
    StateNode,
    WORKFLOW_TOPOLOGY,
    TERMINAL_STATES,
    ACTIVE_STATES,
)


class TestWorkflowStateEnum:
    EXPECTED_ACTIVE = {
        "IDLE", "DISCOVERING", "LEAD_PARTITIONING", "AUDITING",
        "OPPORTUNITY_ANALYSIS", "REPORT_GENERATION", "AWAITING_APPROVAL",
    }
    EXPECTED_TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "NO_LEADS_FOUND"}

    def test_all_active_states_present(self):
        actual = {s.value for s in WorkflowState} - {s.value for s in TERMINAL_STATES}
        assert actual == self.EXPECTED_ACTIVE

    def test_all_terminal_states_present(self):
        actual = {s.value for s in TERMINAL_STATES}
        assert actual == self.EXPECTED_TERMINAL

    def test_total_state_count(self):
        assert len(list(WorkflowState)) == 11


class TestStateTypeEnum:
    def test_all_types_present(self):
        expected = {"start", "agent_node", "partition_node", "hitl_gate", "end_node"}
        actual = {s.value for s in StateType}
        assert actual == expected


class TestEvidenceRequirementEnum:
    def test_all_requirements_present(self):
        expected = {
            "DISCOVERY_REQUIRED",
            "AUDIT_REQUIRED",
            "SEO_REQUIRED",
            "COMPETITOR_REQUIRED",
            "REPORT_REQUIRED",
        }
        actual = {r.value for r in EvidenceRequirement}
        assert actual == expected

    def test_requirement_count(self):
        assert len(list(EvidenceRequirement)) == 5


class TestWorkflowTopology:
    def test_topology_covers_all_states(self):
        for state in WorkflowState:
            assert state in WORKFLOW_TOPOLOGY, f"WORKFLOW_TOPOLOGY missing state: {state.value}"

    def test_terminal_states_have_no_transitions(self):
        for state in TERMINAL_STATES:
            node = WORKFLOW_TOPOLOGY[state]
            assert node.allowed_transitions == [], (
                f"Terminal state {state.value} must have no allowed transitions."
            )

    def test_active_states_have_transitions(self):
        for state in ACTIVE_STATES:
            node = WORKFLOW_TOPOLOGY[state]
            assert len(node.allowed_transitions) > 0, (
                f"Active state {state.value} must have at least one allowed transition."
            )

    def test_terminal_states_are_end_nodes(self):
        for state in TERMINAL_STATES:
            node = WORKFLOW_TOPOLOGY[state]
            assert node.state_type == StateType.END_NODE

    def test_idle_is_start_node(self):
        assert WORKFLOW_TOPOLOGY[WorkflowState.IDLE].state_type == StateType.START

    def test_discovering_is_agent_node(self):
        node = WORKFLOW_TOPOLOGY[WorkflowState.DISCOVERING]
        assert node.state_type == StateType.AGENT_NODE
        assert node.owner_agent == "business_discovery_agent"

    def test_lead_partitioning_has_no_owner_agent(self):
        """LEAD_PARTITIONING is executed by the orchestrator, not a worker."""
        node = WORKFLOW_TOPOLOGY[WorkflowState.LEAD_PARTITIONING]
        assert node.state_type == StateType.PARTITION_NODE
        assert node.owner_agent is None

    def test_opportunity_analysis_requires_discovery_and_audit(self):
        node = WORKFLOW_TOPOLOGY[WorkflowState.OPPORTUNITY_ANALYSIS]
        reqs = node.required_evidence
        assert EvidenceRequirement.DISCOVERY_REQUIRED in reqs
        assert EvidenceRequirement.AUDIT_REQUIRED in reqs

    def test_awaiting_approval_requires_report(self):
        node = WORKFLOW_TOPOLOGY[WorkflowState.AWAITING_APPROVAL]
        assert EvidenceRequirement.REPORT_REQUIRED in node.required_evidence

    def test_all_transitions_reference_valid_states(self):
        """Every transition target must be a member of WorkflowState."""
        valid_states = set(WorkflowState)
        for state, node in WORKFLOW_TOPOLOGY.items():
            for target in node.allowed_transitions:
                assert target in valid_states


class TestConvenienceSets:
    def test_terminal_and_active_are_disjoint(self):
        assert TERMINAL_STATES.isdisjoint(ACTIVE_STATES)

    def test_terminal_and_active_cover_all_states(self):
        all_states = frozenset(WorkflowState)
        assert TERMINAL_STATES | ACTIVE_STATES == all_states
