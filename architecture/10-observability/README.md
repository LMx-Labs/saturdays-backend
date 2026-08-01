# 10-OBSERVABILITY — LOGGING, METRICS & ALERTING SPECIFICATIONS

Version: 1.0  
Status: Authoritative Observability Specification Index  
Owner: Chief Architect & Site Reliability Engineering (SRE)  

---

# Purpose

The `10-observability/` directory specifies the structured logging framework, Prometheus operational metrics collection, SLA/SLO monitoring, health check probes, and automated alerting rules for Saturdays and DineGuru.

---

# Consolidated Specifications Index

1. [logging-metrics-and-slas.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/10-observability/logging-metrics-and-slas.md)
   * **Structured Logging Standards**: Structlog JSON configuration, correlation ID context binding, and log level definitions.
   * **Prometheus Metrics Framework**: Four Golden Signals (Latency, Traffic, Errors, Saturation) and domain operational counters.
   * **SLA / SLO Tracking**: 99.9% availability SLA, latency budget SLOs, and error budget consumption rules.
2. [health-checks-and-alerting.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/10-observability/health-checks-and-alerting.md)
   * **Health Check Probes**: `/health/live` (Liveness) and `/health/ready` (Readiness) endpoint probes.
   * **Automated Alerting Rules**: Critical (P1) and Warning (P2) alert thresholds for latency spikes, error rates, and DB pool saturation.

---

# Dependencies

- [03.5-non-functional/performance-scalability-and-sla.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/03.5-non-functional/performance-scalability-and-sla.md) — SLA/SLO performance targets.
- [04-backend/fastapi-architecture-and-layering.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/04-backend/fastapi-architecture-and-layering.md) — Structlog setup.
