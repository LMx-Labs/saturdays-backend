import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { adminApi } from "../api/modules";
import type { Merchant, Payment, User } from "../api/types";
import { Card, ConfirmDialog, dateTime, FilterControls, money, Notice, PageHeader, PaginationControls, SmartForm, State, StatusPill } from "../components/ui";

const refresh = (client: ReturnType<typeof useQueryClient>, key: string) => () =>
  client.invalidateQueries({ queryKey: [key] });

const merchantTransitions: Record<string, string[]> = {
  DRAFT: ["PENDING_VERIFICATION"],
  PENDING_VERIFICATION: ["APPROVED", "REJECTED"],
  REJECTED: ["DRAFT", "PENDING_VERIFICATION"],
  APPROVED: ["SUSPENDED"],
  SUSPENDED: ["APPROVED"],
};

export function AdminDashboard() {
  const analytics = useQuery({ queryKey: ["analytics"], queryFn: adminApi.analytics });
  return <><PageHeader eyebrow="Platform control" title="Operations overview" description="Live totals from the platform analytics route." /><State loading={analytics.isLoading} error={analytics.error} empty={!analytics.data}><div className="metric-grid admin-metrics">{analytics.data && Object.entries(analytics.data).map(([key, value]) => <Card key={key}><span>{key.replaceAll("_", " ")}</span><b>{key.includes("revenue") || key.includes("commission") ? money(value) : value.toLocaleString("en-IN")}</b><small>Current backend aggregate</small></Card>)}</div></State></>;
}

export function ApprovalsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [merchant, setMerchant] = useState<Merchant>();
  const queue = useQuery({ queryKey: ["admin-merchants", page, search, statusFilter], queryFn: () => adminApi.merchants({ page, page_size: 25, search: search || undefined, status: statusFilter || undefined }) });
  const mutation = useMutation({ mutationFn: ({ id, values }: { id: string; values: Record<string, unknown> }) => adminApi.approveMerchant(id, values) });
  const status = useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) => adminApi.updateMerchantStatus(id, value),
    onSuccess: () => { setMerchant(undefined); void queryClient.invalidateQueries({ queryKey: ["admin-merchants"] }); },
  });
  return <><PageHeader eyebrow="Trust and safety" title="Merchant lifecycle queue" description="Search applications, inspect KYC masks and record review decisions." /><FilterControls search={search} onSearch={(value) => { setSearch(value); setPage(1); }}><select aria-label="Merchant status" value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setPage(1); }}><option value="">All statuses</option>{Object.keys(merchantTransitions).map((value) => <option key={value}>{value}</option>)}</select></FilterControls><State loading={queue.isLoading} error={queue.error} empty={!queue.data?.items.length}><div className="stack">{queue.data?.items.map((item) => <Card key={item.id}><div className="card-heading"><div><h3>{item.business_name}</h3><p>{item.legal_entity_name}</p><small>Created {dateTime(item.created_at)}</small></div><StatusPill value={item.status} /></div><button onClick={() => setMerchant(item)}>Review application</button></Card>)}</div></State>{queue.data && <PaginationControls page={page} pages={queue.data.pages} total={queue.data.total} onPageChange={setPage} />}{merchant && <Card><div className="card-heading"><div><h2>{merchant.business_name}</h2><p>{merchant.legal_entity_name}</p></div><StatusPill value={merchant.status} /></div>{merchant.status === "PENDING_VERIFICATION" ? <SmartForm fields={[{ name: "action", label: "Decision", type: "select", required: true, options: ["APPROVE", "REJECT"] }, { name: "reason", label: "Reason", type: "textarea" }]} submitLabel="Record decision" busy={mutation.isPending} error={mutation.error} onSubmit={(values) => mutation.mutate({ id: merchant.id, values }, { onSuccess: () => { setMerchant(undefined); void queryClient.invalidateQueries({ queryKey: ["admin-merchants"] }); } })} /> : <SmartForm compact fields={[{ name: "status", label: "Next lifecycle status", type: "select", required: true, options: merchantTransitions[merchant.status] || [] }]} submitLabel="Update status" busy={status.isPending} error={status.error} onSubmit={(values) => status.mutate({ id: merchant.id, value: String(values.status) })} />}</Card>}</>;
}

