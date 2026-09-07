import { describe, expect, it } from "vitest";
import { can, hasWorkspace } from "./capabilities";
import { roleHome } from "../auth/AuthProvider";

describe("role capabilities", () => {
  it("maps every role to its guarded workspace", () => {
    expect(roleHome("Customer")).toBe("/customer");
    expect(roleHome("KitchenStaff")).toBe("/kitchen");
    expect(roleHome("BranchManager")).toBe("/branch-manager");
    expect(roleHome("MerchantOwner")).toBe("/merchant");
    expect(roleHome("PlatformAdmin")).toBe("/admin");
  });

  it("does not grant workspaces across roles", () => {
    expect(hasWorkspace("Customer", "customer")).toBe(true);
    expect(hasWorkspace("Customer", "admin")).toBe(false);
    expect(hasWorkspace("KitchenStaff", "kitchen")).toBe(true);
    expect(hasWorkspace("MerchantOwner", "merchant")).toBe(true);
  });

  it("limits staff capabilities to returned branch assignments", () => {
    const staff = { role: "KitchenStaff" as const, merchantId: "merchant-1", branchIds: ["branch-1"] };
    expect(can(staff, "fulfil_orders", "branch-1")).toBe(true);
    expect(can(staff, "fulfil_orders", "branch-2")).toBe(false);
    expect(can(staff, "manage_platform")).toBe(false);
  });
});
