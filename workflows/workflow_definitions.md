# Workflow Definitions: GrowthScout AI

This document outlines the workflow routing mechanisms, execution logic, node topologies, and validation rules used by the GrowthScout AI Orchestrator.

---

## 1. Node Topology Catalog

The orchestration framework supports four distinct node execution topologies:

1.  **System Nodes**: Executed directly by the host runtime (e.g., initializing state dictionaries, applying session tokens, and saving checkpoint timestamps).
2.  **Agent Nodes**: Invokes a single ADK agent. Inputs and outputs are mapped to the global state.
3.  **Agent Iterator Nodes (Parallel Map)**: Spawns parallel execution runs of a target agent across an array of inputs. In GrowthScout AI, this is used by the `Website Analysis Agent` to batch-crawls multiple domains simultaneously.
4.  **HITL Gate Nodes**: Suspends execution and waits for client webhook interactions before releasing the execution thread.

---

## 2. Conditional Routing Syntax rules
All workflow nodes define a `transitions` array containing conditional expressions. Transition conditions must resolve to a boolean value. Supported evaluators include:

*   `len(state.variable)`: Evaluates the length of list/dict state properties.
*   `state.variable == value`: Basic equivalence matches.
*   `state.variable.property == true/false`: Nested boolean evaluations.

If no transition condition matches, the workflow runtime defaults to the node defined under the `next` parameter.
