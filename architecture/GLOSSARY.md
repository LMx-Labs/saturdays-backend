# SATURDAYS ARCHITECTURE GLOSSARY

Version: 1.0  
Status: Authoritative Terminology Dictionary  
Owner: Chief Architect  

---

# Purpose

This document is the canonical dictionary of all domain terminology, technical concepts, organizational entities, and acronyms used across the Saturdays Architecture Repository.

To preserve single-source-of-truth integrity and prevent architectural confusion, engineers MUST use these exact terms in code, database schemas, API contracts, and documentation. Inventing unauthorized synonyms or altering definitions is strictly forbidden.

---

# Domain & Business Terms

### Aggregate Root
A Domain-Driven Design (DDD) encapsulation boundary that clusters domain entities and value objects together, enforcing domain invariants across all internal modifications.

### Brand
A public marketing identity and menu umbrella owned by a Merchant (e.g., *Domino's*, *Subway*). A single Merchant MAY own multiple Brands. Each Brand MAY operate multiple physical Branches.

### Branch
A physical store location where food preparation or pickup/delivery fulfillment occurs. Customers place orders specifically against a Branch. Operating hours, menu availability, and pricing MAY vary by Branch.

### Bounded Context
A explicit boundary within which a domain model applies. Each bounded context maps 1:1 to a business domain module inside `07-modules/`.

### Customer
An end-user who browses menus, builds carts, applies coupons, places orders, and submits reviews through the customer-facing **Saturdays** application.

### DineGuru
The merchant-facing application surface used exclusively by restaurant management and kitchen staff for catalog editing, inventory updates, kitchen order dispatch, and store configuration.

### Domain Invariant
A business rule or condition that MUST remain true at all times within a bounded context or aggregate root (e.g., *An order cannot be accepted if an item is out of stock*).

### Kitchen
An operational preparation unit associated with a Branch. In initial phases, each Branch maps 1:1 to a single Kitchen. Architecture supports multi-kitchen routing per branch.

### Merchant
The legal business entity and account holder responsible for financial settlements, subscription payments to the platform, and legal ownership of Brands and Branches.

### Saturdays
The customer-facing application surface (React web app) used exclusively by customers to discover restaurants, order food, and track orders.

---

# Technical & Architectural Terms

### Alembic
The official database migration tool used alongside SQLAlchemy to manage versioned relational schema changes in PostgreSQL.

### Append-Only Ledger
A database design pattern where records (such as payment transactions or audit logs) are strictly inserted and NEVER updated or deleted, providing an immutable historical audit trail.

### FastAPI
The modern, asynchronous Python web framework used to build the core Saturdays unified backend API service.

### Modular Monolith
An architectural style where a system is deployed as a single monolithic container/process, but internally structured into strictly isolated, decoupled business domain modules with clean in-process service boundaries.

### NeonDB
The cloud-native, serverless PostgreSQL database hosting platform utilized for persistence.

### Razorpay
The primary payment gateway provider integrated for handling online customer payments, webhooks, and refund processing.

### RBAC (Role-Based Access Control)
An authorization paradigm that restricts resource access based on assigned user roles (`Customer`, `BranchManager`, `PlatformAdmin`).

### Shared Database Pattern
An architecture pattern where two application surfaces (Saturdays and DineGuru) interact with a single shared PostgreSQL database instance without intermediate API synchronization layers.

---

# Standards & Metrics Glossary

### Latency Budget (p95 / p99)
The maximum acceptable response time for a given percentile of requests (e.g., p95 $< 200\text{ms}$).

### RPO (Recovery Point Objective)
The maximum acceptable duration of data loss measured in time following a disaster or failure.

### RTO (Recovery Time Objective)
The maximum acceptable duration of downtime required to restore normal system operations following a disruption.

### SLA (Service Level Agreement)
The formal commitment made to platform stakeholders regarding system availability and performance.

### SLO (Service Level Objective)
The internal target metric set by engineering teams to measure compliance with SLAs.
