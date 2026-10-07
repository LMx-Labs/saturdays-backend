# Saturdays Monolithic Platform

This repository contains the backend implementation and canonical engineering architecture specification for Saturdays and DineGuru.

---

## Repository Structure

- `app/` — FastAPI application backend source code (Core Infrastructure, Config, Database, Middleware, Logging)
- `alembic/` & `alembic.ini` — PostgreSQL schema migrations
- `architecture/` — Canonical 15-year engineering architecture specification (116 files)
- `prompts/` — Governing prompt specifications and documentation rules
- `.github/workflows/` — CI/CD automation pipeline

---

## Payouts, Store Credit & Branch Managers

- **Daily payouts** — `POST /api/v1/payouts/run` (PlatformAdmin; `dry_run` to preview) or
  `PAYOUT_SCHEDULER_ENABLED=true`, or cron `python -m app.payout.scheduler`. Pays each
  approved merchant, from the platform RazorpayX account, the net of completed, fully-paid
  orders (gross − commission). Idempotent; failures are retried; RazorpayX webhook
  `POST /api/v1/payouts/webhook` (`payout.processed|failed|reversed`) updates status.
  Merchants see their own via `GET /payouts/me`. Needs `RAZORPAY_KEY_ID/SECRET`,
  `RAZORPAYX_ACCOUNT_NUMBER`, `RAZORPAY_SIMULATE=false`.
- **No cash refunds** — cancelling or rejecting a paid order issues brand-scoped store credit
  (`/store-credits`, spend it with `use_store_credit` on `POST /orders`). Cash-refund endpoints
  return `REFUNDS_DISABLED_USE_STORE_CREDIT` unless `REFUNDS_ENABLED=true`.
- **BranchManager ↔ branch** — onboard with `POST /admin/branch-managers {email, password,
  branch_id}`; `branch_id` is returned on login, `/auth/me` and in the JWT. Reassign with
  `PUT /admin/branch-managers/{user_id}/branch`.

---

## Local Setup & Quickstart

### Prerequisites
- Python 3.11+
- PostgreSQL 16+ (or Docker)

### Environment Configuration
Copy the sample environment file:
```bash
cp .env.example .env
```

### Installation
Install dependencies:
```bash
make install
# Or: pip install -r requirements.txt && pip install -e .[dev]
```

### Running Local Development Server
Start the FastAPI server:
```bash
make run
# Or: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
API Documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health Checks: `http://localhost:8000/health`, `/health/ready`, `/health/live`

### Docker Setup
Run the full stack via Docker Compose:
```bash
make docker-run
# Or: docker-compose up --build
```

### Testing & Code Quality
```bash
# Run Pytest suite
make test

# Code formatting & linting
make format
make lint
```