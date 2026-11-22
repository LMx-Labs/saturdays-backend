# Cloud Run Deployment Guide — Saturdays Backend

> **Read-before-you-run.**  
> This guide covers the **complete manual sequence** to migrate the Python/FastAPI backend
> from Vercel to Google Cloud Run. No command here touches production automatically.

---

## Live Deployment Status (Deployed & Verified)

- **Service Name:** `saturdays-api`
- **Region:** `us-central1`
- **Project ID:** `saturdays-campus`
- **Live URL:** `https://saturdays-api-373465250617.us-central1.run.app`
- **Neon Branch:** `production (br-wispy-night-b4y3aqdd)` in `aws-us-east-2`

---

## 0. Prerequisites

| Tool | Minimum version | Install |
|------|----------------|---------|
| `gcloud` CLI | 455+ | https://cloud.google.com/sdk/docs/install |
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| Python | 3.11 | (for local alembic migrations only) |

```bash
gcloud auth login
gcloud auth configure-docker          # if pushing manually
gcloud components update
```

---

## 1. Enable required Google Cloud APIs

```bash
PROJECT_ID="YOUR_GCP_PROJECT_ID"      # replace once; paste everywhere below

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  --project "$PROJECT_ID"
```

---

## 2. Region selection

Neon (PostgreSQL) is likely hosted in **AWS us-east-1** (Virginia) or **eu-west-1** (Ireland).  
Choose the nearest Cloud Run region to minimise DB round-trips:

| Neon region | Recommended Cloud Run region |
|-------------|------------------------------|
| `aws-us-east-1` | `us-east1` (South Carolina) |
| `aws-eu-west-1` | `europe-west1` (Belgium) |
| `aws-ap-southeast-1` | `asia-southeast1` (Singapore) |

```bash
REGION="us-east1"   # adjust to match your Neon region
```

---

## 3. Create Secret Manager secrets

**Never paste secrets into env-var flags** — use Secret Manager.

```bash
# DATABASE_URL  (use Neon's pooled connection string for runtime)
echo -n "postgresql+asyncpg://user:pass@ep-xxx.pooler.neon.tech/saturdays?sslmode=require" \
  | gcloud secrets create DATABASE_URL --data-file=- --project "$PROJECT_ID"

# JWT_SECRET_KEY  (generate a new one for production)
python -c "import secrets; print(secrets.token_hex(32))" \
  | gcloud secrets create JWT_SECRET_KEY --data-file=- --project "$PROJECT_ID"

# SECRET_KEY  (same value as JWT_SECRET_KEY)
gcloud secrets versions access latest --secret JWT_SECRET_KEY --project "$PROJECT_ID" \
  | gcloud secrets create SECRET_KEY --data-file=- --project "$PROJECT_ID"

# Razorpay
echo -n "rzp_live_XXXX"   | gcloud secrets create RAZORPAY_KEY_ID     --data-file=- --project "$PROJECT_ID"
echo -n "your_secret"     | gcloud secrets create RAZORPAY_KEY_SECRET  --data-file=- --project "$PROJECT_ID"
echo -n "webhook_secret"  | gcloud secrets create RAZORPAY_WEBHOOK_SECRET --data-file=- --project "$PROJECT_ID"
echo -n "account_number"  | gcloud secrets create RAZORPAYX_ACCOUNT_NUMBER --data-file=- --project "$PROJECT_ID"

# WhatsApp (only if WHATSAPP_ENABLED=true)
echo -n "EAA..." | gcloud secrets create WHATSAPP_ACCESS_TOKEN --data-file=- --project "$PROJECT_ID"
echo -n "..."    | gcloud secrets create WHATSAPP_APP_SECRET   --data-file=- --project "$PROJECT_ID"
echo -n "..."    | gcloud secrets create WHATSAPP_VERIFY_TOKEN --data-file=- --project "$PROJECT_ID"
```

### Grant the Cloud Run service account access

```bash
SERVICE_ACCOUNT="saturdays-api@${PROJECT_ID}.iam.gserviceaccount.com"

# Create a dedicated service account (recommended)
gcloud iam service-accounts create saturdays-api \
  --display-name "Saturdays API Cloud Run SA" \
  --project "$PROJECT_ID"

# Grant Secret Manager access
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:${SERVICE_ACCOUNT}" \
  --role "roles/secretmanager.secretAccessor"
```

