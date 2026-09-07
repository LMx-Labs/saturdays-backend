export const queryKeys = {
  auth: { me: ["auth", "me"] as const },
  brands: (merchantId?: string) => ["brands", merchantId ?? "all"] as const,
  branches: (brandId?: string) => ["branches", brandId ?? "all"] as const,
  branch: (id: string) => ["branch", id] as const,
  menu: (branchId: string) => ["menu", branchId] as const,
  cart: ["cart"] as const,
  order: (id: string) => ["order", id] as const,
  orders: (scope = "customer", filter?: string) => ["orders", scope, filter ?? "all"] as const,
  notifications: ["notifications"] as const,
  staff: ["merchant", "staff"] as const,
  adminMerchants: (filters: object = {}) => ["admin", "merchants", filters] as const,
};
