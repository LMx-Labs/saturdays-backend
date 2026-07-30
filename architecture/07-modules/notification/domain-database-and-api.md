# NOTIFICATION MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Notification & Messaging Engineering Team  

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `Notification`
- **Identifier**: `id` (`UUIDv7`)
- **Entities / Value Objects**: `NotificationLog`, `DeviceToken`
- **Owner Module**: `notification` (Exclusive)

## Authoritative Domain Invariants
1. **INV-NOTIF-001 (Vendor Decoupling)**: Vendor SDKs MUST NOT be imported directly into business domain services; all dispatches MUST route through `NotificationProviderInterface` adapters ([14-adrs/ADR-0011](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0011-provider-agnostic-notification-architecture.md)).

---

# Owned Database Schema (`notifications` Table)

The `notification` module has exclusive write ownership over `notifications` ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    user_id UUID NOT NULL REFERENCES users(id),
    channel VARCHAR(20) NOT NULL, -- "EMAIL", "SMS", "PUSH"
    recipient VARCHAR(255) NOT NULL,
    subject VARCHAR(255) NULL,
    body TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING', -- PENDING, SENT, FAILED
    vendor_message_id VARCHAR(100) NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. GET `/api/v1/notifications/me`
- **Owner Module**: `notification`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `ALL_ROLES`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `401 Unauthorized`
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 50\text{ms}$ (p95)
