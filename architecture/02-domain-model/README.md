# 02-DOMAIN-MODEL — BOUNDED CONTEXTS & DOMAIN INVARIANTS SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain Model Specifications Index  
Owner: Chief Architect & Domain Modeling Group  

---

# Purpose

The `02-domain-model/` directory establishes the formal Domain-Driven Design (DDD) model for the platform. 

It defines the boundaries of all 17 business domain contexts, maps aggregate root entities to single owner modules, specifies domain invariant rules, and establishes domain event contracts across the platform.

---

# Consolidated Specifications Index

1. [bounded-contexts-and-aggregates.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/02-domain-model/bounded-contexts-and-aggregates.md)
   * **Domain Bounded Context Boundaries**: Boundary definitions for all 17 functional business contexts.
   * **Aggregate Roots & Entities**: Definition of aggregate root boundaries, internal entity relationships, and aggregate ownership rules.
   * **Domain Ownership Matrix**: Authoritative matrix mapping every domain model to its single owning module.
2. [domain-invariants-and-events.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/02-domain-model/domain-invariants-and-events.md)
   * **Master Domain Invariants Registry**: Non-negotiable domain rules enforced by aggregate roots before state persistence.
   * **Domain Event Contracts**: Formal schemas and payload standards for in-process domain events published upon state transitions.

---

# Dependencies

- [01-business/business-model-and-monetization.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/01-business/business-model-and-monetization.md) — Business revenue and subscription logic.
- [14-adrs/ADR-0003](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0003-merchant-brand-branch-kitchen-hierarchy.md) — 4-tier merchant hierarchy.
- [14-adrs/ADR-0007](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0007-in-process-domain-event-propagation.md) — In-process event dispatcher.
