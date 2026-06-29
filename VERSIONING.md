# Semantic Versioning & Deprecation Policy

This document defines the versioning scheme, API mappings boundaries, deprecation life cycles, and compatibility guarantees for GrowthScout AI.

---

## 1. SemVer 2.0 Compliance

All modules, packages, and client SDKs comply strictly with the [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) specification:

```
  v [ Major ] . [ Minor ] . [ Patch ] - [ Pre-release ]
```

- **Major**: Incremented when backward-incompatible API changes occur (e.g. deleting endpoints, altering required fields).
- **Minor**: Incremented when backward-compatible features are added (e.g. new endpoints, optional fields).
- **Patch**: Incremented for backward-compatible bug fixes and security upgrades.
- **Pre-release**: Formatted as `-rcN` for Release Candidates during testing phases.

---

## 2. API Contract Alignment

Client SDK major versions map directly to the corresponding major version of the public REST API endpoints:
- **`growthscout` v1.x.y** ──► consumes **`/api/v1`**
- **`growthscout` v2.x.y** ──► consumes **`/api/v2`**

---

## 3. Deprecation Lifecycle

When an API field or route is marked for deprecation:
1.  **Marking**: Annotate schema elements with `deprecated: true` inside the OpenAPI spec.
2.  **Notification**: The SDK log streams emit deprecation warning logs identifying migration alternatives.
3.  **Active Grace Window**: Deprecated endpoints remain functional and supported for at least **6 months** or **1 full Major release cycle** before final removal.
