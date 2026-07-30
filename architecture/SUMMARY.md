# SATURDAYS ARCHITECTURE REPOSITORY SUMMARY

Version: 1.0  
Status: Authoritative Master Table of Contents  
Platform Scope: Saturdays (Customer Surface) & DineGuru (Merchant Surface)  
Owner: Saturdays Engineering Team  

---

# Purpose

This document serves as the master navigation index and table of contents for the Saturdays Architecture Repository. 

It provides an organized map of every specification section, foundation document, domain model, system boundary, database schema, API specification, operational runbook, and Architecture Decision Record (ADR) across the entire platform.

---

# Root Navigation & Repository Tracking

| Document Path | Description / Purpose | Key Dependencies |
| :--- | :--- | :--- |
| [EXECUTION_PLAN.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/EXECUTION_PLAN.md) | Master architectural generation roadmap, directory tree, and quality gates. | Governing prompts |
| [PROJECT_STATE.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/PROJECT_STATE.md) | Live progress ledger, completed document metrics, and unresolved decision log. | EXECUTION_PLAN.md |
| [README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/README.md) | Master repository landing page, dual-surface platform scope, and domain ownership matrix.| EXECUTION_PLAN.md |
| [SUMMARY.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/SUMMARY.md) | Hierarchical table of contents and full repository file index. | README.md |
| [CONTRIBUTING.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/CONTRIBUTING.md) | Governance procedures for adding, modifying, and reviewing architecture specifications. | WORKFLOW.md prompt |
| [CHANGELOG.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/CHANGELOG.md) | Formal version history log of architectural decisions and repository updates. | Baseline setup |
| [GLOSSARY.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/GLOSSARY.md) | Canonical dictionary of all domain terminology, entity names, and acronyms. | PROJECT prompt |
| [ARCHITECTURE_PRINCIPLES.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/ARCHITECTURE_PRINCIPLES.md) | Non-negotiable engineering axioms (Explicit > Implicit, Explain WHY > HOW). | ROLE prompt |

---

# Section Specifications

## 00-foundation — Core Platform Foundation
*Location*: [00-foundation/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/00-foundation/README.md)  
*Purpose*: Defines baseline business vision, initial deployment context (VIT Vellore), non-goals, and core architectural style.

* [00-foundation/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/00-foundation/README.md) — Foundation section index and structural summary.
* [00-foundation/foundation-overview.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/00-foundation/foundation-overview.md) — Strategic vision, platform mission, ecosystem goals, and explicit non-goals.
* [00-foundation/architecture-and-quality-attributes.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/00-foundation/architecture-and-quality-attributes.md) — Modular Monolith rationale, hard system constraints, and quality attribute tradeoffs.

---

## 01-business — Business Models & User Journeys
*Location*: [01-business/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/01-business/README.md)  
*Purpose*: Specifies platform revenue streams, merchant/customer lifecycles, and marketplace policies.

* [01-business/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/01-business/README.md) — Business specifications index.
* [01-business/business-model-and-monetization.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/01-business/business-model-and-monetization.md) — Subscription plans (DineGuru), per-order commission calculations, and revenue settlement rules.
* [01-business/merchant-and-customer-journeys.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/01-business/merchant-and-customer-journeys.md) — Merchant onboarding lifecycle, customer ordering workflows, and cancellation/refund policies.

---

## 02-domain-model — Domain Bounded Contexts & Invariants
*Location*: [02-domain-model/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/02-domain-model/README.md)  
*Purpose*: Establishes Domain-Driven Design (DDD) bounded contexts, aggregate root boundaries, and domain rules.

* [02-domain-model/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/02-domain-model/README.md) — Domain model section index.
* [02-domain-model/bounded-contexts-and-aggregates.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/02-domain-model/bounded-contexts-and-aggregates.md) — Boundary definitions for all 17 business contexts, aggregate roots, and domain ownership matrix.
* [02-domain-model/domain-invariants-and-events.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/02-domain-model/domain-invariants-and-events.md) — Non-negotiable domain invariant rules and domain event contracts.

---

## 03-system — High-Level System Architecture
*Location*: [03-system/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03-system/README.md)  
*Purpose*: Outlines container architecture, internal component communication, and failure isolation boundaries.

* [03-system/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03-system/README.md) — System architecture section index.
* [03-system/system-architecture-and-boundaries.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03-system/system-architecture-and-boundaries.md) — High-level container layout, FastAPI in-process service boundaries, and communication protocols.
* [03-system/failure-and-isolation-boundaries.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03-system/failure-and-isolation-boundaries.md) — Failure boundaries, circuit breakers, fallback modes, and blast radius isolation.

