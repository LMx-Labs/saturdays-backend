# 07-MODULES — BUSINESS DOMAIN MODULE SPECIFICATIONS

Version: 1.0  
Status: Authoritative Business Domain Specifications Index  
Owner: Chief Architect & Domain Module Owners  

---

# Purpose

The `07-modules/` directory contains the deep architectural, database, API, event, state machine, sequence diagram, security, testing, and operational monitoring specifications for all 17 functional business domain modules.

Every module represents a distinct Domain-Driven Design (DDD) bounded context ([02-domain-model/bounded-contexts-and-aggregates.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/02-domain-model/bounded-contexts-and-aggregates.md)). To prevent domain boundary erosion, generic "shared" modules and administrative interfaces are excluded from this directory; operational admin workflows are specified in [08-admin/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/08-admin/README.md).

---

# Consolidated Module Structure

Following the high-granularity maintainability directive ([EXECUTION_PLAN.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/EXECUTION_PLAN.md)), each of the 17 business modules contains **3 consolidated, rich specification documents**:

1. `overview-and-architecture.md`: Purpose, bounded context scope, single-source-of-truth responsibilities, module dependencies, security boundary, and future roadmap.
2. `domain-database-and-api.md`: Aggregate roots, domain invariants, owned database table schemas (with foreign key rationales & index strategies), and REST API endpoint specifications conforming to the 8-attribute standard ([06-api/api-design-and-authentication.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/06-api/api-design-and-authentication.md)).
3. `workflows-and-state-machines.md`: Mermaid state machine diagrams, sequence diagrams, domain event contracts, testing strategy, and observability monitoring rules.

---

# Index of Business Domain Modules (17 Modules)

| Module Directory | Bounded Context Name | Owning Aggregate Root | Owned Database Tables |
| :--- | :--- | :--- | :--- |
| [auth/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/auth/README.md) | Authentication & Identity | `User` | `users` |
| [customer/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/customer/README.md) | Customer Management | `CustomerProfile` | `customer_profiles`, `customer_addresses`, `customer_favorites` |
| [merchant/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/merchant/README.md) | Merchant Legal Entity | `Merchant` | `merchants` |
| [brand/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/brand/README.md) | Brand Umbrella | `Brand` | `brands` |
| [branch/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/branch/README.md) | Physical Branch Location | `Branch` | `branches` |
| [kitchen/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/kitchen/README.md) | Kitchen Preparation | `Kitchen` | `kitchens` |
| [menu/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/menu/README.md) | Catalog & Menu | `Menu` | `menus`, `menu_categories`, `menu_items`, `menu_modifiers` |
| [inventory/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/inventory/README.md) | Inventory Management | `InventoryItem` | `inventory_items`, `inventory_logs` (DineGuru Exclusive) |
| [search/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/search/README.md) | Search Engine | `SearchQuery` | None (Read-Only Query Engine) |
| [cart/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/cart/README.md) | Shopping Cart Session | `Cart` | `carts`, `cart_items` |
| [checkout/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/checkout/README.md) | Order Checkout Session | `CheckoutSession` | None (Transient Validation Engine) |
| [order/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/order/README.md) | Order Processing & State | `Order` | `orders`, `order_items`, `order_status_logs` |
| [payment/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/payment/README.md) | Payment Ledger | `Payment` | `payments`, `payment_transactions` |
| [coupon/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/coupon/README.md) | Coupon Engine | `Coupon` | `coupons`, `coupon_redemptions` |
| [review/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/review/README.md) | Reviews & Ratings | `Review` | `reviews` |
| [notification/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/notification/README.md) | Notifications Engine | `Notification` | `notifications` |
| [subscription/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/subscription/README.md) | Merchant Subscriptions | `Subscription` | `merchant_subscriptions`, `platform_commissions` |

---

# Module Validation Mandate

Every module specification generated MUST comply with the following validation rules:
- **Non-Overlapping Boundaries**: Bounded context responsibilities MUST be strictly isolated.
- **Aggregate & Table Ownership Alignment**: Matches [02-domain-model/bounded-contexts-and-aggregates.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/02-domain-model/bounded-contexts-and-aggregates.md) and [05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md).
- **API Standards Conformity**: REST endpoints MUST define all 8 mandatory attributes ([06-api/api-design-and-authentication.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/06-api/api-design-and-authentication.md)).
- **Transaction Concurrency Rules**: Transactions MUST be scoped explicitly in the Service layer ([04-backend/concurrency-transactions-and-background-tasks.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/04-backend/concurrency-transactions-and-background-tasks.md)).
- **Zero Table Cross-Writing**: No module MAY write to database tables owned by another module.
- **Zero Duplicate Invariants**: Invariants MUST be owned by exactly one module.
