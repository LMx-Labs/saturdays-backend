# 05-DATABASE — SHARED DATABASE ARCHITECTURE SPECIFICATIONS

Version: 1.0  
Status: Authoritative Database Architecture Specification Index  
Owner: Chief Architect & Lead Database Engineer  

---

# Purpose

The `05-database/` directory defines the relational database architecture, shared persistence rules, table naming conventions, primary key strategy, full 28-table schema design, foreign key rationales, index strategies, Alembic migration standards, soft deletion rules, and audit logging specifications for Saturdays and DineGuru.

It establishes PostgreSQL hosted on NeonDB as the platform's single source of truth ([14-adrs/ADR-0002](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0002-shared-postgresql-database.md)).

---

# Consolidated Specifications Index

1. [database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)
   * **Shared Database Governance**: Zero-lag persistence sharing rules between Saturdays and DineGuru; single table owner assignments.
   * **Primary Key Strategy Resolution**: Formal resolution adopting `UUIDv7` as the platform-wide primary key standard for B-Tree index performance.
   * **Complete 28-Table Relational Schema**: Detailed specifications for all 28 schema tables, including business rationale, owning module, and foreign key justification.
2. [indexing-migrations-and-auditing.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/indexing-migrations-and-auditing.md)
   * **Indexing Strategy**: Primary B-Tree indexes, composite query indexes, and unique constraints.
   * **Alembic Migration Pipeline**: Versioned schema migration procedures, zero-downtime DDL rules, and rollback safety.
   * **Soft Delete vs Hard Purge**: Justification for `deleted_at` soft deletion vs hard deletion for financial tables.
   * **Audit Logging & Timestamping**: Standard `created_at`, `updated_at`, `deleted_at` column rules and immutable `admin_audit_logs`.

---

# Dependencies

- [00-foundation/architecture-and-quality-attributes.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/00-foundation/architecture-and-quality-attributes.md) — NeonDB PostgreSQL infrastructure setup.
- [02-domain-model/bounded-contexts-and-aggregates.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/02-domain-model/bounded-contexts-and-aggregates.md) — Aggregate root ownership matrix.
- [14-adrs/ADR-0002](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0002-shared-postgresql-database.md) — Shared PostgreSQL decision.
- [14-adrs/ADR-0005](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0005-in-database-order-processing-model.md) — Real-time DB order visibility.
