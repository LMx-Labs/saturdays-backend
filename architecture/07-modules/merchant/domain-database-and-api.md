# MERCHANT MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Merchant Product & Engineering Team  

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `Merchant`
- **Identifier**: `id` (`UUIDv7`)
- **Entities / Value Objects**: `MerchantKYC`, `BankAccountDetails`
- **Owner Module**: `merchant` (Exclusive)

## Authoritative Domain Invariants
1. **INV-MERCH-001 (Unique Tax ID)**: Every registered merchant MUST have a unique GSTIN / FSSAI license identifier.
2. **INV-MERCH-002 (Verification Required for Payouts)**: Financial payouts MUST NOT be dispatched to a merchant whose account state is not `APPROVED`.

---

# Owned Database Schema (`merchants` Table)

The `merchant` module has exclusive write ownership over `merchants` ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).

```sql
CREATE TABLE merchants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    owner_user_id UUID NOT NULL REFERENCES users(id),
    business_name VARCHAR(150) NOT NULL,
    legal_entity_name VARCHAR(150) NOT NULL,
    gstin VARCHAR(20) NULL,
    fssai_license_number VARCHAR(30) NOT NULL,
    bank_account_number VARCHAR(50) NULL,
    bank_ifsc_code VARCHAR(20) NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT', -- DRAFT, PENDING_VERIFICATION, APPROVED, SUSPENDED
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE NULL
);
```

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. GET `/api/v1/merchants/me`
- **Owner Module**: `merchant`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `MerchantOwner`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `401 Unauthorized`, `404 Not Found`
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 50\text{ms}$ (p95)

### 2. POST `/api/v1/merchants/onboard`
- **Owner Module**: `merchant`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `MerchantOwner`
- **Idempotency**: `NON_IDEMPOTENT`
- **Transaction Scope**: `READ_WRITE_SINGLE`
- **Failure Modes**: `400 Bad Request` (Invalid FSSAI format), `409 Conflict` (Duplicate GSTIN)
- **Retry Behavior**: `DO_NOT_RETRY`
- **Expected Latency Target**: $< 150\text{ms}$ (p95)
