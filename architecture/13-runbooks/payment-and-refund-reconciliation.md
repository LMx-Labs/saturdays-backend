# PAYMENT & REFUND RECONCILIATION RUNBOOK SPECIFICATIONS

Version: 1.0  
Status: Authoritative Financial Reconciliation Runbook  
Owner: Chief Architect & Financial Operations Engineering  

---

# Purpose

This document provides step-by-step operational runbooks for resolving Razorpay payment gateway discrepancies, webhook failures, and merchant commission payout reconciliation.

---

# Incident 1: Unmatched Razorpay Webhooks (Missed Webhook Callbacks)

## Trigger
Customer's bank account debited, but order status remains `PLACED` (unverified payment).

## Step-by-Step Reconciliation Guide
1. **Step 1: Fetch Pending Payment Records**:
   * Query `payments` table for transactions created $> 10\text{ minutes}$ ago with no matching `VERIFIED` transaction entry in `payment_transactions`.
2. **Step 2: Query Razorpay API Directly**:
   * Fetch payment status via Razorpay REST API: `GET /v1/payments/{razorpay_payment_id}`.
3. **Step 3: Append Transaction Ledger Record**:
   * If Razorpay status is `captured`, insert an append-only row into `payment_transactions` with status `SUCCESS` ([14-adrs/ADR-0012](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0012-append-only-payment-ledger-and-refunds.md)).
4. **Step 4: Update Order State**:
   * Update order status to `ACCEPTED` and broadcast WebSocket alert to DineGuru kitchen.

---

# Incident 2: Merchant Monthly Commission Payout Settlement

1. **Calculate Payout Ledger**: Aggregate `platform_commissions` rows for merchant for billing cycle:
   $$\text{Net Merchant Payout} = \sum (\text{gross\_order\_amount}) - \sum (\text{commission\_amount})$$
2. **Verify Settlement Account**: Confirm merchant status is `APPROVED` and bank IFSC/account details are verified ([07-modules/merchant/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/merchant/README.md)).
3. **Dispatch Automated Payout**: Initiate batch bank transfer via Razorpay Route API.
