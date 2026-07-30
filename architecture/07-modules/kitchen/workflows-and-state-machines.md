# KITCHEN MODULE — WORKFLOWS, STATE MACHINES & TESTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Workflows & Testing Specification  
Owner: Kitchen & Dispatch Engineering Team  

---

# Kitchen Prep Queue Routing Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Event as In-Process Event Dispatcher
    participant Service as KitchenService
    participant Repo as KitchenRepository
    participant DB as PostgreSQL

    Event->>Service: Handle OrderAcceptedEvent (order_id, branch_id)
    Service->>Repo: find_active_kitchen_for_branch(branch_id)
    Repo->>DB: SELECT id FROM kitchens WHERE branch_id = ... AND is_active = true
    DB-->>Repo: Kitchen Record
    Service->>Service: Route Order to Kitchen Prep Queue
```

---

# Testing & Operational Observability

## Key Operational Metrics (SLIs)
- `kitchen_prep_queue_routing_latency_ms`: p95 latency budget $< 50\text{ms}$.
