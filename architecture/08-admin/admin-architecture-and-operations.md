# ADMIN ARCHITECTURE & OPERATIONS SPECIFICATIONS

Version: 1.0  
Status: Authoritative Admin Operations Specification  
Owner: Chief Architect & Internal Tools Team  

---

# Purpose

This document specifies the operational admin portal architecture, merchant onboarding approval queues, and manual refund override authorization workflows.

---

# Admin Portal Architecture

Operational admin routes reside under the `/api/v1/admin/` prefix and MUST require `PlatformAdmin` role authorization ([06-api/authorization-errors-and-rate-limiting.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/06-api/authorization-errors-and-rate-limiting.md)).

```mermaid
flowchart TD
    subgraph Admin Portal Surface
        A[Internal Admin Web Dashboard] -->|Bearer JWT (PlatformAdmin Role)| B[FastAPI Admin Router: /api/v1/admin]
    end

    subgraph Operation Delegation Layer
        B -->|1. KYC Approval| C[MerchantService]
        B -->|2. Manual Refund| D[PaymentService]
        B -->|3. System Audit Log| E[AdminAuditRepository]
    end

    subgraph Audit Logging
        E --> F[(admin_audit_logs Table in PostgreSQL)]
    end

    style F fill:#f9f,stroke:#333,stroke-width:2px
```

---

# Operational Workflows

## 1. Merchant Onboarding & KYC Approval
- Admin operators review pending merchant tax records (GSTIN, FSSAI licenses).
- Executing approval updates merchant status to `APPROVED` in `merchants` table via `MerchantService` and emits `MerchantApprovedEvent`.

## 2. Manual Refund Override Authorization
- Manual refund requests (for customer dispute resolution) MUST be authorized by a `PlatformAdmin` user.
- Execution invokes `PaymentService.process_refund()` and inserts an immutable audit log entry into `admin_audit_logs`.
