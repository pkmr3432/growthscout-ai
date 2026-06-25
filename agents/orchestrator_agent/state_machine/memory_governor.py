# agents/orchestrator_agent/state_machine/memory_governor.py
"""
Advisory memory governance for the GrowthScout AI Orchestrator.

Ownership: orchestrator_agent (sole authority for committing memory writes)

MemoryGovernor is a side-effect-free validator.
It NEVER:
  - raises exceptions for permission failures
  - terminates workflows
  - mutates WorkflowContext
  - writes memory
  - publishes events

It evaluates whether a proposed memory operation is authorized per the
access control matrix in memory_bank_config.yaml and returns a MemoryDecision.
The orchestrator (agent.py) decides how to respond to denied operations.

Invariants:
  - MemoryDecision.allowed=False means the orchestrator must handle the denial
    (typically by emitting a VALIDATION_FAILED event and transitioning to FAILED).
  - append_only_immutable policy: the audit_history domain only accepts appends.
  - MemoryGovernor is stateless; the access matrix is read-only at construction.
"""
from __future__ import annotations

import os
from typing import Dict, List, Literal, Optional

import yaml
from pydantic import BaseModel, Field

# ─── Access Matrix (loaded from memory_bank_config.yaml) ─────────────────────

# Canonical domain names as defined in memory_bank_config.yaml
_ALL_DOMAINS = frozenset({
    "session_memory",
    "business_profiles",
    "audit_history",
    "opportunity_history",
    "competitor_snapshots",
    "growth_reports",
    "human_notes",
})

# Domains that enforce append-only immutability per workflow_routing.yaml
_APPEND_ONLY_DOMAINS = frozenset({"audit_history"})

# Fallback access matrix (mirrors memory_bank_config.yaml agent_access block)
# Used when the config file cannot be parsed at runtime.
_FALLBACK_ACCESS_MATRIX: Dict[str, Dict[str, List[str]]] = {
    "orchestrator_agent": {
        "read": ["session_memory", "human_notes"],
        "write": ["session_memory", "human_notes"],
    },
    "business_discovery_agent": {
        "read": ["session_memory", "business_profiles"],
        "write": ["business_profiles"],
    },
    "website_analysis_agent": {
        "read": ["session_memory", "business_profiles"],
        "write": ["audit_history"],
    },
    "opportunity_agent": {
        "read": ["business_profiles", "audit_history", "competitor_snapshots"],
        "write": ["opportunity_history", "competitor_snapshots"],
    },
    "growth_intelligence_agent": {
        "read": [
            "business_profiles",
            "audit_history",
            "competitor_snapshots",
            "opportunity_history",
        ],
        "write": ["growth_reports"],
    },
}


def _load_access_matrix() -> Dict[str, Dict[str, List[str]]]:
    """
    Load the agent_access block from memory_bank_config.yaml.
    Falls back to the hardcoded matrix if the file is unavailable.
    """
    try:
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "memory", "memory_bank_config.yaml"
        )
        config_path = os.path.normpath(config_path)
        with open(config_path, "r") as f:
            raw = yaml.safe_load(f)
        return raw["memory_bank"]["agent_access"]
    except Exception:
        return _FALLBACK_ACCESS_MATRIX


# ─── MemoryDecision ───────────────────────────────────────────────────────────

class MemoryDecision(BaseModel):
    """
    Advisory result from MemoryGovernor.evaluate_write() or evaluate_read().

    Inputs:  (returned by MemoryGovernor)
    Outputs:
      allowed:              True when the operation is authorized
      denied_reason:        Explanation for denial (None when allowed)
      target_memory_domain: Domain the operation was evaluated against
      requested_operation:  "write" or "read"
      governance_notes:     Advisory notes (can be non-empty even when allowed)
    """
    model_config = {"frozen": True}

    allowed: bool = Field(..., description="True when the operation is authorized.")
    denied_reason: Optional[str] = Field(
        None,
        description="Human-readable explanation for denied operations.",
    )
    target_memory_domain: str = Field(..., description="Domain evaluated.")
    requested_operation: Literal["write", "read"] = Field(
        ..., description="Operation type evaluated."
    )
    governance_notes: List[str] = Field(
        default_factory=list,
        description="Advisory notes about the evaluation (non-empty even when allowed).",
    )


# ─── MemoryGovernor ───────────────────────────────────────────────────────────

