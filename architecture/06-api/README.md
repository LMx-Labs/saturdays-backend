# 06-API — REST & SECURITY ARCHITECTURE SPECIFICATIONS

Version: 1.0  
Status: Authoritative API Architecture Specification Index  
Owner: Chief Architect & API Engineering Lead  

---

# Purpose

The `06-api/` directory defines the REST API standards, URL versioning conventions, authentication header parsing, Role-Based Access Control (RBAC) matrices, standard error payload schemas, pagination standards, and rate-limiting enforcement for Saturdays and DineGuru.

---

# Consolidated Specifications Index

1. [api-design-and-authentication.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/06-api/api-design-and-authentication.md)
   * **REST Design Standards**: Resource naming, HTTP verbs, JSON snake_case conventions, and URL major path versioning (`/api/v1/`).
   * **Authentication Headers**: JWT Bearer token processing (`Authorization: Bearer <token>`), OAuth 2.0 callbacks, and token lifetimes.
   * **Mandatory Per-Endpoint Attributes**: Endpoint specification standards (owner module, authentication, authorization, idempotency, transaction boundaries, failure modes, retry behavior, latency targets).
2. [authorization-errors-and-rate-limiting.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/06-api/authorization-errors-and-rate-limiting.md)
   * **RBAC Role Matrix**: System-wide permission grid (`Customer`, `BranchManager`, `MerchantOwner`, `PlatformAdmin`).
   * **Standard Error Payloads**: Structured error JSON responses, HTTP status mapping, and correlation ID tracking.
   * **Pagination, Filtering & Rate Limiting**: Cursor pagination guidelines, query parameters, and IP/User rate limits.

---

# Dependencies

- [04-backend/fastapi-architecture-and-layering.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/04-backend/fastapi-architecture-and-layering.md) — FastAPI router layering and exception handlers.
- [05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md) — Primary key UUIDv7 routing parameters.
- [14-adrs/ADR-0004](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0004-multi-tenant-authentication-identity-strategy.md) — JWT & OAuth identity strategy.
- [14-adrs/ADR-0008](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0008-api-versioning-and-backward-compatibility.md) — URL path API versioning.
