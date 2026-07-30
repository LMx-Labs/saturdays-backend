# Saturdays

## Project Constitution

Version: 1.0

Status: Authoritative

---

# Vision

Saturdays is a production-grade online food ordering platform built specifically for the VIT Vellore ecosystem.

The platform connects customers with restaurants while allowing restaurants to continue operating entirely through DineGuru.

Unlike traditional marketplaces, Saturdays and DineGuru are not independent products communicating over APIs.

Instead, they are two applications built on top of the same platform and the same PostgreSQL database.

Customers interact only with Saturdays.

Restaurants interact only with DineGuru.

The database acts as the single source of truth.

No synchronization layer exists.

No duplicated business logic exists.

No duplicated menu data exists.

No duplicated inventory exists.

No duplicated order state exists.

Every piece of business data has exactly one owner.

---

# Long-Term Vision

The long-term goal is to become the operating system for restaurant commerce.

Initially the platform serves VIT Vellore.

Later it expands to:

- Entire Vellore
- Nearby cities
- Tamil Nadu
- India

The architecture must support expansion without redesigning the core platform.

Geographical expansion should primarily involve configuration rather than architectural changes.

---

# Core Philosophy

Restaurants should never manage their business in two different systems.

Everything operational happens inside DineGuru.

Everything customer-facing happens inside Saturdays.

This separation keeps responsibilities clear.

---

# Platform Overview

The platform consists of two applications.

## Saturdays

Customer-facing application.

Responsibilities include:

- Customer registration
- Authentication
- Restaurant discovery
- Menu browsing
- Search
- Cart
- Checkout
- Payments
- Coupons
- Order placement
- Reviews
- Favorites
- Address management
- Notifications

Customers never access DineGuru.

---

## DineGuru

Restaurant-facing application.

Responsibilities include:

- Restaurant onboarding
- Menu management
- Pricing
- Inventory
- Kitchen operations
- Order acceptance
- Order preparation
- Procurement
- Recipes
- Billing
- Analytics
- Restaurant dashboards
- Employee management

Restaurants never access Saturdays.

---

# Shared Database Philosophy

Both applications use the same PostgreSQL database.

The database is the platform.

Neither application owns the database.

Instead, ownership exists at the module level.

Example:

Menu module owns menu tables.

Orders module owns order tables.

Inventory module owns inventory tables.

Customers module owns customer tables.

Every module has a clearly defined owner.

No table should have multiple writers without explicit architectural justification.

---

# Source of Truth

Every business entity has exactly one source of truth.

Examples

Customer

Owner:
Customers Module

Restaurant

Owner:
Restaurant Module

Menu

Owner:
Menu Module

Inventory

Owner:
Inventory Module (DineGuru)

Orders

Owner:
Orders Module

Payments

Owner:
Payments Module

Coupons

Owner:
Coupon Module

Reviews

Owner:
Reviews Module

Violating ownership boundaries is considered an architectural defect.

---

# Business Model

The platform earns revenue through two mechanisms.

## Monthly Subscription

Restaurants subscribe to use DineGuru.

Subscription plans determine available features.

Examples:

Basic

Professional

Enterprise

Future plans may introduce additional tiers.

---

## Commission

Every successful order generates platform commission.

Commission rates may vary.

Examples:

Restaurant-specific

Campaign-specific

Subscription-specific

Category-specific

Commission rules must be configurable.

Commission calculations must remain auditable.

---

# Merchant Hierarchy

Restaurants are not modeled as a single entity.

The hierarchy is:

Merchant

↓

Brand

↓

Branch

↓

Kitchen

Definitions

Merchant

Business owner.

Responsible for subscriptions.

Responsible for legal identity.

Responsible for settlements.

Responsible for billing.

---

Brand

Public identity visible to customers.

Examples:

McDonald's

Domino's

Burger King

A merchant may own multiple brands.

A brand may have multiple branches.

---

Branch

A physical ordering location.

Customers place orders from branches.

Pricing may vary per branch.

Operating hours vary per branch.

Availability varies per branch.

Delivery zones vary per branch.

Menus may vary.

---

Kitchen

Food preparation unit.

Initially one kitchen per branch.

Architecture must support multiple kitchens.

---

# Initial Geographic Scope

Initial deployment targets:

