# CUSTOMER MODULE — WORKFLOWS, STATE MACHINES & TESTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Workflows & Testing Specification  
Owner: Customer Product & Engineering Team  

---

# Customer Profile Initialization Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Event as In-Process Event Dispatcher
    participant Service as CustomerService
    participant Repo as CustomerRepository
    participant DB as PostgreSQL

    Event->>Service: Handle UserRegisteredEvent (user_id, email, role)
    alt Role == Customer
        Service->>Repo: create_initial_profile(user_id, email)
        Repo->>DB: INSERT INTO customer_profiles (user_id, full_name)
        Service->>DB: COMMIT Transaction
    end
```

---

# Testing & Operational Observability

## Unit & Integration Testing Strategy
- **1:1 Mapping Verification**: Test that attempting to insert a second `customer_profiles` row for the same `user_id` throws a database `UniqueViolationError`.
- **Primary Address Atomicity**: Test that marking a new address as primary cleanly updates all previous address records for that customer to `is_primary = FALSE` within a single atomic transaction.

## Key Operational Metrics (SLIs)
- `customer_profile_read_latency_ms`: p95 latency budget $< 50\text{ms}$.
- `customer_address_count`: Counter tracking total active saved delivery addresses per customer.
