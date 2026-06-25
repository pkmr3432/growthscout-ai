# agents/orchestrator_agent/__init__.py
"""
Orchestrator Agent package for GrowthScout AI.

Exports the ADK LlmAgent instance (`agent`) and the core coordination
class (`GrowthScoutOrchestrator`) for use by test suites and future
runner scripts.
"""
from .agent import agent, GrowthScoutOrchestrator, OrchestratorDependencies

__all__ = [
    "agent",
    "GrowthScoutOrchestrator",
    "OrchestratorDependencies",
]
