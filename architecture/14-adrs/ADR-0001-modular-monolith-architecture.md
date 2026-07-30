# ADR-0001: PRODUCTION-GRADE MODULAR MONOLITH ARCHITECTURE

- **Status**: ACCEPTED  
- **Date**: 2026-07-30  
- **Author**: Chief Architect  
- **Scope**: Platform Container Architecture  

---

# Problem & Context

Saturdays and DineGuru require a robust, maintainable backend architecture to handle restaurant management, customer food ordering, menu browsing, inventory tracking, and payment processing. 

A key engineering decision is selecting the container deployment pattern: whether to build a distributed microservices architecture or a monolithic application. The architecture MUST comfortably scale to 500 restaurants, 20,000+ users, and 50 orders/sec at VIT Vellore while remaining operationally manageable for a lean engineering team.

---

# Options Considered

1. **Option A: Distributed Microservices Architecture**
   - Independent microservice deployments per business domain (`auth-service`, `catalog-service`, `order-service`, `payment-service`) communicating over gRPC / HTTP REST APIs with independent per-service databases.
2. **Option B: Production-Grade Modular Monolith Architecture**
   - Single FastAPI process container housing decoupled business modules (`07-modules/`) communicating via in-process Python service interfaces and sharing a single PostgreSQL database instance on NeonDB.
3. **Option C: Unstructured Monolith**
   - Single process container with inter-mingled code, shared global helpers, and direct cross-domain database ORM imports.

---

# Trade-Off Analysis

| Architectural Metric | Option A (Microservices) | Option B (Modular Monolith) | Option C (Unstructured Monolith) |
| :--- | :--- | :--- | :--- |
| **Operational Complexity** | High (K8s, service mesh, distributed tracing) | **Low** (Single container deployment) | Low |
| **Data Consistency** | Low (Eventual consistency, Saga patterns) | **High** (ACID PostgreSQL transactions) | High |
| **Network Latency Overhead**| High (Inter-service RPC network hops) | **Zero** (In-process memory calls) | Zero |
| **Code Isolation** | High (Hard network boundaries) | **High** (Strict layer rules & module interfaces) | Low (Spaghetti coupling) |
| **Extractability** | N/A | **High** (Clean interfaces allow microservice extraction) | Low (Rewrite required) |

---

# Decision

The Saturdays platform **MUST** be implemented as a **Production-Grade Modular Monolith** (Option B). 

All backend capabilities MUST be deployed inside a single FastAPI application container. Domain modules MUST maintain strict isolation by communicating through in-process service interfaces (`Service` layer) and MUST NOT directly access ORM models owned by other modules.

---

# Consequences

## Positive
- Minimizes operational infrastructure overhead and deployment complexity.
- Guarantees ACID transactional consistency across multi-entity operations (e.g. order creation and inventory allocation).
- Eliminates network hop latency between internal business domains.

## Negative / Risks
- All modules share container CPU and memory resources; a memory leak in one module impacts the entire container. (Mitigated via automated health checks and stateless pod restarts).

---

# Alternatives Rejected

- **Option A (Microservices)**: Rejected because distributed system operational overhead (distributed transactions, network failure modes, microservice cluster maintenance) is unjustified for the initial scale targets of 500 restaurants and 20,000 users.
- **Option C (Unstructured Monolith)**: Rejected due to severe technical debt risk, boundary erosion, and inability to extract services in future roadmap phases.

---

# Future Evolution & Migration

If future throughput metrics exceed monolithic container limits (e.g. multi-city expansion reaching 10,000+ orders/sec), high-load modules (such as `search` or `notification`) MAY be extracted into independent microservices by wrapping their existing in-process service interfaces into gRPC / REST endpoints without rewriting internal domain logic.
