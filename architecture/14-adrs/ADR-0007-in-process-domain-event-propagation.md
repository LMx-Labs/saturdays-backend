# ADR-0007: IN-PROCESS DOMAIN EVENT PROPAGATION STRATEGY

- **Status**: ACCEPTED  
- **Date**: 2026-07-30  
- **Author**: Chief Architect  
- **Scope**: Domain Infrastructure & Module Communication  

---

# Problem & Context

When domain events occur (e.g. `OrderPlaced`, `PaymentVerified`, `MerchantOnboarded`), secondary actions MUST be triggered (e.g. sending email notifications, updating status logs). 

The architecture MUST establish an event propagation model that preserves module decoupling without introducing external message broker infrastructure (Kafka, RabbitMQ).

---

# Options Considered

1. **Option A: External Message Broker Event Bus (Kafka / RabbitMQ)**
   - Events published to external message queue infrastructure.
2. **Option B: In-Process Domain Event Dispatcher Pattern**
   - Events published to an in-process Python async event bus inside FastAPI, triggering synchronous subscribers or FastAPI `BackgroundTasks`.

---

# Decision

The platform **MUST** utilize an **In-Process Domain Event Dispatcher Pattern** (Option B). 

Domain events are published to an in-memory event dispatcher within the FastAPI application instance. Subscribers execute in-process or enqueue non-blocking async tasks using FastAPI's `BackgroundTasks`.

---

# Consequences

## Positive
- Decouples publishing modules from consuming modules without external operational dependencies.
- Eliminates message serialization overhead and broker maintenance costs.

## Negative / Risks
- In-memory events are volatile if the Python process crashes before a background task executes. (Critical side-effects, such as payment verification, MUST be persisted transactionally in PostgreSQL before event publication).
