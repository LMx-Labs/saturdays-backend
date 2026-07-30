# ADR-0002: SHARED POSTGRESQL DATABASE PATTERN

- **Status**: ACCEPTED  
- **Date**: 2026-07-30  
- **Author**: Chief Architect  
- **Scope**: Platform Data Layer & Persistence Architecture  

---

# Problem & Context

Saturdays (customer ordering surface) and DineGuru (merchant operational surface) are two separate web applications that must operate over identical business entity states (orders, menus, branch hours, inventory). 

A critical architectural decision is determining how persistence is structured between these two surfaces: whether to use a single shared relational database or separate databases with asynchronous synchronization layers.

---

# Options Considered

1. **Option A: Database-per-Application with Asynchronous API/Queue Sync**
   - Saturdays and DineGuru maintain independent databases; menu updates and new orders are synchronized asynchronously via Webhooks or Kafka message queues.
2. **Option B: Shared PostgreSQL Database Pattern**
   - Both Saturdays and DineGuru connect to a single shared PostgreSQL database instance hosted on NeonDB.
3. **Option C: Dual Write Pattern from Frontend Clients**
   - Web clients write data to both Saturdays and DineGuru backends simultaneously.

---

# Trade-Off Analysis

| Metric | Option A (Database-per-App) | Option B (Shared PostgreSQL) | Option C (Dual Write Clients) |
| :--- | :--- | :--- | :--- |
| **Data Consistency** | Low (Sync lag, out-of-order messages) | **Absolute** (ACID transactional single source of truth) | Low (Client network drop leads to divergence) |
| **Operational Complexity** | High (CDC pipelines, outbox pattern) | **Low** (Single database engine to operate) | High (Client retry complexity) |
| **Development Velocity** | Low (Duplicate schemas & sync glue) | **High** (Direct SQL schema queries) | Low |
| **Schema Coupling Risk** | Low | **Medium** (Managed via module table ownership) | High |

---

# Decision

The platform **MUST** utilize a **Shared PostgreSQL Database Pattern** (Option B). 

Both Saturdays and DineGuru application routes inside the unified FastAPI backend MUST read and write directly to a single shared PostgreSQL instance on NeonDB. Out-of-band asynchronous database sync layers and duplicate order/menu tables MUST NOT exist.

To mitigate schema coupling risks, database table ownership MUST be strictly enforced: every table has exactly ONE owning domain module inside `07-modules/` that manages schema migrations and write operations.

---

# Consequences

## Positive
- Guarantees immediate zero-latency visibility of new orders in DineGuru when placed on Saturdays.
- Eliminates complex CDC (Change Data Capture) synchronization pipelines and message queue infrastructure.
- Provides atomic cross-table transactions (e.g., updating order status and logging status history).

## Negative / Risks
- All application queries target a single PostgreSQL cluster; database performance degradation affects both customer and merchant surfaces. (Mitigated via NeonDB serverless scaling and index tuning).

---

# Alternatives Rejected

- **Option A (Database-per-App)**: Rejected because synchronization lag between menu updates in DineGuru and customer views in Saturdays creates inventory inconsistencies and ghost orders.
- **Option C (Dual Write Clients)**: Rejected due to catastrophic data divergence risks caused by partial client network failures.
