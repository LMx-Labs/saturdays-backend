# ADR-0005: IN-DATABASE ORDER PROCESSING MODEL

- **Status**: ACCEPTED  
- **Date**: 2026-07-30  
- **Author**: Chief Architect  
- **Scope**: Order Bounded Context & Real-Time Processing  

---

# Problem & Context

When a customer places an order on Saturdays, kitchen staff using DineGuru MUST receive immediate notification of the new order. 

The architecture MUST determine how orders are passed between Saturdays checkout routes and DineGuru order management interfaces without introducing polling lag or complex external message bus infrastructure.

---

# Options Considered

1. **Option A: External Message Broker Async Sync (Kafka / RabbitMQ)**
   - Orders published to an external message queue; DineGuru workers consume messages to populate local merchant order views.
2. **Option B: Real-Time In-Database Order Processing Model**
   - Customer checkout creates an order record directly in the shared PostgreSQL `orders` table within an atomic transaction. DineGuru queries the `orders` table directly, receiving instant state updates via WebSocket push alerts.

---

# Decision

The platform **MUST** execute orders using the **Real-Time In-Database Order Processing Model** (Option B). 

Orders created on Saturdays are written directly to PostgreSQL. Because DineGuru reads from the same database, the order is immediately visible without intermediate sync layers. Real-time alerting is delivered via WebSocket connections backed by PostgreSQL `LISTEN/NOTIFY`.

---

# Consequences

## Positive
- Guarantees 0-millisecond data synchronization lag between Saturdays and DineGuru.
- Prevents split-brain order states or lost messages caused by queue consumer failures.

## Negative / Risks
- Requires strict database connection pool management during peak campus dining hours.
