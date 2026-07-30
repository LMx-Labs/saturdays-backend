# COUPON MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Promotions & Marketing Engineering Team  

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `Coupon`
- **Identifier**: `id` (`UUIDv7`)
- **Entities / Value Objects**: `CouponRedemption`, `DiscountRule`
- **Owner Module**: `coupon` (Exclusive)

## Authoritative Domain Invariants
1. **INV-0004 (Immutable Past Financials)**: A coupon MUST NOT modify historical orders or previously calculated commissions.
2. **INV-CPN-001 (Redemption Limit)**: A customer MUST NOT redeem a coupon more than `max_redemptions_per_user`.

---

# Owned Database Schemas

The `coupon` module has exclusive write ownership over `coupons` and `coupon_redemptions` ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).

```sql
CREATE TABLE coupons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    branch_id UUID NULL REFERENCES branches(id), -- Nullable for global campus coupons
    code VARCHAR(50) NOT NULL UNIQUE,
    discount_type VARCHAR(20) NOT NULL, -- "PERCENTAGE", "FLAT"
    discount_value NUMERIC(10, 2) NOT NULL,
    max_discount_amount NUMERIC(10, 2) NULL,
    min_order_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    max_redemptions_per_user INT NOT NULL DEFAULT 1,
    valid_from TIMESTAMP WITH TIME ZONE NOT NULL,
    valid_until TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE NULL
);

CREATE TABLE coupon_redemptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    coupon_id UUID NOT NULL REFERENCES coupons(id),
    customer_profile_id UUID NOT NULL REFERENCES customer_profiles(id),
    order_id UUID NOT NULL REFERENCES orders(id),
    discount_amount_applied NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. POST `/api/v1/coupons/validate`
- **Owner Module**: `coupon`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `Customer`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `400 Bad Request` (Expired coupon, minimum order value not met, usage limit reached)
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 50\text{ms}$ (p95)