export function BannersPage() {
  const queryClient = useQueryClient();
  const [removeId, setRemoveId] = useState("");
  const query = useQuery({ queryKey: ["admin-banners"], queryFn: () => adminApi.banners(false) });
  const create = useMutation({ mutationFn: adminApi.createBanner, onSuccess: refresh(queryClient, "admin-banners") });
  const update = useMutation({ mutationFn: ({ id, values }: { id: string; values: Record<string, unknown> }) => adminApi.updateBanner(id, values), onSuccess: refresh(queryClient, "admin-banners") });
  const remove = useMutation({ mutationFn: adminApi.deleteBanner, onSuccess: () => { setRemoveId(""); void queryClient.invalidateQueries({ queryKey: ["admin-banners"] }); } });
  return <><PageHeader eyebrow="Content" title="Homepage banners" /><div className="split-grid"><Card><h2>Create campaign</h2><SmartForm fields={[{ name: "title", label: "Title", required: true }, { name: "image_url", label: "Image URL", type: "url", required: true }, { name: "target_url", label: "Target URL", type: "url" }, { name: "display_order", label: "Display order", type: "number", defaultValue: 0 }, { name: "is_active", label: "Active", type: "checkbox", defaultValue: true }]} submitLabel="Publish banner" busy={create.isPending} error={create.error} onSubmit={(values, form) => create.mutate(values, { onSuccess: () => form.reset() })} /></Card><State loading={query.isLoading} error={query.error} empty={!query.data?.length}><div className="stack">{query.data?.map((banner) => <Card key={String(banner.id)}><div className="card-heading"><h3>{String(banner.title)}</h3><StatusPill value={Boolean(banner.is_active)} /></div><SmartForm compact fields={[{ name: "title", label: "Title", required: true, defaultValue: String(banner.title) }, { name: "image_url", label: "Image URL", type: "url", required: true, defaultValue: String(banner.image_url) }, { name: "target_url", label: "Target URL", type: "url", defaultValue: banner.target_url ? String(banner.target_url) : "" }, { name: "display_order", label: "Display order", type: "number", defaultValue: Number(banner.display_order) }, { name: "is_active", label: "Active", type: "checkbox", defaultValue: Boolean(banner.is_active) }]} submitLabel="Save banner" busy={update.isPending} onSubmit={(values) => update.mutate({ id: String(banner.id), values })} /><button className="danger" onClick={() => setRemoveId(String(banner.id))}>Delete banner</button></Card>)}</div></State></div><ConfirmDialog open={Boolean(removeId)} title="Delete banner?" description="The campaign will immediately disappear from the storefront." destructive confirmLabel="Delete banner" onCancel={() => setRemoveId("")} onConfirm={() => remove.mutate(removeId)} /></>;
}

export function AdminCouponsPage() {
  const queryClient = useQueryClient();
  const [removeId, setRemoveId] = useState("");
  const coupons = useQuery({ queryKey: ["admin-coupons"], queryFn: () => adminApi.coupons() });
  const mutation = useMutation({ mutationFn: adminApi.createCoupon, onSuccess: refresh(queryClient, "admin-coupons") });
  const toggle = useMutation({ mutationFn: ({ id, active }: { id: string; active: boolean }) => adminApi.toggleCoupon(id, active), onSuccess: refresh(queryClient, "admin-coupons") });
  const remove = useMutation({ mutationFn: adminApi.deleteCoupon, onSuccess: () => { setRemoveId(""); void queryClient.invalidateQueries({ queryKey: ["admin-coupons"] }); } });
  const now = new Date();
  const later = new Date(now.getTime() + 30 * 86400000);
  return <><PageHeader eyebrow="Promotions" title="Platform coupons" description="Create global offers and manage their active lifecycle." /><div className="split-grid"><Card><h2>Create coupon</h2><SmartForm fields={[{ name: "code", label: "Coupon code", required: true }, { name: "discount_type", label: "Discount type", type: "select", required: true, options: ["PERCENTAGE", "FLAT"] }, { name: "discount_value", label: "Discount value", type: "number", required: true }, { name: "max_discount_amount", label: "Maximum discount", type: "number" }, { name: "min_order_amount", label: "Minimum order", type: "number", defaultValue: 0 }, { name: "max_redemptions_per_user", label: "Redemptions per user", type: "number", defaultValue: 1 }, { name: "valid_from", label: "Valid from", type: "datetime-local", required: true, defaultValue: now.toISOString().slice(0, 16) }, { name: "valid_until", label: "Valid until", type: "datetime-local", required: true, defaultValue: later.toISOString().slice(0, 16) }, { name: "is_active", label: "Active", type: "checkbox", defaultValue: true }]} submitLabel="Create coupon" busy={mutation.isPending} error={mutation.error} onSubmit={(values, form) => mutation.mutate({ ...values, valid_from: new Date(String(values.valid_from)).toISOString(), valid_until: new Date(String(values.valid_until)).toISOString() }, { onSuccess: () => form.reset() })} /></Card><State loading={coupons.isLoading} error={coupons.error} empty={!coupons.data?.length}><div className="stack">{coupons.data?.map((coupon) => <Card key={String(coupon.id)}><div className="card-heading"><div><h3>{String(coupon.code)}</h3><small>{String(coupon.discount_type)} · {String(coupon.discount_value)}</small></div><StatusPill value={Boolean(coupon.is_active)} /></div><div className="card-actions"><button onClick={() => toggle.mutate({ id: String(coupon.id), active: !coupon.is_active })}>{coupon.is_active ? "Deactivate" : "Activate"}</button><button className="danger" onClick={() => setRemoveId(String(coupon.id))}>Delete</button></div></Card>)}</div></State></div><ConfirmDialog open={Boolean(removeId)} title="Delete coupon?" description="Customers will no longer be able to redeem this offer." destructive confirmLabel="Delete coupon" onCancel={() => setRemoveId("")} onConfirm={() => remove.mutate(removeId)} /></>;
}

