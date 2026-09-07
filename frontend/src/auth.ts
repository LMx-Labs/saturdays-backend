import type { AuthTokens } from "./api/types/identity";
import { joinUrl } from "./utils";

const REFRESH_KEY = "saturdays.refreshToken";

export class AuthClient {
  private accessToken: string | null = null;
  private refreshPromise: Promise<boolean> | null = null;

  constructor(
    private getBaseUrl: () => string,
    private storage: Pick<Storage, "getItem" | "setItem" | "removeItem"> = sessionStorage,
  ) {}

  getAccessToken(): string | null {
    return this.accessToken;
  }

  hasRefreshToken(): boolean {
    return Boolean(this.storage.getItem(REFRESH_KEY));
  }

  acceptTokens(tokens: AuthTokens): void {
    this.accessToken = tokens.access_token;
    this.storage.setItem(REFRESH_KEY, tokens.refresh_token);
  }

  clear(): void {
    this.accessToken = null;
    this.storage.removeItem(REFRESH_KEY);
  }

  getRefreshToken(): string | null {
    return this.storage.getItem(REFRESH_KEY);
  }

  async authenticate(kind: "login" | "register", payload: object): Promise<AuthTokens> {
    const response = await fetch(joinUrl(this.getBaseUrl(), `/api/v1/auth/${kind}`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.message || result.detail?.message || result.detail || response.statusText);
    }
    this.acceptTokens(result);
    return result;
  }

  async acceptInvitation(token: string, password: string): Promise<AuthTokens> {
    const response = await fetch(joinUrl(this.getBaseUrl(), "/api/v1/auth/invitations/accept"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, password }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || response.statusText);
    this.acceptTokens(result);
    return result;
  }

  async refresh(): Promise<boolean> {
    if (this.refreshPromise) return this.refreshPromise;
    const refreshToken = this.storage.getItem(REFRESH_KEY);
    if (!refreshToken) return false;

    this.refreshPromise = (async () => {
      try {
        const response = await fetch(joinUrl(this.getBaseUrl(), "/api/v1/auth/refresh"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!response.ok) {
          this.clear();
          return false;
        }
        this.acceptTokens(await response.json());
        return true;
      } catch {
        return false;
      } finally {
        this.refreshPromise = null;
      }
    })();
    return this.refreshPromise;
  }

  async logout(all = false): Promise<void> {
    const refreshToken = this.getRefreshToken();
    try {
      if (all) {
        await this.fetch(joinUrl(this.getBaseUrl(), "/api/v1/auth/logout-all"), { method: "POST" }, false);
      } else if (refreshToken) {
        await fetch(joinUrl(this.getBaseUrl(), "/api/v1/auth/logout"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      }
    } finally {
      this.clear();
    }
  }

  async fetch(input: string, init: RequestInit = {}, retry = true): Promise<Response> {
    const headers = new Headers(init.headers);
    if (this.accessToken) headers.set("Authorization", `Bearer ${this.accessToken}`);
    let response = await fetch(input, { ...init, headers });
    if (response.status === 401 && retry && (await this.refresh())) {
      headers.set("Authorization", `Bearer ${this.accessToken}`);
      response = await fetch(input, { ...init, headers });
    }
    return response;
  }
}

export { REFRESH_KEY };
