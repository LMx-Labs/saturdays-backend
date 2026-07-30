# 13-RUNBOOKS — OPERATIONAL INCIDENT RUNBOOKS SPECIFICATIONS

Version: 1.0  
Status: Authoritative Operational Runbooks Specification Index  
Owner: Chief Architect & Operations Engineering  

---

# Purpose

The `13-runbooks/` directory contains step-by-step incident response procedures, failover protocols, database outage restoration guides, and financial payment/refund reconciliation runbooks for Saturdays and DineGuru operations.

---

# Consolidated Specifications Index

1. [system-outages-and-failover.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/13-runbooks/system-outages-and-failover.md)
   * **Database Failover & Outage Response**: NeonDB serverless outage response, PITR branch promotion runbook, and FastAPI container pod restart procedures.
   * **High Latency & Connection Pool Saturation**: Mitigation steps for connection pool exhaustion during peak campus dining rushes.
2. [payment-and-refund-reconciliation.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/13-runbooks/payment-and-refund-reconciliation.md)
   * **Razorpay Gateway Discrepancy Reconciliation**: Resolving unmatched webhook events, payment signature verification failures, and offline status sync.
   * **Merchant Payout & Refund Settlement**: Step-by-step procedures for auditing platform commission ledgers and processing merchant payouts.

---

# Dependencies

- [03.5-non-functional/resilience-disaster-recovery-and-security-nfrs.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03.5-non-functional/resilience-disaster-recovery-and-security-nfrs.md) — RTO/RPO DR SLAs.
- [11-devops/database-ops-and-disaster-recovery.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/11-devops/database-ops-and-disaster-recovery.md) — NeonDB PITR.
- [14-adrs/ADR-0012](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/14-adrs/ADR-0012-append-only-payment-ledger-and-refunds.md) — Append-only payment ledger.
