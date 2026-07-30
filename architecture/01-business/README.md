# 01-BUSINESS — BUSINESS MODEL & OPERATIONAL POLICIES SPECIFICATIONS

Version: 1.0  
Status: Authoritative Business Specifications Index  
Owner: Saturdays Product & Business Engineering  

---

# Purpose

The `01-business/` directory defines the commercial model, revenue streams, merchant/customer journeys, cancellation rules, and operational policies governing the Saturdays food ordering platform and DineGuru merchant application.

It translates the strategic baseline established in [00-foundation/foundation-overview.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/00-foundation/foundation-overview.md) into concrete business workflows, financial logic, and policy rules.

---

# Consolidated Specifications Index

1. [business-model-and-monetization.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/01-business/business-model-and-monetization.md)
   * **Monetization Dual Engine**: Platform revenue model combining DineGuru monthly store subscriptions and per-order commission fees.
   * **Subscription Tiers**: Basic, Professional, and Enterprise merchant tier limits and billing cycles.
   * **Commission Calculations**: Configurable per-branch commission formulas and auditable platform financial settlement ledgers.
2. [merchant-and-customer-journeys.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/01-business/merchant-and-customer-journeys.md)
   * **Merchant Lifecycle**: End-to-end onboarding, document verification, branch setup, subscription activation, and store suspension workflows.
   * **Customer Journey**: Discovery, catalog browsing, cart construction, checkout validation, Razorpay payment, real-time order tracking, and review submission.
   * **Operational Policies**: Order cancellation windows, store-initiated rejection rules, refund policies, and operating hours enforcement.

---

# Dependencies

- [00-foundation/foundation-overview.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/00-foundation/foundation-overview.md) — Strategic vision and dual-surface platform philosophy.
- [14-adrs/ADR-0003](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0003-merchant-brand-branch-kitchen-hierarchy.md) — 4-tier merchant organizational structure (`Merchant` $\rightarrow$ `Brand` $\rightarrow$ `Branch` $\rightarrow$ `Kitchen`).
- [14-adrs/ADR-0012](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0012-append-only-payment-ledger-and-refunds.md) — Append-only payment ledger rules.
