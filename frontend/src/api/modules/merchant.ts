import { api } from "../client";
import { customerApi } from "./customer";
import { discoveryApi } from "./discovery";
import type {
  Brand, Branch, BranchPerformance, CommissionSummary, Coupon, InventoryDetail, InventoryItem,
  InventoryLog, Invitation, Kitchen, Menu, Merchant, Order, Page, Payment, PaymentRefundSummary, Review,
  SalesSummary, StaffAssignment, Subscription,
} from "../types";

export const merchantApi = {
  me: () => api.get<Merchant>("/merchants/me"),
  assignedBranches: () => api.get<Branch[]>("/merchants/me/branches"),
  onboard: (body: unknown) => api.post<Merchant>("/merchants/onboard", body),
  submit: () => api.post<Merchant>("/merchants/me/submit"),
  update: (id: string, body: unknown) => api.patch<Merchant>(`/merchants/${id}`, body),
  brands: (merchantId: string) => discoveryApi.brands(merchantId),
  createBrand: (body: unknown) => api.post<Brand>("/brands", body),
  updateBrand: (id: string, body: unknown) => api.patch<Brand>(`/brands/${id}`, body),
  deleteBrand: (id: string) => api.delete(`/brands/${id}`),
  createBranch: (body: unknown) => api.post<Branch>("/branches", body),
  updateBranch: (id: string, body: unknown) => api.patch<Branch>(`/branches/${id}`, body),
  deleteBranch: (id: string) => api.delete(`/branches/${id}`),
  branchStatus: (id: string, active: boolean) =>
    api.patch<Branch>(`/branches/${id}/status`, { is_active: active }),
  kitchens: (branchId: string) => api.get<Kitchen[]>(`/branches/${branchId}/kitchens`),
  createKitchen: (body: unknown) => api.post<Kitchen>("/kitchens", body),
  updateKitchen: (id: string, body: unknown) => api.patch<Kitchen>(`/kitchens/${id}`, body),
  deleteKitchen: (id: string) => api.delete(`/kitchens/${id}`),
  createMenu: (branchId: string, body: unknown) => api.post<Menu>(`/branches/${branchId}/menus`, body),
  updateMenu: (id: string, body: unknown) => api.patch<Menu>(`/menus/${id}`, body),
  createCategory: (branchId: string, body: unknown) =>
    api.post(`/branches/${branchId}/menu/categories`, body),
  updateCategory: (id: string, body: unknown) => api.patch(`/menu/categories/${id}`, body),
  deleteCategory: (id: string) => api.delete(`/menu/categories/${id}`),
  createMenuItem: (branchId: string, body: unknown) =>
    api.post(`/branches/${branchId}/menu/items`, body),
  updateMenuItem: (id: string, body: unknown) => api.patch(`/menu/items/${id}`, body),
  itemAvailability: (id: string, available: boolean) =>
    api.patch(`/menu/items/${id}/availability`, { is_available: available }),
  deleteMenuItem: (id: string) => api.delete(`/menu/items/${id}`),
  createModifier: (itemId: string, body: unknown) => api.post(`/menu/items/${itemId}/modifiers`, body),
  updateModifier: (id: string, body: unknown) => api.patch(`/menu/modifiers/${id}`, body),
  deleteModifier: (id: string) => api.delete(`/menu/modifiers/${id}`),
  inventory: (branchId: string) => api.get<InventoryDetail[]>(`/branches/${branchId}/inventory/details`),
  createInventory: (branchId: string, body: unknown) =>
    api.post<InventoryItem>(`/branches/${branchId}/inventory`, body),
  stock: (id: string, body: unknown) => api.patch<InventoryItem>(`/inventory/${id}/stock`, body),
  inventoryLogs: (id: string, page = 1) =>
    api.get<Page<InventoryLog>>(`/inventory/${id}/logs`, { page, page_size: 25 }),
  orders: (branchId: string, status?: string) => api.get<Order[]>("/orders", { branch_id: branchId, status }),
  order: (id: string) => api.get<Order>(`/orders/${id}`),
  orderStatus: (id: string, status: string) => api.patch<Order>(`/orders/${id}/status`, { status }),
  reviews: (branchId: string) => discoveryApi.reviews(branchId),
  reply: (id: string, merchantReply: string) =>
    api.post<Review>(`/reviews/${id}/reply`, { merchant_reply: merchantReply }),
  subscription: () => api.get<Subscription>("/merchants/me/subscription"),
  subscribe: (body: unknown) => api.post<Subscription>("/merchants/me/subscription", body),
  renew: (body: unknown) => api.post<Subscription>("/merchants/me/subscription/renew", body),
  commissions: () => api.get<Array<Record<string, unknown>>>("/merchants/me/commissions"),
  invoices: () => api.get<Array<Record<string, unknown>>>("/merchants/me/invoices"),
  payments: (branchId: string, page = 1) =>
    api.get<Page<Payment>>("/payments/history", { branch_id: branchId, page, page_size: 25 }),
  payment: (id: string) => customerApi.payment(id),
  refund: (id: string, body: unknown) => api.post(`/payments/${id}/refund`, body),
  coupons: (branchId: string) => api.get<Coupon[]>("/coupons", { branch_id: branchId }),
  createCoupon: (body: unknown) => api.post<Coupon>("/coupons", body),
  updateCoupon: (id: string, body: unknown) => api.patch<Coupon>(`/coupons/${id}`, body),
  toggleCoupon: (id: string, active: boolean) =>
    api.post<Coupon>(`/coupons/${id}/${active ? "activate" : "deactivate"}`),
  deleteCoupon: (id: string) => api.delete(`/coupons/${id}`),
  couponRedemptions: (id: string) => api.get<Array<Record<string, unknown>>>(`/coupons/${id}/redemptions`),
  staff: () => api.get<StaffAssignment[]>("/merchants/staff"),
  inviteStaff: (body: unknown) => api.post<Invitation>("/merchants/staff/invitations", body),
  updateStaff: (id: string, body: unknown) => api.patch<StaffAssignment>(`/merchants/staff/${id}`, body),
  removeStaff: (id: string) => api.delete(`/merchants/staff/${id}`),
  salesReport: (branchId: string, dateFrom?: string, dateTo?: string) =>
    api.get<SalesSummary>("/reports/merchant/sales", { branch_id: branchId, date_from: dateFrom, date_to: dateTo }),
  branchReport: (branchId: string, dateFrom?: string, dateTo?: string) =>
    api.get<BranchPerformance>(`/reports/branches/${branchId}/performance`, { date_from: dateFrom, date_to: dateTo }),
  paymentReport: (branchId: string, dateFrom?: string, dateTo?: string) =>
    api.get<PaymentRefundSummary>("/reports/payments-refunds", { branch_id: branchId, date_from: dateFrom, date_to: dateTo }),
  commissionReport: (merchantId?: string, dateFrom?: string, dateTo?: string) =>
    api.get<CommissionSummary>("/reports/commissions", { merchant_id: merchantId, date_from: dateFrom, date_to: dateTo }),
};