---

## 4. First deploy (staging)

Use source-deploy so Cloud Build builds and pushes the image automatically:

```bash
SERVICE_NAME="saturdays-api"

gcloud run deploy "$SERVICE_NAME" \
  --source "." \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --platform managed \
  --service-account "$SERVICE_ACCOUNT" \
  --port 8080 \
  --cpu 1 \
  --memory 1Gi \
  --concurrency 8 \
  --min-instances 0 \
  --max-instances 5 \
  --timeout 60 \
  --no-allow-unauthenticated \
  --set-env-vars "ENVIRONMENT=production,PROJECT_NAME=Saturdays API,API_V1_STR=/api/v1,RAZORPAY_SIMULATE=false,PAYOUT_SCHEDULER_ENABLED=false,WHATSAPP_ENABLED=false" \
  --set-env-vars "CORS_ORIGINS=https://saturdays.co.in,https://www.saturdays.co.in,https://saturdays-lmx.web.app,https://saturdays-admin.web.app,https://saturdays-restaurant.web.app" \
  --set-env-vars "CORS_ORIGIN_REGEX=^https://.*(\\.vercel\\.app|\\.web\\.app|\\.firebaseapp\\.com|saturdays\\.co\\.in)$" \
  --set-secrets "DATABASE_URL=DATABASE_URL:latest,JWT_SECRET_KEY=JWT_SECRET_KEY:latest,SECRET_KEY=SECRET_KEY:latest,RAZORPAY_KEY_ID=RAZORPAY_KEY_ID:latest,RAZORPAY_KEY_SECRET=RAZORPAY_KEY_SECRET:latest,RAZORPAY_WEBHOOK_SECRET=RAZORPAY_WEBHOOK_SECRET:latest,RAZORPAYX_ACCOUNT_NUMBER=RAZORPAYX_ACCOUNT_NUMBER:latest"
```

> **`--no-allow-unauthenticated`** locks Cloud Run's outer IAM layer.  
> Application-level auth (JWT Bearer tokens) is preserved and enforced at the FastAPI layer.  
> To allow browser clients (they cannot attach GCP identity tokens), you will switch this  
> to `--allow-unauthenticated` **after** validating the staging URL — see step 7.

---

## 5. Run database migrations (manual — never automatic)

Migrations must be run from a machine that can reach Neon **directly** (not via the pooler).  
Use Neon's **unpooled** connection string for alembic.

```bash
# In the backend directory, with your virtualenv active:
export DATABASE_URL="postgresql+asyncpg://user:pass@ep-xxx.neon.tech/saturdays?sslmode=require"
alembic upgrade head
```

---

## 6. Health check validation

```bash
CLOUD_RUN_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region "$REGION" --project "$PROJECT_ID" \
  --format "value(status.url)")

# Liveness (no DB)
curl -sf "${CLOUD_RUN_URL}/health/live"

# Readiness (requires DB connection)
curl -sf "${CLOUD_RUN_URL}/health/ready"

# Full health (returns version)
curl -sf "${CLOUD_RUN_URL}/health"
```

Expected responses:
- `/health/live`  → `{"status":"alive"}`
- `/health/ready` → `{"status":"ready","database":"connected"}`
- `/health`       → `{"status":"ok","version":"1.0.0"}`

Configure Cloud Run health checks in Console:
- **Liveness probe**: `GET /health/live`, initial delay 10 s, period 30 s
- **Startup probe**: `GET /health/ready`, initial delay 5 s, period 5 s, failure threshold 6

---

## 7. Open to public traffic (after staging validation)

```bash
gcloud run services update "$SERVICE_NAME" \
  --region "$REGION" --project "$PROJECT_ID" \
  --allow-unauthenticated
```

Application-level JWT auth still enforces all protected routes.

---

## 8. Run load test against staging

```bash
# Install k6: https://k6.io/docs/getting-started/installation/
export BASE_URL="$CLOUD_RUN_URL"
export JWT_TOKEN="<issue a test-customer token from /api/v1/auth/login>"
k6 run scripts/load_test.js
```

Acceptance targets:
- `p95 < 1500 ms` for read endpoints
- `unexpected_failures rate < 1%`

---

## 9. Update Firebase frontend API URL

