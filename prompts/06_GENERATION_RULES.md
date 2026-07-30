# GENERATION RULES

Version: 1.0

Status: Mandatory

These rules govern every document generated for the Saturdays architecture repository.

Violating these rules produces invalid documentation.

---

# Primary Objective

Produce documentation that could realistically become the internal engineering handbook of a company.

Not example documentation.

Not educational material.

Not tutorials.

Not blog posts.

Produce engineering specifications.

---

# Rule 1

Always explain WHY before HOW.

Wrong:

Orders are stored in PostgreSQL.

Correct:

Orders are stored in PostgreSQL because transactional consistency, ACID guarantees, referential integrity, and operational simplicity outweigh the benefits of distributed persistence at the expected scale.

---

# Rule 2

Never introduce technology because it is popular.

Every technology must justify its existence.

For every framework, library, dependency, or infrastructure component explain

Why it exists.

Why it was chosen.

Alternatives considered.

Why alternatives were rejected.

Operational cost.

Migration difficulty.

Scaling implications.

Long-term maintenance implications.

---

# Rule 3

Never use buzzwords.

Forbidden examples

Scalable

Enterprise-grade

Cloud-native

Future-proof

Modern

Robust

Instead explain exactly HOW the architecture achieves those properties.

---

# Rule 4

Never leave TODOs.

Never write

TODO

TBD

Coming later

Future implementation

Implementation omitted

Instead describe

How future implementation should integrate.

What assumptions already exist.

Which extension points were intentionally designed.

---

# Rule 5

Every feature must justify its existence.

Never document a feature without explaining

Business problem

Engineering problem

Operational problem

Future benefit

Tradeoffs

---

# Rule 6

Every architectural decision must have tradeoff analysis.

Document

Advantages

Disadvantages

Alternatives

Risks

Migration cost

Maintenance burden

Future evolution

---

# Rule 7

Never duplicate ownership.

Every concept has one authoritative owner.

Examples

Authentication

Authentication chapter.

Orders

Orders chapter.

Payments

Payments chapter.

Other documents reference them.

Never redefine concepts.

---

# Rule 8

Every business rule must explain WHY it exists.

Example

Orders cannot change branches.

Do not stop there.

Explain

Operational consistency.

Kitchen ownership.

Payment integrity.

Reporting.

Fraud prevention.

Analytics consistency.

---

# Rule 9

Every table deserves architectural reasoning.

Do not simply list columns.

Explain

Why table exists.

Why primary key exists.

Why foreign keys exist.

Why indexes exist.

Expected query patterns.

Growth expectations.

Retention policy.

Migration strategy.

---

# Rule 10

Every API deserves architectural reasoning.

Before request body.

Before response body.

Explain

Purpose.

Consumers.

Ownership.

Transaction boundaries.

Authorization.

Concurrency.

Failure behaviour.

Retries.

Idempotency.

Performance expectations.

---

# Rule 11

Every workflow requires diagrams.

Use Mermaid.

Whenever possible include

Sequence diagrams.

State diagrams.

Flowcharts.

Component diagrams.

ER diagrams.

Deployment diagrams.

Dependency diagrams.

Text alone is insufficient.

---

# Rule 12

Document failure before success.

Every subsystem should first answer

What happens when it fails?

Only then explain normal operation.

Failure handling is architecture.

---

# Rule 13

Document operational behaviour.

Every subsystem should answer

How is it monitored?

How is it deployed?

How is it rolled back?

How is it upgraded?

How is it debugged?

How is it recovered?

---

# Rule 14

Document security as a first-class concern.

Never treat security as an appendix.

Every subsystem should explain

Authentication.

Authorization.

Trust boundaries.

Input validation.

Sensitive data.

Encryption.

Logging.

Rate limiting.

Abuse prevention.

Threat model.

---

# Rule 15

Document observability.

Every subsystem should expose

Logs.

Metrics.

Health checks.

Alerts.

Tracing.

Dashboards.

Expected signals.

---

# Rule 16

Document scalability honestly.

Do not claim infinite scalability.

Document

Current limits.

Expected bottlenecks.

Migration path.

Horizontal scaling strategy.

Vertical scaling strategy.

Database scaling.

Operational cost.

---

# Rule 17

Use precise language.

Forbidden

Fast

Simple

Efficient

Optimized

Instead quantify.

Expected latency.

Expected throughput.

Expected scale.

Expected complexity.

---

# Rule 18

Prefer explicit assumptions.

Whenever assumptions exist,

state them explicitly.

Never hide assumptions.

---

# Rule 19

Every chapter concludes with

Current Design

Known Limitations

Technical Debt

Future Improvements

Migration Paths

Breaking Change Risks

Open Questions

References

---

# Rule 20

Maintain consistency.

Terminology.

Naming.

Ownership.

Architecture.

Diagrams.

Examples.

Everything.

---

# Rule 21

Every statement should answer one of

Why?

What?

Who?

When?

Where?

How?

If a sentence answers none of these,

it probably does not belong.

---

# Rule 22

Assume engineers disagree.

Document enough reasoning that future engineers can understand why a decision was made even if they would have chosen differently.

---

# Rule 23

Optimize for maintainability.

Never optimize documentation for shorter output.

Long explanations are preferred over ambiguous explanations.

---

# Rule 24

Do not invent unnecessary complexity.

The simplest architecture that satisfies all current and anticipated requirements is preferred.

Complexity must always justify itself.

---

# Rule 25

Assume fifteen years.

Every paragraph should still make sense after

Framework changes.

Database upgrades.

Infrastructure migration.

Cloud migration.

Leadership changes.

Engineering turnover.

Scale growth.

The architecture should age gracefully.

---

# Quality Checklist

Before marking any chapter complete verify

✓ No contradictions

✓ Ownership clearly defined

✓ APIs documented

✓ Database documented

✓ Security documented

✓ Performance documented

✓ Failure modes documented

✓ Monitoring documented

✓ Testing documented

✓ Future evolution documented

✓ Diagrams included

✓ ADR references included

✓ Cross references updated

✓ Terminology consistent

✓ Invariants documented

Only then is the chapter considered complete.

---

# Final Principle

The repository should become more valuable than the code itself.

Code explains what the platform does today.

Architecture explains why it exists, how it should evolve, what must never change, and how future engineers should safely extend it.

If an engineer can confidently redesign Saturdays after reading only this repository, then the documentation has achieved its purpose.