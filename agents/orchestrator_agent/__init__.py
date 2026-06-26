# agents/orchestrator_agent/__init__.py
"""
Orchestrator Agent package for GrowthScout AI.

Exports the ADK LlmAgent instance (`agent`) and the core coordination
class (`GrowthScoutOrchestrator`) for use by test suites and future
runner scripts.
"""
import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from .agent import agent, GrowthScoutOrchestrator, OrchestratorDependencies

__all__ = [
    "agent",
    "GrowthScoutOrchestrator",
    "OrchestratorDependencies",
]
