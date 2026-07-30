# 09-SECURITY — PLATFORM SECURITY & COMPLIANCE SPECIFICATIONS

Version: 1.0  
Status: Authoritative Security Specification Index  
Owner: Chief Architect & Security Engineering Lead  

---

# Purpose

The `09-security/` directory defines the threat model, STRIDE threat analysis, Role-Based Access Control (RBAC) authorization matrix, PII field-level encryption standards, secrets management, and OWASP Top 10 compliance rules for Saturdays and DineGuru.

---

# Consolidated Specifications Index

1. [threat-model-and-rbac.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/09-security/threat-model-and-rbac.md)
   * **STRIDE Threat Modeling Matrix**: System trust boundaries, spoofing, tampering, repudiation, information disclosure, DoS, and elevation of privilege mitigations.
   * **Full System RBAC Authorization Matrix**: Comprehensive permission matrix across `Customer`, `KitchenStaff`, `BranchManager`, `MerchantOwner`, and `PlatformAdmin`.
2. [secrets-encryption-and-compliance.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/09-security/secrets-encryption-and-compliance.md)
   * **Data Encryption Standards**: TLS 1.3 in transit and AES-256 GCM field-level encryption at rest for customer PII.
   * **Secrets Management Strategy**: Environment variable injection, Doppler/Vault integration, and rotation policies.
   * **OWASP Top 10 Compliance Mapping**: Mandatory safeguards against SQLi, BOLA, XSS, CSRF, and broken authentication.

---

# Dependencies

- [03.5-non-functional/resilience-disaster-recovery-and-security-nfrs.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03.5-non-functional/resilience-disaster-recovery-and-security-nfrs.md) — Security NFRs.
- [06-api/authorization-errors-and-rate-limiting.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/06-api/authorization-errors-and-rate-limiting.md) — API authorization standards.
- [14-adrs/ADR-0004](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0004-multi-tenant-authentication-identity-strategy.md) — Multi-tenant identity strategy.
