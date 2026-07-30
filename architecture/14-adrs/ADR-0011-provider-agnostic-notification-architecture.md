# ADR-0011: PROVIDER-AGNOSTIC NOTIFICATION ADAPTER PATTERN

- **Status**: ACCEPTED  
- **Date**: 2026-07-30  
- **Author**: Chief Architect  
- **Scope**: Notification Bounded Context  

---

# Problem & Context

The platform sends transactional notifications (order receipts, OTPs, status updates) across multiple channels (Email initially; Push, SMS, WhatsApp in future phases). 

Hardcoding vendor SDKs (e.g. SendGrid, Twilio) directly into domain logic creates vendor lock-in and complicates testing.

---

# Options Considered

1. **Option A: Direct Vendor Integration in Domain Services**
2. **Option B: Provider-Agnostic Notification Adapter Pattern**

---

# Decision

The platform **MUST** implement a **Provider-Agnostic Notification Adapter Pattern** (Option B). 

The `notification` module MUST define an abstract interface (`NotificationProviderInterface`) with concrete implementations (`SendGridEmailProvider`, `MockEmailProvider`). Domain modules invoke the abstract interface without knowledge of underlying vendor APIs.

---

# Consequences

## Positive
- Enables switching external email/SMS vendors without modifying business domain code.
- Allows instant unit testing using mock in-memory notification providers.

## Negative / Risks
- Requires abstracting vendor-specific features to maintain interface neutrality.