For each frontend app (`student`, `admin`, `restaurant`):

```bash
# apps/student/.env.production  (or set in your CI/CD environment)
VITE_API_URL=https://<your-cloud-run-url>/api/v1
```

Then rebuild and redeploy:
```bash
cd "Saturdays frontend"
pnpm run build        # or your existing build command
firebase deploy --only hosting
```

---

## 10. Rollback procedure

**Cloud Run traffic split (zero-downtime rollback):**
```bash
# List revisions
gcloud run revisions list --service "$SERVICE_NAME" --region "$REGION" --project "$PROJECT_ID"

# Roll back to a previous revision instantly
gcloud run services update-traffic "$SERVICE_NAME" \
  --region "$REGION" --project "$PROJECT_ID" \
  --to-revisions REVISION_NAME=100
```

**Vercel fallback:** Vercel is untouched throughout. If Cloud Run fails validation,
update `VITE_API_URL` back to the Vercel URL and redeploy the frontend.

---

## 11. Retire Vercel (only after full validation)

1. Confirm production traffic is stable on Cloud Run for ≥ 48 h.
2. Remove the `VITE_API_URL` Vercel URL from frontend env files.
3. Archive (do not delete) the Vercel project to preserve deployment logs.
4. Remove Vercel env vars containing secrets.

---

## 12. Scaling beyond initial config

After load testing, adjust with:

```bash
gcloud run services update "$SERVICE_NAME" \
  --region "$REGION" --project "$PROJECT_ID" \
  --concurrency 20 \
  --max-instances 20
```

**Neon connection math:** `max_instances × (pool_size + max_overflow)`.  
Current code: `5 × (5+5) = 50` connections at peak with 5 instances.  
At 20 instances: `20 × 10 = 200` connections — upgrade Neon plan before scaling past 10 instances.

**10k daily users estimate:** ~70 req/s sustained, ~200 req/s peak.  
With concurrency=20 and max_instances=20, Cloud Run handles this comfortably.  
Increase pool_size to 8 and max_overflow to 7 when scaling beyond 10 instances.

---

## 13. Environment variable reference

| Variable | Source | Notes |
|----------|--------|-------|
| `DATABASE_URL` | Secret Manager | Use pooled Neon URL for runtime |
| `JWT_SECRET_KEY` | Secret Manager | Generate with `secrets.token_hex(32)` |
| `SECRET_KEY` | Secret Manager | Same value as JWT_SECRET_KEY |
| `RAZORPAY_KEY_ID` | Secret Manager | |
| `RAZORPAY_KEY_SECRET` | Secret Manager | |
| `RAZORPAY_WEBHOOK_SECRET` | Secret Manager | |
| `RAZORPAYX_ACCOUNT_NUMBER` | Secret Manager | |
| `WHATSAPP_ACCESS_TOKEN` | Secret Manager | Only when WHATSAPP_ENABLED=true |
| `WHATSAPP_APP_SECRET` | Secret Manager | Only when WHATSAPP_ENABLED=true |
| `WHATSAPP_VERIFY_TOKEN` | Secret Manager | Only when WHATSAPP_ENABLED=true |
| `ENVIRONMENT` | Env var | `production` |
| `CORS_ORIGINS` | Env var | Comma-separated list |
| `CORS_ORIGIN_REGEX` | Env var | Regex for Vercel/Firebase previews |
| `RAZORPAY_SIMULATE` | Env var | `false` in production |
| `PAYOUT_SCHEDULER_ENABLED` | Env var | `false` — run via Cloud Scheduler separately |
| `WHATSAPP_ENABLED` | Env var | `false` until ready |

---

## 14. Known bottlenecks and risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| `GET /api/v1/media/<uuid>` reads binary blobs from DB | High latency at scale | Move images to Cloud Storage + CDN (see Phase 5 notes) |
| WebSocket `ws_manager` is in-process | WS clients disconnect on scale-in | Acceptable at ≤5 instances; at scale use Redis Pub/Sub |
| Payout scheduler inside API process | Runs on every container if `ENABLED=true` | Keep disabled; use Cloud Scheduler → Cloud Run Job instead |
| `ORDER_PAYMENT_WINDOW_MINUTES` timeout relies on background task | No persistent task queue | Same as above — Cloud Scheduler is safer |
