# COUPON MODULE — WORKFLOWS, STATE MACHINES & TESTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Workflows & Testing Specification  
Owner: Promotions & Marketing Engineering Team  

---

# Coupon Validation Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer (Saturdays)
    participant API as Coupon Router
    participant Service as CouponService
    participant Repo as CouponRepository
    participant DB as PostgreSQL

    Customer->>API: POST /api/v1/coupons/validate (code: "WELCOME50", order_amount: 300)
    API->>Service: validate_coupon("WELCOME50", customer_id, order_amount)
    Service->>Repo: find_by_code("WELCOME50")
    Repo->>DB: SELECT * FROM coupons WHERE code = 'WELCOME50' AND is_active = true
    Service->>Repo: count_user_redemptions(coupon_id, customer_id)
    Repo->>DB: SELECT COUNT(*) FROM coupon_redemptions WHERE coupon_id = ... AND customer_profile_id = ...
    alt Redemptions < Limit AND order_amount >= min_order_amount
        Service-->>API: Return Discount Calculation Payload
        API-->>Customer: HTTP 200 OK (Discount: ₹50)
    else Invalid Conditions
        Service-->>API: Raise CouponValidationError (HTTP 400)
    end
```

---

# Testing & Operational Observability

## Key Operational Metrics (SLIs)
- `coupon_validation_latency_ms`: p95 latency budget $< 50\text{ms}$.
