# MERCHANT & CUSTOMER JOURNEYS SPECIFICATIONS

Version: 1.0  
Status: Authoritative User Workflow Specification  
Owner: Saturdays Product & Business Engineering  

---

# Purpose

This document defines the lifecycle states and operational workflows for both user populations: Merchants operating through **DineGuru** and Customers ordering through **Saturdays**.

---

# Merchant Journey & Lifecycle (DineGuru)

Merchants progress through a formal onboarding and verification lifecycle managed by `merchant` and `08-admin` operational interfaces.

```mermaid
stateDiagram-v2
    [*] --> DRAFT: Merchant Registers Account
    DRAFT --> PENDING_VERIFICATION: Upload Business Documents
    PENDING_VERIFICATION --> APPROVED: Admin Approves KYC & Legal Identity
    PENDING_VERIFICATION --> REJECTED: KYC Rejected
    APPROVED --> ACTIVE: Subscribe to Tier & Configure Branch/Menu
    ACTIVE --> SUSPENDED: Manual Admin Suspension or Overdue Billing
    SUSPENDED --> ACTIVE: Compliance Restored / Billing Settled
    REJECTED --> DRAFT: Re-upload Correct Documents
```

## Lifecycle States
1. **DRAFT**: Initial registration; merchant account created, tax/KYC documents pending upload.
2. **PENDING_VERIFICATION**: Business registration, FSSAI licenses, and bank account details submitted to `08-admin` review queue.
3. **APPROVED**: Admin approval complete; merchant assigned legal `merchant_id`.
4. **ACTIVE**: DineGuru subscription activated; Brand, Branch, and Menu configured; receiving customer orders.
5. **SUSPENDED**: Operational write access disabled due to compliance violations or billing delinquency.

---

# Customer Journey (Saturdays)

The customer workflow spans discovery, catalog inspection, cart building, checkout validation, payment, real-time tracking, and review submission.

```mermaid
sequenceDiagram
    autonumber
    actor C as Customer (Saturdays)
    participant B as Backend API (FastAPI)
    participant M as DineGuru (Merchant)
    participant P as Razorpay Payment Gateway

    C->>B: Browse Restaurants & Menus (Branch Query)
    B-->>C: Return Menu & Live Item Stock Status
    C->>B: Add Items to Cart & Submit Checkout Validation
    B-->>C: Validate Cart, Taxes, Coupons & Stock
    C->>B: Initialize Order & Payment
    B->>P: Create Razorpay Order Transaction
    P-->>C: Payment Signature Verification
    C->>B: Send Payment Verification Payload
    B->>B: Persist Payment Ledger & Set Order State = ACCEPTED
    B-->>M: Broadcast WebSocket Real-Time Alert
    M-->>B: Kitchen Updates State (PREPARING -> READY)
    B-->>C: Real-Time Order Status Update
```

---

# Operational Policies & Cancellation Rules

## Order Cancellation Policy
1. **Customer-Initiated Cancellation**:
   * Allowed ONLY when order state is `PLACED` or `PENDING_PAYMENT` (prior to merchant acceptance).
   * Forbidden once order transitions to `ACCEPTED` or `PREPARING` by the merchant.
2. **Merchant-Initiated Cancellation**:
   * Merchants MAY reject an order prior to prep if items are out of stock or branch is overloaded.
   * Merchant rejection MUST trigger an automated full refund via Razorpay ([14-adrs/ADR-0012](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0012-append-only-payment-ledger-and-refunds.md)).

## Branch Operating Hours Policy
- Branch order placement MUST be strictly blocked by backend validation outside configured store operating hours or when store status is toggled to `OFFLINE` in DineGuru.
