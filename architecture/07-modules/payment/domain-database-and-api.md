# PAYMENT MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Payment & Financial Engineering Team  

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `Payment`
- **Identifier**: `id` (`UUIDv7`)
- **Entities / Value Objects**: `PaymentTransaction`, `RefundTransaction`
- **Owner Module**: `payment` (Exclusive)

## Authoritative Domain Invariants
1. **INV-0003 (Append-Only Financial Ledger)**: Financial records in `payments` and `payment_transactions` MUST NOT be updated or deleted. State transitions and refunds MUST be appended as new rows ([14-adrs/ADR-0012](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0012-append-only-payment-ledger-and-refunds.md)).
2. **INV-PAY-001 (Refund Cap)**: Total refunded amount across all transactions for a given `payment_id` MUST NOT exceed original `amount`.

---

# Owned Database Schemas

The `payment` module has exclusive write ownership over `payments` and `payment_transactions` ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).

```sql
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    order_id UUID NOT NULL REFERENCES orders(id),
    customer_profile_id UUID NOT NULL REFERENCES customer_profiles(id),
    amount NUMERIC(10, 2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(10) NOT NULL DEFAULT 'INR',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payment_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    payment_id UUID NOT NULL REFERENCES payments(id),
    transaction_type VARCHAR(50) NOT NULL, -- "INTENT_CREATED", "VERIFIED", "CAPTURED", "REFUNDED"
    razorpay_payment_id VARCHAR(100) NULL,
    razorpay_order_id VARCHAR(100) NULL,
    razorpay_signature VARCHAR(255) NULL,
    amount NUMERIC(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL, -- "SUCCESS", "FAILED"
    payload_snapshot JSONB NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. POST `/api/v1/payments/verify`
- **Owner Module**: `payment`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `Customer`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_WRITE_ATOMIC_MULTITABLE` (Inserts `payment_transactions` and publishes `PaymentVerifiedEvent`)
- **Failure Modes**: `400 Bad Request` (Invalid HMAC signature)
- **Retry Behavior**: `DO_NOT_RETRY`
- **Expected Latency Target**: $< 100\text{ms}$ (p95)

### 2. POST `/api/v1/payments/webhook`
- **Owner Module**: `payment`
- **Authentication**: `NONE` (Razorpay HMAC Webhook Header signature validation)
- **Authorization**: `PUBLIC`
- **Idempotency**: `IDEMPOTENT` (Matches `razorpay_payment_id`)
- **Transaction Scope**: `READ_WRITE_ATOMIC_MULTITABLE`
- **Failure Modes**: `400 Bad Request` (Invalid signature)
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 80\text{ms}$ (p95)
