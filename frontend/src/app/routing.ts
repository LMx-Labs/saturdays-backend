import type { Role } from "../api/types";

export const roleHome = (role: Role) => {
  if (role === "Customer") return "/customer";
  if (role === "KitchenStaff") return "/kitchen";
  if (role === "BranchManager") return "/branch-manager";
  if (role === "MerchantOwner") return "/merchant";
  return "/admin";
};

export function intendedRoute(state: unknown, role: Role): string {
  if (state && typeof state === "object" && "from" in state) {
    const from = (state as { from?: unknown }).from;
    if (typeof from === "string" && from.startsWith("/") && !from.startsWith("//")) return from;
  }
  return roleHome(role);
}

export function apiWorkbenchEnabled(mode: string, configured?: string): boolean {
  if (configured !== undefined) return configured.toLowerCase() === "true";
  return mode === "development";
}
