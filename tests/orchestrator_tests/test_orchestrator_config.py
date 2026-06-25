# tests/orchestrator_tests/test_orchestrator_config.py
"""
Tests: Orchestrator Agent ADK configuration.

Validates that the orchestrator agent:
  - has the correct name and model from definition.yaml
  - has tools=[] (no direct MCP access)
  - has all three shared policies in its system instruction
  - exposes GrowthScoutOrchestrator and OrchestratorDependencies

No network access, Gemini API, or MCP subprocess is required.
"""
import pytest
from agents.orchestrator_agent.agent import (
    agent,
    GrowthScoutOrchestrator,
    OrchestratorDependencies,
)


class TestOrchestratorLlmAgentConfig:
    """LlmAgent configuration contract tests."""

    def test_agent_name(self):
        assert agent.name == "orchestrator_agent"

    def test_agent_model(self):
        # Must use a production-grade model per definition.yaml
        assert "gemini" in agent.model.lower()

    def test_agent_has_no_tools(self):
        """Orchestrator security boundary: zero direct MCP access."""
        assert len(agent.tools) == 0, (
            "Orchestrator must have tools=[] — it delegates all tool calls to workers."
        )

    def test_agent_instruction_contains_safety_policy(self):
        assert "safety policy" in agent.instruction.lower() or \
               "isolation boundary" in agent.instruction.lower()

    def test_agent_instruction_contains_evidence_policy(self):
        assert "evidence policy" in agent.instruction.lower() or \
               "tool output citations" in agent.instruction.lower()

    def test_agent_instruction_contains_grounding_policy(self):
        assert "grounding policy" in agent.instruction.lower() or \
               "zero invention" in agent.instruction.lower()

    def test_agent_description_is_set(self):
        assert agent.description is not None
        assert len(agent.description) > 0


class TestOrchestratorDependencies:
    """OrchestratorDependencies DI container tests."""

    def test_default_construction(self):
        """All components must be constructable with default factories."""
        deps = OrchestratorDependencies()
        assert deps.transition_controller is not None
        assert deps.memory_governor is not None
        assert deps.worker_registry is not None
        assert deps.evidence_validator is not None
        assert deps.audit_writer is not None
        assert deps.checkpoint_interface is not None
        assert deps.event_publisher is not None
        assert deps.resumability_controller is not None

    def test_resumability_controller_wired_to_checkpoint(self):
        """ResumabilityController must be wired to the same CheckpointInterface."""
        deps = OrchestratorDependencies()
        # ResumabilityController must reference the same CheckpointInterface instance
        assert deps.resumability_controller._checkpoints is deps.checkpoint_interface

    def test_custom_dependencies_accepted(self):
        """DI container must accept injected collaborators."""
        from agents.orchestrator_agent.state_machine.transition_controller import TransitionController
        custom_tc = TransitionController()
        deps = OrchestratorDependencies(transition_controller=custom_tc)
        assert deps.transition_controller is custom_tc


class TestGrowthScoutOrchestrator:
    """GrowthScoutOrchestrator class contract tests."""

    def test_instantiates_from_dependencies(self):
        deps = OrchestratorDependencies()
        orch = GrowthScoutOrchestrator(deps=deps)
        assert orch is not None

    def test_orchestrator_exposes_request_transition(self):
        deps = OrchestratorDependencies()
        orch = GrowthScoutOrchestrator(deps=deps)
        assert callable(orch.request_transition)

    def test_orchestrator_exposes_attempt_resume(self):
        deps = OrchestratorDependencies()
        orch = GrowthScoutOrchestrator(deps=deps)
        assert callable(orch.attempt_resume)
