# AUTH MODULE — DOMAIN, DATABASE & API SPECIFICATIONS

Version: 1.0  
Status: Authoritative Domain, Database & API Specification  
Owner: Auth & Security Engineering Team  

---

# Aggregate Root & Domain Invariants

## Aggregate Root: `User`
- **Identifier**: `id` (`UUIDv7`)
- **Entities / Value Objects**: `UserCredentials`, `UserRoles`, `AuthToken`
- **Owner Module**: `auth` (Exclusive)

## Authoritative Domain Invariants
1. **INV-AUTH-001 (Unique Email)**: Every registered user MUST have a globally unique case-insensitive email address.
2. **INV-AUTH-002 (Password Hash Security)**: Raw plaintext passwords MUST NEVER be persisted or logged; passwords MUST be hashed using Argon2id prior to storage.
3. **INV-AUTH-003 (Token Expiration)**: Access tokens MUST expire after exactly 15 minutes; refresh tokens MUST expire after 7 days.

---

# Owned Database Schema (`users` Table)

The `auth` module has exclusive write ownership over the `users` table ([05-database/database-philosophy-and-schema.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/database-philosophy-and-schema.md)).

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid_v7(),
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NULL, -- Nullable for OAuth-only users
    role VARCHAR(50) NOT NULL DEFAULT 'Customer',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE NULL
);

CREATE UNIQUE INDEX idx_users_email_lower ON users(LOWER(email)) WHERE deleted_at IS NULL;
```

---

# REST API Endpoint Specifications (8 Mandatory Attributes)

### 1. POST `/api/v1/auth/register`
- **Owner Module**: `auth`
- **Authentication**: `NONE` (Public endpoint)
- **Authorization**: `PUBLIC`
- **Idempotency**: `NON_IDEMPOTENT` (Requires unique email validation)
- **Transaction Scope**: `READ_WRITE_ATOMIC_MULTITABLE` (Creates `users` row and triggers `customer_profiles` initialization via event)
- **Failure Modes**: `400 Bad Request` (Validation error), `409 Conflict` (Email already registered)
- **Retry Behavior**: `DO_NOT_RETRY` (Requires modified input if email exists)
- **Expected Latency Target**: $< 250\text{ms}$ (p95, includes Argon2id hash overhead)

### 2. POST `/api/v1/auth/login`
- **Owner Module**: `auth`
- **Authentication**: `NONE` (Public endpoint)
- **Authorization**: `PUBLIC`
- **Idempotency**: `IDEMPOTENT` (Repeated valid credentials yield fresh JWT)
- **Transaction Scope**: `READ_ONLY` (Verifies user credentials)
- **Failure Modes**: `401 Unauthorized` (Invalid email or password)
- **Retry Behavior**: `RETRY_WITH_EXPONENTIAL_BACKOFF`
- **Expected Latency Target**: $< 200\text{ms}$ (p95)

### 3. POST `/api/v1/auth/refresh`
- **Owner Module**: `auth`
- **Authentication**: `BEARER_JWT` (Valid Refresh Token)
- **Authorization**: `ALL_ROLES`
- **Idempotency**: `IDEMPOTENT`
- **Transaction Scope**: `READ_ONLY`
- **Failure Modes**: `401 Unauthorized` (Expired or revoked refresh token)
- **Retry Behavior**: `DO_NOT_RETRY` (Requires re-login if refresh token invalid)
- **Expected Latency Target**: $< 50\text{ms}$ (p95, pure JWT signature verification)
