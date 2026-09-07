# Saturdays Monolithic Platform

This repository contains the FastAPI/PostgreSQL backend, React/Vite product frontend,
Alembic schema, and canonical engineering architecture for Saturdays and DineGuru.

---

## Repository Structure

- `app/` — FastAPI application backend source code (Core Infrastructure, Config, Database, Middleware, Logging)
- `alembic/` & `alembic.ini` — PostgreSQL schema migrations
- `architecture/` — Canonical 15-year engineering architecture specification (116 files)
- `prompts/` — Governing prompt specifications and documentation rules
- `.github/workflows/` — CI/CD automation pipeline

---

## Local Setup & Quickstart

### Prerequisites
- Python 3.11+
- PostgreSQL 16+ (or Docker)
- Node.js 22+ and npm

### Environment Configuration
Copy the sample environment file:
```bash
cp .env.example .env
```

Development defaults use mock payment/email providers. Production startup requires
unique 32+ character `JWT_SECRET_KEY` and `SECRET_KEY` values plus explicit
`CORS_ORIGINS` and `INTERNAL_CLEANUP_KEY`. Production also requires a configured
payment provider; set `PAYMENT_PROVIDER=razorpay` with
`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and `RAZORPAY_WEBHOOK_SECRET`.

### Installation
Install dependencies:
```bash
make install
# Or: pip install -r requirements.txt && pip install -e .[dev]
```

### Running Local Development Server
Apply all migrations through `0007` before starting:
```bash
alembic upgrade head
```

Create the first Platform Admin with the explicit operator command below. After
bootstrap, that administrator provisions restaurant owners and other administrators
from the Admin workspace; public registration remains Customer-only.

```bash
python scripts/create_platform_admin.py admin@example.com
```

Start the FastAPI server:
```bash
make run
# Or: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
API Documentation available at:
- Swagger UI: `http://localhost:8000/api/v1/docs`
- ReDoc: `http://localhost:8000/api/v1/redoc`
- OpenAPI JSON: `http://localhost:8000/api/v1/openapi.json`
- Health Checks: `http://localhost:8000/health`, `/health/ready`, `/health/live`

### Product Frontend

The React frontend in `frontend/` provides public discovery and dedicated Customer,
Merchant Owner, Kitchen Staff, Branch Manager, and Platform Admin workspaces. The
OpenAPI request workbench remains available to Platform Admin at `/dev/api`.

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173` while the backend is running on port `8000`.
Set `VITE_API_BASE_URL` when connecting to a backend on another origin.

Role landing routes are `/customer`, `/merchant`, `/kitchen`, `/branch-manager`, and
`/admin`. Public registration creates Customer accounts only. Platform Admin can
provision users and invitations; Merchant Owners invite Kitchen Staff or Branch
Managers and assign only their own branches.

Customer checkout is server-authoritative: cart/address/coupon validation creates a
short-lived quote; order creation consumes that quote once while reserving stock and
recording coupon use; payment intent amount and currency come from the persisted
order. Development uses the in-app mock completion flow, while Razorpay mode keeps
all signing and webhook secrets server-side.

Authorization is enforced in the API, not by frontend route guards. Merchant,
branch, kitchen, menu, inventory, order, review, report, refund, and WebSocket
operations recheck ownership or active staff branch assignments. Webhooks and
authenticated cleanup operations intentionally have no product GUI.

Frontend requirements and the complete implemented API contract are available as:

- [`docs/FRONTEND_BACKEND_INTEGRATION.md`](docs/FRONTEND_BACKEND_INTEGRATION.md)
- [`docs/FRONTEND_BACKEND_INTEGRATION.pdf`](docs/FRONTEND_BACKEND_INTEGRATION.pdf)

### Docker Setup
Run the full stack via Docker Compose:
```bash
make docker-run
# Or: docker-compose up --build
```

The container waits for PostgreSQL health and runs `alembic upgrade head` before
starting Uvicorn. For multi-replica production releases, run migrations once as a
deployment job before scaling replicas.

### Testing & Code Quality
```bash
# Run Pytest suite
make test

# Code formatting & linting
make format
make lint

# Frontend checks
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```