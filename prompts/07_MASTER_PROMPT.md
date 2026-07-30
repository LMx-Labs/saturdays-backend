# Saturdays Architecture Generation

## Master Execution Prompt

You are beginning a long-term engineering project.

Before writing anything, you MUST read and fully internalize the following governing documents located in the `prompts/` directory:

1. 01_ROLE.md
2. 02_PROJECT.md
3. 03_DOCUMENT_REQUIREMENTS.md
4. 04_WORKFLOW.md
5. 05_OUTPUT_STRUCTURE.md
6. 06_GENERATION_RULES.md

Treat these six files as immutable governing documents.

Never contradict them.

If a conflict arises, stop and explain the conflict rather than making assumptions.

---

# Mission

Your mission is to generate the complete engineering architecture repository for Saturdays.

This repository should become the canonical engineering specification for the platform.

The documentation should be capable of surviving at least fifteen years of engineering evolution.

The repository should contain enough information that an experienced engineering team could rebuild the platform from scratch without consulting the original authors.

---

# Project Context

Use the project definition contained in `02_PROJECT.md`.

Do not invent additional business requirements unless absolutely necessary.

If assumptions are required,

state them explicitly,

justify them,

and minimize them.

---

# Engineering Philosophy

Always optimize for

Maintainability.

Correctness.

Clarity.

Operational simplicity.

Explicit reasoning.

Long-term evolution.

Never optimize for shorter output.

Never optimize for impressiveness.

Never optimize for fashionable architecture.

Always optimize for engineering quality.

---

# Documentation Philosophy

The generated repository is NOT documentation.

It is an engineering specification.

Every architectural decision should answer

Why was this chosen?

What alternatives existed?

Why were those alternatives rejected?

How will this evolve?

What must future engineers never violate?

---

# Output Strategy

Do NOT attempt to generate the entire repository at once.

Instead,

generate one document at a time.

Each document should be production quality before continuing.

After completing a document,

verify

cross references,

terminology,

ownership,

ADRs,

glossary,

diagrams,

and consistency.

Only then continue.

---

# Repository Ownership

Every document owns exactly one concept.

Never duplicate ownership.

Instead,

cross-reference the authoritative document.

Example

Authentication owns authentication.

Orders owns orders.

Payments owns payments.

Database owns schema design.

Other documents should reference these.

---

# Architecture Style

The architecture should be based on

Production-grade Modular Monolith

FastAPI

SQLAlchemy

PostgreSQL

NeonDB

JWT Authentication

React frontend

Shared database with DineGuru

Merchant

↓

Brand

↓

Branch

↓

Kitchen

Architecture should support future extraction into microservices without requiring business logic rewrites.

---

# Required Quality

Every document must satisfy the requirements defined in

03_DOCUMENT_REQUIREMENTS.md

Do not omit any required sections.

---

# Required Workflow

Follow

04_WORKFLOW.md

for every document.

Never skip review.

Never skip consistency verification.

Never skip cross references.

---

# Repository Structure

Generate documentation exactly according to

05_OUTPUT_STRUCTURE.md

Do not invent a different structure.

---

# Hard Rules

Follow

06_GENERATION_RULES.md

at all times.

These rules override convenience.

---

# Diagrams

Prefer Mermaid.

Use PlantUML only where Mermaid is insufficient.

Every important workflow should include diagrams.

Every important state should include state machines.

Every major subsystem should include component diagrams.

Every important relationship should include ER diagrams.

---

# Architecture Decision Records

Every major engineering decision should produce or update an ADR.

Never introduce major architecture without documenting why it exists.

---

# Writing Style

Use precise engineering language.

Avoid marketing language.

Avoid buzzwords.

Avoid vague wording.

Avoid unnecessary adjectives.

Write like internal engineering documentation written by experienced Staff Engineers.

---

# Assumptions

Whenever assumptions are required

Create a clearly labeled

"Assumptions"

section.

Never hide assumptions inside prose.

---

# If Information Is Missing

If information required to make an architectural decision is unavailable

Do NOT invent business requirements.

Instead

1. Explain what information is missing.

2. Explain why it matters.

3. Make the smallest reasonable assumption.

4. Continue while clearly documenting that assumption.

---

# Generation Order

Generate the repository in the following order.

Foundation

↓

Business

↓

Domain Model

↓

System

↓

Backend

↓

Database

↓

API

↓

Modules

↓

Admin

↓

Security

↓

Observability

↓

DevOps

↓

Testing

↓

Runbooks

↓

ADRs

↓

Roadmap

↓

Appendices

Do not skip ahead.

---

# Repository Maintenance

Whenever a later architectural decision changes an earlier one,

update the earlier document.

Do not allow stale documentation.

Do not allow contradictions.

Treat the repository as a living engineering specification.

---

# Completion Criteria

The repository is complete only when

Every module has an owner.

Every table is documented.

Every API is documented.

Every business rule is documented.

Every invariant is documented.

Every workflow has sequence diagrams.

Every stateful entity has state machines.

Every architectural decision has reasoning.

Every important decision has an ADR.

Every subsystem has security documentation.

Every subsystem has observability documentation.

Every subsystem has scalability documentation.

Every subsystem has operational documentation.

Every subsystem has migration guidance.

Every subsystem has future evolution guidance.

Every cross-reference is valid.

No contradictions exist.

---

# Final Principle

Assume that every original engineer has permanently left the company.

The architecture repository is now the only source of engineering truth.

Generate documentation worthy of that responsibility.

---

# Begin

Begin by generating:

architecture/

README.md

Then continue with

00-foundation/

following the repository structure defined in `05_OUTPUT_STRUCTURE.md`.

After every completed document,

perform a consistency review before generating the next document.