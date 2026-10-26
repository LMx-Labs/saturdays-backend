# Saturdays backend

FastAPI and PostgreSQL backend for Saturdays and DineGuru. The current DineGuru integration branch contains restaurant onboarding, menu and inventory management, authenticated ordering, stock reservations, and staff order actions. The `architecture/` tree records design intent; use the application code and [deployment runbook](docs/deployment.md) for current operations.

## Local development

Use Python 3.11+ and PostgreSQL. Copy `.env.example` to `.env`, set a local `DATABASE_URL` and a unique `JWT_SECRET_KEY`, then run:

```sh
pip install -r requirements.txt
pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload
```

API documentation: `/api/v1/docs` and `/api/v1/redoc`. Health checks: `/health`, `/health/live`, `/health/ready`.

Public registration creates Customer accounts only. A PlatformAdmin provisions MerchantOwner and branch staff accounts; see the runbook for the first-admin procedure. The DineGuru frontend must use the backend's `/api/v1` routes and an explicitly trusted CORS origin.

## Payment boundary

Payment collection, verification, webhooks, refunds, and payout initiation remain gated with HTTP 503 pending product policy and provider integration. Setting `REFUNDS_ENABLED` or provider credentials does not enable them. Keep `PAYOUT_SCHEDULER_ENABLED=false` in production. No `REGISTRATION_OPEN` switch or `provider_order_id` uniqueness guarantee exists in this code.

## Checks

```sh
ruff check app tests scripts
black --check app tests scripts
pytest
```

CI separately runs native PostgreSQL tests and both disposable migration paths. `pytest` alone skips native tests when `TEST_POSTGRES_URL` is unset. See [deployment runbook](docs/deployment.md) for the guarded migration verification commands and production gates.
