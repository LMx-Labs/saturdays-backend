# ADR-0008: API VERSIONING & BACKWARD COMPATIBILITY PROTOCOL

- **Status**: ACCEPTED  
- **Date**: 2026-07-30  
- **Author**: Chief Architect  
- **Scope**: API Architecture & Interface Standards  

---

# Problem & Context

As the platform expands to mobile applications and multi-city deployments, API contracts will evolve. 

The architecture requires a standardized API versioning protocol to prevent breaking changes for existing client applications.

---

# Options Considered

1. **Option A: Header-Based API Versioning (`Accept: application/vnd.saturdays.v1+json`)**
2. **Option B: Query Parameter Versioning (`/api/orders?version=1`)**
3. **Option C: Explicit URL Path Versioning (`/api/v1/orders`)**

---

# Decision

The platform **MUST** enforce **Explicit URL Path Versioning** (Option C). 

All public and internal REST API routes MUST contain the explicit major version prefix in the URL path:

$$\text{URL Pattern: } \text{/api/v1/\{module\}/\{resource\}}$$

Breaking changes MUST prompt a major version increment (`/api/v2/`), maintaining `/api/v1/` routes until formal sunset dates. Non-breaking additions (optional fields) MUST NOT increment major version paths.

---

# Consequences

## Positive
- Simple, explicit, and easy to route, inspect, cache, and document in OpenAPI schemas.

## Negative / Risks
- Requires maintaining dual router handlers during major version deprecation windows.
