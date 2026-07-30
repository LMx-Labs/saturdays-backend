# SATURDAYS DOCUMENTATION STYLE GUIDE

Version: 1.0

Status: Mandatory

---

# Purpose

This document defines writing standards for every document in the Saturdays Architecture Repository.

The objective is consistency.

Every document should appear as though it was written by the same engineering organization.

Regardless of when it was generated.

Regardless of who generated it.

---

# Writing Style

Write like an internal engineering specification.

Not like a textbook.

Not like a blog.

Not like marketing documentation.

Not like tutorials.

Assume the audience consists of experienced software engineers.

---

# Language

Use

Clear

Direct

Technical

Objective

Neutral

Avoid conversational writing.

Avoid unnecessary adjectives.

Avoid storytelling.

---

# RFC 2119

Use RFC 2119 terminology.

MUST

MUST NOT

REQUIRED

SHALL

SHALL NOT

SHOULD

SHOULD NOT

RECOMMENDED

MAY

OPTIONAL

These words have normative meaning.

Use them consistently.

---

# Markdown Rules

Always use

# H1

## H2

### H3

#### H4

Never skip heading levels.

Never use bold text instead of headings.

---

# Headings

Every document begins with

Title

Version

Status

Purpose

Scope

Dependencies

Ownership

Never omit these.

---

# Paragraphs

Keep paragraphs short.

Each paragraph should communicate one idea.

Avoid giant walls of text.

---

# Lists

Prefer unordered lists.

Only use numbered lists for

Workflows

Procedures

Sequences

Algorithms

Everything else should use bullets.

---

# Tables

Use tables whenever comparing

Architectural options

Database fields

APIs

Permissions

Tradeoffs

States

Responsibilities

Avoid tables for prose.

---

# Callouts

Use callouts sparingly.

Example

> Important

> Warning

> Note

Do not overuse.

---

# Diagrams

Prefer Mermaid.

Every major workflow should include diagrams.

Every stateful object should include state machines.

Every module should include component diagrams.

Every database chapter should include ER diagrams.

Every deployment chapter should include deployment diagrams.

---

# Mermaid Style

Use

flowchart

sequenceDiagram

stateDiagram-v2

erDiagram

graph TD

Avoid overly complex diagrams.

Split diagrams if necessary.

---

# Naming

Use lowercase filenames.

Example

merchant-onboarding.md

Never

MerchantOnboarding.md

Never

merchant onboarding.md

---

# Module Naming

Use singular nouns.

Correct

Customer

Merchant

Branch

Order

Payment

Incorrect

Customers

Orders

Payments

---

# API Naming

Use REST conventions.

Example

GET /orders

POST /orders

GET /orders/{id}

PATCH /orders/{id}

DELETE /orders/{id}

Avoid verbs.

Never

/createOrder

/getOrder

/updateOrder

---

# Database Naming

Tables

snake_case

Columns

snake_case

Foreign Keys

<entity>_id

Example

customer_id

branch_id

merchant_id

---

# Primary Keys

Use

id

Avoid

customerID

CustomerId

pk_customer

---

# Timestamps

Use

created_at

updated_at

deleted_at

Never invent alternatives.

---

# UUIDs

Document reasoning whenever UUIDs are used.

Explain

Why UUID

Why not integer

Operational implications

Index implications

---

# Code Blocks

Always specify language.

```python

```sql

```mermaid

```bash

Never use plain code blocks.

---

# SQL

Use uppercase SQL keywords.

Example

SELECT

FROM

WHERE

JOIN

ORDER BY

---

# JSON

Pretty print.

2-space indentation.

Keys in logical order.

---

# Examples

Every important concept should include examples.

Examples should be realistic.

Never use

Foo

Bar

Baz

Use restaurant-related examples.

---

# Cross References

Always link to authoritative documents.

Never duplicate explanations.

Example

See:

Orders Module

Payments Module

Database Standards

ADR-0004

---

# Architecture Decision Records

Every ADR follows

Problem

Context

Options

Tradeoffs

Decision

Consequences

Migration

Future Evolution

---

# Module Documents

Every module follows

README

Overview

Responsibilities

Architecture

Database

APIs

Events

State Machines

Security

Monitoring

Testing

Future

Exactly this order.

---

# Database Documentation

Every table follows

Purpose

Business Ownership

Relationships

Columns

Indexes

Constraints

Triggers

Query Patterns

Growth

Retention

Migration

Examples

---

# API Documentation

Every endpoint follows

Purpose

Route

Authentication

Authorization

Request

Validation

Business Rules

Transaction

Errors

Examples

Performance

Security

Future

---

# State Machines

Every state machine documents

States

Transitions

Illegal States

Recovery

Terminal States

Failure States

---

# Sequence Diagrams

Every sequence diagram identifies

Actors

Systems

Messages

Errors

Retries

Compensation

Timeouts

---

# Glossary

Every technical term belongs in

GLOSSARY.md

Never define terms repeatedly.

---

# Terminology

Always use

Merchant

Brand

Branch

Kitchen

Customer

Order

Payment

Coupon

Module

Aggregate

Domain Event

Never invent synonyms.

Consistency matters.

---

# Architecture Vocabulary

Use

Module

Subsystem

Component

Layer

Boundary

Contract

Aggregate

Invariant

Never randomly switch terminology.

---

# Writing Philosophy

Explain WHY before WHAT.

Explain WHAT before HOW.

Explain HOW before IMPLEMENTATION.

---

# Quality Standard

Every document should be understandable by

A new graduate.

A senior engineer.

A staff engineer.

A principal engineer.

A CTO.

Without additional explanation.

---

# Final Principle

The documentation should feel like it belongs inside an engineering organization that values precision, clarity, and long-term maintainability over speed.

Every document should look as though it was written by the same author, even if generated years apart.