export function FeatureFlagsPage() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["flags"], queryFn: adminApi.flags });
  const update = useMutation({ mutationFn: ({ key, enabled, value }: { key: string; enabled: boolean; value?: string }) => adminApi.updateFlag(key, { enabled, value }), onSuccess: refresh(queryClient, "flags") });
  return <><PageHeader eyebrow="Runtime controls" title="Feature flags" description="Operational controls are process-local in the current backend." /><Notice title="Prototype control">Changes are lost when the API process restarts and are not shared across multiple workers.</Notice><State loading={query.isLoading} error={query.error} empty={!query.data?.length}><div className="stack">{query.data?.map((flag) => <Card key={flag.flag_key}><div className="card-heading"><div><h3>{flag.flag_key}</h3><p>{flag.value || "No configured value"}</p></div><StatusPill value={flag.enabled} /></div><button onClick={() => update.mutate({ key: flag.flag_key, value: flag.value, enabled: !flag.enabled })}>{flag.enabled ? "Disable" : "Enable"}</button></Card>)}</div></State></>;
}

export function RefundOverridePage() {
  const mutation = useMutation({ mutationFn: adminApi.refundOverride });
  return <><PageHeader eyebrow="Financial controls" title="Refund override" description="Create a privileged refund audit record." /><Notice title="No gateway refund">The current backend returns a synthetic refund identifier but does not call Razorpay or append a payment transaction.</Notice><Card><SmartForm fields={[{ name: "payment_id", label: "Payment ID", required: true }, { name: "amount", label: "Refund amount", type: "number", required: true }, { name: "reason", label: "Operational reason", type: "textarea", required: true }]} submitLabel="Record override" busy={mutation.isPending} error={mutation.error} onSubmit={(values) => mutation.mutate(values)} />{Boolean(mutation.data) && <pre>{JSON.stringify(mutation.data, null, 2)}</pre>}</Card></>;
}

export function AuditPage() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const [target, setTarget] = useState("");
  const limit = 50;
  const query = useQuery({ queryKey: ["audit", page, action, target], queryFn: () => adminApi.audit({ skip: (page - 1) * limit, limit, action: action || undefined, target_entity: target || undefined }) });
  return <><PageHeader eyebrow="Governance" title="Audit log" description="Filter and page through immutable administration records." /><div className="filter-controls"><input aria-label="Audit action" placeholder="Exact action" value={action} onChange={(event) => { setAction(event.target.value); setPage(1); }} /><input aria-label="Target entity" placeholder="Exact target entity" value={target} onChange={(event) => { setTarget(event.target.value); setPage(1); }} /></div><State loading={query.isLoading} error={query.error} empty={!query.data?.length}><div className="audit-list">{query.data?.map((row) => <Card key={String(row.id)}><div><b>{String(row.action)}</b><span>{String(row.target_entity)} {row.target_entity_id ? `· ${String(row.target_entity_id).slice(0, 8)}` : ""}</span></div><small>{dateTime(String(row.created_at))}<br />{String(row.ip_address)}</small></Card>)}</div></State><PaginationControls page={page} pages={query.data?.length === limit ? page + 1 : page} onPageChange={setPage} /></>;
}

async function health(path: string) {
  const response = await fetch(path);
  const data = await response.json();
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return data as Record<string, unknown>;
}

