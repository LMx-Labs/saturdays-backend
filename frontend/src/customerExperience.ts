import type { Address, Cart, CheckoutQuote, Payment } from "./api/types";

export type SearchFilters = {
  q?: string;
  type?: string;
  cuisine?: string;
  isVeg?: boolean;
  minPrice?: number;
  maxPrice?: number;
  latitude?: number;
  longitude?: number;
  radiusKm?: number;
  sortBy?: string;
  page?: number;
  limit?: number;
};

export function searchQuery(filters: SearchFilters) {
  const limit = filters.limit ?? 20;
  return {
    q: filters.q || undefined,
    type: filters.type || "all",
    cuisine: filters.cuisine || undefined,
    is_veg: filters.isVeg || undefined,
    min_price: filters.minPrice,
    max_price: filters.maxPrice,
    latitude: filters.latitude,
    longitude: filters.longitude,
    radius_km: filters.radiusKm,
    sort_by: filters.sortBy || "relevance",
    skip: Math.max(0, ((filters.page ?? 1) - 1) * limit),
    limit,
  };
}

export const addressLabel = (address: Address) =>
  `${address.building_name || address.campus_zone} — ${address.address_line}`;

export function hasCrossBranchConflict(cart: Cart | undefined, branchId: string) {
  return Boolean(cart?.items.length && cart.branch_id !== branchId);
}

export function canCheckout(cart: Cart | undefined, addressId: string, validationValid = true) {
  return Boolean(cart?.items.length && !cart.is_expired && addressId && validationValid);
}

export function checkoutIssueSummary(quote: CheckoutQuote) {
  return quote.issues.map((issue) => ({ ...issue, title: issue.code.replaceAll("_", " ").toLowerCase() }));
}

export function paymentState(payment?: Payment) {
  if (!payment) return "NOT_STARTED";
  const latest = payment.transactions.at(-1);
  if (!latest) return "PENDING";
  if (latest.transaction_type === "CAPTURED" && latest.status === "SUCCESS") return "CAPTURED";
  if (latest.status === "FAILED") return "FAILED";
  if (latest.transaction_type === "REFUNDED" && latest.status === "SUCCESS") return "REFUNDED";
  return "PENDING";
}

export const isMockProviderOrder = (providerOrderId: string) => providerOrderId.startsWith("order_mock_");
