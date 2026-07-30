# SATURDAYS ARCHITECTURE DECISIONS

Version: 1.0

Status: LOCKED

This document defines architectural decisions that are already finalized.

These decisions MUST NOT be changed unless explicitly instructed by the project owner.

If a better alternative exists, document it as an ADR, but do not change the architecture.

---

# Architecture

Decision

Production Modular Monolith

Status

LOCKED

Reason

Expected scale does not justify distributed systems.

The complexity of microservices outweighs their benefits.

The architecture should remain capable of future extraction.

---

Decision

Shared PostgreSQL Database

Status

LOCKED

Reason

DineGuru and Saturdays are two applications on one platform.

Synchronization layers introduce unnecessary complexity.

Single source of truth.

No duplicated business data.

---

Decision

One Source of Truth

Status

LOCKED

Every business entity has exactly one owner.

Examples

Menu

Inventory

Orders

Payments

Customers

Coupons

Reviews

No duplicated ownership.

---

# Technology

Backend

FastAPI

Status

LOCKED

---

ORM

SQLAlchemy

Status

LOCKED

---

Database

PostgreSQL

Status

LOCKED

Provider

NeonDB

---

Authentication

JWT

Google OAuth

Email OTP

Future Phone OTP

Status

LOCKED

---

Frontend

React

Status

LOCKED

---

Database Migrations

Alembic

Status

LOCKED

---

Caching

None initially

Only introduce Redis when justified.

Status

LOCKED

---

Message Broker

None initially.

No Kafka.

No RabbitMQ.

Introduce only after architectural justification.

Status

LOCKED

---

# Product Structure

Customer App

Saturdays

Status

LOCKED

---

Restaurant App

DineGuru

Status

LOCKED

---

Admin Portal

Integrated into Saturdays backend.

Status

LOCKED

---

Restaurant Hierarchy

Merchant

↓

Brand

↓

Branch

↓

Kitchen

Status

LOCKED

---

# Business Decisions

Restaurants never use Saturdays.

Status

LOCKED

---

Customers never use DineGuru.

Status

LOCKED

---

Orders appear immediately inside DineGuru.

No synchronization.

No polling.

No duplicate order tables.

Status

LOCKED

---

Inventory only changes inside DineGuru.

Status

LOCKED

---

Menus managed only inside DineGuru.

Customers consume those menus through Saturdays.

Status

LOCKED

---

Subscription

Monthly subscription.

Status

LOCKED

---

Revenue

Monthly subscription

+

Per-order commission.

Status

LOCKED

---

# Payments

Provider

Razorpay

Status

LOCKED

---

Payment records

Append-only.

Never rewritten.

Status

LOCKED

---

Refunds

Supported.

Status

LOCKED

---

# Initial Scope

Target

VIT Vellore

Restaurants inside campus.

Restaurants outside campus.

Students.

Faculty.

Status

LOCKED

---

Scale

100–500 restaurants

Status

LOCKED

---

Users

Tens of thousands.

Status

LOCKED

---

# Search

Supported

Restaurant

Dish

Cuisine

Category

Distance

Rating

Offers

Availability

Status

LOCKED

---

AI Search

Future.

Status

Deferred

---

# Reviews

Restaurant reviews

Food reviews

No rider reviews.

No photo reviews.

Status

LOCKED

---

# Notifications

Current

Email

Future

Push

SMS

WhatsApp

Status

LOCKED

---

# Rider System

Not implemented.

Architecture should support future rider integration.

Status

Deferred

---

# Wallet

Deferred.

---

# Loyalty

Deferred.

---

# Recommendations

Deferred.

---

# AI

Deferred.

---

# Multi-city

Deferred.

Architecture must support expansion.

---

# Coding Philosophy

Explicit over implicit.

Simple over clever.

Maintainable over optimized.

Operationally simple.

Domain-driven.

Strong module ownership.

Minimal coupling.

High cohesion.

---

# Documentation Philosophy

Every architectural decision requires

Reasoning

Tradeoffs

Future evolution

Migration considerations

Failure modes

Operational implications

Security implications

Performance implications

---

# Change Policy

No locked decision may be modified automatically.

If a future document requires changing a locked decision,

Create an ADR.

Explain why.

Describe migration.

Describe operational impact.

Wait for explicit approval.

Never silently redesign the platform.

---

# Final Principle

Architecture consistency is more valuable than architectural perfection.

Protect consistency.