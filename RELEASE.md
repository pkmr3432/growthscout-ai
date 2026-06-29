# Release Guidelines & Promotion Lifecycle

This document describes the release strategy, branching policies, quality gates, and automated pipelines for GrowthScout AI.

---

## 1. Branching Topology

```
   [ main ]  ◄── (Merge approved Release Candidates)
      ▲
      │
   [ release-v1.0 ]  ◄── (Release stabilization branch)
      ▲
      │
   [ develop ]  ◄── (Integration branch for features)
      ▲
      │
   [ feature/* ]  ◄── (Developer feature branches)
```

- **Branch Protection Rules**:
  - Direct pushes to `main` and `release-*` are blocked.
  - Merges require PR reviews from at least one OWNER, passing lint checks, and passing API contract compatibility tests.

---

## 2. Release Promotion Pipeline

```
  [ PR Merged to develop ]
             │
             ▼
  [ Build Release Candidate (RC) ]
  - Generate temporary tag: vX.Y.Z-rcN
  - Execute full test suite (399+ validation checks)
  - Generate CycloneDX SBOM
  - Scan Docker base images (Trivy/Snyk)
             │
             ▼
  [ Push to Test environments ]
  - Dry-run validation of client SDKs
  - Conduct E2E integration validation
             │
             ▼
  [ Release Promoted to main ]
  - Create release tag: vX.Y.Z
  - Generate artifact checksum digests
  - Publish certified client SDK packages
```

---

## 3. Quality Gates Checklist

To qualify for release promotion, the candidate build must satisfy the following thresholds:
1.  **Unit Tests Pass**: 100% pass rate on all backend (271) and gateway service (122) tests.
2.  **Zero Security Violations**: No critical or high vulnerability warnings in container scanner audits.
3.  **OpenAPI Spec Compatibility**: 100% backward compatible (0 breaking changes relative to the frozen spec contract).
4.  **SDK Synchronization**: Client SDK typed models align with openapi parameters exactly.
