# ADR-0004: MULTI-TENANT AUTHENTICATION & IDENTITY STRATEGY

- **Status**: ACCEPTED  
- **Date**: 2026-07-30  
- **Author**: Chief Architect  
- **Scope**: Authentication & Security Architecture  

---

# Problem & Context

The platform serves two distinct user populations across separate application surfaces: Customers on Saturdays and Restaurant Owners/Staff on DineGuru. 

The architecture requires an authentication strategy that provides secure identity verification, OAuth integration, role-based authorization, and stateless session management across both web applications.

---

# Options Considered

1. **Option A: Session-Cookie Stateful Auth**
   - Server-side stored sessions in database or memory with HTTP-only cookies.
2. **Option B: Multi-Tenant JWT & OAuth Identity Strategy**
   - Stateless JSON Web Tokens (JWT) for API access, paired with Google OAuth 2.0 and Email OTP for customers, and JWT access tokens for merchant users.

---

# Decision

The platform **MUST** adopt a **Multi-Tenant JWT & OAuth Identity Strategy** (Option B):

1. **Customer Authentication (Saturdays)**: Supports Google OAuth 2.0 and Email + OTP verification. Upon successful verification, the API issues a signed JWT access token.
2. **Merchant Authentication (DineGuru)**: Supports credentials/Email OTP issuing signed JWT access tokens with embedded tenant claims (`merchant_id`, `branch_id`, `roles`).
3. **Stateless API Bearer Headers**: All authenticated API endpoints parse JWT tokens from the standard `Authorization: Bearer <token>` header. Token lifetime MUST be 15 minutes for access tokens, backed by rolling refresh tokens.

---

# Consequences

## Positive
- Keeps the FastAPI backend stateless, allowing instant horizontal scaling and pod restarts without invalidating active user sessions.
- Embeds RBAC claims directly inside JWT payloads, eliminating database session lookups on every request.

## Negative / Risks
- Token revocation before expiration requires token blacklisting logic for security edge-cases.
