# SEARCH MODULE — WORKFLOWS, STATE MACHINES & TESTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Workflows & Testing Specification  
Owner: Discovery & Search Engineering Team  

---

# Customer Search Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer (Saturdays)
    participant API as Search Router
    participant Service as SearchService
    participant DB as PostgreSQL Database

    Customer->>API: GET /api/v1/search?q=biryani
    API->>Service: execute_search("biryani")
    Service->>DB: SELECT menu_items JOIN branches WHERE title ILIKE %biryani% AND is_active = true
    DB-->>Service: Return Ranked Results
    Service-->>API: Format Search Result Payload
    API-->>Customer: HTTP 200 OK (Items & Stores Payload)
```

---

# Testing & Operational Observability

## Key Operational Metrics (SLIs)
- `search_query_latency_ms`: p95 latency budget $< 100\text{ms}$.
