import { api, type Query } from "../client";
import type { Brand, Branch, Coupon, Menu, Review, SearchResponse } from "../types";

export const discoveryApi = {
  brands: (merchantId?: string) => api.get<Brand[]>("/brands", { merchant_id: merchantId }),
  brand: (id: string) => api.get<Brand>(`/brands/${id}`),
  branches: (brandId?: string) => api.get<Branch[]>("/branches", { brand_id: brandId }),
  branch: (id: string) => api.get<Branch>(`/branches/${id}`),
  menu: (branchId: string) => api.get<Menu>(`/branches/${branchId}/menu`),
  search: (query: Query) => api.get<SearchResponse>("/search", query),
  suggestions: (q: string) =>
    api.get<{ suggestions: Array<{ text: string; type: string; entity_id?: string }> }>(
      "/search/suggestions",
      { q },
    ),
  reviews: (branchId: string) => api.get<Review[]>(`/branches/${branchId}/reviews`),
  rating: (branchId: string) =>
    api.get<{ average_rating: number; total_reviews: number; rating_distribution: Record<string, number> }>(
      `/branches/${branchId}/rating-summary`,
    ),
  coupons: (branchId?: string) => api.get<Coupon[]>("/coupons", { branch_id: branchId }),
  coupon: (id: string) => api.get<Coupon>(`/coupons/${id}`),
  banners: () =>
    api.get<Array<{ id: string; title: string; image_url: string; target_url?: string }>>("/admin/banners"),
};
