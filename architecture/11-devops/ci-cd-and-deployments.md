# CI/CD & DEPLOYMENT SPECIFICATIONS

Version: 1.0  
Status: Authoritative CI/CD Specification  
Owner: Chief Architect & DevOps/Infrastructure Lead  

---

# Purpose

This document specifies the automated CI/CD build pipeline, Docker container packaging standards, and zero-downtime deployment workflows.

---

# Automated GitHub Actions Pipeline

```mermaid
flowchart LR
    A[Git Push to main] --> B[Job 1: Lint & Formatting (Ruff/Black)]
    B --> C[Job 2: Unit & Integration Tests (Pytest)]
    C --> D[Job 3: Docker Build & Vulnerability Scan (Trivy)]
    D --> E[Job 4: Run Alembic DB Migrations]
    E --> F[Job 5: Rolling Container Deployment]
```

## Pipeline Stages
1. **Lint & Formatting**: Enforces PEP 8 compliance using `ruff` and `black`.
2. **Automated Testing**: Executes `pytest` unit, integration, and architectural fitness function tests.
3. **Container Build & Security Scan**: Builds multi-stage Docker image and scans for vulnerability CVEs.
4. **Database Migration**: Executes `alembic upgrade head` before container routing.
5. **Rolling Deployment**: Deploys updated container pod instances using readiness probes for zero downtime.

---

# Multi-Stage Production Dockerfile

```dockerfile
# Stage 1: Build dependencies
FROM python:3.11-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential libpq-dev
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Final minimal runtime container
FROM python:3.11-slim
WORKDIR /app
RUN useradd -m -u 1000 appuser && apt-get update && apt-get install -y libpq5 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser . /app
ENV PATH=/home/appuser/.local/bin:$PATH
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```
