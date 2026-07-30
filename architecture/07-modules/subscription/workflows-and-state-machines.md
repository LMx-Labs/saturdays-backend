# SUBSCRIPTION MODULE — WORKFLOWS, STATE MACHINES & TESTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Workflows & Testing Specification  
Owner: Monetization & Billing Engineering Team  

---

# Commission Calculation Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Event as In-Process Event Dispatcher
    participant Service as SubscriptionService
    participant Repo as SubscriptionRepository
    participant DB as PostgreSQL

    Event->>Service: Handle PaymentVerifiedEvent (order_id, gross_amount, merchant_id)
    Service->>Repo: get_active_subscription(merchant_id)
    Repo->>DB: SELECT commission_rate_percentage FROM merchant_subscriptions WHERE merchant_id = ...
    DB-->>Repo: Commission Rate (e.g. 5%)
    Service->>Service: Calculate Commission (Gross * 0.05) & Net Payout
    Service->>Repo: insert_commission_ledger(order_id, commission_data)
    Repo->>DB: INSERT INTO platform_commissions
    Service->>DB: COMMIT Transaction
```

---

# Testing & Operational Observability

## Key Operational Metrics (SLIs)
- `commission_calculation_latency_ms`: p95 latency budget $< 50\text{ms}$.
