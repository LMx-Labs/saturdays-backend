# ADR-0009: DEFERRED REDIS & EXTERNAL MESSAGE BROKERS POLICY

- **Status**: ACCEPTED  
- **Date**: 2026-07-30  
- **Author**: Chief Architect  
- **Scope**: Infrastructure & Caching Policy  

---

# Problem & Context

Engineering teams often introduce Redis caching clusters and Kafka message brokers early in development under the assumption that they are necessary for "scalability". 

However, premature caching introduces cache invalidation bugs, stale state risks, and additional cloud infrastructure overhead. The platform requires a formal policy governing when caching and brokers MAY be introduced.

---

# Options Considered

1. **Option A: Include Redis & RabbitMQ in Baseline Architecture**
2. **Option B: Deferred Caching & Broker Policy (Postpone Until Quantified Triggers)**

---

# Decision

The platform **MUST** adopt a **Deferred Caching & External Message Brokers Policy** (Option B). 

Redis caching servers, Memcached, Kafka, RabbitMQ, and external search clusters MUST NOT be deployed in Version 1.0. All performance optimization MUST first utilize PostgreSQL index tuning, eager ORM loading, and query optimization.

Introduction of Redis or brokers MUST require a formal ADR demonstrating that:
1. PostgreSQL query optimization has been exhausted.
2. Production load metrics exceed $1,000$ sustained read requests/sec or $200$ write requests/sec.

---

# Consequences

## Positive
- Dramatically reduces cloud infrastructure costs, deployment complexity, and operational failure modes.
- Eliminates cache invalidation race conditions between DineGuru menu updates and Saturdays views.

## Negative / Risks
- Database CPU usage must be monitored closely during peak campus dining hours.
