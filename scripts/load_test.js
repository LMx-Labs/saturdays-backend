"""k6 load-test for Saturdays API staging environment.

Usage:
  export BASE_URL=https://<your-cloud-run-staging-url>
  export JWT_TOKEN=<valid-access-token-for-a-test-customer>
  k6 run scripts/load_test.js

Targets:
  - p95 latency < 1500 ms for ordinary reads
  - Unexpected failure rate (non-4xx) < 1%
  - Ramp 100 → 200 VUs over 5 min, hold 5 min, ramp down 2 min
*/
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const failRate   = new Rate('unexpected_failures');
const p95Read    = new Trend('p95_read_latency');

export const options = {
  stages: [
    { duration: '2m', target: 100 },   // ramp to 100 VUs
    { duration: '3m', target: 200 },   // ramp to 200 VUs
    { duration: '5m', target: 200 },   // hold at 200 VUs
    { duration: '2m', target: 0   },   // ramp down
  ],
  thresholds: {
    'http_req_duration{type:read}': ['p(95)<1500'],
    'unexpected_failures':          ['rate<0.01'],
    'http_req_failed':              ['rate<0.05'],
  },
};

const BASE_URL  = __ENV.BASE_URL  || 'http://localhost:8000';
const JWT_TOKEN = __ENV.JWT_TOKEN || '';

const authHeaders = {
  'Authorization': `Bearer ${JWT_TOKEN}`,
  'Content-Type':  'application/json',
};

export default function () {
  // ── Health check ──────────────────────────────────────────────────────────
  const health = http.get(`${BASE_URL}/health`);
  check(health, { 'health 200': (r) => r.status === 200 });

  // ── Menu read (high-traffic, unauthenticated) ─────────────────────────────
  const menu = http.get(`${BASE_URL}/api/v1/menu`, { tags: { type: 'read' } });
  p95Read.add(menu.timings.duration);
  const menuOk = check(menu, { 'menu 200': (r) => r.status === 200 });
  if (!menuOk && menu.status >= 500) failRate.add(1); else failRate.add(0);

  // ── Branch list read ──────────────────────────────────────────────────────
  const branches = http.get(`${BASE_URL}/api/v1/branches`, { tags: { type: 'read' } });
  p95Read.add(branches.timings.duration);
  if (branches.status >= 500) failRate.add(1); else failRate.add(0);

  // ── Authenticated: cart read (requires JWT_TOKEN) ─────────────────────────
  if (JWT_TOKEN) {
    const cart = http.get(`${BASE_URL}/api/v1/cart`, {
      headers: authHeaders,
      tags: { type: 'read' },
    });
    p95Read.add(cart.timings.duration);
    if (cart.status >= 500) failRate.add(1); else failRate.add(0);

    // ── Authenticated: order list (paginated, DB-heavy) ───────────────────
    const orders = http.get(`${BASE_URL}/api/v1/orders`, {
      headers: authHeaders,
      tags: { type: 'read' },
    });
    p95Read.add(orders.timings.duration);
    if (orders.status >= 500) failRate.add(1); else failRate.add(0);
  }

  sleep(1);
}
