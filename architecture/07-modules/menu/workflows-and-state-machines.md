# MENU MODULE — WORKFLOWS, STATE MACHINES & TESTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Workflows & Testing Specification  
Owner: Catalog & Menu Engineering Team  

---

# Menu Item Creation Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Manager as Branch Manager (DineGuru)
    participant API as Menu Router
    participant Service as MenuService
    participant Repo as MenuRepository
    participant DB as PostgreSQL
    participant Event as Event Dispatcher

    Manager->>API: POST /api/v1/branches/{id}/menu/items (item_data)
    API->>Service: create_menu_item(category_id, schema)
    Service->>Service: Validate Base Price >= 0.00
    Service->>Repo: insert_item(item_entity)
    Repo->>DB: INSERT INTO menu_items
    Service->>DB: COMMIT Transaction
    Service->>Event: Publish MenuItemCreatedEvent
    Service-->>API: Return MenuItem Payload
    API-->>Manager: HTTP 201 Created
```

---

# Published Domain Events

1. **`MenuItemCreatedEvent`**:
   * **Publisher**: `menu` module.
   * **Payload**: `{ "menu_item_id": "UUIDv7", "branch_id": "UUIDv7", "base_price": 180.00, "created_at": "..." }`
   * **Consumers**: [07-modules/inventory/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/inventory/README.md) (initializes inventory stock record).

---

# Testing & Operational Observability

## Key Operational Metrics (SLIs)
- `menu_fetch_latency_ms`: p95 latency budget $< 50\text{ms}$.
