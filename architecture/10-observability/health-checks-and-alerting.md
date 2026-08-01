# HEALTH CHECKS & ALERTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Health Check & Alerting Specification  
Owner: Chief Architect & Site Reliability Engineering (SRE)  

---

# Purpose

This document specifies the container health check probe endpoints and automated alerting rules.

---

# Container Health Check Probes

1. **Liveness Probe (`GET /health/live`)**:
   * **Purpose**: Verifies that the FastAPI process container is alive and responding to requests.
   * **Response**: `HTTP 200 OK` `{ "status": "UP" }`.
   * **Action on Failure**: Container orchestrator automatically restarts the pod container.
2. **Readiness Probe (`GET /health/ready`)**:
   * **Purpose**: Verifies that the container can connect to PostgreSQL database pool on NeonDB.
   * **Response**: `HTTP 200 OK` `{ "status": "READY", "database": "CONNECTED" }`.
   * **Action on Failure**: Container orchestrator removes pod container from load balancer routing until connection recovers.

---

# Automated Alerting Rules Matrix

| Severity | Alert Rule Trigger | Target Channel | Response SLA | Action Required |
| :--- | :--- | :--- | :--- | :--- |
| **P1 - Critical** | HTTP 5xx error rate $> 2\%$ over 5 minutes OR DB connection pool saturation $> 95\%$. | PagerDuty / On-Call Phone Call | $< 15\text{ minutes}$ | Immediate incident response; trigger DR failover if DB unresponsive. |
| **P2 - Warning** | p95 API latency $> 300\text{ms}$ over 15 minutes OR SendGrid error rate $> 5\%$. | Slack `#alerts-warning` Channel | $< 2\text{ hours}$ | Investigate query logs, slow queries, or third-party vendor status pages. |
