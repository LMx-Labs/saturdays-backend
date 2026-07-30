# ARCHITECTURE STYLE & QUALITY ATTRIBUTES

Version: 1.0  
Status: Authoritative Architectural Trade-Off Specification  
Owner: Chief Architect & Staff Engineering Council  

---

# Purpose

This document specifies the core architectural pattern (Production-Grade Modular Monolith), system-wide technical constraints, and quality attribute trade-offs governing the Saturdays and DineGuru platform.

---

# Architectural Pattern — Production-Grade Modular Monolith

The platform is designed as a **Production-Grade Modular Monolith**. The application is packaged, deployed, and operated as a single FastAPI process container backed by a single PostgreSQL database instance on NeonDB.

```mermaid
flowchart LR
    subgraph FastAPI Monolithic Process Container
        direction TB
        subgraph Domain Modules Layer
            M1[auth]
            M2[customer]
            M3[merchant]
            M4[menu]
            M5[inventory]
            M6[order]
            M7[payment]
        end
        
        M1 <-->|In-Process Service Call| M2
        M6 <-->|In-Process Service Call| M5
        M6 <-->|In-Process Service Call| M7
    end

    FastAPI Monolithic Process Container -->|SQLAlchemy Connection Pool| DB[(Shared PostgreSQL Database)]
```

## Why Modular Monolith Over Microservices?
1. **Operational Simplicity**: At the target scale of 100–500 restaurants and 20,000+ users, the operational complexity of distributed microservices (distributed tracing, network latency overhead, k8s cluster orchestration, saga pattern rollbacks) vastly outweighs its benefits.
2. **Zero-Lag Shared Persistence**: Saturdays and DineGuru share exact business entity states (orders, menus, inventory). A monolithic backend accessing PostgreSQL directly eliminates event propagation lag and duplicate sync code.
3. **Future Extraction Capability**: Modules inside `07-modules/` are strictly decoupled. Domain modules communicate *only* through in-process service interfaces (`Service` layer), never by directly importing or modifying another module's ORM models. This ensures any module can be extracted into an independent microservice in future roadmap phases without rewriting domain logic.

---

# System Constraints

1. **Technology Stack Bounds**:
   * Backend: Python 3.11+, FastAPI framework, SQLAlchemy ORM, Alembic migrations.
   * Database: PostgreSQL 15+ hosted on NeonDB (serverless Postgres).
   * Frontend: React web applications for both Saturdays and DineGuru.
   * Payments: Razorpay payment gateway integration.
2. **Infrastructure Constraints**:
   * No Redis, Memcached, Kafka, or RabbitMQ MUST be deployed in the initial MVP release.
   * Background asynchronous processing MUST utilize FastAPI's native `BackgroundTasks` runner or in-database state flags.
3. **Persistence Constraints**:
   * The database is shared between Saturdays and DineGuru.
   * Every database table MUST have exactly ONE owner module enforcing write permissions.

---

# Quality Attributes & Architectural Trade-offs

| Quality Attribute | Target Metric | Architectural Strategy & Trade-off |
| :--- | :--- | :--- |
| **Maintainability** | 15+ year operational lifespan | **Trade-off**: Strict in-process module boundaries enforced over quick cross-module database joins. High initial discipline reduces long-term technical debt. |
| **Performance (Latency)** | API p95 $< 200\text{ms}$; DB queries $< 20\text{ms}$ | **Trade-off**: Relies on tuned PostgreSQL B-Tree indexes and eager loading rather than introducing external Redis caching clusters. Reduces infra ops. |
| **Availability** | 99.9% Uptime (Target) | **Trade-off**: Relies on NeonDB multi-AZ serverless storage resilience and stateless FastAPI container restarts rather than complex multi-region active-active clusters. |
| **Data Consistency** | ACID Transactional Guarantees | **Trade-off**: Atomic PostgreSQL transactions prevent partial order/inventory updates, sacrificing distributed eventual consistency paradigms. |
| **Simplicity** | Minimal cloud infra footprint | **Trade-off**: Rejects microservices, event streaming brokers (Kafka), and NoSQL stores in favor of a single relational database engine. |
