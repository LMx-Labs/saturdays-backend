# SATURDAYS ENGINEERING ARCHITECTURE REPOSITORY

Version: 1.0  
Status: Authoritative Master Index  
Platform Scope: Saturdays (Customer Surface) & DineGuru (Merchant Surface)  
Owner: Saturdays Engineering Team  

---

# Purpose

This repository is the canonical engineering specification for the Saturdays platform and its integrated merchant companion, DineGuru. 

It defines the absolute technical source of truth for all platform architecture, domain bounded contexts, database models, API contracts, security mechanisms, non-functional requirements, operational runbooks, and architectural decision records (ADRs).

This repository is NOT marketing material, developer onboarding tutorials, or superficial implementation notes. It is a formal engineering specification designed to survive 15+ years of software evolution. It provides sufficient detail to allow an engineering team to rebuild, extend, maintain, or audit the entire platform without relying on tribal knowledge or original authors.

---

# Scope

## Included
- **Dual Application Surfaces**: Full architectural specification for both Saturdays (customer-facing React web app) and DineGuru (merchant-facing React web app).
- **Unified Backend Service**: Production-grade Modular Monolith built with FastAPI (Python) serving both applications.
- **Shared Data Layer**: Single PostgreSQL instance hosted on NeonDB acting as the single source of truth for both user surfaces.
- **Organizational Hierarchy**: Complete specifications for `Merchant` $\rightarrow$ `Brand` $\rightarrow$ `Branch` $\rightarrow$ `Kitchen` multi-tenant entities.
- **Domain Modules**: Detailed domain specifications across all 17 core business modules (Authentication, Customer, Merchant, Brand, Branch, Kitchen, Menu, Inventory, Search, Cart, Checkout, Order, Payment, Coupon, Review, Notification, Subscription).
- **Platform Governance**: Security threat models, RBAC matrices, non-functional targets (SLAs/SLOs/RTO/RPO), observability standards, CI/CD, and operational incident runbooks.

## Excluded (Initial Scope Boundaries)
- **Delivery Rider Subsystem**: Rider dispatch, routing algorithms, and driver apps are deferred; extension points are documented in [15-roadmap/multi-phase-evolution-roadmap.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/15-roadmap/multi-phase-evolution-roadmap.md).
- **AI Recommendation Engine**: Natural language dish search and personalized ML recommendations are deferred to post-MVP roadmap phases.
- **Customer Subscriptions & Wallets**: Native platform wallets and consumer subscription passes are excluded from the initial release.

---

# Dependencies

This specification depends on the foundational governing documents established in the project prompts:
1. [01_ROLE.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/prompts/01_ROLE.md) — Chief Architect mandate and 15-year survival requirement.
2. [02_PROJECT.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/prompts/02_PROJECT.md) — Saturdays Project Constitution & Business Vision.
3. [03_DOCUMENT_REQUIREMENTS.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/prompts/03_DOCUMENT_REQUIREMENTS.md) — Mandatory structural sections for all engineering documents.
4. [04_WORKFLOW.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/prompts/04_WORKFLOW.md) — Anti-drift lifecycle and review workflow.
5. [05_OUTPUT_STRUCTURE.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/prompts/05_OUTPUT_STRUCTURE.md) — Master repository directory tree definition.
6. [06_GENERATION_RULES.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/prompts/06_GENERATION_RULES.md) — Specification writing and quality rules.
7. [08_REVIEWER.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/prompts/08_REVIEWER.md) — Mandatory quality gate audit framework.
8. [09_DECISIONS.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/prompts/09_DECISIONS.md) — Locked platform technology and architectural decisions.
9. [10_STYLE_GUIDE.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/prompts/10_STYLE_GUIDE.md) — RFC 2119 language standards and naming conventions.
10. [11_ARCHITECT_CHECKLIST.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/prompts/11_ARCHITECT_CHECKLIST.md) — Definition of Done checklist.

---

# Ownership & Governance

Every concept, table, API endpoint, and business invariant in this platform MUST have exactly one authoritative owner module. Duplicated business logic or split ownership across modules is strictly forbidden.

| Domain Area | Authoritative Module | Authoritative Specification File |
| :--- | :--- | :--- |
| **Authentication & Identity** | `auth` | [07-modules/auth/overview-and-architecture.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/auth/overview-and-architecture.md) |
| **Customer Profiles & Favorites**| `customer` | [07-modules/customer/overview-and-architecture.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/customer/overview-and-architecture.md) |
| **Merchant Legal & Billing** | `merchant` | [07-modules/merchant/overview-and-architecture.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/merchant/overview-and-architecture.md) |
| **Physical Locations & Hours** | `branch` | [07-modules/branch/overview-and-architecture.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/branch/overview-and-architecture.md) |
| **Catalog, Categories & Items** | `menu` | [07-modules/menu/overview-and-architecture.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/menu/overview-and-architecture.md) |
| **Stock & Item Availability** | `inventory` (DineGuru)| [07-modules/inventory/overview-and-architecture.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/inventory/overview-and-architecture.md) |
| **Order Processing & States** | `order` | [07-modules/order/overview-and-architecture.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/order/overview-and-architecture.md) |
| **Payments & Transactions** | `payment` | [07-modules/payment/overview-and-architecture.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/payment/overview-and-architecture.md) |
| **Administrative Operations** | `08-admin` | [08-admin/admin-architecture-and-operations.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/08-admin/admin-architecture-and-operations.md) |

