# DATABASE PHILOSOPHY & MASTER SCHEMA SPECIFICATIONS

Version: 1.0  
Status: Authoritative Database Schema Specification  
Owner: Chief Architect & Lead Database Engineer  

---

# Purpose

This document defines the shared PostgreSQL database philosophy, resolves the platform-wide primary key strategy, specifies explicit table ownership across all 28 schema tables, and details foreign key rationales, transaction boundaries, and write path concurrency assumptions.

---

# Primary Key Strategy Resolution — `UUIDv7` Standard

## RESOLUTION SUMMARY: ADOPT `UUIDv7`
Platform-wide aggregate root primary keys MUST utilize **`UUIDv7`** (128-bit time-ordered UUIDs).

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                           unix_ts_ms                          |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|          unix_ts_ms           |  ver  |       rand_a          |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|var|                        rand_b                             |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                            rand_b                             |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

## Why `UUIDv7` Over `BIGINT` Auto-Increment or `UUIDv4`?
1. **B-Tree Index Locality (vs UUIDv4)**: `UUIDv4` is completely random, causing severe B-Tree page fragmentation and cache eviction on NeonDB. `UUIDv7` embeds a 48-bit millisecond timestamp prefix, ensuring sequential B-Tree append locality identical to `BIGINT`.
2. **Security & Offline Generation (vs BIGINT)**: `BIGINT` auto-increment IDs expose order volume metrics and are vulnerable to ID enumeration attacks. `UUIDv7` allows secure client/service side ID pre-generation without central database sequence lock contention.

---

# Master Schema & Module Ownership Matrix (28 Tables)

Every table MUST have exactly ONE owner module. Write access is restricted to the owner module's repository layer.

