# 11-DEVOPS — DEPLOYMENT, DATABASE OPS & DR SPECIFICATIONS

Version: 1.0  
Status: Authoritative DevOps & Infrastructure Specification Index  
Owner: Chief Architect & DevOps/Infrastructure Lead  

---

# Purpose

The `11-devops/` directory defines the CI/CD pipeline, Docker container packaging, zero-downtime deployment strategies, PostgreSQL database operations, automated Alembic migrations, and Disaster Recovery (DR) procedures for Saturdays and DineGuru.

---

# Consolidated Specifications Index

1. [ci-cd-and-deployments.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/11-devops/ci-cd-and-deployments.md)
   * **GitHub Actions CI/CD Pipeline**: Linting, automated unit/integration testing, Docker image build, security scanning, and deployment stages.
   * **Multi-Stage Dockerfile Strategy**: Minimized production image size, non-root user execution, and security hardening.
   * **Rolling Zero-Downtime Deployments**: Container health probe routing and blue/green deployment strategy.
2. [database-ops-and-disaster-recovery.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/11-devops/database-ops-and-disaster-recovery.md)
   * **NeonDB Operations & Backup Retention**: Continuous WAL archiving, daily automated snapshots (30-day retention), and monthly backups (12-month retention).
   * **Point-In-Time Recovery (PITR)**: RTO $< 15\text{min}$ and RPO $< 1\text{min}$ database restoration procedures.

---

# Dependencies

- [03.5-non-functional/resilience-disaster-recovery-and-security-nfrs.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03.5-non-functional/resilience-disaster-recovery-and-security-nfrs.md) — DR targets.
- [05-database/indexing-migrations-and-auditing.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/05-database/indexing-migrations-and-auditing.md) — Alembic migration standards.
