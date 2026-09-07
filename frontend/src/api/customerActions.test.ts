import { afterEach, describe, expect, it, vi } from "vitest";
import { customerApi } from "./modules/customer";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("customer notification actions", () => {
  it("marks one notification and all notifications read", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "notice-1", is_read: true }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ updated: 3 }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await customerApi.markNotificationRead("notice-1");
    await expect(customerApi.markAllNotificationsRead()).resolves.toEqual({ updated: 3 });
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "PATCH" });
    expect(String(fetchMock.mock.calls[0][0])).toContain("/notifications/notice-1/read");
    expect(String(fetchMock.mock.calls[1][0])).toContain("/notifications/me/read-all");
  });
});
