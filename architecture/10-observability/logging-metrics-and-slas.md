# LOGGING, METRICS & SLA SPECIFICATIONS

Version: 1.0  
Status: Authoritative Logging & Metrics Specification  
Owner: Chief Architect & Site Reliability Engineering (SRE)  

---

# Purpose

This document specifies the structured JSON logging format, Prometheus operational metrics schema, Four Golden Signals telemetry, and SLA/SLO tracking policies.

---

# Structured JSON Logging Schema

All backend logs MUST be emitted as single-line JSON strings to standard stdout using `structlog`:

```json
{
  "timestamp": "2026-07-30T19:55:00.123456Z",
  "level": "info",
  "event": "Order placed successfully",
  "correlation_id": "req-9b8c7a6f-5e4d-3c2b-1a0f-1234567890ab",
  "module": "order",
  "user_id": "018f3a9b-7c1d-7000-8000-000000000001",
  "order_id": "018f3a9b-7c1d-7000-8000-000000000002",
  "branch_id": "018f3a9b-7c1d-7000-8000-000000000003",
  "latency_ms": 142.5
}
```

---

# Prometheus Operational Metrics (Four Golden Signals)

The `/metrics` endpoint MUST expose Prometheus formatted metrics tracking system state:

| Golden Signal | Prometheus Metric Name | Type | Description |
| :--- | :--- | :--- | :--- |
| **Latency** | `http_request_duration_seconds` | Histogram | Request latency bucketed by route, method, and status code. |
| **Traffic** | `http_requests_total` | Counter | Total HTTP requests processed. |
| **Errors** | `http_requests_failed_total` | Counter | Total 5xx server errors and unhandled exceptions. |
| **Saturation** | `db_connection_pool_active` | Gauge | Active PostgreSQL connections in use. |

---

# SLA / SLO Tracking & Error Budget Policy

- **Availability SLA**: 99.9% monthly uptime ($< 43.8\text{ minutes}$ allowable downtime / month).
- **Latency SLO**: 95% of API requests MUST complete in $< 200\text{ms}$; 99% in $< 500\text{ms}$.
- **Error Budget Exhaustion Policy**: If 80% of monthly error budget is consumed, feature deployments are frozen; engineering team focuses 100% on performance and stability fixes.
