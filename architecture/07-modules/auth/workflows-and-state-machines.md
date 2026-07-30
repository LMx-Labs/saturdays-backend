# AUTH MODULE — WORKFLOWS, STATE MACHINES & TESTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Workflows & Testing Specification  
Owner: Auth & Security Engineering Team  

---

# User Account State Machine

```mermaid
stateDiagram-v2
    [*] --> UNVERIFIED: Register (Email/Password)
    [*] --> ACTIVE: OAuth Registration (Google Verified)
    UNVERIFIED --> ACTIVE: Complete Email OTP Verification
    ACTIVE --> SUSPENDED: Admin / Security Lock
    SUSPENDED --> ACTIVE: Admin Reinstatement
    ACTIVE --> DELETED: Account Deletion (Soft Delete)
```

---

# User Registration & Token Issuance Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Client as Saturdays / DineGuru Client
    participant API as Auth Router
    participant Service as AuthService
    participant Repo as UserRepository
    participant DB as PostgreSQL
    participant Event as Event Dispatcher

    Client->>API: POST /api/v1/auth/register (email, password)
    API->>Service: register_user(schema)
    Service->>Repo: find_by_email(email)
    Repo->>DB: SELECT WHERE email = LOWER(email)
    alt Email Exists
        DB-->>Repo: User Record Found
        Repo-->>Service: User Entity
        Service-->>API: Raise EmailAlreadyExistsError (HTTP 409)
    else Email Available
        Service->>Service: Hash Password (Argon2id)
        Service->>Repo: create_user(user_entity)
        Repo->>DB: INSERT INTO users
        Service->>DB: COMMIT Transaction
        Service->>Event: Publish UserRegisteredEvent
        Service-->>API: Return User Claims + JWT Access Token
        API-->>Client: HTTP 201 Created (Token Payload)
    end
```

---

# Published Domain Events

1. **`UserRegisteredEvent`**:
   * **Publisher**: `auth` module.
   * **Payload**: `{ "user_id": "UUIDv7", "email": "...", "role": "Customer", "registered_at": "..." }`
   * **Consumers**: [07-modules/customer/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/customer/README.md) (creates customer profile), [07-modules/notification/](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/07-modules/notification/README.md) (sends welcome email).

---

# Testing & Operational Observability

## Unit & Integration Testing Strategy
- **Password Hashing Tests**: Verify Argon2id hash generation and constant-time password verification algorithms.
- **JWT Verification Tests**: Test token signature validation, expired token rejection, and tampered claim rejection.
- **Database Boundary Tests**: Verify `LOWER(email)` unique index enforcement during concurrent registration calls.

## Key Operational Metrics (SLIs)
- `auth_login_latency_ms`: p95 latency budget $< 200\text{ms}$.
- `auth_failure_count`: Counter tracking failed login attempts per minute (alerts on threshold $> 50$ indicating brute-force attack).
