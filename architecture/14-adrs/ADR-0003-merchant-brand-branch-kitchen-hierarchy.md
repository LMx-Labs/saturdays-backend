# ADR-0003: 4-TIER MERCHANT ORGANIZATIONAL HIERARCHY

- **Status**: ACCEPTED  
- **Date**: 2026-07-30  
- **Author**: Chief Architect  
- **Scope**: Merchant Bounded Context & Entity Modeling  

---

# Problem & Context

Food merchants operate under diverse business structures ranging from single-location independent restaurants to large franchise groups owning multiple brand identities and physical branches across campus and city locations. 

The architecture requires a standardized entity hierarchy model that cleanly separates legal/billing responsibilities, marketing brand identities, physical fulfillment locations, and kitchen preparation workflows.

---

# Options Considered

1. **Option A: Flat Restaurant Entity Model**
   - Single `restaurant` table combining legal entity, brand, store location, and kitchen into one flat record.
2. **Option B: 2-Tier Model (`Merchant` $\rightarrow$ `Store`)**
   - Separates legal merchant accounts from store locations, but lacks brand identity abstractions.
3. **Option C: 4-Tier Organizational Hierarchy (`Merchant` $\rightarrow$ `Brand` $\rightarrow$ `Branch` $\rightarrow$ `Kitchen`)**
   - Explicit 4-tier model representing business legal owner, marketing brand identity, physical store location, and operational preparation unit.

---

# Decision

The platform **MUST** enforce a **4-Tier Organizational Hierarchy** (Option C):

$$\text{Merchant} \longrightarrow \text{Brand} \longrightarrow \text{Branch} \longrightarrow \text{Kitchen}$$

1. **Merchant**: Legal business owner, subscription billings, tax details, and bank settlement account.
2. **Brand**: Public customer-facing brand identity and marketing umbrella (e.g. *Domino's*).
3. **Branch**: Physical ordering location with specific geo-location, operating hours, delivery radius, and pricing overrides.
4. **Kitchen**: Operational preparation unit within a branch responsible for food prep workflows.

---

# Consequences

## Positive
- Accommodates single-store independent restaurants and multi-brand franchise groups without schema changes.
- Allows independent branch pricing, menu overrides, and store-specific operating hours.

## Negative / Risks
- Increases foreign key join depth across queries. (Mitigated via composite indexing on `branch_id`).
