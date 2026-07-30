# BRAND MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Catalog & Merchant Engineering Team  

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `Brand`
- **Identifier**: `id` (`UUIDv7`)
- **Entities / Value Objects**: `BrandMetadata`, `BrandAssets`
- **Owner Module**: `brand` (Exclusive)

## Authoritative Domain Invariants
1. **INV-BRAND-001 (Valid Merchant Parent)**: Every `Brand` MUST belong to a valid `Merchant` entity (`merchant_id`).

---

# Owned Database Schema (`brands` Table)

The `brand` module has exclusive write ownership over `brands` ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).

```sql
CREATE TABLE brands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    merchant_id UUID NOT NULL REFERENCES merchants(id),
    name VARCHAR(100) NOT NULL,
    logo_url VARCHAR(255) NULL,
    banner_url VARCHAR(255) NULL,
    description TEXT NULL,
    cuisine_types VARCHAR(255)[] NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE NULL
);

CREATE INDEX idx_brands_merchant_id ON brands(merchant_id) WHERE deleted_at IS NULL;
```

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. GET `/api/v1/brands`
- **Owner Module**: `brand`
- **Authentication**: `NONE` (Public endpoint for customer catalog)
- **Authorization**: `PUBLIC`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `400 Bad Request`
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 50\text{ms}$ (p95)

### 2. POST `/api/v1/brands`
- **Owner Module**: `brand`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `MerchantOwner`
- **Idempotency**: `NON_IDEMPOTENT`
- **Transaction Scope**: `READ_WRITE_SINGLE`
- **Failure Modes**: `400 Bad Request`, `401 Unauthorized`
- **Retry Behavior**: `DO_NOT_RETRY`
- **Expected Latency Target**: $< 100\text{ms}$ (p95)
