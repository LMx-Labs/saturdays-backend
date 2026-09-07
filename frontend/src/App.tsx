import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AuthClient } from "./auth";
import { authClient } from "./api/client";
import type {
  Endpoint,
  HistoryItem,
  JsonSchema,
  OpenApiDocument,
  Parameter,
  ResponseRecord,
} from "./types";
import {
  extractEndpoints,
  formatJson,
  joinUrl,
  redactSecrets,
  requestExamples,
  resolveSchema,
  schemaDefaults,
  serializeUrl,
} from "./utils";

const configuredBase = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");
const METHODS_WITH_BODY = new Set(["POST", "PUT", "PATCH"]);

function methodClass(method: string): string {
  return `method method-${method.toLowerCase()}`;
}

function constraintText(schema: JsonSchema): string {
  const parts = [
    schema.format && `format: ${schema.format}`,
    schema.enum && `one of: ${schema.enum.join(", ")}`,
    schema.minLength !== undefined && `min length: ${schema.minLength}`,
    schema.maxLength !== undefined && `max length: ${schema.maxLength}`,
    schema.minimum !== undefined && `min: ${schema.minimum}`,
    schema.maximum !== undefined && `max: ${schema.maximum}`,
    schema.minItems !== undefined && `min items: ${schema.minItems}`,
    schema.maxItems !== undefined && `max items: ${schema.maxItems}`,
    schema.pattern && `pattern: ${schema.pattern}`,
  ];
  return parts.filter(Boolean).join(" · ");
}

function Field({
  parameter,
  value,
  onChange,
}: {
  parameter: Parameter;
  value: string;
  onChange: (value: string) => void;
}) {
  const schema = parameter.schema || {};
  return (
    <label className="field">
      <span>
        <strong>{parameter.name}</strong>
        <small className="location">{parameter.in}</small>
        {(parameter.required || parameter.in === "path") && <small className="required">required</small>}
      </span>
      {schema.enum ? (
        <select value={value} onChange={(event) => onChange(event.target.value)}>
          <option value="">Select a value</option>
          {schema.enum.map((option) => (
            <option key={String(option)} value={String(option)}>
              {String(option)}
            </option>
          ))}
        </select>
      ) : (
        <input
          value={value}
          type={schema.format === "password" ? "password" : "text"}
          required={parameter.required || parameter.in === "path"}
          placeholder={
            parameter.example !== undefined
              ? String(parameter.example)
              : schema.default !== undefined
                ? String(schema.default)
                : schema.type || "value"
          }
          onChange={(event) => onChange(event.target.value)}
        />
      )}
      {(parameter.description || constraintText(schema)) && (
        <small>{[parameter.description, constraintText(schema)].filter(Boolean).join(" · ")}</small>
      )}
    </label>
  );
}

function AuthPanel({
  client,
  baseUrl,
  onChange,
}: {
  client: AuthClient;
  baseUrl: string;
  onChange: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [user, setUser] = useState<unknown>();

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage("Authenticating...");
    try {
      const tokens = await client.authenticate("login", {
        email,
        password,
      });
      setUser(tokens.user);
      setMessage("Authenticated. Access token is held in memory.");
      onChange();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Authentication failed.");
    }
  };

  const refresh = async () => {
    setMessage((await client.refresh()) ? "Token pair refreshed." : "Refresh failed.");
    onChange();
  };

  const loadMe = async () => {
    const response = await client.fetch(joinUrl(baseUrl, "/api/v1/auth/me"));
    const data = await response.json();
    setUser(data);
    setMessage(response.ok ? "Profile loaded." : `Profile request failed (${response.status}).`);
  };

  const logout = async () => {
    await client.logout();
    setUser(undefined);
    setMessage("Session revoked and local credentials cleared.");
    onChange();
  };

  return (
    <section className="panel auth-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Identity</span>
          <h2>Authentication</h2>
        </div>
        <span className={`status-dot ${client.getAccessToken() ? "online" : ""}`}>
          {client.getAccessToken() ? "Access token active" : client.hasRefreshToken() ? "Refresh available" : "Signed out"}
        </span>
      </div>
      <form onSubmit={submit} className="auth-form">
        <input aria-label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="developer@example.com" required />
        <input aria-label="Password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password" required />
        <button className="primary" type="submit">Login</button>
      </form>
      <div className="button-row">
        <button onClick={refresh} disabled={!client.hasRefreshToken()}>Refresh</button>
        <button onClick={loadMe} disabled={!client.getAccessToken()}>Load profile</button>
        <button onClick={() => void logout()} disabled={!client.getAccessToken() && !client.hasRefreshToken()}>Logout</button>
      </div>
      {message && <p className="message">{message}</p>}
      {user !== undefined && <pre className="compact-code">{formatJson(user)}</pre>}
    </section>
  );
}

