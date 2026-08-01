# SYSTEM OUTAGES & FAILOVER RUNBOOK SPECIFICATIONS

Version: 1.0  
Status: Authoritative Operational Incident Runbook  
Owner: Chief Architect & Operations Engineering  

---

# Purpose

This document provides step-by-step incident response procedures for system outages, database connection pool exhaustion, and regional failover.

---

# Incident 1: Database Outage & PITR Restoration

## Alert Trigger
- PagerDuty P1 Alert: `PostgreSQL connection failed` OR `/health/ready` returns 503.

## Step-by-Step Execution Guide
1. **Step 1: Declare Incident & Notify On-Call SRE**:
   * Open incident bridge; set status page to "Database Degradation under investigation".
2. **Step 2: Inspect NeonDB Console Status**:
   * Verify if NeonDB primary compute endpoint is responsive.
   * If primary endpoint is unrecoverable, prepare Point-In-Time Recovery (PITR).
3. **Step 3: Execute PITR Branch Promotion**:
   ```bash
   # Restore parent branch to timestamp prior to incident
   neonctl branches create --project-id <project_id> --parent main --timestamp 2026-07-30T19:50:00Z --name restored-main
   ```
4. **Step 4: Update Database Connection Secret**:
   * Update `DATABASE_URL` environment variable secret in Vault / Cloud Run to target restored compute endpoint.
5. **Step 5: Restart Application Containers**:
   * Execute rolling restart of FastAPI container instances to reset database connection pools.
6. **Step 6: Verify Recovery & Resolve Incident**:
   * Test `/health/ready` endpoint; verify successful read/write connection; set status page to Operational.

---

# Incident 2: DB Connection Pool Saturation (> 95%)

1. **Enable Degradation Mode**: Immediately enable non-critical API shedding (return 503 on reviews and cms routes).
2. **Identify Slow Queries**: Inspect `pg_stat_activity` for long-running queries ($> 5\text{ seconds}$).
3. **Kill Blocked Queries**: Execute `SELECT pg_terminate_backend(pid)` on blocked connection threads.
