import { afterEach, describe, expect, it, vi } from "vitest";
import { authenticatedWebSocket, webSocketUrl } from "./client";
import { adminApi } from "./modules/admin";
import { merchantApi } from "./modules/merchant";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const response = (body: unknown = {}) =>
  Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));

describe("merchant operational contracts", () => {
  it("sends merchant CRUD and staff assignment payloads", async () => {
    const fetchMock = vi.fn<typeof fetch>(() => response());
    vi.stubGlobal("fetch", fetchMock);

    await merchantApi.updateBrand("brand-1", { name: "Campus Kitchen" });
    await merchantApi.inviteStaff({
      email: "manager@example.com",
      role: "BranchManager",
      branch_ids: ["branch-1"],
    });
    await merchantApi.orderStatus("order-1", "PREPARING");

    expect(String(fetchMock.mock.calls[0][0])).toContain("/brands/brand-1");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      method: "PATCH",
      body: JSON.stringify({ name: "Campus Kitchen" }),
    });
    expect(String(fetchMock.mock.calls[1][0])).toContain("/merchants/staff/invitations");
    expect(fetchMock.mock.calls[1][1]).toMatchObject({
      body: JSON.stringify({
        email: "manager@example.com",
        role: "BranchManager",
        branch_ids: ["branch-1"],
      }),
    });
    expect(fetchMock.mock.calls[2][1]).toMatchObject({
      body: JSON.stringify({ status: "PREPARING" }),
    });
  });

  it("loads only assignment-scoped branches", async () => {
    const fetchMock = vi.fn<typeof fetch>(() => response([]));
    vi.stubGlobal("fetch", fetchMock);
    await merchantApi.assignedBranches();
    expect(String(fetchMock.mock.calls[0][0])).toContain("/merchants/me/branches");
  });

  it("uses branch-scoped coupon lifecycle operations", async () => {
    const fetchMock = vi.fn<typeof fetch>(() => response([]));
    vi.stubGlobal("fetch", fetchMock);
    await merchantApi.coupons("branch-1");
    await merchantApi.toggleCoupon("coupon-1", false);
    await merchantApi.couponRedemptions("coupon-1");
    expect(String(fetchMock.mock.calls[0][0])).toContain("branch_id=branch-1");
    expect(String(fetchMock.mock.calls[1][0])).toContain("/coupons/coupon-1/deactivate");
    expect(String(fetchMock.mock.calls[2][0])).toContain("/coupons/coupon-1/redemptions");
  });
});

describe("platform administration contracts", () => {
  it("uses queue, moderation, flags and real refund operations", async () => {
    const fetchMock = vi.fn<typeof fetch>(() => response());
    vi.stubGlobal("fetch", fetchMock);

    await adminApi.merchants({ page: 2, status: "PENDING_VERIFICATION", search: "cafe" });
    await adminApi.moderateReview("review-1", { is_hidden: false });
    await adminApi.updateFlag("checkout", { enabled: true });
    await merchantApi.refund("payment-1", { amount: 125, reason: "ORDER_CANCELLED" });

    expect(String(fetchMock.mock.calls[0][0])).toContain("page=2");
    expect(String(fetchMock.mock.calls[0][0])).toContain("status=PENDING_VERIFICATION");
    expect(String(fetchMock.mock.calls[1][0])).toContain("/reviews/review-1/moderate");
    expect(fetchMock.mock.calls[2][1]).toMatchObject({ method: "PUT" });
    expect(String(fetchMock.mock.calls[3][0])).toContain("/payments/payment-1/refund");
  });
});

describe("authenticated kitchen stream", () => {
  it("builds the API websocket URL and bearer subprotocol", () => {
    const socket = vi.fn();
    vi.stubGlobal("WebSocket", socket);
    expect(webSocketUrl("/ws/branches/branch-1/orders")).toContain(
      "/api/v1/ws/branches/branch-1/orders",
    );
    authenticatedWebSocket("/ws/branches/branch-1/orders", "access-token");
    expect(socket).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/ws/branches/branch-1/orders"),
      ["bearer", "access-token"],
    );
  });
});
