# ADMIN CMS, FEATURE FLAGS & AUDIT SPECIFICATIONS

Version: 1.0  
Status: Authoritative Admin Audit & CMS Specification  
Owner: Chief Architect & Internal Tools Team  

---

# Purpose

This document specifies the marketing CMS banner configuration, system feature flags, and immutable administrative audit log schema.

---

# System Feature Flags & Operational Toggles

The admin portal provides real-time feature flags stored in environment variables or dynamic system configuration:
- `EMERGENCY_MAINTENANCE_MODE`: Halts customer checkout globally across Saturdays during major campus network disruptions.
- `MAX_CAMPUS_ORDERS_PER_HOUR`: Dynamic throttle cap preventing store overload during campus festival events.

---

# Owned Database Schema (`admin_audit_logs` Table)

The admin subsystem has exclusive write ownership over `admin_audit_logs` ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).

```sql
CREATE TABLE admin_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    admin_user_id UUID NOT NULL REFERENCES users(id),
    action VARCHAR(100) NOT NULL, -- "MERCHANT_APPROVED", "MANUAL_REFUND_ISSUED", "FEATURE_FLAG_TOGGLED"
    target_entity VARCHAR(100) NOT NULL, -- "merchants", "payments", "system"
    target_entity_id UUID NULL,
    changes_payload JSONB NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_admin_audit_user ON admin_audit_logs(admin_user_id, created_at DESC);
```

## Immutable Audit Trail Policy
`admin_audit_logs` records MUST be retained for a minimum of 7 years and MUST NOT be deleted or altered.
