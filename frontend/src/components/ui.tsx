import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { ApiError } from "../api/client";
import type { Order, OrderStatus } from "../api/types";
import { orderTransitions } from "./formValidation";

export const money = (value?: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(value || 0);

export const dateTime = (value?: string) =>
  value ? new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "Not available";

export function PageHeader({ eyebrow, title, description, action }: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <span className="product-eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action}
    </header>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`product-card ${className}`}>{children}</section>;
}

export function State({ loading, error, empty, children }: {
  loading?: boolean;
  error?: unknown;
  empty?: boolean;
  children: ReactNode;
}) {
  if (loading) return <div className="product-state" role="status"><span className="loader" />Loading current data...</div>;
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    return <div className="product-state error-state"><b>You are offline</b><span>Reconnect to load current data.</span></div>;
  }
  if (error) {
    return <ApiErrorPanel error={error} />;
  }
  if (empty) return <div className="product-state"><b>Nothing here yet</b><span>New records will appear here when available.</span></div>;
  return <>{children}</>;
}

export type FieldSpec = {
  name: string;
  label: string;
  type?: "text" | "email" | "password" | "number" | "url" | "textarea" | "select" | "checkbox" | "datetime-local";
  required?: boolean;
  placeholder?: string;
  options?: Array<string | { value: string; label: string }>;
  defaultValue?: string | number | boolean;
};

export function SmartForm({ fields, submitLabel, busy, error, onSubmit, compact = false }: {
  fields: FieldSpec[];
  submitLabel: string;
  busy?: boolean;
  error?: unknown;
  onSubmit: (values: Record<string, unknown>, form: HTMLFormElement) => void | Promise<void>;
  compact?: boolean;
}) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const values: Record<string, unknown> = {};
    fields.forEach((field) => {
      if (field.type === "checkbox") values[field.name] = data.get(field.name) === "on";
      else if (field.type === "number") {
        const raw = String(data.get(field.name) || "");
        values[field.name] = raw === "" ? undefined : Number(raw);
      } else {
        const raw = String(data.get(field.name) || "").trim();
        values[field.name] = raw === "" ? undefined : raw;
      }
    });
    void onSubmit(values, form);
  };
  return (
    <form className={`smart-form ${compact ? "compact" : ""}`} onSubmit={submit}>
      {fields.map((field) => (
        <label key={field.name}>
          <span>{field.label}</span>
          {field.type === "textarea" ? (
            <textarea name={field.name} required={field.required} placeholder={field.placeholder} defaultValue={String(field.defaultValue || "")} />
          ) : field.type === "select" ? (
            <select name={field.name} required={field.required} defaultValue={String(field.defaultValue || "")}>
              <option value="">Select</option>
              {field.options?.map((option) => {
                const item = typeof option === "string" ? { value: option, label: option } : option;
                return <option key={item.value} value={item.value}>{item.label}</option>;
              })}
            </select>
          ) : field.type === "checkbox" ? (
            <input name={field.name} type="checkbox" defaultChecked={Boolean(field.defaultValue)} />
          ) : (
            <input name={field.name} type={field.type || "text"} required={field.required} placeholder={field.placeholder} defaultValue={String(field.defaultValue || "")} />
          )}
        </label>
      ))}
      {Boolean(error) && <div className="inline-error">{error instanceof Error ? error.message : "Request failed."}</div>}
      <button className="product-button primary" type="submit" disabled={busy}>{busy ? "Saving..." : submitLabel}</button>
    </form>
  );
}

export function StatusPill({ value }: { value: string | boolean }) {
  const text = typeof value === "boolean" ? value ? "Active" : "Inactive" : value;
  const good = value === true || ["ACTIVE", "APPROVED", "COMPLETED", "READY", "CAPTURED", "ONLINE"].includes(text.toUpperCase());
  return <span className={`pill ${good ? "good" : ""}`}>{text}</span>;
}

export function Notice({ title, children }: { title: string; children: ReactNode }) {
  return <div className="product-notice"><b>{title}</b><span>{children}</span></div>;
}

