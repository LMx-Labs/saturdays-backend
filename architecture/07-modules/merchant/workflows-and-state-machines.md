# MERCHANT MODULE — WORKFLOWS, STATE MACHINES & TESTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Workflows & Testing Specification  
Owner: Merchant Product & Engineering Team  

---

# Merchant Account Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> DRAFT: Initial Registration
    DRAFT --> PENDING_VERIFICATION: Submit KYC & Bank Info
    PENDING_VERIFICATION --> APPROVED: Admin Approves KYC
    PENDING_VERIFICATION --> REJECTED: Admin Rejects KYC
    REJECTED --> DRAFT: Resubmit Documents
    APPROVED --> SUSPENDED: Violation / Non-payment
    SUSPENDED --> APPROVED: Compliance Restored
```

---

# Published Domain Events

1. **`MerchantApprovedEvent`**:
   * **Publisher**: `merchant` module (or admin override).
   * **Payload**: `{ "merchant_id": "UUIDv7", "owner_user_id": "UUIDv7", "approved_at": "..." }`
   * **Consumers**: [07-modules/subscription/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/subscription/README.md) (activates trial tier), [07-modules/notification/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/notification/README.md) (sends approval notification).

---

# Testing & Operational Observability

## Key Operational Metrics (SLIs)
- `merchant_onboarding_lead_time_hours`: Target $< 24\text{ hours}$ from `PENDING_VERIFICATION` to `APPROVED`.
