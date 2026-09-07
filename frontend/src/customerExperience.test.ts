import { describe, expect, it } from "vitest";
import type { Address, Cart, CheckoutQuote, Payment } from "./api/types";
import {
  addressLabel, canCheckout, checkoutIssueSummary, hasCrossBranchConflict,
  isMockProviderOrder, paymentState, searchQuery,
} from "./customerExperience";

const cart: Cart = {
  id: "cart-1",
  branch_id: "branch-a",
  total_items: 1,
  subtotal: 120,
  is_expired: false,
  items: [{ id: "line-1", menu_item_id: "item-1", quantity: 1 }],
};

describe("public and customer experience rules", () => {
  it("maps all supported public search filters and pagination", () => {
    expect(searchQuery({
      q: "dosa", type: "dish", cuisine: "South Indian", isVeg: true,
      minPrice: 50, maxPrice: 250, latitude: 12.9, longitude: 77.6,
      radiusKm: 4, sortBy: "distance", page: 3, limit: 20,
    })).toEqual({
      q: "dosa", type: "dish", cuisine: "South Indian", is_veg: true,
      min_price: 50, max_price: 250, latitude: 12.9, longitude: 77.6,
      radius_km: 4, sort_by: "distance", skip: 40, limit: 20,
    });
  });

  it("detects cross-branch cart conflicts without blocking the same branch", () => {
    expect(hasCrossBranchConflict(cart, "branch-b")).toBe(true);
    expect(hasCrossBranchConflict(cart, "branch-a")).toBe(false);
  });

  it("requires a live non-empty cart and address for checkout", () => {
    expect(canCheckout(cart, "address-1", true)).toBe(true);
    expect(canCheckout({ ...cart, items: [] }, "address-1", true)).toBe(false);
    expect(canCheckout(cart, "", true)).toBe(false);
    expect(canCheckout(cart, "address-1", false)).toBe(false);
  });

  it("presents structured quote issues with friendly titles", () => {
    const quote = {
      issues: [{ code: "ITEM_UNAVAILABLE", message: "Masala dosa is unavailable." }],
    } as CheckoutQuote;
    expect(checkoutIssueSummary(quote)).toEqual([{
      code: "ITEM_UNAVAILABLE",
      title: "item unavailable",
      message: "Masala dosa is unavailable.",
    }]);
  });

  it("recognizes deterministic local mock checkout and payment states", () => {
    expect(isMockProviderOrder("order_mock_123")).toBe(true);
    expect(isMockProviderOrder("order_live_123")).toBe(false);
    const payment = {
      transactions: [{ transaction_type: "CAPTURED", status: "SUCCESS" }],
    } as Payment;
    expect(paymentState(payment)).toBe("CAPTURED");
    expect(paymentState({ transactions: [{ transaction_type: "VERIFIED", status: "FAILED" }] } as Payment)).toBe("FAILED");
  });

  it("uses friendly address labels instead of identifiers", () => {
    const address = { building_name: "Library", campus_zone: "North", address_line: "Gate 2" } as Address;
    expect(addressLabel(address)).toBe("Library — Gate 2");
  });
});
