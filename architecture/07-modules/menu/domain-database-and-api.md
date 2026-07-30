# MENU MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Catalog & Menu Engineering Team  

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `Menu`
- **Identifier**: `id` (`UUIDv7`)
- **Entities / Value Objects**: `MenuCategory`, `MenuItem`, `ModifierGroup`, `Modifier`
- **Owner Module**: `menu` (Exclusive)

## Authoritative Domain Invariants
1. **INV-MENU-001 (Non-Negative Base Price)**: The `base_price` of a `MenuItem` MUST be greater than or equal to 0.00.
2. **INV-MENU-002 (Valid Category Hierarchy)**: A `MenuItem` MUST belong to an active `MenuCategory` within the same `Branch` menu.

---

# Owned Database Schemas

The `menu` module has exclusive write ownership over `menus`, `menu_categories`, `menu_items`, and `menu_modifiers` ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).

```sql
CREATE TABLE menus (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    name VARCHAR(100) NOT NULL DEFAULT 'Main Menu',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE NULL
);

CREATE TABLE menu_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    menu_id UUID NOT NULL REFERENCES menus(id),
    name VARCHAR(100) NOT NULL, -- e.g., "Starters", "Beverages"
    display_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE NULL
);

CREATE TABLE menu_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    category_id UUID NOT NULL REFERENCES menu_categories(id),
    name VARCHAR(150) NOT NULL,
    description TEXT NULL,
    base_price NUMERIC(10, 2) NOT NULL CHECK (base_price >= 0),
    image_url VARCHAR(255) NULL,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    is_veg BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE NULL
);

CREATE TABLE menu_modifiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    menu_item_id UUID NOT NULL REFERENCES menu_items(id),
    name VARCHAR(100) NOT NULL, -- e.g., "Extra Cheese", "Large Size"
    price_delta NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. GET `/api/v1/branches/{branch_id}/menu`
- **Owner Module**: `menu`
- **Authentication**: `NONE` (Public endpoint)
- **Authorization**: `PUBLIC`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `404 Not Found`
- **Retry Behavior**: `SAFE_IMMEDIATE_RETRY`
- **Expected Latency Target**: $< 50\text{ms}$ (p95, optimized composite index `idx_menu_items_branch_avail`)

### 2. POST `/api/v1/branches/{branch_id}/menu/items`
- **Owner Module**: `menu`
- **Authentication**: `BEARER_JWT`
- **Authorization**: `BranchManager` or `MerchantOwner`
- **Idempotency**: `NON_IDEMPOTENT`
- **Transaction Scope**: `READ_WRITE_SINGLE`
- **Failure Modes**: `400 Bad Request` (Negative price), `401 Unauthorized`, `403 Forbidden`
- **Retry Behavior**: `DO_NOT_RETRY`
- **Expected Latency Target**: $< 100\text{ms}$ (p95)
