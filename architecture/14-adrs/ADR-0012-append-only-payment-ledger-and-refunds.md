# ADR-0012: APPEND-ONLY PAYMENT LEDGER & REFUND FINANCIAL MODEL

- **Status**: ACCEPTED  
- **Date**: 2026-07-30  
- **Author**: Chief Architect  
- **Scope**: Payment Bounded Context & Financial Accounting  

---

# Problem & Context

Customer payments, Razorpay gateway transactions, and refunds require absolute financial auditability. 

Modifying or overwriting existing payment records during status changes (e.g. updating a `payments` row from `SUCCESS` to `REFUNDED`) destroys historical audit trails and complicates financial reconciliation.

---

# Options Considered

1. **Option A: Mutable Payment Entity Status Updating**
   - Single `payments` table where status columns are updated in place upon refunds or state transitions.
2. **Option B: Append-Only Payment Ledger & Transaction Log Model**
   - Core `payments` table records the intent, while individual transaction events (authorizations, captures, webhooks, refunds) are written as immutable append-only rows in `payment_transactions`.

---

# Decision

The platform **MUST** adopt an **Append-Only Payment Ledger & Transaction Log Model** (Option B). 

Payment events (captures, failures, Razorpay webhook payloads, partial refunds, full refunds) MUST be recorded as immutable rows in `payment_transactions`. Existing financial rows MUST NEVER be updated or deleted. Financial state is calculated by aggregating transaction log history.

---

# Consequences

## Positive
- Guarantees 100% financial auditability and compliance for platform commissions and store payouts.
- Eliminates destructive state updates and race conditions during concurrent webhook callbacks.

## Negative / Risks
- Requires explicit aggregate queries to compute net payment balances.
