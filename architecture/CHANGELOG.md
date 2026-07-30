# SATURDAYS ARCHITECTURE REPOSITORY CHANGELOG

Version: 1.0  
Status: Authoritative Version History  
Owner: Saturdays Engineering Team  

---

# Purpose

This document tracks all versioned modifications, additions, deprecations, and structural governance revisions made to the Saturdays Architecture Repository.

---

## [1.0.0] — 2026-07-30

### Initial Repository Architecture Baseline
- **Execution Roadmap**: Established canonical execution plan in [EXECUTION_PLAN.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/EXECUTION_PLAN.md) under a high-granularity consolidated maintenance model.
- **Continuous State Tracking**: Initialized live state ledger in [PROJECT_STATE.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/PROJECT_STATE.md).
- **Master Landing Page & Index**: Created master index in [README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/README.md) establishing dual-surface scope (Saturdays & DineGuru) and domain ownership matrices.
- **Repository Structure Map**: Published complete table of contents in [SUMMARY.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/SUMMARY.md).
- **Governance Standards**: Defined modification rules, ADR submission flow, and anti-drift procedures in [CONTRIBUTING.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/CONTRIBUTING.md).

### Key Architectural Decisions Formalized
- **Production Modular Monolith**: Adopted single FastAPI codebase with explicit module boundaries over distributed microservices.
- **Shared Data Layer**: Adopted single PostgreSQL database (NeonDB) as the sole persistence layer shared between Saturdays and DineGuru.
- **4-Tier Organizational Hierarchy**: Defined legal and operational entity structure (`Merchant` $\rightarrow$ `Brand` $\rightarrow$ `Branch` $\rightarrow$ `Kitchen`).
- **Domain Boundary Consolidation**: Removed generic `shared` and `admin` modules from business domain roots; consolidated admin workflows into `08-admin/`.
- **First-Class Non-Functional Requirements**: Dedicated `03.5-non-functional/` directory introduced for SLAs, SLOs/SLIs, RTO/RPO, and latency budgets.