| Table Name | Owning Module | Primary Key | Foreign Key Rationales | Deletion Strategy | Concurrency & Write Path Assumptions |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`users`** | `auth` | `id` (UUIDv7) | None | Soft Delete (`deleted_at`) | Low concurrency writes; Unique index on `email` |
| **`customer_profiles`** | `customer` | `id` (UUIDv7) | FK $\rightarrow$ `users.id` (1:1 customer mapping) | Soft Delete (`deleted_at`) | Row-level locking on profile updates |
| **`merchants`** | `merchant` | `id` (UUIDv7) | FK $\rightarrow$ `users.id` (Owner account) | Soft Delete (`deleted_at`) | Administrative write path; Low concurrency |
| **`brands`** | `brand` | `id` (UUIDv7) | FK $\rightarrow$ `merchants.id` (Brand parent) | Soft Delete (`deleted_at`) | Multi-branch brand umbrella grouping |
| **`branches`** | `branch` | `id` (UUIDv7) | FK $\rightarrow$ `brands.id` (Branch brand) | Soft Delete (`deleted_at`) | Operating hours & store toggle updates |
| **`kitchens`** | `kitchen` | `id` (UUIDv7) | FK $\rightarrow$ `branches.id` (Branch kitchen) | Soft Delete (`deleted_at`) | 1:1 prep routing per branch initially |
| **`menus`** | `menu` | `id` (UUIDv7) | FK $\rightarrow$ `branches.id` (Branch catalog) | Soft Delete (`deleted_at`) | Catalog versioning; Low write / High read |
| **`menu_categories`** | `menu` | `id` (UUIDv7) | FK $\rightarrow$ `menus.id` (Category parent) | Hard Delete (Cascade) | Menu structure re-ordering |
| **`menu_items`** | `menu` | `id` (UUIDv7) | FK $\rightarrow$ `menu_categories.id` | Soft Delete (`deleted_at`) | Read-heavy; Price & metadata updates |
| **`menu_modifiers`** | `menu` | `id` (UUIDv7) | FK $\rightarrow$ `menu_items.id` | Hard Delete (Cascade) | Item customization options |
| **`inventory_items`** | `inventory` | `id` (UUIDv7) | FK $\rightarrow$ `branches.id`, FK $\rightarrow$ `menu_items.id` | Soft Delete (`deleted_at`) | High write concurrency; DineGuru exclusive write ([14-adrs/ADR-0006](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0006-inventory-ownership-write-rule.md)) |
| **`inventory_logs`** | `inventory` | `id` (UUIDv7) | FK $\rightarrow$ `inventory_items.id` | Append-Only (No Delete) | Immutable stock adjustment history |
| **`carts`** | `cart` | `id` (UUIDv7) | FK $\rightarrow$ `customer_profiles.id`, FK $\rightarrow$ `branches.id` | Hard Delete / Expiration TTL | High transient write concurrency; Guest session storage |
| **`cart_items`** | `cart` | `id` (UUIDv7) | FK $\rightarrow$ `carts.id`, FK $\rightarrow$ `menu_items.id` | Hard Delete | Frequent item addition/removal |
| **`orders`** | `order` | `id` (UUIDv7) | FK $\rightarrow$ `customer_profiles.id`, FK $\rightarrow$ `branches.id` | **Prohibited** (Immutable) | High write concurrency; `SELECT FOR UPDATE` during state updates |
| **`order_items`** | `order` | `id` (UUIDv7) | FK $\rightarrow$ `orders.id`, FK $\rightarrow$ `menu_items.id` | **Prohibited** (Immutable) | Locked snapshot of ordered dish prices & options |
| **`order_status_logs`** | `order` | `id` (UUIDv7) | FK $\rightarrow$ `orders.id` | Append-Only (No Delete) | Immutable order state transition history |
| **`payments`** | `payment` | `id` (UUIDv7) | FK $\rightarrow$ `orders.id`, FK $\rightarrow$ `customer_profiles.id` | **Prohibited** (Immutable) | Primary payment record ([14-adrs/ADR-0012](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0012-append-only-payment-ledger-and-refunds.md)) |
| **`payment_transactions`**| `payment` | `id` (UUIDv7) | FK $\rightarrow$ `payments.id` | Append-Only (No Delete) | Razorpay webhooks & refund ledger entries |
| **`coupons`** | `coupon` | `id` (UUIDv7) | Optional FK $\rightarrow$ `branches.id` | Soft Delete (`deleted_at`) | Global vs store coupon rules |
| **`coupon_redemptions`** | `coupon` | `id` (UUIDv7) | FK $\rightarrow$ `coupons.id`, FK $\rightarrow$ `customer_profiles.id` | Append-Only (No Delete) | Per-user redemption limit tracking |
| **`reviews`** | `review` | `id` (UUIDv7) | FK $\rightarrow$ `orders.id`, FK $\rightarrow$ `branches.id` | Soft Delete (`deleted_at`) | Verified order review constraint |
| **`customer_favorites`** | `customer` | `id` (UUIDv7) | FK $\rightarrow$ `customer_profiles.id`, FK $\rightarrow$ `branches.id` | Hard Delete | User preference toggles |
| **`customer_addresses`** | `customer` | `id` (UUIDv7) | FK $\rightarrow$ `customer_profiles.id` | Soft Delete (`deleted_at`) | Saved delivery addresses |
| **`merchant_subscriptions`**| `subscription`| `id` (UUIDv7) | FK $\rightarrow$ `merchants.id` | Soft Delete (`deleted_at`) | Recurring billing state |
| **`platform_commissions`**| `subscription`| `id` (UUIDv7) | FK $\rightarrow$ `orders.id`, FK $\rightarrow$ `merchants.id` | Append-Only (No Delete) | Per-order commission ledger |
| **`notifications`** | `notification`| `id` (UUIDv7) | FK $\rightarrow$ `users.id` | Hard Delete / Retention Purge| Dispatch log history |
| **`admin_audit_logs`** | `08-admin` | `id` (UUIDv7) | FK $\rightarrow$ `users.id` | Append-Only (7-yr mandatory) | Security & admin action audit log |

---

# Deletion Strategy Justification (Soft vs Hard vs Prohibited)

1. **Soft Delete (`deleted_at IS NOT NULL`)**: Used for business entities (`users`, `merchants`, `branches`, `menu_items`) where historical orders MUST preserve relationships even if the entity is deactivated.
2. **Hard Delete**: Used ONLY for transient or secondary records (`carts`, `cart_items`, `customer_favorites`) where deactivation has no regulatory or financial audit consequences.
3. **Prohibited / Append-Only**: Applied strictly to financial and transactional ledgers (`orders`, `payments`, `payment_transactions`, `platform_commissions`, `admin_audit_logs`). Records MUST NEVER be updated or deleted.