---

## 03.5-non-functional — Dedicated Non-Functional Specifications
*Location*: [03.5-non-functional/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03.5-non-functional/README.md)  
*Purpose*: Formal specifications for SLAs, SLOs, latency targets, capacity bounds, disaster recovery, and compliance.

* [03.5-non-functional/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03.5-non-functional/README.md) — Non-functional requirements index.
* [03.5-non-functional/performance-scalability-and-sla.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03.5-non-functional/performance-scalability-and-sla.md) — p95/p99 latency budgets, DB query budgets, throughput limits, and SLOs/SLIs.
* [03.5-non-functional/resilience-disaster-recovery-and-security-nfrs.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03.5-non-functional/resilience-disaster-recovery-and-security-nfrs.md) — RTO/RPO targets, database backup strategies, failover bounds, and OWASP compliance rules.

---

## 04-backend — Backend Execution Framework
*Location*: [04-backend/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/04-backend/README.md)  
*Purpose*: Specifies technical execution rules for FastAPI, SQLAlchemy ORM, Dependency Injection, and transactions.

* [04-backend/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/04-backend/README.md) — Backend section index.
* [04-backend/fastapi-architecture-and-layering.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/04-backend/fastapi-architecture-and-layering.md) — FastAPI application setup, strict layer rules (Router $\rightarrow$ Service $\rightarrow$ Repository $\rightarrow$ DB), DI, and directory layout.
* [04-backend/concurrency-transactions-and-background-tasks.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/04-backend/concurrency-transactions-and-background-tasks.md) — Database transaction boundaries, atomic blocks, and async `BackgroundTasks` execution.

---

## 05-database — Shared Data Layer Specifications
*Location*: [05-database/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/README.md)  
*Purpose*: Documents shared PostgreSQL database philosophy, schema design across all 28 tables, indexes, and Alembic.

* [05-database/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/README.md) — Database section index.
* [05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md) — Shared persistence rules, table naming conventions, master ER model, and detailed 28-table specifications.
* [05-database/indexing-migrations-and-auditing.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/indexing-migrations-and-auditing.md) — B-Tree indexing strategy, zero-downtime Alembic migration rules, soft deletes (`deleted_at`), and immutable audit logging.

---

## 06-api — REST & Security Standards
*Location*: [06-api/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/06-api/README.md)  
*Purpose*: Defines API conventions, JWT/OAuth standards, RBAC authorization, error payloads, and rate limits.

* [06-api/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/06-api/README.md) — API standards index.
* [06-api/api-design-and-authentication.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/06-api/api-design-and-authentication.md) — REST URL standards, JSON conventions, JWT headers, Google OAuth callbacks, and URL versioning.
* [06-api/authorization-errors-and-rate-limiting.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/06-api/authorization-errors-and-rate-limiting.md) — Role-Based Access Control (RBAC) rules, standard error payload schema, cursor pagination, and rate limiting thresholds.

---

## 07-modules — Business Domain Modules (17 Bounded Contexts)
*Location*: [07-modules/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/README.md)  
*Purpose*: Deep architectural specifications for all 17 true business domain modules. Each module contains 3 rich consolidated specification files: `overview-and-architecture.md`, `domain-database-and-api.md`, and `workflows-and-state-machines.md`.

* [07-modules/auth/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/auth/README.md) — Identity, JWT, OAuth, Email OTP.
* [07-modules/customer/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/customer/README.md) — Customer profile, addresses, favorites, account lifecycle.
* [07-modules/merchant/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/merchant/README.md) — Merchant legal entity, onboarding, subscriptions, approval.
* [07-modules/brand/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/brand/README.md) — Brand identity, multi-branch umbrella management.
* [07-modules/branch/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/branch/README.md) — Physical store location, operating hours, geo-fencing.
* [07-modules/kitchen/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/kitchen/README.md) — Food preparation unit, kitchen workflow routing.
* [07-modules/menu/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/menu/README.md) — Catalog, categories, items, modifiers, pricing.
* [07-modules/inventory/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/inventory/README.md) — Stock availability, ingredient tracking (DineGuru write-exclusive).
* [07-modules/search/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/search/README.md) — Restaurant, dish, cuisine, distance, and availability search.
* [07-modules/cart/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/cart/README.md) — Customer shopping cart session and price calculation.
* [07-modules/checkout/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/checkout/README.md) — Pre-order validation, tax/fee calculation, order creation.
* [07-modules/order/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/order/README.md) — Order state machine, acceptance, kitchen preparation, ready/delivery states.
* [07-modules/payment/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/payment/README.md) — Razorpay integration, append-only payment transactions, refund ledgers.
* [07-modules/coupon/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/coupon/README.md) — Global/merchant coupons, eligibility validation, usage limits.
* [07-modules/review/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/review/README.md) — Restaurant and food ratings, moderation, feedback.
* [07-modules/notification/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/notification/README.md) — Email, Push, SMS, WhatsApp provider-agnostic dispatch engine.
* [07-modules/subscription/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/subscription/README.md) — Merchant platform subscriptions and commission calculation.

