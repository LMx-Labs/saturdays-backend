import { describe, expect, it } from "vitest";
import type { OpenApiDocument } from "./types";
import { redactSecrets, schemaDefaults, serializeUrl } from "./utils";

describe("serializeUrl", () => {
  it("encodes path values and omits empty query values", () => {
    const url = serializeUrl("https://api.test/", "/orders/{id}", {
      id: "abc/123",
      status: "in progress",
      empty: "",
    }, [
      { name: "id", in: "path", required: true },
      { name: "status", in: "query" },
      { name: "empty", in: "query" },
    ]);
    expect(url).toBe("https://api.test/orders/abc%2F123?status=in+progress");
  });
});

describe("schemaDefaults", () => {
  it("resolves component references and applies nested defaults", () => {
    const document: OpenApiDocument = {
      components: {
        schemas: {
          Request: {
            type: "object",
            properties: {
              count: { type: "integer", default: 2 },
              enabled: { type: "boolean" },
              name: { type: "string", example: "Saturday" },
            },
          },
        },
      },
    };
    expect(schemaDefaults({ $ref: "#/components/schemas/Request" }, document)).toEqual({
      count: 2,
      name: "Saturday",
    });
  });

  it("creates required array entries and resolves nullable schemas", () => {
    const document: OpenApiDocument = {};
    expect(schemaDefaults({
      type: "array",
      minItems: 1,
      items: {
        type: "object",
        required: ["id"],
        properties: {
          id: { anyOf: [{ type: "string" }, { type: "null" }] },
          note: { type: "string" },
        },
      },
    }, document)).toEqual([{ id: "" }]);
  });
});

describe("redactSecrets", () => {
  it("redacts secret-looking keys at every depth", () => {
    expect(redactSecrets({
      Authorization: "Bearer token",
      body: { password: "secret", profile: { email: "safe", refresh_token: "token" } },
    })).toEqual({
      Authorization: "[REDACTED]",
      body: { password: "[REDACTED]", profile: { email: "safe", refresh_token: "[REDACTED]" } },
    });
  });
});
