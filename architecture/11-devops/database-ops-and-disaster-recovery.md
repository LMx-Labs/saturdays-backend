# DATABASE OPS & DISASTER RECOVERY SPECIFICATIONS

Version: 1.0  
Status: Authoritative Database Ops & DR Specification  
Owner: Chief Architect & DevOps/Infrastructure Lead  

---

# Purpose

This document specifies database operational management, NeonDB backup retention schedules, and Point-In-Time Recovery (PITR) procedures.

---

# Backup & Retention Schedule

```mermaid
flowchart TD
    A[NeonDB Primary Database] -->|Continuous WAL Archiving| B[Continuous PITR Window (7 Rolling Days)]
    A -->|Daily 03:00 AM IST Snapshot| C[Daily Snapshots (30-Day Retention)]
    A -->|Monthly 1st Day Snapshot| D[Archival Snapshots (12-Month Retention)]
```

- **Continuous WAL Archiving**: Retained for 7 rolling days to support precise point-in-time recovery to any exact second.
- **Daily Automated Snapshots**: Executed daily at 03:00 AM IST and retained for 30 rolling days.
- **Monthly Archival Snapshots**: Retained for 12 months for compliance reconciliation.

---

# Point-In-Time Recovery (PITR) Execution Procedure

In the event of database corruption or region outage:

1. **Target RPO**: $< 1\text{ minute}$ of data loss.
2. **Target RTO**: $< 15\text{ minutes}$ to restore full operational service.
3. **Execution Steps**:
   * Step 1: Identify exact timestamp immediately prior to corruption event.
   * Step 2: Trigger NeonDB PITR branch restoration via CLI / API: `neonctl branches create --parent main --timestamp <target_timestamp>`.
   * Step 3: Promote restored database branch to primary production connection string.
   * Step 4: Restart FastAPI application instances to reset database connection pools.
