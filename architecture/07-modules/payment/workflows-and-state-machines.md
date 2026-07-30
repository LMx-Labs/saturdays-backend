# PAYMENT MODULE — WORKFLOWS, STATE MACHINES & TESTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Workflows & Testing Specification  
Owner: Payment & Financial Engineering Team  

---

# Payment Signature Verification Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Client as Saturdays Client
    participant API as Payment Router
    participant Service as PaymentService
    participant Gateway as Razorpay Adapter
    participant Repo as PaymentRepository
    participant DB as PostgreSQL
    participant Event as Event Dispatcher

    Client->>API: POST /api/v1/payments/verify (order_id, razorpay_payment_id, signature)
    API->>Service: verify_payment(schema)
    Service->>Gateway: verify_hmac_signature(order_id, payment_id, signature)
    alt Signature Valid
        Gateway-->>Service: Signature Verified
        Service->>Repo: insert_transaction("VERIFIED", "SUCCESS")
        Repo->>DB: INSERT INTO payment_transactions
        Service->>DB: COMMIT Transaction
        Service->>Event: Publish PaymentVerifiedEvent
        Service-->>API: Return Verification Success
        API-->>Client: HTTP 200 OK
    else Signature Invalid
        Gateway-->>Service: Signature Invalid
        Service->>Repo: insert_transaction("VERIFIED", "FAILED")
        Service-->>API: Raise InvalidPaymentSignatureError (HTTP 400)
    end
```

---

# Published Domain Events

1. **`PaymentVerifiedEvent`**:
   * **Publisher**: `payment` module.
   * **Payload**: `{ "payment_id": "UUIDv7", "order_id": "UUIDv7", "razorpay_payment_id": "...", "amount": 450.00, "status": "CAPTURED" }`
   * **Consumers**: [07-modules/order/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/order/README.md) (transitions status to `ACCEPTED`), [07-modules/notification/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/notification/README.md) (dispatches receipt).

---

# Testing & Operational Observability

## Key Operational Metrics (SLIs)
- `payment_verification_latency_ms`: p95 latency budget $< 100\text{ms}$.
- `payment_failure_rate`: Ratio of failed payment transactions to total intents.
