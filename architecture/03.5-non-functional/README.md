# 03.5-NON-FUNCTIONAL — NON-FUNCTIONAL REQUIREMENTS SPECIFICATIONS

Version: 1.0  
Status: Authoritative NFR Specification Index  
Owner: Chief Architect & Operations Engineering  

---

# Purpose

The `03.5-non-functional/` directory establishes first-class architectural specifications for performance budgets, latency targets, capacity limits, availability SLAs, SLOs/SLIs, error budgets, disaster recovery (RTO/RPO), and security compliance objectives for Saturdays and DineGuru.

Rather than scattering non-functional concerns across individual component specs, this section serves as the single source of truth for platform operational targets.

---

# Consolidated Specifications Index

1. [performance-scalability-and-sla.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03.5-non-functional/performance-scalability-and-sla.md)
   * **Latency Targets**: Quantified p95 ($< 200\text{ms}$) and p99 ($< 500\text{ms}$) API response budgets; PostgreSQL query execution limits ($< 20\text{ms}$).
   * **Throughput & Capacity Bounds**: Target capacity for 500 restaurants, 20,000+ active users, and 50 peak orders/second at VIT Vellore.
   * **SLAs, SLOs & Error Budgets**: Operational 99.9% uptime SLA, service level indicators (SLIs), and error budget exhaustion policies.
2. [resilience-disaster-recovery-and-security-nfrs.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03.5-non-functional/resilience-disaster-recovery-and-security-nfrs.md)
   * **Disaster Recovery Targets**: Recovery Time Objective ($\text{RTO} < 15\text{min}$) and Recovery Point Objective ($\text{RPO} < 1\text{min}$) specifications.
   * **Backup Strategy**: NeonDB automated point-in-time recovery (PITR) and daily snapshot retention rules.
   * **Security & Compliance NFRs**: OWASP Top 10 mitigation rules, field-level encryption targets, and audit trail retention bounds.

---

# Dependencies

- [00-foundation/architecture-and-quality-attributes.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/00-foundation/architecture-and-quality-attributes.md) — Baseline quality attribute tradeoffs.
- [ARCHITECTURE_PRINCIPLES.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/ARCHITECTURE_PRINCIPLES.md) — Rule 6 (Zero Unquantified Buzzwords).
