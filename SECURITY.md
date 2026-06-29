# Security Policy & Vulnerability Disclosure

This document outlines the security policies, update guidelines, vulnerability reporting protocols, and dependency patching schedules for GrowthScout AI.

---

## 1. Supported Versions

Only the active stable release and release candidate branches receive security patches:

| Version | Supported | Security Updates |
|:---|:---:|:---|
| **v1.0.0-rc1** | Yes | Active (All reported bugs fixed immediately) |
| **v0.x.y** | No | None (Operators must upgrade to v1.0.x) |

---

## 2. Reporting a Vulnerability

We take the security of our platform seriously. If you discover a vulnerability, please report it immediately:

1.  **Do not open a public GitHub issue**. Reports should be handled confidentially to prevent exploit dispersion.
2.  Email your detailed report to **security@growthscout.ai**.
3.  Include a proof of concept (PoC), steps to reproduce, and impact details.
4.  If reporting critical access leaks, please encrypt the email payload using our GPG public key.

---

## 3. Vulnerability Response Timeline

Upon receiving a report:
- **Triage**: Security maintainers will triage and confirm the report within **24 hours**.
- **Fix Preparation**: A private security patch will be prepared inside an isolated workspace.
- **Disclosure**: Remediation updates will be pushed to the stable branches within **7 days** for critical leaks, and a public advisory (CVE) will be generated.
- **Auto-Update**: Client SDK versions will be tagged with a patch increment (e.g. `v1.0.1`), triggering automated builds.