function ResponseInspector({ response }: { response?: ResponseRecord }) {
  const [view, setView] = useState<"body" | "headers">("body");
  if (!response) return <div className="empty-state">Execute a request to inspect its response.</div>;

  return (
    <div>
      <div className="response-meta">
        <span className={`status-code ${response.status < 400 ? "success" : "failure"}`}>{response.status} {response.statusText}</span>
        <span>{response.duration.toFixed(0)} ms</span>
        {response.correlationId && <span>Correlation: <code>{response.correlationId}</code></span>}
      </div>
      <div className="tabs">
        <button className={view === "body" ? "active" : ""} onClick={() => setView("body")}>Body</button>
        <button className={view === "headers" ? "active" : ""} onClick={() => setView("headers")}>Headers</button>
      </div>
      <pre>{view === "body" ? formatJson(response.body) : formatJson(response.headers)}</pre>
    </div>
  );
}

function WebSocketPanel({ baseUrl, token }: { baseUrl: string; token: string | null }) {
  const [branchId, setBranchId] = useState("");
  const [state, setState] = useState("Disconnected");
  const [events, setEvents] = useState<Array<{ time: string; type: string; data: string }>>([]);
  const socket = useRef<WebSocket | null>(null);

  const log = useCallback((type: string, data: string) => {
    setEvents((current) => [{ time: new Date().toLocaleTimeString(), type, data }, ...current].slice(0, 100));
  }, []);

  const connect = () => {
    socket.current?.close();
    const root = baseUrl || window.location.origin;
    const wsRoot = root.replace(/^http/, "ws");
    if (!token) {
      log("error", "An access token is required");
      return;
    }
    const ws = new WebSocket(
      joinUrl(wsRoot, `/api/v1/ws/branches/${encodeURIComponent(branchId)}/orders`),
      ["bearer", token],
    );
    socket.current = ws;
    setState("Connecting");
    ws.onopen = () => { setState("Connected"); log("system", "Connection opened"); };
    ws.onmessage = (event) => log("event", String(event.data));
    ws.onerror = () => log("error", "WebSocket error");
    ws.onclose = (event) => { setState("Disconnected"); log("system", `Closed (${event.code})`); };
  };

  useEffect(() => () => socket.current?.close(), []);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div><span className="eyebrow">Real time</span><h2>Branch order stream</h2></div>
        <span className={`status-dot ${state === "Connected" ? "online" : ""}`}>{state}</span>
      </div>
      <div className="inline-form">
        <input value={branchId} onChange={(event) => setBranchId(event.target.value)} placeholder="Branch UUID" />
        <button className="primary" onClick={connect} disabled={!branchId}>Connect</button>
        <button onClick={() => { socket.current?.send("ping"); log("sent", "ping"); }} disabled={state !== "Connected"}>Ping</button>
        <button onClick={() => socket.current?.close()} disabled={state === "Disconnected"}>Disconnect</button>
      </div>
      <p className="hint">The access token is sent through the negotiated bearer subprotocol.</p>
      <div className="event-log">
        {events.length === 0 ? <div className="empty-state">No events received.</div> : events.map((event, index) => (
          <div className="event" key={`${event.time}-${index}`}>
            <time>{event.time}</time><b>{event.type}</b><code>{event.data}</code>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function App() {
  const [baseUrl, setBaseUrl] = useState(configuredBase);
  const baseRef = useRef(baseUrl);
  baseRef.current = baseUrl;
  const auth = authClient;
  const [, forceAuthRender] = useState(0);
  const [document, setDocument] = useState<OpenApiDocument>();
  const [loadError, setLoadError] = useState("");
  const [health, setHealth] = useState<{ state: string; detail?: unknown; latency?: number }>({ state: "Unchecked" });
  const [search, setSearch] = useState("");
  const [tag, setTag] = useState("All");
  const [selected, setSelected] = useState<Endpoint>();
  const [values, setValues] = useState<Record<string, string>>({});
  const [body, setBody] = useState("");
  const [response, setResponse] = useState<ResponseRecord>();
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [requestError, setRequestError] = useState("");

  const loadOpenApi = useCallback(async () => {
    setLoadError("");
    try {
      const response = await fetch(joinUrl(baseRef.current, "/api/v1/openapi.json"));
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      setDocument(await response.json());
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Unable to load OpenAPI.");
    }
  }, []);

  const checkHealth = useCallback(async () => {
    const start = performance.now();
    setHealth({ state: "Checking" });
    try {
      const response = await fetch(joinUrl(baseRef.current, "/health"));
      const detail = await response.json();
      setHealth({ state: response.ok ? "Connected" : "Degraded", detail, latency: performance.now() - start });
    } catch (error) {
      setHealth({ state: "Offline", detail: error instanceof Error ? error.message : error, latency: performance.now() - start });
    }
  }, []);

  useEffect(() => { void loadOpenApi(); void checkHealth(); }, [loadOpenApi, checkHealth]);

  const endpoints = useMemo(() => document ? extractEndpoints(document) : [], [document]);
  const tags = useMemo(() => ["All", ...new Set(endpoints.flatMap((endpoint) => endpoint.operation.tags || ["Other"]))], [endpoints]);
  const visibleEndpoints = endpoints.filter((endpoint) => {
    const text = `${endpoint.method} ${endpoint.path} ${endpoint.operation.summary || ""}`.toLowerCase();
    return (tag === "All" || endpoint.operation.tags?.includes(tag)) && text.includes(search.toLowerCase());
  });
  const grouped = visibleEndpoints.reduce<Record<string, Endpoint[]>>((groups, endpoint) => {
    const group = endpoint.operation.tags?.[0] || "Other";
    (groups[group] ||= []).push(endpoint);
    return groups;
  }, {});

  const selectEndpoint = (endpoint: Endpoint) => {
    setSelected(endpoint);
    setResponse(undefined);
    setRequestError("");
    setValues(Object.fromEntries(endpoint.parameters.map((parameter) => [parameter.name, String(parameter.schema?.default ?? parameter.example ?? "")])));
    const media = endpoint.operation.requestBody?.content;
    const schema = media?.["application/json"]?.schema;
    setBody(schema && document ? JSON.stringify(schemaDefaults(schema, document), null, 2) : "");
  };

  const execute = async () => {
    if (!selected) return;
    for (const parameter of selected.parameters) {
      if ((parameter.required || parameter.in === "path") && !values[parameter.name]) {
        setRequestError(`${parameter.name} is required.`);
        return;
      }
    }
    setBusy(true);
    setRequestError("");
    try {
      const url = serializeUrl(baseUrl, selected.path, values, selected.parameters);
      const headers: Record<string, string> = {};
      selected.parameters.filter((parameter) => parameter.in === "header").forEach((parameter) => {
        if (values[parameter.name]) headers[parameter.name] = values[parameter.name];
      });
      let parsedBody: unknown;
      if (body && METHODS_WITH_BODY.has(selected.method)) {
        parsedBody = JSON.parse(body);
        headers["Content-Type"] = "application/json";
      }
      if (auth.getAccessToken()) headers.Authorization = "Bearer [IN-MEMORY TOKEN]";
      const start = performance.now();
      const result = await auth.fetch(url, {
        method: selected.method,
        headers: Object.fromEntries(Object.entries(headers).filter(([, value]) => value !== "Bearer [IN-MEMORY TOKEN]")),
        body: parsedBody === undefined ? undefined : JSON.stringify(parsedBody),
      });
      const duration = performance.now() - start;
      const rawBody = await result.text();
      let parsedResponse: unknown = rawBody;
      try { parsedResponse = rawBody ? JSON.parse(rawBody) : null; } catch { /* Keep non-JSON response as text. */ }
      const responseHeaders = Object.fromEntries(result.headers.entries());
      const record: ResponseRecord = {
        status: result.status,
        statusText: result.statusText,
        duration,
        headers: responseHeaders,
        body: parsedResponse,
        rawBody,
        correlationId: result.headers.get("x-correlation-id") || result.headers.get("x-request-id") || undefined,
      };
      setResponse(record);
      setHistory((current) => [{
        id: crypto.randomUUID(),
        timestamp: new Date().toISOString(),
        method: selected.method,
        url,
        headers: redactSecrets(headers),
        body: redactSecrets(parsedBody),
        status: result.status,
        duration,
      }, ...current].slice(0, 30));
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  };

  const bodySchema = selected?.operation.requestBody?.content?.["application/json"]?.schema;
  const resolvedBodySchema = document ? resolveSchema(bodySchema, document) : {};

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark">S</span><div><b>Saturdays</b><span>API Workbench</span></div></div>
        <div className="environment"><span>API base</span><input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="Same origin" /><button onClick={() => { void loadOpenApi(); void checkHealth(); }}>Apply</button></div>
      </header>

      <main>
        <section className="hero">
          <div><span className="eyebrow">Developer console</span><h1>Build against the platform with confidence.</h1><p>Explore the live contract, authenticate, execute requests, and inspect real-time order events.</p></div>
          <div className="health-card">
            <div className="panel-heading"><div><span className="eyebrow">Connection</span><h2>API health</h2></div><span className={`status-dot ${health.state === "Connected" ? "online" : health.state === "Offline" ? "offline" : ""}`}>{health.state}</span></div>
            <div className="health-detail"><span>{health.latency === undefined ? "—" : `${health.latency.toFixed(0)} ms`}</span><code>GET /health</code></div>
            {health.detail !== undefined && <pre className="compact-code">{formatJson(health.detail)}</pre>}
            <button onClick={() => void checkHealth()}>Check again</button>
          </div>
        </section>

        <div className="dashboard-grid">
          <AuthPanel client={auth} baseUrl={baseUrl} onChange={() => forceAuthRender((value) => value + 1)} />
          <section className="panel warnings">
            <div className="panel-heading"><div><span className="eyebrow">Review before use</span><h2>Known risks</h2></div><span className="risk-count">4</span></div>
            <ul>
              <li><b>WebSocket tokens are short lived.</b><span>Reconnect after access-token rotation.</span></li>
              <li><b>Logout revokes this refresh session.</b><span>Use logout-all in the product security page for all devices.</span></li>
              <li><b>Refresh token lives in sessionStorage.</b><span>It is isolated per tab but remains accessible to injected scripts.</span></li>
              <li><b>Wildcard CORS may be enabled.</b><span>Use an explicit origin allowlist outside local development.</span></li>
            </ul>
          </section>
        </div>

        <section className="workbench">
          <aside className="endpoint-nav panel">
            <div className="panel-heading"><div><span className="eyebrow">Live OpenAPI</span><h2>{document?.info?.title || "Endpoints"}</h2></div><span className="endpoint-count">{endpoints.length}</span></div>
            <input className="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search endpoints" />
            <select value={tag} onChange={(event) => setTag(event.target.value)}>{tags.map((value) => <option key={value}>{value}</option>)}</select>
            {loadError && <div className="error-box">OpenAPI unavailable: {loadError}<button onClick={() => void loadOpenApi()}>Retry</button></div>}
            <nav className="endpoint-list">
              {Object.entries(grouped).map(([group, items]) => (
                <div className="endpoint-group" key={group}>
                  <h3>{group}</h3>
                  {items?.map((endpoint) => (
                    <button key={`${endpoint.method}-${endpoint.path}`} className={selected === endpoint ? "selected" : ""} onClick={() => selectEndpoint(endpoint)}>
                      <span className={methodClass(endpoint.method)}>{endpoint.method}</span><span><b>{endpoint.path}</b><small>{endpoint.operation.summary}</small></span>
                    </button>
                  ))}
                </div>
              ))}
            </nav>
          </aside>

          <section className="request-panel panel">
            {!selected ? <div className="empty-state large">Select an endpoint from the OpenAPI explorer.</div> : (
              <>
                <div className="request-title"><span className={methodClass(selected.method)}>{selected.method}</span><div><h2>{selected.operation.summary || selected.path}</h2><code>{selected.path}</code></div></div>
                {selected.operation.description && <p className="description">{selected.operation.description}</p>}
                {selected.parameters.length > 0 && <div className="fields"><h3>Parameters</h3>{selected.parameters.map((parameter) => <Field key={`${parameter.in}-${parameter.name}`} parameter={parameter} value={values[parameter.name] || ""} onChange={(value) => setValues((current) => ({ ...current, [parameter.name]: value }))} />)}</div>}
                {bodySchema && (
                  <div className="body-editor">
                    <div className="section-title"><h3>JSON body {selected.operation.requestBody?.required && <span className="required">required</span>}</h3><span>{Object.keys(resolvedBodySchema.properties || {}).length} fields</span></div>
                    {Object.entries(resolvedBodySchema.properties || {}).length > 0 && <div className="schema-summary">{Object.entries(resolvedBodySchema.properties || {}).map(([name, schema]) => {
                      const resolved = resolveSchema(schema, document!);
                      return <div key={name}><code>{name}</code><span>{resolved.type || resolved.format || "object"}{resolvedBodySchema.required?.includes(name) ? " · required" : ""}</span><small>{constraintText(resolved)}</small></div>;
                    })}</div>}
                    <textarea aria-label="JSON request body" value={body} onChange={(event) => setBody(event.target.value)} spellCheck={false} />
                  </div>
                )}
                {requestError && <div className="error-box">{requestError}</div>}
                <div className="execute-row"><button className="primary execute" onClick={() => void execute()} disabled={busy}>{busy ? "Sending..." : "Execute request"}</button><span>{auth.getAccessToken() ? "Bearer token will be attached" : "Request will be sent without auth"}</span></div>
                <div className="response-section"><h3>Response</h3><ResponseInspector response={response} /></div>
              </>
            )}
          </section>
        </section>

        <section className="lower-grid">
          <section className="panel history-panel">
            <div className="panel-heading"><div><span className="eyebrow">Session</span><h2>Request history</h2></div><button onClick={() => setHistory([])} disabled={!history.length}>Clear</button></div>
            {history.length === 0 ? <div className="empty-state">Executed requests appear here. Secrets are redacted.</div> : history.map((item) => {
              const examples = requestExamples(item.method, item.url, item.headers, item.body);
              return <details key={item.id}><summary><span className={methodClass(item.method)}>{item.method}</span><code>{item.url}</code><span className={item.status && item.status < 400 ? "text-success" : "text-failure"}>{item.status}</span><small>{item.duration?.toFixed(0)} ms</small></summary><div className="history-detail"><h4>Request</h4><pre>{formatJson(redactSecrets({ headers: item.headers, body: item.body }))}</pre><h4>cURL</h4><pre>{examples.curl}</pre><h4>fetch</h4><pre>{examples.fetch}</pre></div></details>;
            })}
          </section>
          <WebSocketPanel baseUrl={baseUrl} token={auth.getAccessToken()} />
        </section>
      </main>
      <footer>
        <span>OpenAPI source: <code>/api/v1/openapi.json</code></span>
        <nav>
          <a href={joinUrl(baseUrl, "/api/v1/docs")} target="_blank" rel="noreferrer">Swagger UI</a>
          <a href={joinUrl(baseUrl, "/api/v1/redoc")} target="_blank" rel="noreferrer">ReDoc</a>
          <a href="/FRONTEND_BACKEND_INTEGRATION.md" target="_blank" rel="noreferrer">Integration contract</a>
        </nav>
        <span>Access tokens are never persisted.</span>
      </footer>
    </div>
  );
}