VIT Vellore

Restaurants inside campus.

Restaurants immediately outside campus.

Students ordering to hostels.

Faculty ordering to departments.

Future expansion should not require redesign.

---

# Customers

Only one public user role exists.

Customer.

Customers may:

Create account.

Login.

Search restaurants.

Browse menus.

Manage addresses.

Place orders.

Use coupons.

Review restaurants.

Track orders.

View history.

Manage profile.

Favorite restaurants.

Manage saved payment methods (future).

---

# Restaurant Users

Restaurants never use Saturdays.

All operational work happens in DineGuru.

Examples:

Menu editing.

Inventory.

Price updates.

Availability.

Kitchen workflow.

Order acceptance.

Billing.

Recipes.

Procurement.

Employee management.

---

# Authentication

Customer authentication.

Supported methods:

Google Sign-In.

Email + OTP verification.

JWT access tokens.

Refresh tokens.

Future:

Phone OTP.

Passkeys.

Restaurants will eventually use mobile OTP authentication through DineGuru.

---

# Payments

Payment provider:

Razorpay.

Supported flow:

Create order.

Redirect payment.

Verify signature.

Mark payment successful.

Create business order.

Notify restaurant.

Refund support required.

Webhook verification mandatory.

Payments are append-only.

Payment history must never be rewritten.

---

# Delivery

The platform initially supports:

Restaurant delivery.

Self-managed delivery.

Customer pickup.

Architecture must support future rider integration.

No rider subsystem exists today.

Its future addition should not require redesigning Orders.

---

# Search

Customers can search by:

Restaurant name.

Dish name.

Cuisine.

Category.

Tags.

Distance.

Rating.

Popularity.

Offers.

Open now.

Future:

AI-powered natural language search.

---

# Coupons

Coupons exist in two scopes.

Global.

Restaurant.

Coupons may be created by:

Platform Admin.

Restaurant.

Coupon engine should support:

Minimum order.

Maximum discount.

Usage limits.

Per-user limits.

Date ranges.

Stacking rules.

Restaurant restrictions.

Category restrictions.

Future loyalty integration.

---

# Reviews

Customers may review:

Restaurants.

Food.

Overall experience.

No rider reviews initially.

No photo reviews initially.

Architecture should support both later.

---

# Notifications

Current:

Email.

Future:

Push Notifications.

SMS.

WhatsApp.

Notification architecture should remain provider-agnostic.

---

# Admin Portal

The platform includes an internal administrative portal.

Responsibilities include:

Restaurant onboarding.

Merchant verification.

Subscription management.

Commission configuration.

Coupon creation.

Refund approval.

Payment monitoring.

Analytics.

CMS.

Banner management.

Restaurant suspension.

Customer moderation.

Support tools.

Operational dashboards.

Feature flags.

Audit logs.

The Admin Portal is part of the same backend.

It is not a separate product.

---

# Scale Targets

Initial scale:

100–500 restaurants.

20,000+ customers.

Several thousand orders per day.

Architecture should comfortably scale beyond these numbers without requiring redesign.

---

# Technology Stack

Backend

FastAPI.

Python.

SQLAlchemy.

Alembic.

PostgreSQL.

NeonDB.

Frontend

React.

Future

Mobile applications.

No Firebase.

No unnecessary infrastructure.

The platform should remain operationally simple.

---

# Architectural Style

Primary architecture:

Production-grade modular monolith.

Modules communicate through well-defined service boundaries.

The database remains shared.

Future extraction into microservices should be possible without rewriting business logic.

Every module should have clear ownership.

---

# Non-Goals

The first version intentionally excludes:

Delivery riders.

AI recommendations.

Wallet.

Loyalty system.

Subscriptions for customers.

Table reservations.

Marketplace advertisements.

Live GPS tracking.

These features should have documented extension points for future implementation.

---

# Success Criteria

Saturdays succeeds when:

Customers can discover restaurants quickly.

Restaurants operate entirely through DineGuru.

Menus remain consistent.

Orders appear instantly inside DineGuru.

Inventory never becomes inconsistent.

Payments remain reliable.

Administration is operationally simple.

The platform remains maintainable for many years.

Engineering velocity remains high without sacrificing architectural integrity.

This document defines the product.

Future documentation defines its implementation.