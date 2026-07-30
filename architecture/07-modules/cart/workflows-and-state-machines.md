# CART MODULE — WORKFLOWS, STATE MACHINES & TESTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Workflows & Testing Specification  
Owner: Checkout & Ordering Engineering Team  

---

# Add Item to Cart & Single Branch Enforcement Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer (Saturdays)
    participant API as Cart Router
    participant Service as CartService
    participant Repo as CartRepository
    participant DB as PostgreSQL

    Customer->>API: POST /api/v1/cart/items (branch_id, menu_item_id, quantity)
    API->>Service: add_item(customer_id, branch_id, menu_item_id, qty)
    Service->>Repo: get_active_cart(customer_id)
    Repo->>DB: SELECT * FROM carts WHERE customer_profile_id = ...
    alt Cart Exists for Different Branch
        DB-->>Repo: Cart Record (branch_id_A != requested_branch_id_B)
        Service-->>API: Raise SingleBranchCartConflictError (HTTP 400)
    else Cart Empty or Same Branch
        Service->>Repo: insert_or_update_item(cart_id, menu_item_id, qty)
        Repo->>DB: INSERT/UPDATE cart_items
        Service->>DB: COMMIT Transaction
        Service-->>API: Return Cart Summary Payload
        API-->>Customer: HTTP 200 OK
    end
```

---

# Testing & Operational Observability

## Key Operational Metrics (SLIs)
- `cart_item_add_latency_ms`: p95 latency budget $< 100\text{ms}$.
