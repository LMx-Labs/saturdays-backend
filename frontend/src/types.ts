export type JsonSchema = {
  $ref?: string;
  type?: string;
  format?: string;
  title?: string;
  description?: string;
  default?: unknown;
  example?: unknown;
  enum?: unknown[];
  nullable?: boolean;
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  minItems?: number;
  maxItems?: number;
  pattern?: string;
  items?: JsonSchema;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  allOf?: JsonSchema[];
  anyOf?: JsonSchema[];
  oneOf?: JsonSchema[];
};

export type Parameter = {
  name: string;
  in: "path" | "query" | "header" | "cookie";
  required?: boolean;
  description?: string;
  schema?: JsonSchema;
  example?: unknown;
};

export type Operation = {
  operationId?: string;
  summary?: string;
  description?: string;
  tags?: string[];
  parameters?: Parameter[];
  requestBody?: {
    required?: boolean;
    content?: Record<string, { schema?: JsonSchema; example?: unknown }>;
  };
  security?: Array<Record<string, string[]>>;
};

export type OpenApiDocument = {
  info?: { title?: string; version?: string; description?: string };
  paths?: Record<string, Record<string, Operation | Parameter[]>>;
  components?: { schemas?: Record<string, JsonSchema> };
};

export type Endpoint = {
  method: string;
  path: string;
  operation: Operation;
  parameters: Parameter[];
};

export type ResponseRecord = {
  status: number;
  statusText: string;
  duration: number;
  headers: Record<string, string>;
  body: unknown;
  rawBody: string;
  correlationId?: string;
};

export type HistoryItem = {
  id: string;
  timestamp: string;
  method: string;
  url: string;
  headers: Record<string, string>;
  body?: unknown;
  status?: number;
  duration?: number;
};

export type AuthTokens = {
  access_token: string;
  refresh_token: string;
  token_type?: string;
  expires_in?: number;
  user?: unknown;
};
