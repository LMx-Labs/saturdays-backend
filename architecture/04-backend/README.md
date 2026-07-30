# 04-BACKEND — FASTAPI BACKEND ARCHITECTURE SPECIFICATIONS

Version: 1.0  
Status: Authoritative Backend Execution Specification Index  
Owner: Chief Architect & Backend Engineering Lead  

---

# Purpose

The `04-backend/` directory defines the technical execution standards, layered software architecture rules, dependency injection patterns, database transaction scopes, exception handling, input validation, and background execution mechanisms for the FastAPI backend service.

It details how domain bounded contexts established in [02-domain-model/bounded-contexts-and-aggregates.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/02-domain-model/bounded-contexts-and-aggregates.md) are structured into clean, maintainable Python packages inside the unified modular monolith container.

---

# Consolidated Specifications Index

1. [fastapi-architecture-and-layering.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/04-backend/fastapi-architecture-and-layering.md)
   * **FastAPI Application Setup & Middleware**: Application initialization, CORS policies, request correlation IDs, and global middleware stack.
   * **Strict Layered Architecture Rules**: Unidirectional dependencies (`Router` $\rightarrow$ `Service` $\rightarrow$ `Repository` $\rightarrow$ `Database Model`).
   * **Dependency Injection (DI)**: FastAPI `Depends()` pattern for Database Session injection, authentication context, and service instances.
   * **Pydantic Validation & Exception Handling**: Input validation standards, custom exception handlers, and structured HTTP error responses.
   * **Structured Logging Strategy**: Structlog JSON logging configuration, context binding, and correlation ID propagation.
2. [concurrency-transactions-and-background-tasks.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/04-backend/concurrency-transactions-and-background-tasks.md)
   * **Database Transaction Scope & Atomic Boundaries**: Explicit `async_session` lifecycle management, commit/rollback rules, and nested atomic blocks.
   * **Service & Repository Boundaries**: Responsibilities of Service Layer vs Repository Layer; isolation rules between domain modules.
   * **Background Tasks Execution**: Async execution model using FastAPI `BackgroundTasks` for non-blocking notifications and audit logging.

---

# Dependencies

- [00-foundation/architecture-and-quality-attributes.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/00-foundation/architecture-and-quality-attributes.md) — Modular Monolith architecture pattern.
- [03-system/system-architecture-and-boundaries.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03-system/system-architecture-and-boundaries.md) — System boundaries and container topology.
- [14-adrs/ADR-0001](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0001-modular-monolith-architecture.md) — Modular monolith container decision.
