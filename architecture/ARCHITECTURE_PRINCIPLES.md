# SATURDAYS ARCHITECTURE PRINCIPLES

Version: 1.0  
Status: Non-Negotiable Architectural Axioms  
Owner: Chief Architect & Staff Engineering Council  

---

# Purpose

This document defines the baseline architectural principles governing every engineering design, database schema modification, API contract, and operational workflow across the Saturdays and DineGuru platforms.

These principles take precedence over developer preference, framework popularity, or short-term implementation speed. Every engineer contributing to this repository MUST understand, enforce, and abide by these axioms.

---

# Baseline Principles

## 1. Explain WHY Before HOW
Code explains *what* the system does today; architecture explains *why* the system exists, what trade-offs were evaluated, and why alternative approaches were rejected. 

Every design document MUST explain the business rationale and operational justification before detailing technical mechanics.

## 2. Production-Grade Modular Monolith
The platform MUST remain deployed as a single, operationally simple FastAPI application container sharing a single PostgreSQL database instance. 

Distributed microservice architectures, gRPC inter-service calls, and independent database per-service models are strictly forbidden at current scale targets. However, code MUST maintain clean, unidirectional in-process module boundaries to permit future service extraction if justified by scale metrics.

## 3. Shared Database with Single Ownership (No Synchronization)
Saturdays (customer surface) and DineGuru (merchant surface) operate over the same physical PostgreSQL database. 

Duplicate tables, asynchronous synchronization pipelines, and out-of-band polling for shared business data are strictly forbidden. To prevent data corruption, every database table MUST have exactly ONE owner business domain module that controls write access.

## 4. Single Source of Truth for Domain Concepts
Every business concept (Menu, Inventory, Order, Payment, Coupon) MUST be owned by exactly one bounded context module inside `07-modules/`. 

Other modules MUST consume data via explicit service interfaces or read-only repository queries owned by the authoritative module. Redefining domain entities or duplicating business validation across modules is considered an architectural defect.

## 5. Operations-First Design (Failure Before Success)
Architecture MUST prioritize operational survival over happy-path developer convenience. 

Every subsystem specification MUST define failure modes, degradation paths, rate limits, and recovery protocols before detailing normal operating workflows.

## 6. Zero Unquantified Buzzwords
Vague adjectives (*scalable*, *robust*, *modern*, *enterprise-grade*) are forbidden. 

All quality attributes MUST be expressed as concrete, verifiable metrics (e.g., *p95 latency $< 150\text{ms}$ at 500 requests/sec*, *RTO $< 15\text{min}$*, *RPO $< 1\text{min}$*).

## 7. Deferred Infrastructure Complexity
Infrastructure components MUST NOT be introduced simply because they are popular. 

Redis caching servers, Kafka/RabbitMQ message brokers, and Elasticsearch clusters MUST remain deferred until explicit performance or scale triggers documented in [15-roadmap/multi-phase-evolution-roadmap.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/15-roadmap/multi-phase-evolution-roadmap.md) are breached.

## 8. RFC 2119 Precision & 15-Year Maintainability
Documentation MUST be written using normative RFC 2119 language (`MUST`, `MUST NOT`, `SHOULD`, `MAY`) and maintain enough detail for a newly hired engineering team to operate the system 15 years from now without relying on original authors.
