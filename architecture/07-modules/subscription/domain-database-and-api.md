# SUBSCRIPTION MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Monetization & Billing Engineering Team  

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `Subscription`
- **Identifier**: `id` (`UUIDv7`)
- **Entities / Value Objects**: `PlatformCommission`, `SubscriptionPlan`
- **Owner Module**: `subscription` (Exclusive)

## Authoritative Domain Invariants
1. **INV-SUB-001 (Immutable Commission Ledger)**: Platform commission calculations in `platform_commissions` MUST be append-only and immutable.
2. **INV-SUB-002 (Branch Limit Enforcement)**: A merchant MUST NOT create more active branches than permitted by their `plan_tier` (Basic: 1, Professional: 5, Enterprise: Unlimited).

---

# Owned Database Schemas

The `subscription` module has exclusive write ownership over `merchant_subscriptions` and `platform_commissions` ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).

```sql
CREATE TABLE merchant_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    merchant_id UUID NOT NULL REFERENCES merchants(id),
    plan_tier VARCHAR(50) NOT NULL DEFAULT 'BASIC', -- BASIC, PROFESSIONAL, ENTERPRISE
    billing_cycle VARCHAR(20) NOT NULL DEFAULT 'MONTHLY',
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    commission_rate_percentage NUMERIC(5, 2) NOT NULL DEFAULT 5.00,
    valid_until TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE NULL
);

CREATE TABLE platform_commissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    order_id UUID NOT NULL REFERENCES orders(id),
    merchant_id UUID NOT NULL REFERENCES merchants(id),
    gross_order_amount NUMERIC(10, 2) NOT NULL,
    commission_rate_percentage NUMERIC(5, 2) NOT NULL,
    commission_amount NUMERIC(10, 2) NOT NULL,
    merchant_net_payout NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. GET `/api/v1/merchants/me/subscription`
- **Owner Module**: `subscription`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `MerchantOwner`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `401 Unauthorized`, `404 Not Found`
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 50\text{ms}$ (p95)

### 2. GET `/api/v1/merchants/me/commissions`
- **Owner Module**: `subscription`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `MerchantOwner`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `401 Unauthorized`
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 80\text{ms}$ (p95)
