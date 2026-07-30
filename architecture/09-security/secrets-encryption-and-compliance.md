# SECRETS, ENCRYPTION & COMPLIANCE SPECIFICATIONS

Version: 1.0  
Status: Authoritative Secrets & Encryption Specification  
Owner: Chief Architect & Security Engineering Lead  

---

# Purpose

This document specifies data encryption standards in transit and at rest, secrets injection policies, and OWASP Top 10 compliance rules.

---

# Data Encryption Standards

1. **Encryption in Transit (TLS 1.3)**: 100% of HTTP connections MUST be encrypted using TLS 1.3 (TLS 1.2 minimum). Plaintext HTTP traffic MUST be automatically redirected to HTTPS with HSTS headers.
2. **Field-Level Encryption at Rest (AES-256 GCM)**: Sensitive customer Personally Identifiable Information (PII) (e.g. phone numbers, delivery addresses) and OAuth tokens MUST be encrypted before PostgreSQL persistence using AES-256 GCM.

---

# Secrets Management Strategy

- **Zero Hardcoded Secrets**: Secrets (JWT private signing keys, Razorpay API keys, NeonDB credentials, SendGrid API keys) MUST NEVER be committed to source repositories.
- **Environment Variable Injection**: In production, secrets MUST be injected at runtime via secure secret managers (e.g., AWS Secrets Manager, GCP Secret Manager, or Doppler).
- **Key Rotation Policy**: Encryption keys and API secret tokens MUST be rotated every 90 days.

---

# OWASP Top 10 Compliance Mapping

| OWASP Vulnerability | Technical Safeguard & Implementation Rule |
| :--- | :--- |
| **A01: Broken Access Control** | BOLA checks on every endpoint (`WHERE id = :id AND customer_profile_id = :user_id`); RBAC middleware enforcement. |
| **A02: Cryptographic Failures** | Argon2id for password hashing; AES-256 GCM for PII; TLS 1.3 in transit. |
| **A03: Injection (SQLi / Command)**| 100% parameterized SQLAlchemy ORM queries; raw string SQL queries strictly prohibited. |
| **A04: Insecure Design** | Explicit threat modeling; principle of least privilege across all service layers. |
| **A05: Security Misconfiguration** | Automated security scanning; CORS origin whitelist; secure HTTP headers (`X-Content-Type-Options: nosniff`). |
| **A07: Identification & Auth Failures** | 15-minute JWT lifetime; rate-limited auth endpoints (10 req/min); strong password rules. |
