# ADR-0010: REAL-TIME WEBSOCKET STORE ALERT ARCHITECTURE

- **Status**: ACCEPTED  
- **Date**: 2026-07-30  
- **Author**: Chief Architect  
- **Scope**: Communication & Notification Architecture  

---

# Problem & Context

Kitchen staff using DineGuru MUST receive real-time audio-visual alerts when a new order is placed on Saturdays, without constantly polling the backend via REST endpoints.

The architecture MUST establish a real-time push mechanism within the constraints of the FastAPI framework and PostgreSQL database (without external message brokers).

---

# Options Considered

1. **Option A: HTTP Client Polling (`GET /api/v1/orders/pending` every 5 seconds)**
2. **Option B: FastAPI WebSockets with PostgreSQL `LISTEN/NOTIFY` Pub/Sub**
3. **Option C: External Push Service (Firebase Cloud Messaging)**

---

# Decision

The platform **MUST** utilize **FastAPI WebSockets backed by PostgreSQL `LISTEN/NOTIFY`** (Option B). 

1. DineGuru web clients establish a persistent WebSocket connection to `/api/v1/ws/branches/{id}/orders`.
2. When a customer places an order, the PostgreSQL transaction executes `NOTIFY order_channel, '{"branch_id": ...}'`.
3. The FastAPI process container listens to `order_channel` via `asyncpg` and broadcasts the order alert payload over active WebSockets to connected DineGuru clients for that branch.

---

# Consequences

## Positive
- Provides sub-100ms real-time order alerts to kitchen staff.
- Replaces wasteful HTTP polling requests, reducing database read load.

## Negative / Risks
- In multi-pod container deployments, PostgreSQL `LISTEN/NOTIFY` acts as the central cross-pod broadcast bus, requiring careful connection management.
