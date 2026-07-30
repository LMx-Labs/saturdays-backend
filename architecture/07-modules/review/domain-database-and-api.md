# REVIEW MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Customer Experience & Reviews Engineering Team  

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `Review`
- **Identifier**: `id` (`UUIDv7`)
- **Entities / Value Objects**: `ReviewRating`, `ModerationStatus`
- **Owner Module**: `review` (Exclusive)

## Authoritative Domain Invariants
1. **INV-0007 (Verified Order Requirement)**: A `Customer` MAY submit a review for a `Branch` ONLY if they have a `COMPLETED` order for that branch (`order_id`).
2. **INV-REV-001 (Rating Range)**: `rating` MUST be an integer between 1 and 5 inclusive.

---

# Owned Database Schema (`reviews` Table)

The `review` module has exclusive write ownership over `reviews` ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).

```sql
CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    order_id UUID NOT NULL UNIQUE REFERENCES orders(id),
    customer_profile_id UUID NOT NULL REFERENCES customer_profiles(id),
    branch_id UUID NOT NULL REFERENCES branches(id),
    rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT NULL,
    merchant_reply TEXT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE NULL
);
```

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. GET `/api/v1/branches/{branch_id}/reviews`
- **Owner Module**: `review`
- **Authentication**: `NONE` (Public endpoint)
- **Authorization**: `PUBLIC`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `404 Not Found`
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 50\text{ms}$ (p95)

### 2. POST `/api/v1/reviews`
- **Owner Module**: `review`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `Customer`
- **Idempotency**: `NON_IDEMPOTENT`
- **Transaction Scope**: `READ_WRITE_SINGLE`
- **Failure Modes**: `400 Bad Request` (Order not completed or already reviewed), `401 Unauthorized`
- **Retry Behavior**: `DO_NOT_RETRY`
- **Expected Latency Target**: $< 100\text{ms}$ (p95)
