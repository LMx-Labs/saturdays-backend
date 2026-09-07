export const canonicalRoles = [
  "Customer",
  "KitchenStaff",
  "BranchManager",
  "MerchantOwner",
  "PlatformAdmin",
] as const;

export type Role = typeof canonicalRoles[number];

export type User = {
  id: string;
  email: string;
  role: Role;
  is_active: boolean;
  is_verified: boolean;
  created_at?: string;
  updated_at?: string;
};

export type AuthTokens = {
  access_token: string;
  refresh_token: string;
  token_type?: string;
  expires_in?: number;
  user?: User;
};

export type StaffAssignment = {
  id: string;
  user_id: string;
  email: string;
  role: Extract<Role, "KitchenStaff" | "BranchManager">;
  is_active: boolean;
  merchant_id?: string;
  branch_ids: string[];
  created_at: string;
};

export type Invitation = {
  id: string;
  email: string;
  role: Role;
  merchant_id?: string;
  branch_ids: string[];
  expires_at: string;
  preview_token?: string;
};

export type AuthSession = {
  id: string;
  created_at: string;
  expires_at: string;
  last_used_at?: string;
  revoked_at?: string;
};
