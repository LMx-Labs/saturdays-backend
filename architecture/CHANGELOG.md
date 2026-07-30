# SATURDAYS ARCHITECTURE CHANGELOG

All notable changes to the Saturdays & DineGuru Architecture Repository are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this repository adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0-RC1] - 2026-07-30

### Added
- **Complete Architecture Specification Baseline (v1.0 RC1)**: 116 consolidated specification documents covering platform foundation, domain models, backend execution, database schemas, REST APIs, 17 domain modules, security, observability, DevOps, testing, admin tools, runbooks, and evolution roadmap.
- **Master Baseline ADR Suite**: Authored ADR-0001 through ADR-0012 establishing Modular Monolith architecture, shared NeonDB PostgreSQL database, 4-tier merchant hierarchy, multi-tenant auth, in-database order processing, and append-only payment ledgers.
- **Formal Architectural Decision Resolutions**:
  - Resolved Decision #1: Adopted `UUIDv7` as platform-wide primary key standard for B-Tree index performance ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).
  - Resolved Decision #2: Adopted PostgreSQL `LISTEN/NOTIFY` + WebSockets for real-time order alerts ([07-modules/order/overview-and-architecture.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/order/overview-and-architecture.md)).
  - Resolved Decision #3: Adopted Pessimistic Row Locking (`SELECT FOR UPDATE`) for high-concurrency stock reservation ([07-modules/inventory/overview-and-architecture.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/inventory/overview-and-architecture.md)).
  - Resolved Decision #4: Adopted automated 7-day TTL database cleanup for transient cart states ([07-modules/cart/domain-database-and-api.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/cart/domain-database-and-api.md)).
  - Resolved Decision #5: Defined quantitative performance triggers for post-MVP adoption of Redis ($> 1,000\text{ req/sec}$), Kafka ($> 200\text{ req/sec}$), and Elasticsearch ($> 100,000\text{ items}$) in [15-roadmap/multi-phase-evolution-roadmap.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/15-roadmap/multi-phase-evolution-roadmap.md).
- **Automated Architectural Fitness Functions**: Created [12-testing/architecture-fitness-functions.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/12-testing/architecture-fitness-functions.md) specifying 10 automated CI tests enforcing single table/aggregate/API ownership, zero cross-repository imports, and 0 TODO placeholders.
