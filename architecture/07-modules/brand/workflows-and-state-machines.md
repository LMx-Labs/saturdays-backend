# BRAND MODULE — WORKFLOWS, STATE MACHINES & TESTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Workflows & Testing Specification  
Owner: Catalog & Merchant Engineering Team  

---

# Brand Management Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Merchant as Merchant Owner (DineGuru)
    participant API as Brand Router
    participant Service as BrandService
    participant Repo as BrandRepository
    participant DB as PostgreSQL

    Merchant->>API: POST /api/v1/brands (name, logo_url, cuisine_types)
    API->>Service: create_brand(merchant_id, schema)
    Service->>Repo: insert_brand(brand_entity)
    Repo->>DB: INSERT INTO brands
    Service->>DB: COMMIT Transaction
    Service-->>API: Return Brand Entity Payload
    API-->>Merchant: HTTP 201 Created
```

---

# Testing & Operational Observability

## Key Operational Metrics (SLIs)
- `brand_read_latency_ms`: p95 latency budget $< 50\text{ms}$.
