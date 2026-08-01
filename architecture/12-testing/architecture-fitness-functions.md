# ARCHITECTURE FITNESS FUNCTIONS SPECIFICATIONS

Version: 1.0  
Status: Authoritative Architectural Fitness Function Suite  
Owner: Chief Architect & Quality Engineering Lead  

---

# Purpose

This document defines the automated **Architectural Fitness Functions** executed during CI/CD test runs (`pytest tests/architecture/`) to prevent architectural drift, boundary erosion, uncoordinated cross-table writes, or broken ADR compliance.

---

# Master Architectural Fitness Function Suite

All 10 fitness functions MUST be implemented as automated Python AST (Abstract Syntax Tree) and DB schema static analysis tests.

| Rule ID | Architectural Fitness Function Requirement | Enforcement Mechanism | Target Pass Criteria |
| :--- | :--- | :--- | :--- |
| **FIT-001** | **Single Table Write Ownership**: No module MAY execute INSERT/UPDATE/DELETE queries against database tables owned by another module. | Python AST inspection on `Repository` classes in `07-modules/`. | 0 cross-module write queries. |
| **FIT-002** | **No Cross-Repository Imports**: A module Service layer MUST NOT import or instantiate another module's `Repository` class directly. | Import AST linting; enforce Service-to-Service interface calls. | 0 repository cross-imports. |
| **FIT-003** | **Single Aggregate Ownership**: Every Domain Aggregate Root MUST map to exactly ONE owner module in [02-domain-model/bounded-contexts-and-aggregates.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/02-domain-model/bounded-contexts-and-aggregates.md). | Metadata schema validation. | 100% 1:1 mapping. |
| **FIT-004** | **Single Database Table Ownership**: Every PostgreSQL database table MUST have exactly ONE owner module in [05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md). | DB DDL migration scanner. | 100% 1:1 table mapping. |
| **FIT-005** | **Single API Endpoint Ownership**: Every REST API route MUST define an explicit `Owner Module` attribute in its specification ([06-api/api-design-and-authentication.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/06-api/api-design-and-authentication.md)). | OpenAPI specification parser. | 100% endpoint attribution. |
| **FIT-006** | **Zero Circular Module Dependencies**: Internal Python imports between `07-modules/` MUST form a Directed Acyclic Graph (DAG). | Dependency graph cycle detection via `networkx`. | 0 circular dependency cycles. |
| **FIT-007** | **Single Domain Invariant Ownership**: Every business domain invariant MUST map to exactly ONE authoritative module in [02-domain-model/domain-invariants-and-events.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/02-domain-model/domain-invariants-and-events.md). | Invariants registry parser. | 0 duplicate invariant definitions. |
| **FIT-008** | **Explicit Transaction Scope**: Every Service layer method modifying data MUST declare an explicit transaction boundary (`async_session`). | Service layer AST scanner for `commit()` / `rollback()` blocks. | 0 un-scoped write methods. |
| **FIT-009** | **ADR Compliance & Structure**: Every ADR file in `14-adrs/` MUST contain Status, Context, Decision, Consequences, and Future Evolution sections. | Markdown structural validator. | 100% ADR schema compliance. |
| **FIT-010** | **Zero TODO / TBD Placeholders**: The architecture specification repository MUST NOT contain `TODO`, `TBD`, or unquantified placeholder strings. | Markdown repository grep scanner. | 0 placeholder strings. |
