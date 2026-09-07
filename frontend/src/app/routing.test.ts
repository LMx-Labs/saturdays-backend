import { describe, expect, it } from "vitest";
import { apiWorkbenchEnabled, intendedRoute } from "./routing";

describe("routing foundations", () => {
  it("restores a safe intended route", () => {
    expect(intendedRoute({ from: "/customer/orders?active=true" }, "Customer"))
      .toBe("/customer/orders?active=true");
    expect(intendedRoute({ from: "//malicious.test" }, "Customer")).toBe("/customer");
  });

  it("defaults the API workbench by build mode", () => {
    expect(apiWorkbenchEnabled("development")).toBe(true);
    expect(apiWorkbenchEnabled("production")).toBe(false);
    expect(apiWorkbenchEnabled("production", "true")).toBe(true);
    expect(apiWorkbenchEnabled("development", "false")).toBe(false);
  });
});