---

## 08-admin — Administration Operational Interfaces
*Location*: [08-admin/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/08-admin/README.md)  
*Purpose*: Consolidates operational administrative portals, merchant verification, refund approvals, CMS, and feature flags.

* [08-admin/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/08-admin/README.md) — Admin interface index.
* [08-admin/admin-architecture-and-operations.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/08-admin/admin-architecture-and-operations.md) — Internal admin architecture, merchant onboarding verification, customer moderation, and refund workflows.
* [08-admin/admin-cms-flags-and-audit.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/08-admin/admin-cms-flags-and-audit.md) — Banner CMS management, dynamic feature flags, and administrative audit log monitoring.

---

## 09-security — Platform Security & Compliance
*Location*: [09-security/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/09-security/README.md)  
*Purpose*: Specifies threat modeling, trust boundaries, encryption, secrets management, and compliance rules.

* [09-security/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/09-security/README.md) — Security section index.
* [09-security/threat-model-and-rbac.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/09-security/threat-model-and-rbac.md) — STRIDE threat model, trust boundaries, and platform-wide RBAC role matrix.
* [09-security/secrets-encryption-and-compliance.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/09-security/secrets-encryption-and-compliance.md) — Secrets management, field-level data encryption, key rotation, and OWASP audit rules.

---

## 10-observability — Logging, Metrics & Alerting
*Location*: [10-observability/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/10-observability/README.md)  
*Purpose*: Defines structured logging schemas, metric emission, health check probes, and operational alert triggers.

* [10-observability/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/10-observability/README.md) — Observability index.
* [10-observability/logging-metrics-and-slas.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/10-observability/logging-metrics-and-slas.md) — JSON log schema, request tracing, SLA/SLO metric counters, and latency percentiles.
* [10-observability/health-checks-and-alerting.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/10-observability/health-checks-and-alerting.md) — Liveness/readiness health probes, error budget consumption alerts, and operational escalation rules.

---

## 11-devops — Infrastructure & Operations
*Location*: [11-devops/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/11-devops/README.md)  
*Purpose*: Covers CI/CD automation, deployment topology, database migration workflows, and disaster recovery.

* [11-devops/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/11-devops/README.md) — DevOps section index.
* [11-devops/ci-cd-and-deployments.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/11-devops/ci-cd-and-deployments.md) — GitHub Actions CI/CD pipelines, container building, zero-downtime deployment strategy, and rollback rules.
* [11-devops/database-ops-and-disaster-recovery.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/11-devops/database-ops-and-disaster-recovery.md) — NeonDB automated backups, point-in-time recovery (PITR), schema migration pipelines, and disaster recovery protocols.

---

## 12-testing — Quality Assurance & Testing Strategy
*Location*: [12-testing/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/12-testing/README.md)  
*Purpose*: Outlines unit, integration, and API contract testing specifications across all modules.

* [12-testing/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/12-testing/README.md) — Testing section index.
* [12-testing/testing-strategy-and-contracts.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/12-testing/testing-strategy-and-contracts.md) — Pytest testing setup, database transaction isolation in tests, API contract tests, and mock strategies.

---

## 13-runbooks — Operational Incident Runbooks
*Location*: [13-runbooks/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/13-runbooks/README.md)  
*Purpose*: Actionable step-by-step procedures for handling production failures and operational incidents.

* [13-runbooks/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/13-runbooks/README.md) — Runbook directory index.
* [13-runbooks/system-outages-and-failover.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/13-runbooks/system-outages-and-failover.md) — Runbooks for database connection pool exhaustion, restaurant offline alerts, and backend pod crash loops.
* [13-runbooks/payment-and-refund-reconciliation.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/13-runbooks/payment-and-refund-reconciliation.md) — Runbooks for Razorpay webhook downtime, failed payment reconciliation, and manual refund overrides.

---

## 14-adrs — Architecture Decision Records
*Location*: [14-adrs/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/README.md)  
*Purpose*: Documents non-trivial architectural decisions, tradeoffs, rejected alternatives, and consequences.

