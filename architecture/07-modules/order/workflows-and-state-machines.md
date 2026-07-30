# ORDER MODULE — WORKFLOWS, STATE MACHINES & TESTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Workflows & Testing Specification  
Owner: Order & Kitchen Fulfillment Team  

---

# Order Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> PLACED: Checkout Submitted
    PLACED --> ACCEPTED: Payment Verified / Merchant Accepts
    ACCEPTED --> PREPARING: Kitchen Starts Prep
    PREPARING --> READY: Food Prepared
    READY --> COMPLETED: Customer Picked Up / Delivered
    PLACED --> CANCELLED: Customer Cancels (Pre-Acceptance)
    ACCEPTED --> CANCELLED: Merchant Rejects Order
```

---

# Published Domain Events

1. **`OrderPlacedEvent`**:
   * **Publisher**: `order` module.
   * **Payload**: `{ "order_id": "UUIDv7", "branch_id": "UUIDv7", "customer_profile_id": "UUIDv7", "total_amount": 450.00, "placed_at": "..." }`
   * **Consumers**: [07-modules/notification/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/notification/README.md).
2. **`OrderAcceptedEvent`**:
   * **Publisher**: `order` module.
   * **Payload**: `{ "order_id": "UUIDv7", "branch_id": "UUIDv7", "accepted_at": "..." }`
   * **Consumers**: [07-modules/kitchen/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/kitchen/README.md).

---

# Testing & Operational Observability

## Key Operational Metrics (SLIs)
- `order_status_update_latency_ms`: p95 latency budget $< 100\text{ms}$.
- `order_cancellation_rate`: Percentage of orders ending in `CANCELLED` status.
