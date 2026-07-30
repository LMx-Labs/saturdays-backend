# BRANCH MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Store & Location Engineering Team  

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `Branch`
- **Identifier**: `id` (`UUIDv7`)
- **Entities / Value Objects**: `BranchOperatingHours`, `DeliveryZone`
- **Owner Module**: `branch` (Exclusive)

## Authoritative Domain Invariants
1. **INV-0006 (Operating Hours & Status Validation)**: A branch MUST NOT accept orders if `is_active = FALSE` or if current time falls outside configured `opening_time` and `closing_time`.
2. **INV-BRANCH-001 (Valid Brand Parent)**: Every `Branch` MUST belong to a valid `Brand` entity (`brand_id`).

---

# Owned Database Schema (`branches` Table)

The `branch` module has exclusive write ownership over `branches` ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).

```sql
CREATE TABLE branches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    brand_id UUID NOT NULL REFERENCES brands(id),
    name VARCHAR(150) NOT NULL, -- e.g., "Domino's VIT Main Canteen"
    address_text VARCHAR(255) NOT NULL,
    latitude NUMERIC(10, 7) NULL,
    longitude NUMERIC(10, 7) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    opening_time TIME NOT NULL DEFAULT '08:00:00',
    closing_time TIME NOT NULL DEFAULT '23:00:00',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE NULL
);

CREATE INDEX idx_branches_brand_id ON branches(brand_id) WHERE deleted_at IS NULL;
```

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. GET `/api/v1/branches`
- **Owner Module**: `branch`
- **Authentication**: `NONE` (Public customer catalog discovery)
- **Authorization**: `PUBLIC`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `400 Bad Request`
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 60\text{ms}$ (p95)

### 2. PATCH `/api/v1/branches/{id}/status`
- **Owner Module**: `branch`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `BranchManager` or `MerchantOwner`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_WRITE_SINGLE`
- **Failure Modes**: `401 Unauthorized`, `403 Forbidden`, `404 Not Found`
- **Retry Behavior**: `RETRY_WITH_EXPONENTIAL_BACKOFF`
- **Expected Latency Target**: $< 80\text{ms}$ (p95)
