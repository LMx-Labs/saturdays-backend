# 00-FOUNDATION — PLATFORM FOUNDATION SPECIFICATIONS

Version: 1.0  
Status: Authoritative Foundation Index  
Owner: Saturdays Engineering Council  

---

# Purpose

The `00-foundation/` directory establishes the foundational vision, strategic business alignment, initial deployment target (VIT Vellore ecosystem), core technical constraints, and quality attribute trade-offs governing the Saturdays platform and DineGuru merchant application.

All subsequent domain models, system component boundaries, database schemas, and API contracts MUST conform to the baseline parameters defined in this section.

---

# Consolidated Specifications Index

1. [foundation-overview.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/00-foundation/foundation-overview.md)
   * **Vision & Mission**: Strategic objectives of the Saturdays customer ordering app and DineGuru merchant portal.
   * **Initial Deployment Scope**: Focus on the VIT Vellore ecosystem (hostels, campus dining, off-campus restaurants, faculty ordering).
   * **Product & Engineering Philosophy**: "Restaurants interact only with DineGuru; Customers interact only with Saturdays; Database is the single source of truth."
   * **Explicit Non-Goals**: Features intentionally omitted from initial releases (Riders, AI recommendations, Wallets, Table reservations).
2. [architecture-and-quality-attributes.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/00-foundation/architecture-and-quality-attributes.md)
   * **Architectural Style**: Rationale for the Production-Grade Modular Monolith architecture pattern.
   * **System Constraints**: Hard geographic, infrastructure, technology stack, and shared-persistence bounds.
   * **Quality Attributes & Trade-offs**: Concrete trade-off evaluation balancing maintainability and operational simplicity over premature distributed complexity.

---

# Dependencies

- [README.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/README.md) — Master repository entrypoint and scope.
- [ARCHITECTURE_PRINCIPLES.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/architecture/ARCHITECTURE_PRINCIPLES.md) — Non-negotiable engineering axioms.
- [09_DECISIONS.md](file:///Users/adith/Documents/Dev/LMX/Saturdays/prompts/09_DECISIONS.md) — Locked platform technology choices.
