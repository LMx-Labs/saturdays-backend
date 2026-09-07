import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthClient, REFRESH_KEY } from "./auth";

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("AuthClient", () => {
  it("stores only the refresh token in session storage", () => {
    const client = new AuthClient(() => "");
    client.acceptTokens({ access_token: "access", refresh_token: "refresh" });
    expect(client.getAccessToken()).toBe("access");
    expect(sessionStorage.getItem(REFRESH_KEY)).toBe("refresh");
    expect(sessionStorage.getItem("access_token")).toBeNull();
  });

  it("attaches bearer auth and retries once after refresh", async () => {
    sessionStorage.setItem(REFRESH_KEY, "old-refresh");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response("", { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({ access_token: "new-access", refresh_token: "new-refresh" }))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new AuthClient(() => "https://api.test");

    const response = await client.fetch("https://api.test/protected");

    expect(response.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const retryHeaders = fetchMock.mock.calls[2][1].headers as Headers;
    expect(retryHeaders.get("Authorization")).toBe("Bearer new-access");
    expect(sessionStorage.getItem(REFRESH_KEY)).toBe("new-refresh");
  });

  it("clears both credentials on logout", () => {
    const client = new AuthClient(() => "");
    client.acceptTokens({ access_token: "access", refresh_token: "refresh" });
    client.clear();
    expect(client.getAccessToken()).toBeNull();
    expect(client.hasRefreshToken()).toBe(false);
  });

  it("revokes the refresh session before clearing it", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ message: "Logged out" }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new AuthClient(() => "https://api.test");
    client.acceptTokens({ access_token: "access", refresh_token: "refresh" });
    await client.logout();
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.test/api/v1/auth/logout",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ refresh_token: "refresh" }) }),
    );
    expect(client.hasRefreshToken()).toBe(false);
  });
});
