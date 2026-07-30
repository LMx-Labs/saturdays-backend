# KITCHEN MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Kitchen & Dispatch Engineering Team  

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `Kitchen`
- **Identifier**: `id` (`UUIDv7`)
- **Entities / Value Objects**: `KitchenStation`, `PreparationQueue`
- **Owner Module**: `kitchen` (Exclusive)

## Authoritative Domain Invariants
1. **INV-KITCH-001 (Valid Branch Parent)**: Every `Kitchen` MUST belong to a valid `Branch` entity (`branch_id`).

---

# Owned Database Schema (`kitchens` Table)

The `kitchen` module has exclusive write ownership over `kitchens` ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).

```sql
CREATE TABLE kitchens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    name VARCHAR(150) NOT NULL DEFAULT 'Main Kitchen',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE NULL
);

CREATE INDEX idx_kitchens_branch_id ON kitchens(branch_id) WHERE deleted_at IS NULL;
```

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. GET `/api/v1/branches/{branch_id}/kitchens`
- **Owner Module**: `kitchen`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `KitchenStaff`, `BranchManager`, or `MerchantOwner`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `401 Unauthorized`, `403 Forbidden`, `404 Not Found`
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 50\text{ms}$ (p95)

### 2. POST `/api/v1/kitchens`
- **Owner Module**: `kitchen`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `BranchManager` or `MerchantOwner`
- **Idempotency**: `NON_IDEMPOTENT`
- **Transaction Scope**: `READ_WRITE_SINGLE`
- **Failure Modes**: `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`
- **Retry Behavior**: `DO_NOT_RETRY`
- **Expected Latency Target**: $< 100\text{ms}$ (p95)
