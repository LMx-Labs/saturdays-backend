# CUSTOMER MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Customer Product & Engineering Team  

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `CustomerProfile`
- **Identifier**: `id` (`UUIDv7`)
- **Entities / Value Objects**: `CustomerAddress`, `CustomerFavorite`
- **Owner Module**: `customer` (Exclusive)

## Authoritative Domain Invariants
1. **INV-CUST-001 (Strict 1:1 User Mapping)**: A `CustomerProfile` MUST map to exactly one `User` entity (`user_id`).
2. **INV-CUST-002 (Primary Address Constraint)**: A customer MAY have multiple saved addresses, but MUST have exactly one address flagged `is_primary = TRUE`.
3. **INV-CUST-003 (Favorite Uniqueness)**: A customer MAY favorite a branch only once (`UNIQUE(customer_profile_id, branch_id)`).

---

# Owned Database Schemas

The `customer` module has exclusive write ownership over `customer_profiles`, `customer_addresses`, and `customer_favorites` ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).

```sql
CREATE TABLE customer_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id),
    full_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(20) NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE NULL
);

CREATE TABLE customer_addresses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    customer_profile_id UUID NOT NULL REFERENCES customer_profiles(id),
    address_line VARCHAR(255) NOT NULL,
    building_name VARCHAR(100) NULL,
    campus_zone VARCHAR(100) NOT NULL, -- e.g. "VIT Men's Hostel Phase 1"
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE NULL
);

CREATE TABLE customer_favorites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    customer_profile_id UUID NOT NULL REFERENCES customer_profiles(id),
    branch_id UUID NOT NULL REFERENCES branches(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(customer_profile_id, branch_id)
);
```

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. GET `/api/v1/customers/me`
- **Owner Module**: `customer`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `Customer`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `401 Unauthorized`, `404 Not Found`
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 50\text{ms}$ (p95)

### 2. PUT `/api/v1/customers/me`
- **Owner Module**: `customer`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `Customer`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_WRITE_SINGLE`
- **Failure Modes**: `400 Bad Request` (Validation error), `401 Unauthorized`
- **Retry Behavior**: `RETRY_WITH_EXPONENTIAL_BACKOFF`
- **Expected Latency Target**: $< 100\text{ms}$ (p95)

### 3. POST `/api/v1/customers/me/addresses`
- **Owner Module**: `customer`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `Customer`
- **Idempotency**: `NON_IDEMPOTENT`
- **Transaction Scope**: `READ_WRITE_ATOMIC_MULTITABLE` (Updates previous primary address if `is_primary=TRUE`)
- **Failure Modes**: `400 Bad Request`, `401 Unauthorized`
- **Retry Behavior**: `DO_NOT_RETRY`
- **Expected Latency Target**: $< 120\text{ms}$ (p95)