export function LabeledSelect({ label, options, value, onChange, placeholder = "Select", required }: {
  label: string;
  options: Array<{ value: string; label: string }>;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  const id = useId();
  return (
    <label htmlFor={id} className="labeled-control">
      <span>{label}</span>
      <select id={id} value={value} required={required} onChange={(event) => onChange(event.target.value)}>
        <option value="">{placeholder}</option>
        {options.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
      </select>
    </label>
  );
}

export function ApiErrorPanel({ error, title = "We could not complete that request." }: {
  error: unknown;
  title?: string;
}) {
  const problem = error instanceof ApiError ? error.problem : undefined;
  const message = problem?.message ?? (error instanceof Error ? error.message : "Unable to load data.");
  return (
    <div className="product-state error-state" role="alert">
      <b>{title}</b>
      <span>{message}</span>
      {problem?.code && <code>{problem.code}</code>}
      {problem?.correlationId && <small>Correlation ID: {problem.correlationId}</small>}
      {problem?.details !== undefined && (
        <details><summary>Technical details</summary><pre>{JSON.stringify(problem.details, null, 2)}</pre></details>
      )}
    </div>
  );
}

export function ConfirmDialog({ open, title, description, confirmLabel = "Confirm", cancelLabel = "Cancel", destructive, onConfirm, onCancel }: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog ref={ref} className="confirm-dialog" aria-labelledby="confirm-title" onCancel={onCancel}>
      <h2 id="confirm-title">{title}</h2>
      <p>{description}</p>
      <div className="card-actions">
        <button autoFocus onClick={onCancel}>{cancelLabel}</button>
        <button className={destructive ? "danger" : "primary"} onClick={onConfirm}>{confirmLabel}</button>
      </div>
    </dialog>
  );
}

export function PaginationControls({ page, pages, total, onPageChange }: {
  page: number;
  pages: number;
  total?: number;
  onPageChange: (page: number) => void;
}) {
  return (
    <nav className="pagination" aria-label="Pagination">
      <button disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Previous</button>
      <span>Page {page} of {Math.max(1, pages)}{total !== undefined ? ` · ${total} total` : ""}</span>
      <button disabled={page >= pages} onClick={() => onPageChange(page + 1)}>Next</button>
    </nav>
  );
}

export function FilterControls({ search, onSearch, children }: {
  search: string;
  onSearch: (value: string) => void;
  children?: ReactNode;
}) {
  return <div className="filter-controls"><input aria-label="Filter results" type="search" value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Filter results" />{children}</div>;
}

export function MaskedValue({ value, visible = 4 }: { value?: string; visible?: number }) {
  const [revealed, setRevealed] = useState(false);
  if (!value) return <span>Not provided</span>;
  const masked = value.length <= visible ? "•".repeat(value.length) : `${"•".repeat(Math.min(12, value.length - visible))}${value.slice(-visible)}`;
  return <span className="masked-value"><code>{revealed ? value : masked}</code><button type="button" onClick={() => setRevealed((current) => !current)}>{revealed ? "Hide" : "Reveal"}</button></span>;
}

export function OrderTimeline({ order }: { order: Order }) {
  const events = order.status_logs.length
    ? order.status_logs
    : [{ id: order.id, new_status: order.status, created_at: order.created_at }];
  return <ol className="order-timeline">{events.map((event) => <li key={event.id}><StatusPill value={event.new_status} /><time>{dateTime(event.created_at)}</time></li>)}</ol>;
}

export function OrderTransitionControls({ status, busy, onTransition }: {
  status: OrderStatus;
  busy?: boolean;
  onTransition: (status: OrderStatus) => void;
}) {
  const [pending, setPending] = useState<OrderStatus>();
  return (
    <>
      <div className="card-actions">
        {orderTransitions[status].map((target) => <button className={target === "CANCELLED" ? "danger" : "primary"} disabled={busy} key={target} onClick={() => setPending(target)}>{target === "CANCELLED" ? "Cancel order" : `Mark ${target.toLowerCase()}`}</button>)}
      </div>
      <ConfirmDialog open={Boolean(pending)} title={`Move order to ${pending?.toLowerCase()}?`} description="This transition is recorded and cannot be reversed from this screen." destructive={pending === "CANCELLED"} confirmLabel="Apply transition" onCancel={() => setPending(undefined)} onConfirm={() => { if (pending) onTransition(pending); setPending(undefined); }} />
    </>
  );
}