export function SystemStatusPage() {
  const general = useQuery({ queryKey: ["health"], queryFn: () => health("/health"), refetchInterval: 30000 });
  const live = useQuery({ queryKey: ["health-live"], queryFn: () => health("/health/live"), refetchInterval: 30000 });
  const ready = useQuery({ queryKey: ["health-ready"], queryFn: () => health("/health/ready"), refetchInterval: 30000 });
  const checks = [["API", general], ["Process", live], ["Database readiness", ready]] as const;
  return <><PageHeader eyebrow="Reliability" title="System status" description="Read-only health probes refresh every 30 seconds." /><div className="metric-grid">{checks.map(([label, query]) => <Card key={label}><div className="card-heading"><h3>{label}</h3><StatusPill value={!query.error} /></div>{query.isLoading ? <span>Checking...</span> : query.error ? <p>{query.error.message}</p> : <div className="detail-grid">{Object.entries(query.data || {}).map(([key, value]) => <span key={key}>{key.replaceAll("_", " ")} <b>{String(value)}</b></span>)}</div>}</Card>)}</div><Notice title="Provider operations">Payment provider callbacks are server-only. Payment transaction histories and health probes provide the supported operational visibility.</Notice></>;
}

export function AdminUsersPage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<User>();
  const [deactivate, setDeactivate] = useState<User>();
  const users = useQuery({ queryKey: ["admin-users"], queryFn: () => adminApi.users() });
  const create = useMutation({ mutationFn: adminApi.createUser, onSuccess: refresh(queryClient, "admin-users") });
  const update = useMutation({ mutationFn: ({ id, values }: { id: string; values: Record<string, unknown> }) => adminApi.updateUser(id, values), onSuccess: refresh(queryClient, "admin-users") });
  const disable = useMutation({ mutationFn: adminApi.deactivateUser, onSuccess: () => { setDeactivate(undefined); void queryClient.invalidateQueries({ queryKey: ["admin-users"] }); } });
  const invite = useMutation({ mutationFn: adminApi.invite });
  const sessions = useQuery({ queryKey: ["admin-sessions", selected?.id], queryFn: () => adminApi.sessions(selected!.id), enabled: Boolean(selected) });
  const revoke = useMutation({ mutationFn: () => adminApi.revokeSessions(selected!.id), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-sessions", selected?.id] }) });
  return <><PageHeader eyebrow="Identity administration" title="Users, invitations and sessions" /><div className="split-grid"><Card><h2>Create user</h2><SmartForm fields={[{ name: "email", label: "Email", type: "email", required: true }, { name: "password", label: "Temporary password", type: "password", required: true }, { name: "role", label: "Role", type: "select", options: ["Customer", "KitchenStaff", "BranchManager", "MerchantOwner", "PlatformAdmin"], required: true }, { name: "is_verified", label: "Email verified", type: "checkbox", defaultValue: true }]} submitLabel="Create user" busy={create.isPending} error={create.error} onSubmit={(values, form) => create.mutate(values, { onSuccess: () => form.reset() })} /></Card><Card><h2>Send invitation</h2><SmartForm fields={[{ name: "email", label: "Email", type: "email", required: true }, { name: "role", label: "Role", type: "select", options: ["KitchenStaff", "BranchManager", "MerchantOwner", "PlatformAdmin"], required: true }]} submitLabel="Create invitation" busy={invite.isPending} error={invite.error} onSubmit={(values, form) => invite.mutate({ ...values, branch_ids: [] }, { onSuccess: () => form.reset() })} />{invite.data?.preview_token && <Notice title="Development invitation link"><a href={`/auth/invitations/accept?token=${encodeURIComponent(invite.data.preview_token)}`}>Accept invitation for {invite.data.email}</a></Notice>}</Card></div><State loading={users.isLoading} error={users.error} empty={!users.data?.length}><div className="stack">{users.data?.map((user) => <Card key={user.id}><div className="card-heading"><div><h3>{user.email}</h3><small>{user.role} · {user.is_verified ? "Verified" : "Unverified"}</small></div><StatusPill value={user.is_active} /></div><div className="card-actions"><button onClick={() => setSelected(user)}>Sessions</button><button className="danger" disabled={!user.is_active} onClick={() => setDeactivate(user)}>Deactivate</button></div><SmartForm compact fields={[{ name: "email", label: "Email", type: "email", defaultValue: user.email }, { name: "role", label: "Role", type: "select", options: ["Customer", "KitchenStaff", "BranchManager", "MerchantOwner", "PlatformAdmin"], defaultValue: user.role }, { name: "is_verified", label: "Verified", type: "checkbox", defaultValue: user.is_verified }]} submitLabel="Update user" busy={update.isPending} onSubmit={(values) => update.mutate({ id: user.id, values })} /></Card>)}</div></State>{selected && <Card><div className="card-heading"><h2>Sessions for {selected.email}</h2><button onClick={() => setSelected(undefined)}>Close</button></div><State loading={sessions.isLoading} error={sessions.error} empty={!sessions.data?.length}>{sessions.data?.map((session) => <div className="line-item" key={session.id}><span>Created {dateTime(session.created_at)} · Last used {dateTime(session.last_used_at)}</span><StatusPill value={session.revoked_at ? "REVOKED" : "ACTIVE"} /></div>)}</State><button className="danger" disabled={revoke.isPending} onClick={() => revoke.mutate()}>Revoke all sessions</button></Card>}<ConfirmDialog open={Boolean(deactivate)} title="Deactivate user?" description={`${deactivate?.email} will lose access to all workspaces.`} destructive confirmLabel="Deactivate" onCancel={() => setDeactivate(undefined)} onConfirm={() => disable.mutate(deactivate!.id)} /></>;
}

export function ModerationPage() {
  const queryClient = useQueryClient();
  const reviews = useQuery({ queryKey: ["hidden-reviews"], queryFn: adminApi.hiddenReviews });
  const moderate = useMutation({ mutationFn: ({ id, hidden }: { id: string; hidden: boolean }) => adminApi.moderateReview(id, { is_hidden: hidden }), onSuccess: refresh(queryClient, "hidden-reviews") });
  return <><PageHeader eyebrow="Trust and safety" title="Review moderation queue" description="Review hidden content and restore it when appropriate." /><State loading={reviews.isLoading} error={reviews.error} empty={!reviews.data?.length}><div className="stack">{reviews.data?.map((review) => <Card key={review.id}><div className="card-heading"><b>{review.rating} / 5</b><small>{dateTime(review.created_at)}</small></div><p>{review.comment || "No written comment."}</p><button onClick={() => moderate.mutate({ id: review.id, hidden: false })}>Restore review</button></Card>)}</div></State></>;
}

export function AdminPaymentsPage() {
  const [page, setPage] = useState(1);
  const [payment, setPayment] = useState<Payment>();
  const [values, setValues] = useState<Record<string, unknown>>();
  const payments = useQuery({ queryKey: ["admin-payments", page], queryFn: () => adminApi.payments(page) });
  const refund = useMutation({ mutationFn: () => adminApi.refundOverride({ payment_id: payment!.id, ...values }), onSuccess: () => { setPayment(undefined); setValues(undefined); } });
  return <><PageHeader eyebrow="Financial operations" title="Platform payments and refunds" /><State loading={payments.isLoading} error={payments.error} empty={!payments.data?.items.length}><div className="stack">{payments.data?.items.map((item) => <Card key={item.id}><div className="card-heading"><div><h3>Order {item.order_id.slice(0, 8)}</h3><small>{item.provider} · {dateTime(item.created_at)}</small></div><b>{money(item.amount)}</b></div><SmartForm compact fields={[{ name: "amount", label: "Refund amount", type: "number", required: true }, { name: "reason", label: "Operational reason", required: true }]} submitLabel="Prepare refund" busy={refund.isPending} error={refund.error} onSubmit={(next) => { setPayment(item); setValues(next); }} /></Card>)}</div></State>{payments.data && <PaginationControls page={page} pages={payments.data.pages} total={payments.data.total} onPageChange={setPage} />}<ConfirmDialog open={Boolean(payment)} title="Confirm privileged refund" description={`Issue ${money(Number(values?.amount))} against order ${payment?.order_id.slice(0, 8)}?`} destructive confirmLabel="Issue refund" onCancel={() => { setPayment(undefined); setValues(undefined); }} onConfirm={() => refund.mutate()} /></>;
}

export function AdminReportsPage() {
  const report = useQuery({ queryKey: ["platform-report"], queryFn: () => adminApi.platformReport() });
  return <><PageHeader eyebrow="Platform reporting" title="Operational analytics" /><State loading={report.isLoading} error={report.error} empty={!report.data}><div className="metric-grid">{report.data && Object.entries(report.data).filter(([key]) => key !== "generated_at").map(([key, value]) => <Card key={key}><span>{key.replaceAll("_", " ")}</span><b>{key.includes("sales") ? money(Number(value)) : Number(value).toLocaleString("en-IN")}</b></Card>)}</div></State></>;
}
