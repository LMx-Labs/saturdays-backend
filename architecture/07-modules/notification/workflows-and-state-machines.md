# NOTIFICATION MODULE — WORKFLOWS, STATE MACHINES & TESTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Workflows & Testing Specification  
Owner: Notification & Messaging Engineering Team  

---

# Async Notification Dispatch Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Event as Event Dispatcher
    participant Service as NotificationService
    participant Task as FastAPI BackgroundTasks
    participant Vendor as SendGrid Provider
    participant DB as PostgreSQL

    Event->>Service: Handle OrderPlacedEvent
    Service->>Task: Enqueue dispatch_email_task()
    Note over Task: Executed Asynchronously Post-Response
    Task->>Vendor: send_transactional_email(to, template)
    Vendor-->>Task: 202 Accepted (Message ID)
    Task->>DB: INSERT INTO notifications (status = "SENT")
```

---

# Testing & Operational Observability

## Key Operational Metrics (SLIs)
- `notification_dispatch_latency_ms`: p95 latency budget $< 1,000\text{ms}$ (async).
