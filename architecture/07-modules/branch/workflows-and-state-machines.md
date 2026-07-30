# BRANCH MODULE — WORKFLOWS, STATE MACHINES & TESTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Workflows & Testing Specification  
Owner: Store & Location Engineering Team  

---

# Branch Operational Status Toggle Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Staff as Store Staff (DineGuru)
    participant API as Branch Router
    participant Service as BranchService
    participant Repo as BranchRepository
    participant DB as PostgreSQL
    participant Event as Event Dispatcher

    Staff->>API: PATCH /api/v1/branches/{id}/status (is_active: false)
    API->>Service: set_branch_status(branch_id, is_active)
    Service->>Repo: update_status(branch_id, is_active)
    Repo->>DB: UPDATE branches SET is_active = false
    Service->>DB: COMMIT Transaction
    Service->>Event: Publish BranchStatusChangedEvent
    Service-->>API: Return Branch Entity Payload
    API-->>Staff: HTTP 200 OK
```

---

# Published Domain Events

1. **`BranchStatusChangedEvent`**:
   * **Publisher**: `branch` module.
   * **Payload**: `{ "branch_id": "UUIDv7", "is_active": false, "updated_at": "..." }`
   * **Consumers**: [07-modules/search/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/search/README.md) (invalidates active store search filters), [07-modules/cart/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/cart/README.md) (blocks new checkout sessions for offline branch).

---

# Testing & Operational Observability

## Key Operational Metrics (SLIs)
- `branch_status_update_latency_ms`: p95 latency budget $< 80\text{ms}$.
