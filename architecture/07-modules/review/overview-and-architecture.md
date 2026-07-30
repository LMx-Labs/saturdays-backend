# REVIEW MODULE — OVERVIEW & ARCHITECTURE

Version: 1.0  
Status: Authoritative Module Specification  
Owner: Customer Experience & Reviews Engineering Team  

---

# Executive Summary & Purpose

The `review` module (`07-modules/review/`) is the authoritative bounded context for customer dish and branch ratings, verified order review submissions, and merchant response workflows on Saturdays and DineGuru.

---

# Module Boundaries & Single-Source-of-Truth

## Included Responsibilities
- Verified order review management (`reviews` table).
- Star rating aggregations (1–5 scale) per branch.

## Excluded Responsibilities (Non-Overlapping Boundaries)
- **Order State Verification**: Read-only validation against [07-modules/order/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/order/README.md) to confirm completed order ownership (`INV-0007`).

---

# Architecture & Layering

```mermaid
flowchart TD
    subgraph Presentation Layer
        A[FastAPI Review Router: /api/v1/reviews] --> B[ReviewService Interface]
    end

    subgraph Application Layer
        B --> C[ReviewService Implementation]
    end

    subgraph Persistence Layer
        C --> D[ReviewRepository]
        D --> E[(reviews Table in PostgreSQL)]
    end

    style E fill:#f9f,stroke:#333,stroke-width:2px
```