class MemoryGovernor:
    """
    Advisory memory access controller.

    Ownership: injected into orchestrator agent.py as a dependency.
    Inputs:    requesting_agent, target_domain, operation, keys
    Outputs:   MemoryDecision (never raises, never terminates workflow)

    The access matrix is loaded from memory_bank_config.yaml at construction.
    If the config is unavailable, the hardcoded fallback matrix is used.

    Invariants:
      - Stateless after construction (matrix is read-only).
      - Never raises exceptions for authorization failures.
      - Append-only enforcement: "audit_history" write operations are only
        allowed when policy is "append_only_immutable".
    """

    def __init__(self) -> None:
        self._matrix = _load_access_matrix()

    def evaluate_write(
        self,
        requesting_agent: str,
        target_domain: str,
        keys: Optional[List[str]] = None,
        policy: str = "overwrite",
    ) -> MemoryDecision:
        """
        Evaluate whether requesting_agent may write to target_domain.

        Args:
          requesting_agent: Agent name requesting the write.
          target_domain:    Canonical memory domain name.
          keys:             Keys to be written (informational).
          policy:           Write policy (overwrite / append / append_only_immutable).

        Returns:
          MemoryDecision with allowed=True/False and governance_notes.
        """
        notes: List[str] = []

        # Check if domain is known
        if target_domain not in _ALL_DOMAINS:
            return MemoryDecision(
                allowed=False,
                denied_reason=f"Unknown memory domain '{target_domain}'. "
                              f"Must be one of: {sorted(_ALL_DOMAINS)}",
                target_memory_domain=target_domain,
                requested_operation="write",
                governance_notes=[],
            )

        # Check agent has write access to this domain
        agent_access = self._matrix.get(requesting_agent, {})
        write_domains = agent_access.get("write", [])

        if target_domain not in write_domains:
            return MemoryDecision(
                allowed=False,
                denied_reason=(
                    f"Agent '{requesting_agent}' is not authorised to write to "
                    f"'{target_domain}'. Authorised write domains: {write_domains}"
                ),
                target_memory_domain=target_domain,
                requested_operation="write",
                governance_notes=[],
            )

        # Enforce append-only policy for immutable domains
        if target_domain in _APPEND_ONLY_DOMAINS:
            if policy != "append_only_immutable":
                return MemoryDecision(
                    allowed=False,
                    denied_reason=(
                        f"Domain '{target_domain}' is append-only-immutable. "
                        f"Received policy '{policy}' — must be 'append_only_immutable'."
                    ),
                    target_memory_domain=target_domain,
                    requested_operation="write",
                    governance_notes=["Domain enforces append_only_immutable policy."],
                )
            notes.append(
                f"Write to '{target_domain}' approved under append_only_immutable policy."
            )

        if not notes:
            notes.append(
                f"Write to '{target_domain}' by '{requesting_agent}' is authorised."
            )

        return MemoryDecision(
            allowed=True,
            denied_reason=None,
            target_memory_domain=target_domain,
            requested_operation="write",
            governance_notes=notes,
        )

    def evaluate_read(
        self,
        requesting_agent: str,
        source_domain: str,
    ) -> MemoryDecision:
        """
        Evaluate whether requesting_agent may read from source_domain.

        Args:
          requesting_agent: Agent name requesting the read.
          source_domain:    Canonical memory domain name.

        Returns:
          MemoryDecision with allowed=True/False and governance_notes.
        """
        notes: List[str] = []

        if source_domain not in _ALL_DOMAINS:
            return MemoryDecision(
                allowed=False,
                denied_reason=f"Unknown memory domain '{source_domain}'. "
                              f"Must be one of: {sorted(_ALL_DOMAINS)}",
                target_memory_domain=source_domain,
                requested_operation="read",
                governance_notes=[],
            )

        agent_access = self._matrix.get(requesting_agent, {})
        read_domains = agent_access.get("read", [])

        if source_domain not in read_domains:
            # Read is restricted — agent not in access list
            return MemoryDecision(
                allowed=False,
                denied_reason=(
                    f"Agent '{requesting_agent}' is not authorised to read from "
                    f"'{source_domain}'. Authorised read domains: {read_domains}"
                ),
                target_memory_domain=source_domain,
                requested_operation="read",
                governance_notes=[],
            )

        notes.append(
            f"Read from '{source_domain}' by '{requesting_agent}' is authorised."
        )
        return MemoryDecision(
            allowed=True,
            denied_reason=None,
            target_memory_domain=source_domain,
            requested_operation="read",
            governance_notes=notes,
        )

    def get_authorised_write_domains(self, agent_name: str) -> List[str]:
        """Return the list of domains the agent may write to."""
        return list(self._matrix.get(agent_name, {}).get("write", []))

    def get_authorised_read_domains(self, agent_name: str) -> List[str]:
        """Return the list of domains the agent may read from."""
        return list(self._matrix.get(agent_name, {}).get("read", []))
