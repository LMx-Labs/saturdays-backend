# CHECKOUT MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Checkout & Ordering Engineering Team  

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `CheckoutSession`
- **Identifier**: Value Object (Transient Checkout Request Payload)
- **Entities / Value Objects**: `CheckoutValidationResult`, `FeeSummary`
- **Owner Module**: `checkout` (Exclusive)

## Authoritative Domain Invariants
1. **INV-0005 (Stock Availability Required)**: An order MUST NOT be submitted if any requested item is marked `OUT_OF_STOCK` or if quantity exceeds available inventory.
2. **INV-CHK-001 (Branch Status Validation)**: Checkout MUST fail if the target branch is offline or closed ([14-adrs/ADR-0003](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0003-merchant-brand-branch-kitchen-hierarchy.md)).

---

# Database Tables & Read-Only Access Model

The `checkout` module owns NO database tables. It acts as an in-memory validation engine invoking services across `cart`, `inventory`, `coupon`, and `order`.

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. POST `/api/v1/checkout/validate`
- **Owner Module**: `checkout`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `Customer`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `400 Bad Request` (Out of stock item, expired coupon, closed branch)
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 120\text{ms}$ (p95)

### 2. POST `/api/v1/checkout/submit`
- **Owner Module**: `checkout`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `Customer`
- **Idempotency**: `NON_IDEMPOTENT` (Requires `X-Idempotency-Key` header)
- **Transaction Scope**: `READ_WRITE_ATOMIC_MULTITABLE` (Atomic order & payment intent creation)
- **Failure Modes**: `400 Bad Request`, `409 Conflict` (Duplicate checkout request)
- **Retry Behavior**: `DO_NOT_RETRY`
- **Expected Latency Target**: $< 200\text{ms}$ (p95)
