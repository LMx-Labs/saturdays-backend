import { AuthClient } from "../auth";
import { joinUrl } from "../utils";

const apiBase = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");

export type ApiErrorShape = {
  status: number;
  code?: string;
  message: string;
  details?: unknown;
  correlationId?: string;
};

export type QueryPrimitive = string | number | boolean | null | undefined;
export type Query = Record<string, QueryPrimitive | QueryPrimitive[]>;

export class ApiError extends Error {
  constructor(public readonly problem: ApiErrorShape) {
    super(problem.message);
    this.name = "ApiError";
  }
}

export function errorMessage(payload: unknown, fallback = "Request failed"): string {
  if (typeof payload === "string" && payload) return payload;
  if (!payload || typeof payload !== "object") return fallback;
  const data = payload as Record<string, unknown>;
  if (typeof data.message === "string") return data.message;
  if (typeof data.detail === "string") return data.detail;
  if (data.detail && typeof data.detail === "object") {
    const detail = data.detail as Record<string, unknown>;
    if (typeof detail.message === "string") return detail.message;
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((item) => {
          if (!item || typeof item !== "object") return String(item);
          const issue = item as Record<string, unknown>;
          const path = Array.isArray(issue.loc) ? issue.loc.slice(1).join(".") : "";
          return `${path ? `${path}: ` : ""}${String(issue.msg || "Invalid value")}`;
        })
        .join("; ");
    }
  }
  return fallback;
}

export const authClient = new AuthClient(() => apiBase);

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;
  const text = await response.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export async function request<T>(
  path: string,
  init: RequestInit & { query?: Query } = {},
): Promise<T> {
  const { query, ...requestInit } = init;
  const params = new URLSearchParams();
  Object.entries(query || {}).forEach(([key, value]) => {
    const values = Array.isArray(value) ? value : [value];
    values.forEach((item) => {
      if (item !== undefined && item !== null && item !== "") params.append(key, String(item));
    });
  });
  const url = `${joinUrl(apiBase, `/api/v1${path}`)}${params.size ? `?${params}` : ""}`;
  const headers = new Headers(requestInit.headers);
  if (requestInit.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await authClient.fetch(url, { ...requestInit, headers });
  const payload = await parseBody(response);
  if (!response.ok) {
    const record = payload && typeof payload === "object" ? payload as Record<string, unknown> : {};
    const detail = record.detail && typeof record.detail === "object"
      ? record.detail as Record<string, unknown>
      : {};
    throw new ApiError({
      status: response.status,
      code: String(record.error_code || record.code || detail.error_code || detail.code || "") || undefined,
      message: errorMessage(payload, `${response.status} ${response.statusText}`),
      details: record.details ?? detail.details ?? payload,
      correlationId: String(
        record.correlation_id || detail.correlation_id ||
        response.headers.get("x-correlation-id") || response.headers.get("x-request-id") || "",
      ) || undefined,
    });
  }
  return payload as T;
}

export const api = {
  get: <T>(path: string, query?: Query) =>
    request<T>(path, { query }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body === undefined ? undefined : JSON.stringify(body) }),
  delete: <T = void>(path: string) => request<T>(path, { method: "DELETE" }),
};

export const webSocketUrl = (path: string) => {
  const root = apiBase || window.location.origin;
  return joinUrl(root.replace(/^http/, "ws"), `/api/v1${path}`);
};

export function authenticatedWebSocket(path: string, token: string, mode: "query" | "subprotocol" = "subprotocol") {
  if (mode === "query") {
    const url = new URL(webSocketUrl(path));
    url.searchParams.set("access_token", token);
    return new WebSocket(url, []);
  }
  return new WebSocket(webSocketUrl(path), ["bearer", token]);
}
