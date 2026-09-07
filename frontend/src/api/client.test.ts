import { afterEach, describe, expect, it, vi } from "vitest";
import { errorMessage, request } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("API errors", () => {
  it("parses platform and FastAPI detail error shapes", () => {
    expect(errorMessage({ message: "Platform message" })).toBe("Platform message");
    expect(errorMessage({ detail: { message: "Domain message", code: "TEST" } })).toBe("Domain message");
    expect(errorMessage({ detail: [{ loc: ["body", "email"], msg: "Invalid email" }] }))
      .toBe("email: Invalid email");
  });

  it("throws a typed error with status and code", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ message: "Not allowed", error_code: "FORBIDDEN", correlation_id: "request-123" }),
      { status: 403, headers: { "Content-Type": "application/json" } },
    )));

    await expect(request("/admin/feature-flags")).rejects.toMatchObject({
      problem: { status: 403, code: "FORBIDDEN", message: "Not allowed", correlationId: "request-123" },
    });
  });

  it("serializes array query values without discarding entries", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await request("/search", { query: { cuisine: ["Indian", "Thai"] } });
    expect(String(fetchMock.mock.calls[0][0])).toContain("cuisine=Indian&cuisine=Thai");
  });
});
