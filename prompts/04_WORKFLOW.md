# WORKFLOW

Version: 1.0

Status: Mandatory

---

# Purpose

This document defines how the architecture documentation must be generated.

The goal is to produce a coherent engineering handbook rather than a collection of unrelated documents.

Every chapter must build upon previous chapters.

Every decision must remain consistent.

Architecture drift is forbidden.

---

# General Philosophy

Do not think of this as writing documentation.

Think of this as building a software system.

The documentation itself is a software project.

Each chapter is a module.

Each module has dependencies.

Every dependency must remain consistent.

Never generate chapters independently.

Always understand the complete architecture before writing.

---

# Documentation Lifecycle

For every chapter perform the following steps.

Step 1

Understand all previous chapters.

---

Step 2

Identify every dependency.

---

Step 3

Identify architectural assumptions.

---

Step 4

Verify assumptions against previous documentation.

---

Step 5

Write the chapter.

---

Step 6

Cross-reference previous chapters.

---

Step 7

Update glossary if necessary.

---

Step 8

Update Architecture Decision Records if necessary.

---

Step 9

Update diagrams if necessary.

---

Step 10

Review consistency.

---

Only after these steps may the next chapter begin.

---

# Never Skip Cross References

Whenever a chapter references another subsystem,

create explicit references.

Example

Orders depends on

Payments

Menu

Customers

Branches

Notifications

Inventory

Instead of repeating explanations,

reference the authoritative chapter.

One chapter owns one concept.

---

# Single Source of Truth

Every concept must have exactly one owner.

Examples

Authentication

Owned by Authentication chapter.

Do not redefine authentication elsewhere.

Orders

Owned by Orders chapter.

Payments

Owned by Payments chapter.

Coupons

Owned by Coupon chapter.

Every other chapter references them.

Do not duplicate ownership.

---

# No Contradictions

If a later architectural decision conflicts with an earlier decision,

do NOT ignore the conflict.

Instead

Return to the earlier chapter.

Update it.

Update all references.

Update affected diagrams.

Update Architecture Decision Records.

Maintain consistency.

---

# Living Documentation

The documentation is alive.

Whenever architecture evolves

Old chapters evolve too.

Never allow obsolete documentation to remain.

Never append contradictory notes.

Rewrite instead.

---

# Architecture Decision Process

Every major decision follows this process.

Problem

↓

Requirements

↓

Possible Solutions

↓

Tradeoff Analysis

↓

Decision

↓

Consequences

↓

Future Impact

↓

Migration Strategy

↓

Architecture Decision Record

No major architectural decision should exist without reasoning.

---

# Dependency Rules

Always document dependency direction.

Examples

Orders

depends on

Payments

Customers

Menu

Branches

Notifications

Payments should never depend on Orders internally.

Avoid circular dependencies.

Every dependency should have justification.

---

# Layering Rules

Always enforce architectural layers.

Presentation

↓

API

↓

Application

↓

Domain

↓

Persistence

↓

Database

Never violate dependency direction.

Never allow infrastructure to leak into domain logic.

---

# Module Independence

Every module should be understandable in isolation.

However,

every module should integrate seamlessly with the platform.

Clearly define:

Inputs

Outputs

Dependencies

Ownership

Failure boundaries

---

# Diagrams

Every chapter should update diagrams when required.

Examples

Component diagrams

Sequence diagrams

State diagrams

Deployment diagrams

ER diagrams

Dependency graphs

Never allow diagrams to become outdated.

---

# Glossary

Maintain a single glossary.

Whenever a new engineering term appears,

evaluate whether it belongs in the glossary.

Never define the same term twice.

---

# ADR Workflow

Whenever architecture changes,

create or update Architecture Decision Records.

Examples

Why PostgreSQL

Why FastAPI

Why Shared Database

Why Modular Monolith

Why Merchant hierarchy

Why JWT

Why SQLAlchemy

Why Razorpay

Why NeonDB

Every major engineering decision deserves an ADR.

---

# Database Workflow

Before documenting a table,

identify

Business owner

Module owner

Relationships

Expected growth

Migration strategy

Read patterns

Write patterns

Indexes

Constraints

Retention

Future evolution

Only then describe columns.

Columns should never be documented first.

Business reasoning always comes first.

---

# API Workflow

Before documenting an endpoint,

identify

Business capability

Consumers

Authorization

Validation

Transaction boundaries

Concurrency

Failure handling

Performance

Versioning

Only then define request and response formats.

---

# Feature Workflow

Every new feature should answer

Why does it exist?

Why now?

Who owns it?

Who uses it?

Who modifies it?

How is it monitored?

How is it tested?

How will it evolve?

What happens when it fails?

---

# Review Process

Every completed chapter must be reviewed.

Checklist

✓ No contradictions

✓ No duplicated ownership

✓ References updated

✓ Diagrams updated

✓ ADRs updated

✓ Glossary updated

✓ Terminology consistent

✓ Invariants preserved

✓ Failure modes documented

✓ Security reviewed

✓ Performance reviewed

✓ Scalability reviewed

Only then is the chapter complete.

---

# Future Evolution

Every chapter must conclude with

Current Design

Known Limitations

Extension Points

Migration Paths

Future Improvements

Breaking Change Risks

Backward Compatibility

Long-Term Vision

Every subsystem should be designed for evolution.

---

# Engineering Memory

Whenever an important engineering decision is made,

document it immediately.

Never rely on future engineers remembering context.

Documentation replaces memory.

Documentation replaces meetings.

Documentation replaces tribal knowledge.

---

# Final Principle

Always write as if every engineer who built Saturdays has permanently left the company.

The documentation must be sufficient for a completely new engineering team to continue development without needing additional explanation.

If any implementation detail, architectural decision, or design rationale exists only in your reasoning and not in the documentation, then the documentation is incomplete.

The repository is the engineering memory of Saturdays.

Protect it accordingly.