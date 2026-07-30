# INVENTORY MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Kitchen & Inventory Engineering Team  

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `InventoryItem`
- **Identifier**: `id` (`UUIDv7`)
- **Entities / Value Objects**: `StockLog`, `IngredientItem`
- **Owner Module**: `inventory` (Exclusive)

## Authoritative Domain Invariants
1. **INV-0002 (Exclusive DineGuru Write Rule)**: Stock counts and availability flags MUST be mutated exclusively via DineGuru merchant routes or through `InventoryService` during checkout allocation ([14-adrs/ADR-0006](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0006-inventory-ownership-write-rule.md)).
2. **INV-INV-001 (Non-Negative Stock Quantity)**: Available stock quantity MUST NOT be negative (`quantity >= 0`).

---

# Owned Database Schemas

The `inventory` module has exclusive write ownership over `inventory_items` and `inventory_logs` ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).

```sql
CREATE TABLE inventory_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    menu_item_id UUID NOT NULL REFERENCES menu_items(id),
    quantity INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    is_in_stock BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE NULL,
    UNIQUE(branch_id, menu_item_id)
);

CREATE TABLE inventory_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    inventory_item_id UUID NOT NULL REFERENCES inventory_items(id),
    change_amount INT NOT NULL, -- e.g., -2 for order reservation, +50 for restock
    previous_quantity INT NOT NULL,
    new_quantity INT NOT NULL,
    reason VARCHAR(100) NOT NULL, -- "ORDER_RESERVATION", "MERCHANT_RESTOCK", "WASTE"
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. GET `/api/v1/branches/{branch_id}/inventory`
- **Owner Module**: `inventory`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `KitchenStaff`, `BranchManager`, or `MerchantOwner`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `401 Unauthorized`, `403 Forbidden`
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 50\text{ms}$ (p95)

### 2. PATCH `/api/v1/inventory/{id}/stock`
- **Owner Module**: `inventory`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `KitchenStaff`, `BranchManager`, or `MerchantOwner`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_WRITE_SINGLE`
- **Failure Modes**: `400 Bad Request` (Negative stock quantity), `401 Unauthorized`, `403 Forbidden`
- **Retry Behavior**: `RETRY_WITH_EXPONENTIAL_BACKOFF`
- **Expected Latency Target**: $< 80\text{ms}$ (p95)
