# 08-ADMIN — OPERATIONAL ADMINISTRATION & SYSTEM INTERFACES SPECIFICATIONS

Version: 1.0  
Status: Authoritative Admin Operations Specification Index  
Owner: Chief Architect & Internal Tools Team  

---

# Purpose

The `08-admin/` directory defines the operational administrative interfaces, merchant onboarding approval queues, CMS banner controls, feature flags, manual refund overrides, and immutable security audit logging for Saturdays and DineGuru.

Per architectural governance rules ([EXECUTION_PLAN.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/EXECUTION_PLAN.md)), Admin is NOT a business domain module; all operational administrative workflows are consolidated in this directory.

---

# Consolidated Specifications Index

1. [admin-architecture-and-operations.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/08-admin/admin-architecture-and-operations.md)
   * **Admin Interface Architecture**: Internal admin portal layout, `PlatformAdmin` authentication, and service-layer delegation rules.
   * **Merchant Onboarding & KYC Approval**: Operational verification queues for legal business entities, tax documents, and store activation.
   * **Manual Refund Override Controls**: Administrative authorization rules for processing manual refunds via Razorpay gateway.
2. [admin-cms-flags-and-audit.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/08-admin/admin-cms-flags-and-audit.md)
   * **CMS & Homepage Banner Controls**: Dynamic marketing banner configuration for Saturdays customer web app.
   * **System Feature Flags**: Operational toggles for campus-wide ordering limits, emergency maintenance mode, and new feature rollouts.
   * **Immutable Audit Trail (`admin_audit_logs`)**: Mandatory 7-year audit record specification tracking all administrative actions.

---

# Dependencies

- [01-business/merchant-and-customer-journeys.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/01-business/merchant-and-customer-journeys.md) — Merchant onboarding lifecycle.
- [06-api/authorization-errors-and-rate-limiting.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/06-api/authorization-errors-and-rate-limiting.md) — `PlatformAdmin` RBAC permissions.
- [09-security/threat-model-and-rbac.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/09-security/threat-model-and-rbac.md) — Audit logging security requirement.
