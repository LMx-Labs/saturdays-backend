# DineGuru backend integration checkpoint (2026-10-26)

Branch: `integration/upstream-first-20261026`, based on fetched `origin/main` `df24dde`. The old repair branch remains at `d23decf`; the local merge experiment is preserved at `integration/upstream-20261026` and must not be deployed. Upstream migrations `0004`–`0006` remain unchanged.

## Ported repairs

- Customer-only public registration, active-user checks, branch/tenant authorization, private response and WebSocket access, and administrative owner/staff provisioning.
- Authoritative checkout pricing, category and stock-pause admission, ordered inventory locks, atomic reservation/release, customer-scoped idempotency, legal order transitions, and exactly-once cancellation.
- Payment provider order binding and replay protections; collection, refund, and payout initiation retain their HTTP 503 safety gates. No simulated payment mode is enabled by default.
- DineGuru order, inventory, menu, admin and notification API compatibility. Existing upstream Admin authentication and `/admin/users` are retained.

## Migration chain

`0006` -> `dg_20261026_01` reservations -> `_02` banners and feature flags -> `_03` price snapshots -> `_04` inventory pause -> `_05` review visibility. All are new forward revisions after the upstream head. The conflicting repair history's `0004`–`0008` identities were not copied.

## Checks

- Passed: full backend suite, 157 tests including native PostgreSQL concurrency cases; Ruff `app tests`; `git diff --check`; Alembic single head.
- Passed: disposable PostgreSQL fresh upgrade through `_05` with zero Alembic drift.
- Passed: disposable PostgreSQL upgrade from upstream `0006` with representative merchant, branch and order data; order total/status survived; zero Alembic drift.
- Passed: source-level DineGuru API contract inspection. The frontend suite previously passed 110 tests, typecheck, lint, format and build at `4bb85d1`.
- Not run: authenticated browser/PDF and physical printer acceptance. Black check hangs in this Windows sandbox and was stopped; Ruff and tests pass.

## Publication and production blockers

No code from this branch has been deployed or migrated in production. Pushing is pending confirmation that an integration branch does not auto-deploy. Production migration approval requires the actual deployed backend commit, read-only schema/revision evidence, and a recoverable backup. An `alembic_version` value of `0006` alone is ambiguous because the old repair and upstream histories used that ID for different operations. Do not stamp, reset, or run production migrations based on this checkpoint.
