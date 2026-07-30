# SEARCH MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Discovery & Search Engineering Team  

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `SearchQuery`
- **Identifier**: Value Object (Transient Query Parameters)
- **Entities / Value Objects**: `SearchFilter`, `RelevanceRank`
- **Owner Module**: `search` (Exclusive)

## Authoritative Domain Invariants
1. **INV-SRCH-001 (Active Store Filter Enforcement)**: Search results MUST automatically filter out branches where `is_active = FALSE` or where current time falls outside operating hours.

---

# Database Tables & Read-Only Access Model

The `search` module owns NO database tables. It executes optimized SQL queries against:
- `branches` (owned by `branch`)
- `menu_items` (owned by `menu`)
- `brands` (owned by `brand`)

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. GET `/api/v1/search`
- **Owner Module**: `search`
- **Authentication**: `NONE` (Public search endpoint)
- **Authorization**: `PUBLIC`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `400 Bad Request` (Empty query term)
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 100\text{ms}$ (p95)

### 2. GET `/api/v1/search/suggestions`
- **Owner Module**: `search`
- **Authentication**: `NONE`
- **Authorization**: `PUBLIC`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `400 Bad Request`
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 50\text{ms}$ (p95)