* [14-adrs/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/README.md) — ADR directory index.
* [14-adrs/ADR-0001-modular-monolith-architecture.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0001-modular-monolith-architecture.md) — Decision record for Production-Grade Modular Monolith architecture.
* [14-adrs/ADR-0002-shared-postgresql-database.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0002-shared-postgresql-database.md) — Decision record for shared Postgres database between Saturdays and DineGuru.
* [14-adrs/ADR-0003-merchant-brand-branch-kitchen-hierarchy.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0003-merchant-brand-branch-kitchen-hierarchy.md) — Decision record for 4-tier merchant organizational structure.
* [14-adrs/ADR-0004-multi-tenant-authentication-identity-strategy.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0004-multi-tenant-authentication-identity-strategy.md) — Decision record for multi-tenant JWT & OAuth identity management.
* [14-adrs/ADR-0005-in-database-order-processing-model.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0005-in-database-order-processing-model.md) — Decision record for real-time in-database order visibility.
* [14-adrs/ADR-0006-inventory-ownership-write-rule.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0006-inventory-ownership-write-rule.md) — Decision record for DineGuru exclusive inventory write access.
* [14-adrs/ADR-0007-in-process-domain-event-propagation.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0007-in-process-domain-event-propagation.md) — Decision record for in-process event dispatcher over external brokers.
* [14-adrs/ADR-0008-api-versioning-and-backward-compatibility.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0008-api-versioning-and-backward-compatibility.md) — Decision record for URL path versioning protocol.
* [14-adrs/ADR-0009-deferred-redis-and-message-brokers.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0009-deferred-redis-and-message-brokers.md) — Decision record for postponing Redis/Kafka infrastructure in initial MVP.
* [14-adrs/ADR-0010-real-time-websocket-architecture.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0010-real-time-websocket-architecture.md) — Decision record for WebSocket connection handling in FastAPI.
* [14-adrs/ADR-0011-provider-agnostic-notification-architecture.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0011-provider-agnostic-notification-architecture.md) — Decision record for provider-agnostic notification adapter pattern.
* [14-adrs/ADR-0012-append-only-payment-ledger-and-refunds.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0012-append-only-payment-ledger-and-refunds.md) — Decision record for immutable payment transactions and refund ledgers.

---

## 15-roadmap — Platform Evolution Roadmap
*Location*: [15-roadmap/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/15-roadmap/README.md)  
*Purpose*: Maps platform evolution across 4 distinct phases (VIT Vellore launch through multi-city and AI search).

* [15-roadmap/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/15-roadmap/README.md) — Roadmap section index.
* [15-roadmap/multi-phase-evolution-roadmap.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/15-roadmap/multi-phase-evolution-roadmap.md) — Phase 1 (VIT Vellore), Phase 2 (Multi-City), Phase 3 (Rider Subsystem), Phase 4 (AI Search & Recommendations).

---

## diagrams — Visual Architecture Diagrams
*Location*: [diagrams/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/diagrams/README.md)  
*Purpose*: Houses standalone Mermaid (`.mmd`) visual source files for all system models.

* [diagrams/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/diagrams/README.md) — Diagrams directory index.
* [diagrams/system-context.mmd](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/diagrams/system-context.mmd) — High-level system context diagram.
* [diagrams/component-architecture.mmd](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/diagrams/component-architecture.mmd) — FastAPI component architecture diagram.
* [diagrams/database-er.mmd](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/diagrams/database-er.mmd) — Entity-Relationship diagram across all 28 tables.
* [diagrams/order-state-machine.mmd](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/diagrams/order-state-machine.mmd) — Order lifecycle state diagram.
* [diagrams/payment-state-machine.mmd](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/diagrams/payment-state-machine.mmd) — Payment transaction state diagram.
* [diagrams/cart-checkout-sequence.mmd](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/diagrams/cart-checkout-sequence.mmd) — Cart and checkout flow sequence diagram.
* [diagrams/order-fulfillment-sequence.mmd](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/diagrams/order-fulfillment-sequence.mmd) — Order placement to kitchen prep sequence diagram.
* [diagrams/deployment-infrastructure.mmd](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/diagrams/deployment-infrastructure.mmd) — Container deployment and NeonDB topology diagram.

---

## appendices — Reference Tables & Error Registries
*Location*: [appendices/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/appendices/README.md)  
*Purpose*: Centralized lookup tables for platform error codes, HTTP status mappings, and configuration keys.

* [appendices/README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/appendices/README.md) — Appendices index.
* [appendices/reference-tables-and-error-registry.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/appendices/reference-tables-and-error-registry.md) — Master error code registry, HTTP status code mappings, and system environment key documentation.
