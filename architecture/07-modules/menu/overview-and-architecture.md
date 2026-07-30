# MENU MODULE — OVERVIEW & ARCHITECTURE

Version: 1.0  
Status: Authoritative Module Specification  
Owner: Catalog & Menu Engineering Team  

---

# Executive Summary & Purpose

The `menu` module (`07-modules/menu/`) is the authoritative bounded context for store catalog management, menu category structuring, item pricing, modifier groups (toppings, sizes, add-ons), and dish metadata across Saturdays and DineGuru.

---

# Module Boundaries & Single-Source-of-Truth

## Included Responsibilities
- Branch menus and categories (`menus`, `menu_categories` tables).
- Dish items and modifier options (`menu_items`, `menu_modifiers` tables).
- Read-heavy catalog queries for customer browsing on Saturdays.

## Excluded Responsibilities (Non-Overlapping Boundaries)
- **Real-time Item Stock Availability**: Stock counts and out-of-stock toggles are owned exclusively by [07-modules/inventory/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/inventory/README.md) (DineGuru Exclusive).
- **Physical Branch Profile**: Owned exclusively by [07-modules/branch/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/branch/README.md).

---

# Architecture & Layering

```mermaid
flowchart TD
    subgraph Presentation Layer
        A[FastAPI Menu Router: /api/v1/branches/{id}/menu] --> B[MenuService Interface]
    end

    subgraph Application Layer
        B --> C[MenuService Implementation]
    end

    subgraph Persistence Layer
        C --> D[MenuRepository]
        D --> E[(menus, menu_categories, menu_items, menu_modifiers)]
    end

    style E fill:#f9f,stroke:#333,stroke-width:2px
```
