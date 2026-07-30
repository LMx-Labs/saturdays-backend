# 14-ADRS — ARCHITECTURE DECISION RECORDS

Version: 1.0  
Status: Authoritative ADR Registry Index  
Owner: Chief Architect & Staff Engineering Council  

---

# Purpose

The `14-adrs/` directory contains all formal Architecture Decision Records (ADRs) generated for Saturdays and DineGuru.

Every ADR captures a non-trivial architectural decision involving significant technical trade-offs, documenting the problem context, decision made, rejected alternatives, operational consequences, and long-term implications.

---

# Mandatory ADR Format

Every ADR MUST conform to the following standard section hierarchy:
1. **Title & Metadata**: Number, Working Title, Date, Status (`PROPOSED`, `ACCEPTED`, `REJECTED`, `SUPERSEDED`), Author.
2. **Problem & Context**: Business and technical drivers forcing an architectural decision.
3. **Options Considered**: Detailed analysis of all valid architectural options evaluated.
4. **Trade-off Analysis**: Comparison matrix evaluating performance, operational complexity, scalability, and maintainability.
5. **Decision**: Explicit statement of the chosen option using RFC 2119 normative language.
6. **Consequences**: Positive, negative, and neutral operational impacts of the decision.
7. **Alternatives Rejected**: Detailed explanation of why competing options were rejected.
8. **Future Evolution & Migration**: Guidelines for superseding or modifying this decision in future roadmap phases.

---

# Baseline Architecture Decision Records (ADR-0001 to ADR-0012)

| ADR ID | Decision Title | Status | Primary Bounded Context |
| :--- | :--- | :--- | :--- |
| [ADR-0001](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0001-modular-monolith-architecture.md) | Production-Grade Modular Monolith Architecture | `ACCEPTED` | Container Architecture |
| [ADR-0002](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0002-shared-postgresql-database.md) | Shared PostgreSQL Database Pattern | `ACCEPTED` | Data Layer & Persistence |
| [ADR-0003](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0003-merchant-brand-branch-kitchen-hierarchy.md) | 4-Tier Merchant Organizational Hierarchy | `ACCEPTED` | Merchant Bounded Context |
| [ADR-0004](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0004-multi-tenant-authentication-identity-strategy.md) | Multi-Tenant Identity & Auth Strategy | `ACCEPTED` | Auth Bounded Context |
| [ADR-0005](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0005-in-database-order-processing-model.md) | Real-Time In-Database Order Processing | `ACCEPTED` | Order Bounded Context |
| [ADR-0006](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0006-inventory-ownership-write-rule.md) | Exclusive DineGuru Inventory Write Rule | `ACCEPTED` | Inventory Bounded Context |
| [ADR-0007](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0007-in-process-domain-event-propagation.md) | In-Process Event Dispatcher Pattern | `ACCEPTED` | Domain Infrastructure |
| [ADR-0008](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0008-api-versioning-and-backward-compatibility.md) | URL Path API Versioning Protocol | `ACCEPTED` | API Architecture |
| [ADR-0009](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0009-deferred-redis-and-message-brokers.md) | Deferred Redis & External Message Brokers Policy | `ACCEPTED` | Infrastructure |
| [ADR-0010](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0010-real-time-websocket-architecture.md) | FastAPI WebSocket Store Alert Architecture | `ACCEPTED` | Notification & Orders |
| [ADR-0011](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0011-provider-agnostic-notification-architecture.md) | Provider-Agnostic Notification Adapter Pattern | `ACCEPTED` | Notification Bounded Context |
| [ADR-0012](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0012-append-only-payment-ledger-and-refunds.md) | Append-Only Payment Ledger & Refund Financial Model | `ACCEPTED` | Payment Bounded Context |
