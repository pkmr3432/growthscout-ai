# agents/orchestrator_agent/hooks/__init__.py
"""
Hooks package for the GrowthScout AI Orchestrator Agent.

Exports the evidence validation hook and the immutable audit trail writer.
Both components are pure — they never mutate WorkflowContext.
"""
from .evidence_validator import (
    EvidenceValidationHook,
    EvidenceValidationResult,
)
from .audit_trail import (
    AuditTrailWriter,
    AuditTrailEntry,
    AuditEventType,
)

__all__ = [
    "EvidenceValidationHook",
    "EvidenceValidationResult",
    "AuditTrailWriter",
    "AuditTrailEntry",
    "AuditEventType",
]
