# ORDER MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Order & Kitchen Fulfillment Team  

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `Order`
- **Identifier**: `id` (`UUIDv7`)
- **Entities / Value Objects**: `OrderItem`, `OrderStatusLog`, `OrderCancelReason`
- **Owner Module**: `order` (Exclusive)

## Authoritative Domain Invariants
1. **INV-0001 (Single Branch Ownership)**: An `Order` MUST belong to exactly one physical `Branch` (`branch_id`).
2. **INV-ORD-001 (Immutable Order History)**: Once created, `orders` and `order_items` records MUST NOT be modified or deleted. Status transitions MUST be appended to `order_status_logs`.
3. **INV-ORD-002 (Valid State Machine Transition)**: Status changes MUST follow legal sequence paths (`PLACED` $\rightarrow$ `ACCEPTED` $\rightarrow$ `PREPARING` $\rightarrow$ `READY` $\rightarrow$ `COMPLETED`).

---

# Owned Database Schemas

The `order` module has exclusive write ownership over `orders`, `order_items`, and `order_status_logs` ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).

```sql
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    customer_profile_id UUID NOT NULL REFERENCES customer_profiles(id),
    branch_id UUID NOT NULL REFERENCES branches(id),
    total_amount NUMERIC(10, 2) NOT NULL CHECK (total_amount >= 0),
    status VARCHAR(50) NOT NULL DEFAULT 'PLACED',
    delivery_address_snapshot JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    order_id UUID NOT NULL REFERENCES orders(id),
    menu_item_id UUID NOT NULL REFERENCES menu_items(id),
    item_name_snapshot VARCHAR(150) NOT NULL,
    unit_price_snapshot NUMERIC(10, 2) NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    selected_modifiers_snapshot JSONB NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_status_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    order_id UUID NOT NULL REFERENCES orders(id),
    previous_status VARCHAR(50) NULL,
    new_status VARCHAR(50) NOT NULL,
    changed_by_user_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. GET `/api/v1/orders`
- **Owner Module**: `order`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `Customer` (lists customer orders) or `BranchManager`/`KitchenStaff` (lists branch orders)
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `401 Unauthorized`, `403 Forbidden`
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 80\text{ms}$ (p95)

### 2. PATCH `/api/v1/orders/{id}/status`
- **Owner Module**: `order`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `KitchenStaff`, `BranchManager`, or `MerchantOwner`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_WRITE_ATOMIC_MULTITABLE` (Updates `orders` and inserts `order_status_logs`)
- **Failure Modes**: `400 Bad Request` (Illegal state transition), `401 Unauthorized`, `403 Forbidden`, `404 Not Found`
- **Retry Behavior**: `RETRY_WITH_EXPONENTIAL_BACKOFF`
- **Expected Latency Target**: $< 100\text{ms}$ (p95)
