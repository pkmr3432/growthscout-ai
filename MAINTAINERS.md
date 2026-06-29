# Project Maintainers & CODEOWNERS

This document registers the active maintainers of GrowthScout AI and outlines the review standards required for code contributions.

---

## 1. List of Active Maintainers

| Name | Role | GitHub Handle | Specialty |
|:---|:---|:---|:---|
| **Alex Chen** | Platform Architect | `@achen-gs` | Gateway & Workflows Runtime |
| **Sarah Jenkins** | Security Lead | `@sjenkins-gs` | Supply Chain & Infrastructure |
| **Kenji Takahashi**| SDK Developer | `@ktakahashi-gs` | Python & TypeScript client modules |

---

## 2. Review Guidelines & Standards

All code contributions must be reviewed and approved by at least **one** maintainer:

- **Strict Isolation Constraints**: Modifications to the feature-frozen backend (`orchestrator/`, `workers/`, `mcp/`) are strictly blocked.
- **OpenAPI Alignment**: PRs touching `service/api/` must run compatibility testing. Breaking changes to schemas will be rejected automatically.
- **Code Formatting Check**: Python scripts must be formatted with `black` and comply with `flake8` styles. TS scripts must pass type-check bundle tests.
- **Test Integrity**: Every feature modification must include corresponding test suites maintaining 100% service test coverage.
