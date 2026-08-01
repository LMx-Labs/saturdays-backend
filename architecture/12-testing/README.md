# 12-TESTING — TESTING STRATEGY & FITNESS FUNCTIONS SPECIFICATIONS

Version: 1.0  
Status: Authoritative Testing & Quality Gate Specification Index  
Owner: Chief Architect & Quality Engineering Lead  

---

# Purpose

The `12-testing/` directory defines the testing pyramid, unit/integration testing standards, API contract verification, and automated architectural fitness functions for Saturdays and DineGuru.

---

# Consolidated Specifications Index

1. [testing-strategy-and-contracts.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/12-testing/testing-strategy-and-contracts.md)
   * **Testing Pyramid**: Unit tests (Pytest), integration tests (PostgreSQL test containers), and E2E API contract tests.
   * **Test Data Setup**: Factory Boy fixtures and transactional rollbacks during test execution.
2. [architecture-fitness-functions.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/12-testing/architecture-fitness-functions.md)
   * **Automated Architectural Enforcement Suite**: Pytest static analysis tests enforcing single table ownership, zero cross-module repository imports, 1:1 aggregate mapping, explicit transaction boundaries, and 0 TODO placeholders.

---

# Dependencies

- [CONTRIBUTING.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/CONTRIBUTING.md) — Architecture quality gates.
- [04-backend/fastapi-architecture-and-layering.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/04-backend/fastapi-architecture-and-layering.md) — Unidirectional software layering.
