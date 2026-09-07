import type { Endpoint, JsonSchema, OpenApiDocument, Operation, Parameter } from "./types";

const HTTP_METHODS = new Set(["get", "post", "put", "patch", "delete", "head", "options"]);
const SECRET_KEY = /authorization|password|token|secret|api[-_]?key|cookie/i;

export function joinUrl(base: string, path: string): string {
  return `${base.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

export function serializeUrl(
  base: string,
  path: string,
  values: Record<string, string>,
  parameters: Parameter[],
): string {
  let resolvedPath = path;
  const query = new URLSearchParams();

  for (const parameter of parameters) {
    const value = values[parameter.name];
    if (value === undefined || value === "") continue;
    if (parameter.in === "path") {
      resolvedPath = resolvedPath.replace(`{${parameter.name}}`, encodeURIComponent(value));
    } else if (parameter.in === "query") {
      query.append(parameter.name, value);
    }
  }

  const queryString = query.toString();
  return `${joinUrl(base, resolvedPath)}${queryString ? `?${queryString}` : ""}`;
}

export function resolveSchema(schema: JsonSchema | undefined, document: OpenApiDocument): JsonSchema {
  if (!schema) return {};
  if (schema.$ref) {
    const name = schema.$ref.split("/").at(-1);
    return name && document.components?.schemas?.[name]
      ? resolveSchema(document.components.schemas[name], document)
      : schema;
  }
  if (schema.allOf?.length) {
    return schema.allOf.reduce<JsonSchema>((merged, item) => {
      const resolved = resolveSchema(item, document);
      return {
        ...merged,
        ...resolved,
        properties: { ...merged.properties, ...resolved.properties },
        required: [...new Set([...(merged.required || []), ...(resolved.required || [])])],
      };
    }, {});
  }
  const alternatives = schema.anyOf || schema.oneOf;
  if (alternatives?.length) {
    const preferred = alternatives.find((item) => resolveSchema(item, document).type !== "null");
    if (preferred) {
      return {
        ...schema,
        ...resolveSchema(preferred, document),
        nullable: schema.nullable || alternatives.some((item) => resolveSchema(item, document).type === "null"),
      };
    }
  }
  return schema;
}

export function schemaDefaults(schema: JsonSchema | undefined, document: OpenApiDocument): unknown {
  const resolved = resolveSchema(schema, document);
  if (resolved.default !== undefined) return resolved.default;
  if (resolved.example !== undefined) return resolved.example;
  if (resolved.enum?.length) return resolved.enum[0];
  if (resolved.type === "array") {
    return resolved.minItems && resolved.minItems > 0
      ? Array.from({ length: resolved.minItems }, () => schemaDefaults(resolved.items, document))
      : [];
  }
  if (resolved.type === "object" || resolved.properties) {
    return Object.fromEntries(
      Object.entries(resolved.properties || {})
        .filter(([key, value]) => {
          const property = resolveSchema(value, document);
          return resolved.required?.includes(key) ||
            property.default !== undefined ||
            property.example !== undefined;
        })
        .map(([key, value]) => [key, schemaDefaults(value, document)]),
    );
  }
  if (resolved.type === "boolean") return false;
  if (resolved.type === "integer" || resolved.type === "number") return 0;
  return "";
}

export function extractEndpoints(document: OpenApiDocument): Endpoint[] {
  return Object.entries(document.paths || {}).flatMap(([path, pathItem]) => {
    const shared = (pathItem.parameters as Parameter[] | undefined) || [];
    return Object.entries(pathItem)
      .filter(([method]) => HTTP_METHODS.has(method))
      .map(([method, value]) => {
        const operation = value as Operation;
        return {
          method: method.toUpperCase(),
          path,
          operation,
          parameters: [...shared, ...(operation.parameters || [])],
        };
      });
  });
}

export function redactSecrets<T>(value: T): T {
  const walk = (item: unknown, key = ""): unknown => {
    if (SECRET_KEY.test(key)) return "[REDACTED]";
    if (Array.isArray(item)) return item.map((entry) => walk(entry));
    if (item && typeof item === "object") {
      return Object.fromEntries(
        Object.entries(item).map(([childKey, child]) => [childKey, walk(child, childKey)]),
      );
    }
    return item;
  };
  return walk(value) as T;
}

export function formatJson(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

export function requestExamples(
  method: string,
  url: string,
  headers: Record<string, string>,
  body?: unknown,
): { curl: string; fetch: string } {
  const safeHeaders = redactSecrets(headers);
  const headerArgs = Object.entries(safeHeaders)
    .map(([key, value]) => `-H '${key}: ${value}'`)
    .join(" ");
  const payload = body === undefined ? "" : ` --data '${JSON.stringify(redactSecrets(body))}'`;
  const curl = `curl -X ${method} '${url}' ${headerArgs}${payload}`.trim();
  const fetchOptions = {
    method,
    headers: safeHeaders,
    ...(body === undefined ? {} : { body: JSON.stringify(redactSecrets(body)) }),
  };
  return { curl, fetch: `fetch(${JSON.stringify(url)}, ${JSON.stringify(fetchOptions, null, 2)})` };
}
