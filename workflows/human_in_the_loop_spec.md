# Human-in-the-Loop (HITL) Specification: GrowthScout AI

This specification defines the validation states, approval rules, feedback models, and timeout gates for human checkpoints in the GrowthScout AI pipeline.

---

## 1. Approval Gateway States
The HITL checkpoint operates on the `awaiting_approval` state node. When reached:
*   **State Block**: The Orchestrator halts execution. It serializes session state and pauses CPU/LLM execution turns.
*   **Websocket Event**: A websocket notification is emitted to the gateway:
    ```json
    {
      "event": "session_awaiting_approval",
      "session_id": "sess_89a0c102",
      "proposal_drafts": "# Proposal for..."
    }
    ```

---

## 2. Callback Payload Schema
The human reviewer interacts with the state machine by posting an approval payload to the REST endpoint `/api/v1/sessions/{session_id}/approve`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ApprovalCallbackPayload",
  "type": "object",
  "required": ["approved"],
  "properties": {
    "approved": {
      "type": "boolean",
      "description": "True to transition to completed. False routes back to REPORT_GENERATION for regeneration."
    },
    "feedback": {
      "type": "string",
      "maxLength": 1000,
      "description": "Instruction notes to guide prompt regeneration if approved is false."
    }
  }
}
```

---

## 3. Transition and Regeneration Rules
*   **Approval (True)**: The orchestrator parses the callback, updates `state.hitl_approval_status = {"approved": true}`, saves the record to Firestore, and transitions to `COMPLETED`.
*   **Rejection (False)**: If rejected with feedback:
    1.  The orchestrator appends the feedback to `state.query_context.user_feedback` or `human_notes.reviewer_feedback`.
    2.  Sets the next node to `REPORT_GENERATION`.
    3.  Wakes up the Growth Intelligence Agent, supplying both the opportunities metadata and the new feedback block to compile a refined report draft.

---

## 4. Timeout and Expiry Rules
*   **Session Suspension**: A session can remain in the `awaiting_approval` state for up to **7 days**.
*   **Auto-Expiry**: If no callback payload is received within 7 days, the session status is automatically marked as `failed` with the resolution code `approval_timeout`. The associated database lock is released.
