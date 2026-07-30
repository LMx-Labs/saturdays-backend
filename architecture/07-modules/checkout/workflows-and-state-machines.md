# CHECKOUT MODULE — WORKFLOWS, STATE MACHINES & TESTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Workflows & Testing Specification  
Owner: Checkout & Ordering Engineering Team  

---

# Checkout Submission Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer (Saturdays)
    participant API as Checkout Router
    participant Service as CheckoutService
    participant Inv as InventoryService
    participant Ord as OrderService
    participant Pay as PaymentService

    Customer->>API: POST /api/v1/checkout/submit (cart_id, coupon_code)
    API->>Service: submit_checkout(customer_id, schema)
    Service->>Inv: validate_and_lock_stock(branch_id, items)
    Inv-->>Service: Stock Locked
    Service->>Ord: create_order_record(order_payload)
    Ord-->>Service: Order Created (ID, Amount)
    Service->>Pay: create_payment_intent(order_id, amount)
    Pay-->>Service: Razorpay Payment Intent Payload
    Service-->>API: Return Razorpay Order Token Payload
    API-->>Customer: HTTP 201 Created (Proceed to Payment)
```

---

# Testing & Operational Observability

## Key Operational Metrics (SLIs)
- `checkout_submission_latency_ms`: p95 latency budget $< 200\text{ms}$.
- `checkout_abandonment_rate`: Percentage of validated checkout sessions that fail to submit.
