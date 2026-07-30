# REVIEW MODULE — WORKFLOWS, STATE MACHINES & TESTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Workflows & Testing Specification  
Owner: Customer Experience & Reviews Engineering Team  

---

# Verified Review Submission Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer (Saturdays)
    participant API as Review Router
    participant Service as ReviewService
    participant Ord as OrderService
    participant Repo as ReviewRepository
    participant DB as PostgreSQL

    Customer->>API: POST /api/v1/reviews (order_id, rating: 5, comment: "Great food!")
    API->>Service: submit_review(customer_id, schema)
    Service->>Ord: get_order_details(order_id)
    Ord-->>Service: Order Record (status: "COMPLETED", customer_id)
    alt Order Completed AND Belongs to Customer
        Service->>Repo: insert_review(review_entity)
        Repo->>DB: INSERT INTO reviews
        Service->>DB: COMMIT Transaction
        Service-->>API: Return Review Payload
        API-->>Customer: HTTP 201 Created
    else Unverified Order
        Service-->>API: Raise UnverifiedReviewError (HTTP 400)
    end
```

---

# Testing & Operational Observability

## Key Operational Metrics (SLIs)
- `review_submission_latency_ms`: p95 latency budget $< 100\text{ms}$.
