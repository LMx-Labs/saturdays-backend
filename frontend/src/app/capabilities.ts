import type { Role } from "../api/types";

export type Workspace = "customer" | "merchant" | "branchManager" | "kitchen" | "admin";
export type Capability =
  | "shop"
  | "manage_merchant"
  | "manage_branch"
  | "fulfil_orders"
  | "manage_platform"
  | "use_api_workbench";

export type AccessScope = {
  role: Role;
  merchantId?: string;
  branchIds?: string[];
};

export const workspaceRoles: Record<Workspace, Role[]> = {
  customer: ["Customer"],
  merchant: ["MerchantOwner"],
  branchManager: ["BranchManager"],
  kitchen: ["KitchenStaff"],
  admin: ["PlatformAdmin"],
};

export const hasWorkspace = (role: Role, workspace: Workspace) =>
  workspaceRoles[workspace].includes(role);

const roleCapabilities: Record<Role, Capability[]> = {
  Customer: ["shop"],
  KitchenStaff: ["fulfil_orders"],
  BranchManager: ["manage_branch", "fulfil_orders"],
  MerchantOwner: ["manage_merchant", "manage_branch", "fulfil_orders"],
  PlatformAdmin: ["manage_platform", "use_api_workbench"],
};

export const capabilitiesFor = ({ role }: AccessScope): ReadonlySet<Capability> =>
  new Set(roleCapabilities[role]);

export const can = (scope: AccessScope, capability: Capability, branchId?: string) => {
  if (!capabilitiesFor(scope).has(capability)) return false;
  if (!branchId || scope.role === "PlatformAdmin" || scope.role === "MerchantOwner") return true;
  return Boolean(scope.branchIds?.includes(branchId));
};

export const roleLabel: Record<Role, string> = {
  Customer: "Customer",
  KitchenStaff: "Kitchen staff",
  BranchManager: "Branch manager",
  MerchantOwner: "Merchant owner",
  PlatformAdmin: "Platform admin",
};
