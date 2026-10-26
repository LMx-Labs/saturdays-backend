# DineGuru backend maintainer runbook

This describes source setup and review gates. It does not authorize a production deployment or migration.

## Before a deployment

Confirm the deployed backend commit and the actual database schema, including `alembic_version`, tables, columns and indexes. Upstream and old repair histories reused migration IDs `0004`–`0006`; the revision value alone cannot identify which schema exists. Confirm a recoverable database backup and rehearse the exact upgrade on a staging copy. Upstream `0006` drops Garba tables without a downgrade. A code rollback does not undo a database migration or restore data.

Confirm which Git branches deploy to production and Preview. A Preview deployment of integration commit `ff37937` already occurred. The `review/dineguru-final-20261026` branch is excluded from Vercel Git deployments in `vercel.json`; keep that exclusion in the first branch commit. Before deploying any code or publishing another branch without this exclusion, confirm Preview uses an isolated database and its build/start commands cannot migrate production. Do not use production credentials for CI or migration tests.

## Configuration and versioned schema

Set `ENVIRONMENT=production`, a strong unique `JWT_SECRET_KEY`, `DATABASE_URL`, and explicit trusted `CORS_ORIGINS` for the DineGuru frontend. Do not use a broad `CORS_ORIGIN_REGEX` in production unless every matched site is trusted. Keep `RAZORPAY_SIMULATE=false` and `PAYOUT_SCHEDULER_ENABLED=false`. The `.env.example` values are local examples. Supply secrets through the host's secret manager; never commit them.

Current migration chain: upstream `0001` → `0002` → `0003` → `0004` → `0005` → `0006` → `dg_20261026_01` → `_02` → `_03` → `_04` → `_05`. New fields include `orders.price_breakdown_snapshot`, `inventory_items.is_paused`, and `reviews.is_hidden`. Revision `_04` pauses legacy out-of-stock items; staff must explicitly review and resume inventory as needed. Historical orders receive no invented pricing snapshots or reservations.

For disposable PostgreSQL databases only, use a database name beginning `dineguru_repair_` and run `python scripts/verify_migrations.py --mode fresh --destructive-guard` or `--mode upgrade --destructive-guard`. The upgrade mode migrates from canonical upstream `0006` with representative orders and inventory, verifies survival/backfill, and checks drift. The script drops the target database's public schema; never point it at production. CI runs native PostgreSQL concurrency tests with `TEST_POSTGRES_URL`.

## First admin and restaurant onboarding

After the appropriate versioned migrations are approved and run by the hosting maintainer, create the first PlatformAdmin once using the trusted script included in the Docker image. Set `DATABASE_URL`, `BOOTSTRAP_ADMIN_EMAIL`, and `BOOTSTRAP_ADMIN_PASSWORD` in the process environment; run `python scripts/bootstrap_admin.py` from the application root. The password must have at least 12 characters. The script refuses to run if an admin or email already exists and never prints the password. Verify the image contains the script before using this procedure. Hand credentials to operations through a private approved channel, then remove the one-time bootstrap variables.

The PlatformAdmin uses authenticated `/api/v1/admin/staff-accounts` to create MerchantOwner and branch staff accounts, and `/api/v1/admin/merchant-for-owner/{owner_user_id}` to create a merchant for an owner. Then configure brand, branch, kitchen, menu, categories, items and inventory through their authenticated APIs before accepting orders. Check branch hours, merchant approval, active kitchen, available inventory and item pause status. Public registration is Customer-only; there is no `REGISTRATION_OPEN` setting.

## Current release gates

Collection, payment verification, payment webhooks, refunds, and payout initiation return HTTP 503 by design. `REFUNDS_ENABLED=true` does not make these flows operational, and no `provider_order_id` uniqueness guarantee has been established. Paid-order cancellation stays blocked pending policy. Do not represent order summaries as tax invoices or payment proof.

Before merchant rollout, the maintainer must confirm Preview isolation and production deploy rules, inspect deployed schema/backup, approve payment and tax/refund policy, run CI and staging migrations, and complete authenticated DineGuru order journeys. Physical printer acceptance is a separate frontend/hardware check.
