# ADR-0006: EXCLUSIVE DINEGURU INVENTORY WRITE RULE

- **Status**: ACCEPTED  
- **Date**: 2026-07-30  
- **Author**: Chief Architect  
- **Scope**: Inventory & Catalog Bounded Contexts  

---

# Problem & Context

Inventory items and dish stock availability MUST be synchronized between kitchen operations and customer cart validation. 

Allowing multiple application routes or uncoordinated frontend clients to modify inventory state risks race conditions, negative inventory counts, and ghost orders.

---

# Options Considered

1. **Option A: Dual-Application Inventory Writes**
   - Both Saturdays and DineGuru endpoints can update stock counts directly in the database.
2. **Option B: Exclusive DineGuru Inventory Write Rule**
   - Stock modifications, item availability toggles, and inventory adjustments MUST originate exclusively inside DineGuru (or via the `inventory` module service layer during checkout allocation).

---

# Decision

The platform **MUST** enforce the **Exclusive DineGuru Inventory Write Rule** (Option B). 

DineGuru is the exclusive authoritative surface for store inventory management. Saturdays routes MUST treat inventory as a read-only resource during catalog browsing, verifying stock via the `inventory` module service layer prior to order placement.

---

# Consequences

## Positive
- Eliminates inventory mutation race conditions and guarantees clear domain ownership.
- Ensures kitchen staff retain total authority over item availability and emergency stock toggles.

## Negative / Risks
- Saturdays checkout validation MUST execute strict concurrency checks to prevent overselling the last item.
