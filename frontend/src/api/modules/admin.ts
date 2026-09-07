import { api } from "../client";
import type {
  AuthSession, Invitation, Merchant, Page, PageParams, Payment, PlatformOperations,
  Review, User,
} from "../types";

export const adminApi = {
  analytics: () => api.get<Record<string, number>>("/admin/analytics/overview"),
  merchants: (params: PageParams & { status?: string; search?: string } = {}) =>
    api.get<Page<Merchant>>("/admin/merchants", params),
  merchant: (id: string) => api.get<Merchant>(`/admin/merchants/${id}`),
  approveMerchant: (id: string, body: unknown) => api.post(`/admin/merchants/${id}/approval`, body),
  updateMerchantStatus: (id: string, status: string) => api.patch<Merchant>(`/merchants/${id}/status`, { status }),
  banners: (activeOnly = false) => api.get<Array<Record<string, unknown>>>("/admin/banners", { active_only: activeOnly }),
  createBanner: (body: unknown) => api.post("/admin/banners", body),
  updateBanner: (id: string, body: unknown) => api.patch(`/admin/banners/${id}`, body),
  deleteBanner: (id: string) => api.delete(`/admin/banners/${id}`),
  createCoupon: (body: unknown) => api.post("/admin/coupons", body),
  coupons: (active?: boolean) => api.get<Array<Record<string, unknown>>>("/coupons", { active }),
  updateCoupon: (id: string, body: unknown) => api.patch(`/coupons/${id}`, body),
  toggleCoupon: (id: string, active: boolean) => api.post(`/coupons/${id}/${active ? "activate" : "deactivate"}`),
  deleteCoupon: (id: string) => api.delete(`/coupons/${id}`),
  flags: () => api.get<Array<{ flag_key: string; enabled: boolean; value?: string }>>("/admin/feature-flags"),
  updateFlag: (key: string, body: unknown) => api.put(`/admin/feature-flags/${encodeURIComponent(key)}`, body),
  refundOverride: (body: unknown) => api.post("/admin/refunds/override", body),
  payments: (page = 1) => api.get<Page<Payment>>("/payments/history", { page, page_size: 25 }),
  audit: (params: { skip?: number; limit?: number; action?: string; target_entity?: string } = {}) =>
    api.get<Array<Record<string, unknown>>>("/admin/audit-logs", params),
  users: (skip = 0, limit = 100) => api.get<User[]>("/admin/users", { skip, limit }),
  createUser: (body: unknown) => api.post<User>("/admin/users", body),
  updateUser: (id: string, body: unknown) => api.patch<User>(`/admin/users/${id}`, body),
  deactivateUser: (id: string) => api.post<User>(`/admin/users/${id}/deactivate`),
  sessions: (id: string) => api.get<AuthSession[]>(`/admin/users/${id}/sessions`),
  revokeSessions: (id: string) => api.delete(`/admin/users/${id}/sessions`),
  invite: (body: unknown) => api.post<Invitation>("/admin/invitations", body),
  hiddenReviews: () => api.get<Review[]>("/admin/reviews/hidden"),
  moderateReview: (id: string, body: unknown) => api.put<Review>(`/reviews/${id}/moderate`, body),
  platformReport: (dateFrom?: string, dateTo?: string) =>
    api.get<PlatformOperations>("/reports/platform/operations", { date_from: dateFrom, date_to: dateTo }),
};
