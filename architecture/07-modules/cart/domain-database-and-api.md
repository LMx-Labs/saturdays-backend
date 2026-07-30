# CART MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Checkout & Ordering Engineering Team  

---

# Transient Cart State Purge Policy Resolution

## RESOLUTION SUMMARY: AUTOMATED 7-DAY BACKGROUND PURGE & IMMEDIATE CHECKOUT CLEANUP
Transient cart data MUST be managed according to a strict 2-tier purge policy:
1. **Immediate Post-Checkout Deletion**: When an order is placed, converted cart records (`carts` and `cart_items`) MUST be deleted immediately within the checkout transaction block.
2. **Scheduled 7-Day TTL Cleanup**: Abandoned guest and customer carts older than 7 days (`updated_at < NOW() - INTERVAL '7 days'`) MUST be hard-deleted via a scheduled nightly background cleanup job.

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `Cart`
- **Identifier**: `id` (`UUIDv7`)
- **Entities / Value Objects**: `CartItem`, `CartSummary`
- **Owner Module**: `cart` (Exclusive)

## Authoritative Domain Invariants
1. **INV-CART-001 (Single Branch Constraint)**: A customer cart MUST contain items from exactly ONE `Branch`. Adding an item from a different branch MUST prompt cart clearance or rejection.
2. **INV-CART-002 (Positive Quantity)**: Every item quantity in a cart MUST be greater than 0 (`quantity > 0`).

---

# Owned Database Schemas

The `cart` module has exclusive write ownership over `carts` and `cart_items` ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).

```sql
CREATE TABLE carts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    customer_profile_id UUID NOT NULL REFERENCES customer_profiles(id),
    branch_id UUID NOT NULL REFERENCES branches(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cart_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    cart_id UUID NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
    menu_item_id UUID NOT NULL REFERENCES menu_items(id),
    quantity INT NOT NULL CHECK (quantity > 0),
    selected_modifiers JSONB NULL, -- Array of selected modifier IDs and prices
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. GET `/api/v1/cart`
- **Owner Module**: `cart`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `Customer`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `401 Unauthorized`
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 50\text{ms}$ (p95)

### 2. POST `/api/v1/cart/items`
- **Owner Module**: `cart`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `Customer`
- **Idempotency**: `NON_IDEMPOTENT`
- **Transaction Scope**: `READ_WRITE_SINGLE`
- **Failure Modes**: `400 Bad Request` (Cross-branch item addition conflict), `401 Unauthorized`
- **Retry Behavior**: `DO_NOT_RETRY`
- **Expected Latency Target**: $< 100\text{ms}$ (p95)