---

# Core Architectural Principles

1. **Explain WHY Before HOW**: Every architectural choice MUST document the problem context, trade-off evaluation, and justification before explaining implementation details.
2. **Single Source of Truth**: Saturdays and DineGuru access a single PostgreSQL database. Data synchronization layers, duplicate order tables, and redundant message queues MUST NOT exist.
3. **Strict Domain Isolation**: The platform is implemented as a Production-Grade Modular Monolith. Business modules communicate in-process through explicit service interfaces. Modules MUST NOT directly manipulate database models owned by another module.
4. **Operations-First Resilience**: Failure modes, rate limits, circuit breakers, and degraded states MUST be documented before happy-path workflows.
5. **No Unquantified Buzzwords**: Claims of performance, scalability, or availability MUST be backed by explicit quantitative targets in [03.5-non-functional/performance-scalability-and-sla.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03.5-non-functional/performance-scalability-and-sla.md).

---

# Repository Navigation & Structure

To navigate the specification repository, consult the core index files and directory sections below:

### Governance & Meta Specifications
- [EXECUTION_PLAN.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/EXECUTION_PLAN.md) — Master implementation roadmap and progress tracking.
- [PROJECT_STATE.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/PROJECT_STATE.md) — Live real-time status ledger updated after every file generation.
- [SUMMARY.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/SUMMARY.md) — Complete hierarchical document table of contents.
- [GLOSSARY.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/GLOSSARY.md) — Canonical dictionary of domain terminology and acronyms.
- [ARCHITECTURE_PRINCIPLES.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/ARCHITECTURE_PRINCIPLES.md) — Baseline engineering axioms.
- [CONTRIBUTING.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/CONTRIBUTING.md) — Architectural governance and update guidelines.

### Specification Sections
- [00-foundation/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/00-foundation/README.md) — Vision, business constraints, and modular monolith architecture style.
- [01-business/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/01-business/README.md) — Business revenue model, merchant/customer journeys, and operational policies.
- [02-domain-model/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/02-domain-model/README.md) — Bounded contexts, aggregate root definitions, and core domain invariants.
- [03-system/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03-system/README.md) — High-level container layout, component boundaries, and isolation policies.
- [03.5-non-functional/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03.5-non-functional/README.md) — Latency budgets, SLAs, SLOs/SLIs, RTO/RPO, and security targets.
- [04-backend/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/04-backend/README.md) — FastAPI layered architecture, dependency injection, and background tasks.
- [05-database/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/README.md) — PostgreSQL schema design across all 28 tables, indexes, and Alembic migrations.
- [06-api/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/06-api/README.md) — REST standards, JWT/OAuth auth headers, RBAC matrices, and error codes.
- [07-modules/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/README.md) — Deep specifications across all 17 true business domain modules.
- [08-admin/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/08-admin/README.md) — Operational administration, customer moderation, CMS, and feature flags.
- [09-security/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/09-security/README.md) — Threat models, encryption specifications, and OWASP compliance rules.
- [10-observability/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/10-observability/README.md) — Structured logging schemas, metrics, health probes, and alerting rules.
- [11-devops/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/11-devops/README.md) — CI/CD pipelines, deployment topology, and disaster recovery.
- [12-testing/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/12-testing/README.md) — Unit, integration, and contract testing requirements.
- [13-runbooks/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/13-runbooks/README.md) — Operational incident response procedures and failover protocols.
- [14-adrs/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/README.md) — Formal Architecture Decision Records (ADR-0001 through ADR-0012).
- [15-roadmap/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/15-roadmap/README.md) — Multi-phase platform evolution roadmap.
- [diagrams/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/diagrams/README.md) — Mermaid source files for context, ER, sequence, and state diagrams.
- [appendices/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/appendices/README.md) — Reference tables, status codes, and error registries.

---

# Maintenance & Change Policy

This repository is a living specification under strict version control. Any proposed architectural modification MUST follow the decision process defined in [CONTRIBUTING.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/CONTRIBUTING.md):
1. **No Silent Changes**: Decisions locked in [09_DECISIONS.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/prompts/09_DECISIONS.md) or approved ADRs MUST NOT be altered without creating a new ADR justifying the change.
2. **Cascading Updates**: If an architectural decision is modified, all dependent module specs, ER diagrams, state machines, and sequence diagrams MUST be updated in the same pull request.
3. **Zero Inconsistency**: Ambiguous or conflicting specifications MUST be resolved immediately by updating the authoritative source file.
