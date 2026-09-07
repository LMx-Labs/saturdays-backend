import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { discoveryApi, merchantApi } from "../api/modules";
import type { Branch, Payment } from "../api/types";
import {
  Card, ConfirmDialog, dateTime, MaskedValue, money, Notice, OrderTimeline,
  OrderTransitionControls, PageHeader, PaginationControls, SmartForm, State, StatusPill,
} from "../components/ui";
import { useToast } from "../components/toastContext";

const refresh = (client: ReturnType<typeof useQueryClient>, ...keys: string[]) => () =>
  keys.forEach((key) => client.invalidateQueries({ queryKey: [key] }));

const orderTransitions: Record<string, string[]> = {
  PLACED: ["ACCEPTED", "CANCELLED"],
  ACCEPTED: ["PREPARING", "CANCELLED"],
  PREPARING: ["READY"],
  READY: ["COMPLETED"],
};

function BranchPicker({ branches, value, onChange }: { branches?: Branch[]; value: string; onChange: (value: string) => void }) {
  return <select className="branch-picker" value={value} onChange={(event) => onChange(event.target.value)}><option value="">Select a branch</option>{branches?.map((branch) => <option value={branch.id} key={branch.id}>{branch.name}</option>)}</select>;
}

function useMerchantData() {
  const merchant = useQuery({ queryKey: ["merchant"], queryFn: merchantApi.me, retry: false });
  const brands = useQuery({ queryKey: ["merchant-brands", merchant.data?.id], queryFn: () => merchantApi.brands(merchant.data!.id), enabled: Boolean(merchant.data?.id) });
  const branches = useQuery({ queryKey: ["assigned-branches"], queryFn: merchantApi.assignedBranches });
  return { merchant, brands, branches };
}

export function MerchantDashboard() {
  const { merchant, brands, branches } = useMerchantData();
  return <><PageHeader eyebrow="Merchant workspace" title={merchant.data?.business_name || "Run your food business"} description="Manage every location from one operational view." action={merchant.data && <StatusPill value={merchant.data.status} />} /><State loading={merchant.isLoading} error={merchant.error} empty={!merchant.data}><div className="metric-grid"><Card><span>Brands</span><b>{brands.data?.length || 0}</b><small>Customer-facing concepts</small></Card><Card><span>Branches</span><b>{branches.data?.length || 0}</b><small>{branches.data?.filter((branch) => branch.is_active).length || 0} active</small></Card><Card><span>Verification</span><b>{merchant.data?.status || "Pending"}</b><small>Merchant lifecycle state</small></Card></div></State><Notice title="Route ownership is enforced by the backend">Lists may include only records the API returns. The UI never treats hidden controls as authorization.</Notice></>;
}

export function OnboardingPage() {
  const queryClient = useQueryClient();
  const { notify } = useToast();
  const merchant = useQuery({ queryKey: ["merchant"], queryFn: merchantApi.me, retry: false });
  const onboard = useMutation({ mutationFn: merchantApi.onboard, onSuccess: refresh(queryClient, "merchant") });
  const update = useMutation({ mutationFn: (values: Record<string, unknown>) => merchantApi.update(merchant.data!.id, values), onSuccess: refresh(queryClient, "merchant") });
  const submit = useMutation({ mutationFn: merchantApi.submit, onSuccess: (value) => { void queryClient.invalidateQueries({ queryKey: ["merchant"] }); notify(`Application ${value.status.toLowerCase().replace("_", " ")}.`); } });
  const fields = [{ name: "business_name", label: "Business name", required: true }, { name: "legal_entity_name", label: "Legal entity name", required: true }, { name: "fssai_license_number", label: "14-digit FSSAI number", required: true }, { name: "gstin", label: "GSTIN" }, { name: "bank_account_number", label: "Bank account number" }, { name: "bank_ifsc_code", label: "Bank IFSC" }];
  const guidance: Record<string, [string, string]> = {
    DRAFT: ["Application is editable", "Review the details below, then submit them for verification."],
    PENDING_VERIFICATION: ["Verification in progress", "The platform team is reviewing your KYC and payout details."],
    REJECTED: ["Changes requested", "Correct the details below and resubmit for verification."],
    APPROVED: ["Business verified", "Your operational workspace is ready to use."],
    SUSPENDED: ["Account suspended", "Contact platform support before changing operational data."],
  };
  const message = guidance[merchant.data?.status || "DRAFT"];
  return <><PageHeader eyebrow="Business identity" title={merchant.data ? "Merchant profile" : "Complete onboarding"} description="Regulatory and payout details are sent only to authenticated backend routes." action={merchant.data && <StatusPill value={merchant.data.status} />} />{merchant.data && <Notice title={message[0]}>{message[1]}</Notice>}{merchant.data && <Card><h2>Protected details</h2><div className="detail-grid"><span>GSTIN <MaskedValue value={merchant.data.gstin} /></span><span>FSSAI <MaskedValue value={merchant.data.fssai_license_number} /></span><span>Bank account <MaskedValue value={merchant.data.bank_account_number} /></span><span>IFSC <MaskedValue value={merchant.data.bank_ifsc_code} /></span></div></Card>}<Card><h2>{merchant.data ? "Edit application" : "Business and payout details"}</h2><SmartForm key={merchant.data?.updated_at || "new"} fields={fields.map((field) => ({ ...field, defaultValue: merchant.data?.[field.name as keyof typeof merchant.data] as string }))} submitLabel={merchant.data ? "Save changes" : "Create application"} busy={onboard.isPending || update.isPending} error={onboard.error || update.error} onSubmit={(values) => merchant.data ? update.mutate(values) : onboard.mutate(values)} />{merchant.data && ["DRAFT", "REJECTED"].includes(merchant.data.status) && <button className="primary" disabled={submit.isPending} onClick={() => submit.mutate()}>Submit for verification</button>}</Card></>;
}

export function MerchantBrandsPage() {
  const queryClient = useQueryClient();
  const { merchant, brands } = useMerchantData();
  const [removeId, setRemoveId] = useState("");
  const create = useMutation({ mutationFn: merchantApi.createBrand, onSuccess: refresh(queryClient, "merchant-brands") });
  const update = useMutation({ mutationFn: ({ id, values }: { id: string; values: Record<string, unknown> }) => merchantApi.updateBrand(id, values), onSuccess: refresh(queryClient, "merchant-brands") });
  const remove = useMutation({ mutationFn: merchantApi.deleteBrand, onSuccess: () => { setRemoveId(""); void queryClient.invalidateQueries({ queryKey: ["merchant-brands"] }); } });
  return <><PageHeader eyebrow="Catalog" title="Brands" description="Customer-facing identities owned by your merchant." /><div className="split-grid"><Card><h2>Create brand</h2><SmartForm fields={[{ name: "name", label: "Brand name", required: true }, { name: "description", label: "Description", type: "textarea" }, { name: "logo_url", label: "Logo URL", type: "url" }, { name: "banner_url", label: "Banner URL", type: "url" }, { name: "cuisine_types", label: "Cuisine types (comma separated)" }]} submitLabel="Create brand" busy={create.isPending} error={create.error} onSubmit={(values, form) => create.mutate({ ...values, merchant_id: merchant.data?.id, cuisine_types: String(values.cuisine_types || "").split(",").map((value) => value.trim()).filter(Boolean) }, { onSuccess: () => form.reset() })} /></Card><State loading={brands.isLoading} error={brands.error} empty={!brands.data?.length}><div className="stack">{brands.data?.map((brand) => <Card key={brand.id}><h3>{brand.name}</h3><SmartForm compact fields={[{ name: "name", label: "Brand name", required: true, defaultValue: brand.name }, { name: "description", label: "Description", type: "textarea", defaultValue: brand.description }, { name: "logo_url", label: "Logo URL", type: "url", defaultValue: brand.logo_url }, { name: "banner_url", label: "Banner URL", type: "url", defaultValue: brand.banner_url }, { name: "cuisine_types", label: "Cuisines", defaultValue: brand.cuisine_types?.join(", ") }]} submitLabel="Save brand" busy={update.isPending} onSubmit={(values) => update.mutate({ id: brand.id, values: { ...values, cuisine_types: String(values.cuisine_types || "").split(",").map((value) => value.trim()).filter(Boolean) } })} /><button className="danger" onClick={() => setRemoveId(brand.id)}>Delete brand</button></Card>)}</div></State></div><ConfirmDialog open={Boolean(removeId)} title="Delete brand?" description="The brand will be removed from customer discovery. This cannot be undone here." destructive confirmLabel="Delete brand" onCancel={() => setRemoveId("")} onConfirm={() => remove.mutate(removeId)} /></>;
}

export function MerchantBranchesPage() {
  const queryClient = useQueryClient();
  const { brands, branches } = useMerchantData();
  const create = useMutation({ mutationFn: merchantApi.createBranch, onSuccess: refresh(queryClient, "assigned-branches") });
  const [removeId, setRemoveId] = useState("");
  const update = useMutation({ mutationFn: ({ id, values }: { id: string; values: Record<string, unknown> }) => merchantApi.updateBranch(id, values), onSuccess: refresh(queryClient, "assigned-branches") });
  const remove = useMutation({ mutationFn: merchantApi.deleteBranch, onSuccess: () => { setRemoveId(""); void queryClient.invalidateQueries({ queryKey: ["assigned-branches"] }); } });
  const toggle = useMutation({ mutationFn: ({ id, active }: { id: string; active: boolean }) => merchantApi.branchStatus(id, active), onSuccess: refresh(queryClient, "merchant-branches") });
  return <><PageHeader eyebrow="Locations" title="Branches" description="Opening hours and active state feed the public storefront." /><div className="split-grid"><Card><h2>Add branch</h2><SmartForm fields={[{ name: "brand_id", label: "Brand", type: "select", required: true, options: brands.data?.map((brand) => ({ value: brand.id, label: brand.name })) }, { name: "name", label: "Branch name", required: true }, { name: "address_text", label: "Address", required: true }, { name: "opening_time", label: "Opening time", defaultValue: "08:00:00" }, { name: "closing_time", label: "Closing time", defaultValue: "23:00:00" }, { name: "is_active", label: "Open for discovery", type: "checkbox", defaultValue: true }]} submitLabel="Create branch" busy={create.isPending} error={create.error} onSubmit={(values, form) => create.mutate(values, { onSuccess: () => form.reset() })} /></Card><State loading={branches.isLoading} error={branches.error} empty={!branches.data?.length}><div className="stack">{branches.data?.map((branch) => <Card key={branch.id}><div className="card-heading"><div><h3>{branch.name}</h3><p>{branch.address_text}</p></div><StatusPill value={branch.is_active} /></div><SmartForm compact fields={[{ name: "name", label: "Name", defaultValue: branch.name, required: true }, { name: "address_text", label: "Address", defaultValue: branch.address_text, required: true }, { name: "opening_time", label: "Opening", defaultValue: branch.opening_time }, { name: "closing_time", label: "Closing", defaultValue: branch.closing_time }]} submitLabel="Save branch" busy={update.isPending} onSubmit={(values) => update.mutate({ id: branch.id, values })} /><div className="card-actions"><button onClick={() => toggle.mutate({ id: branch.id, active: !branch.is_active })}>{branch.is_active ? "Take offline" : "Bring online"}</button><button className="danger" onClick={() => setRemoveId(branch.id)}>Delete</button></div></Card>)}</div></State></div><ConfirmDialog open={Boolean(removeId)} title="Delete branch?" description="Its storefront and operational records will no longer be available." destructive confirmLabel="Delete branch" onCancel={() => setRemoveId("")} onConfirm={() => remove.mutate(removeId)} /></>;
}

export function KitchensPage() {
  const queryClient = useQueryClient();
  const { branches } = useMerchantData();
  const [branchId, setBranchId] = useState("");
  const [removeId, setRemoveId] = useState("");
  const kitchens = useQuery({ queryKey: ["kitchens", branchId], queryFn: () => merchantApi.kitchens(branchId), enabled: Boolean(branchId) });
  const create = useMutation({ mutationFn: (values: Record<string, unknown>) => merchantApi.createKitchen({ ...values, branch_id: branchId }), onSuccess: refresh(queryClient, "kitchens") });
  const update = useMutation({ mutationFn: ({ id, values }: { id: string; values: Record<string, unknown> }) => merchantApi.updateKitchen(id, values), onSuccess: refresh(queryClient, "kitchens") });
  const remove = useMutation({ mutationFn: merchantApi.deleteKitchen, onSuccess: () => { setRemoveId(""); void queryClient.invalidateQueries({ queryKey: ["kitchens"] }); } });
  return <><PageHeader eyebrow="Operations" title="Kitchen units" action={<BranchPicker branches={branches.data} value={branchId} onChange={setBranchId} />} />{!branchId ? <Notice title="Choose a branch">Kitchen units are always scoped to a branch.</Notice> : <div className="split-grid"><Card><h2>Add prep unit</h2><SmartForm fields={[{ name: "name", label: "Kitchen name", defaultValue: "Main Kitchen", required: true }, { name: "is_active", label: "Active", type: "checkbox", defaultValue: true }]} submitLabel="Create kitchen" busy={create.isPending} error={create.error} onSubmit={(values, form) => create.mutate(values, { onSuccess: () => form.reset() })} /></Card><State loading={kitchens.isLoading} error={kitchens.error} empty={!kitchens.data?.length}><div className="stack">{kitchens.data?.map((kitchen) => <Card key={kitchen.id}><div className="card-heading"><h3>{kitchen.name}</h3><StatusPill value={kitchen.is_active} /></div><SmartForm compact fields={[{ name: "name", label: "Kitchen name", defaultValue: kitchen.name, required: true }, { name: "is_active", label: "Active", type: "checkbox", defaultValue: kitchen.is_active }]} submitLabel="Save kitchen" busy={update.isPending} onSubmit={(values) => update.mutate({ id: kitchen.id, values })} /><button className="danger" onClick={() => setRemoveId(kitchen.id)}>Delete kitchen</button></Card>)}</div></State></div>}<ConfirmDialog open={Boolean(removeId)} title="Delete kitchen?" description="The preparation unit will be removed from branch operations." destructive confirmLabel="Delete kitchen" onCancel={() => setRemoveId("")} onConfirm={() => remove.mutate(removeId)} /></>;
}

export function MenuManagementPage() {
  const queryClient = useQueryClient();
  const { branches } = useMerchantData();
  const [branchId, setBranchId] = useState("");
  const [remove, setRemove] = useState<{ kind: "category" | "item"; id: string }>();
  const menu = useQuery({ queryKey: ["menu", branchId], queryFn: () => discoveryApi.menu(branchId), enabled: Boolean(branchId), retry: false });
  const createMenu = useMutation({ mutationFn: () => merchantApi.createMenu(branchId, { name: "Main Menu", is_active: true }), onSuccess: refresh(queryClient, "menu") });
  const category = useMutation({ mutationFn: (values: Record<string, unknown>) => merchantApi.createCategory(branchId, values), onSuccess: refresh(queryClient, "menu") });
  const item = useMutation({ mutationFn: (values: Record<string, unknown>) => merchantApi.createMenuItem(branchId, values), onSuccess: refresh(queryClient, "menu") });
  const updateCategory = useMutation({ mutationFn: ({ id, values }: { id: string; values: Record<string, unknown> }) => merchantApi.updateCategory(id, values), onSuccess: refresh(queryClient, "menu") });
  const updateItem = useMutation({ mutationFn: ({ id, values }: { id: string; values: Record<string, unknown> }) => merchantApi.updateMenuItem(id, values), onSuccess: refresh(queryClient, "menu") });
  const availability = useMutation({ mutationFn: ({ id, value }: { id: string; value: boolean }) => merchantApi.itemAvailability(id, value), onSuccess: refresh(queryClient, "menu") });
  const modifier = useMutation({ mutationFn: ({ id, values }: { id: string; values: Record<string, unknown> }) => merchantApi.createModifier(id, values), onSuccess: refresh(queryClient, "menu") });
  const removeMutation = useMutation({ mutationFn: () => remove?.kind === "category" ? merchantApi.deleteCategory(remove.id) : merchantApi.deleteMenuItem(remove!.id), onSuccess: () => { setRemove(undefined); void queryClient.invalidateQueries({ queryKey: ["menu"] }); } });
  return <><PageHeader eyebrow="Catalog" title="Menu, categories, items and modifiers" action={<BranchPicker branches={branches.data} value={branchId} onChange={setBranchId} />} />{branchId && !menu.data && !menu.isLoading && <Card><p>No menu is connected to this branch yet.</p><button className="product-button primary" onClick={() => createMenu.mutate()}>Create main menu</button></Card>}{menu.data && <><div className="split-grid"><Card><h2>Add category</h2><SmartForm fields={[{ name: "name", label: "Category name", required: true }, { name: "display_order", label: "Display order", type: "number", defaultValue: 0 }]} submitLabel="Add category" busy={category.isPending} error={category.error} onSubmit={(values, form) => category.mutate(values, { onSuccess: () => form.reset() })} /></Card><Card><h2>Add menu item</h2><SmartForm fields={[{ name: "category_id", label: "Category", type: "select", required: true, options: menu.data.categories.map((value) => ({ value: value.id, label: value.name })) }, { name: "name", label: "Item name", required: true }, { name: "description", label: "Description", type: "textarea" }, { name: "base_price", label: "Price", type: "number", required: true }, { name: "is_veg", label: "Vegetarian", type: "checkbox", defaultValue: true }, { name: "is_available", label: "Available", type: "checkbox", defaultValue: true }]} submitLabel="Add menu item" busy={item.isPending} error={item.error} onSubmit={(values, form) => item.mutate(values, { onSuccess: () => form.reset() })} /></Card></div><div className="stack">{menu.data.categories.map((cat) => <Card key={cat.id}><SmartForm compact fields={[{ name: "name", label: "Category", defaultValue: cat.name, required: true }, { name: "display_order", label: "Order", type: "number", defaultValue: cat.display_order }]} submitLabel="Save category" busy={updateCategory.isPending} onSubmit={(values) => updateCategory.mutate({ id: cat.id, values })} />{cat.items.map((entry) => <Card key={entry.id}><div className="card-heading"><div><h3>{entry.name}</h3><b>{money(entry.base_price)}</b></div><StatusPill value={entry.is_available} /></div><SmartForm compact fields={[{ name: "name", label: "Item name", defaultValue: entry.name, required: true }, { name: "description", label: "Description", defaultValue: entry.description }, { name: "base_price", label: "Price", type: "number", defaultValue: entry.base_price, required: true }, { name: "is_veg", label: "Vegetarian", type: "checkbox", defaultValue: entry.is_veg }]} submitLabel="Save item" busy={updateItem.isPending} onSubmit={(values) => updateItem.mutate({ id: entry.id, values })} /><SmartForm compact fields={[{ name: "name", label: "Modifier name", required: true }, { name: "price_delta", label: "Price change", type: "number", defaultValue: 0 }]} submitLabel="Add modifier" busy={modifier.isPending} onSubmit={(values, form) => modifier.mutate({ id: entry.id, values }, { onSuccess: () => form.reset() })} />{entry.modifiers.map((value) => <div className="line-item" key={value.id}><span>{value.name}</span><b>{money(value.price_delta)}</b></div>)}<div className="card-actions"><button onClick={() => availability.mutate({ id: entry.id, value: !entry.is_available })}>{entry.is_available ? "Mark unavailable" : "Mark available"}</button><button className="danger" onClick={() => setRemove({ kind: "item", id: entry.id })}>Delete item</button></div></Card>)}<button className="danger" onClick={() => setRemove({ kind: "category", id: cat.id })}>Delete category</button></Card>)}</div></>}<ConfirmDialog open={Boolean(remove)} title={`Delete ${remove?.kind || "record"}?`} description="This catalog change cannot be undone from this screen." destructive confirmLabel="Delete" onCancel={() => setRemove(undefined)} onConfirm={() => removeMutation.mutate()} /></>;
}

export function InventoryPage() {
  const queryClient = useQueryClient();
  const { branches } = useMerchantData();
  const [branchId, setBranchId] = useState("");
  const [logItemId, setLogItemId] = useState("");
  const inventory = useQuery({ queryKey: ["inventory", branchId], queryFn: () => merchantApi.inventory(branchId), enabled: Boolean(branchId) });
  const menu = useQuery({ queryKey: ["menu", branchId], queryFn: () => discoveryApi.menu(branchId), enabled: Boolean(branchId), retry: false });
  const logs = useQuery({ queryKey: ["inventory-logs", logItemId], queryFn: () => merchantApi.inventoryLogs(logItemId), enabled: Boolean(logItemId) });
  const create = useMutation({ mutationFn: (values: Record<string, unknown>) => merchantApi.createInventory(branchId, values), onSuccess: refresh(queryClient, "inventory") });
  const stock = useMutation({ mutationFn: ({ id, quantity }: { id: string; quantity: number }) => merchantApi.stock(id, { quantity, reason: "MERCHANT_RESTOCK" }), onSuccess: refresh(queryClient, "inventory") });
  const options = menu.data?.categories.flatMap((category) => category.items).map((item) => ({ value: item.id, label: item.name })) || [];
  return <><PageHeader eyebrow="Supply" title="Inventory and stock log" action={<BranchPicker branches={branches.data} value={branchId} onChange={setBranchId} />} />{branchId && <><Card><h2>Track menu item</h2><SmartForm compact fields={[{ name: "menu_item_id", label: "Menu item", type: "select", options, required: true }, { name: "initial_quantity", label: "Initial quantity", type: "number", defaultValue: 0 }]} submitLabel="Track item" busy={create.isPending} error={create.error} onSubmit={(values, form) => create.mutate(values, { onSuccess: () => form.reset() })} /></Card><State loading={inventory.isLoading} error={inventory.error} empty={!inventory.data?.length}><div className="stack">{inventory.data?.map((item) => <Card key={item.id}><div className="card-heading"><div><h3>{item.menu_item.name}</h3><small>Updated {dateTime(item.updated_at)}</small></div><div><b>{item.quantity} units</b> <StatusPill value={item.is_in_stock} /></div></div><SmartForm compact fields={[{ name: "quantity", label: "New quantity", type: "number", required: true, defaultValue: item.quantity }, { name: "reason", label: "Reason", defaultValue: "MERCHANT_RESTOCK", required: true }]} submitLabel="Update stock" busy={stock.isPending} onSubmit={(values) => stock.mutate({ id: item.id, quantity: Number(values.quantity) })} /><button onClick={() => setLogItemId(logItemId === item.id ? "" : item.id)}>{logItemId === item.id ? "Hide history" : "View stock history"}</button>{logItemId === item.id && <State loading={logs.isLoading} error={logs.error} empty={!logs.data?.items.length}><div className="audit-list">{logs.data?.items.map((log) => <div className="line-item" key={log.id}><span>{log.reason} · {dateTime(log.created_at)}</span><b>{log.previous_quantity} to {log.new_quantity}</b></div>)}</div></State>}</Card>)}</div></State></>}</>;
}

export function MerchantOrdersPage() {
  const queryClient = useQueryClient();
  const { branches } = useMerchantData();
  const [branchId, setBranchId] = useState("");
  const [status, setStatus] = useState("");
  const orders = useQuery({ queryKey: ["merchant-orders", branchId, status], queryFn: () => merchantApi.orders(branchId, status || undefined), enabled: Boolean(branchId), refetchInterval: 15000 });
  const transition = useMutation({ mutationFn: ({ id, state }: { id: string; state: string }) => merchantApi.orderStatus(id, state), onSuccess: refresh(queryClient, "merchant-orders") });
  return <><PageHeader eyebrow="Fulfilment" title="Branch orders" action={<div className="picker-row"><BranchPicker branches={branches.data} value={branchId} onChange={setBranchId} /><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option>{["PLACED", "ACCEPTED", "PREPARING", "READY", "COMPLETED", "CANCELLED"].map((value) => <option key={value}>{value}</option>)}</select></div>} /><State loading={orders.isLoading} error={orders.error} empty={!orders.data?.length}><div className="stack">{orders.data?.map((order) => <Card key={order.id}><div className="card-heading"><div><h3>Order {order.id.slice(0, 8)}</h3><p>{order.items.map((item) => `${item.quantity}× ${item.item_name_snapshot}`).join(", ")}</p><small>{dateTime(order.created_at)} · {money(order.total_amount)}</small></div><StatusPill value={order.status} /></div><div className="card-actions"><Link className="product-button" to={order.id}>View detail</Link>{(orderTransitions[order.status] || []).map((state) => <button disabled={transition.isPending} key={state} onClick={() => transition.mutate({ id: order.id, state })}>{state === "CANCELLED" ? "Cancel" : `Mark ${state.toLowerCase()}`}</button>)}</div></Card>)}</div></State></>;
}

export function MerchantReviewsPage() {
  const queryClient = useQueryClient();
  const { branches } = useMerchantData();
  const [branchId, setBranchId] = useState("");
  const reviews = useQuery({ queryKey: ["reviews", branchId], queryFn: () => merchantApi.reviews(branchId), enabled: Boolean(branchId) });
  const reply = useMutation({ mutationFn: ({ id, text }: { id: string; text: string }) => merchantApi.reply(id, text), onSuccess: refresh(queryClient, "reviews") });
  return <><PageHeader eyebrow="Reputation" title="Guest reviews" action={<BranchPicker branches={branches.data} value={branchId} onChange={setBranchId} />} /><State loading={reviews.isLoading} error={reviews.error} empty={!reviews.data?.length}><div className="stack">{reviews.data?.map((review) => <Card key={review.id}><div className="card-heading"><b>{review.rating} / 5</b><small>{dateTime(review.created_at)}</small></div><p>{review.comment || "No comment."}</p>{review.merchant_reply ? <Notice title="Your reply">{review.merchant_reply}</Notice> : <SmartForm compact fields={[{ name: "reply", label: "Public reply", required: true }]} submitLabel="Reply" busy={reply.isPending} onSubmit={(values) => reply.mutate({ id: review.id, text: String(values.reply) })} />}</Card>)}</div></State></>;
}

export function MerchantCouponsPage() {
  const queryClient = useQueryClient();
  const { branches } = useMerchantData();
  const [branchId, setBranchId] = useState("");
  const [redemptionCoupon, setRedemptionCoupon] = useState("");
  const [removeId, setRemoveId] = useState("");
  const coupons = useQuery({ queryKey: ["merchant-coupons", branchId], queryFn: () => merchantApi.coupons(branchId), enabled: Boolean(branchId) });
  const redemptions = useQuery({ queryKey: ["coupon-redemptions", redemptionCoupon], queryFn: () => merchantApi.couponRedemptions(redemptionCoupon), enabled: Boolean(redemptionCoupon) });
  const create = useMutation({ mutationFn: merchantApi.createCoupon, onSuccess: refresh(queryClient, "merchant-coupons") });
  const update = useMutation({ mutationFn: ({ id, values }: { id: string; values: Record<string, unknown> }) => merchantApi.updateCoupon(id, values), onSuccess: refresh(queryClient, "merchant-coupons") });
  const toggle = useMutation({ mutationFn: ({ id, active }: { id: string; active: boolean }) => merchantApi.toggleCoupon(id, active), onSuccess: refresh(queryClient, "merchant-coupons") });
  const remove = useMutation({ mutationFn: merchantApi.deleteCoupon, onSuccess: () => { setRemoveId(""); void queryClient.invalidateQueries({ queryKey: ["merchant-coupons"] }); } });
  const now = new Date();
  const later = new Date(now.getTime() + 30 * 86400000);
  return <><PageHeader eyebrow="Promotions" title="Branch coupons" description="Offers and redemption history are restricted to assigned branches." action={<BranchPicker branches={branches.data} value={branchId} onChange={setBranchId} />} />{branchId && <div className="split-grid"><Card><h2>Create branch coupon</h2><SmartForm fields={[{ name: "code", label: "Coupon code", required: true }, { name: "discount_type", label: "Discount type", type: "select", options: ["PERCENTAGE", "FLAT"], required: true }, { name: "discount_value", label: "Discount value", type: "number", required: true }, { name: "min_order_amount", label: "Minimum order", type: "number", defaultValue: 0 }, { name: "max_redemptions_per_user", label: "Uses per customer", type: "number", defaultValue: 1 }, { name: "valid_from", label: "Valid from", type: "datetime-local", defaultValue: now.toISOString().slice(0, 16), required: true }, { name: "valid_until", label: "Valid until", type: "datetime-local", defaultValue: later.toISOString().slice(0, 16), required: true }]} submitLabel="Create coupon" busy={create.isPending} error={create.error} onSubmit={(values, form) => create.mutate({ ...values, branch_id: branchId }, { onSuccess: () => form.reset() })} /></Card><State loading={coupons.isLoading} error={coupons.error} empty={!coupons.data?.length}><div className="stack">{coupons.data?.map((coupon) => <Card key={coupon.id}><div className="card-heading"><div><h3>{coupon.code}</h3><small>{coupon.discount_type} · expires {dateTime(coupon.valid_until)}</small></div><StatusPill value={coupon.is_active} /></div><SmartForm compact fields={[{ name: "discount_value", label: "Discount value", type: "number", defaultValue: coupon.discount_value, required: true }, { name: "min_order_amount", label: "Minimum order", type: "number", defaultValue: coupon.min_order_amount }]} submitLabel="Save coupon" busy={update.isPending} onSubmit={(values) => update.mutate({ id: coupon.id, values })} /><div className="card-actions"><button onClick={() => toggle.mutate({ id: coupon.id, active: !coupon.is_active })}>{coupon.is_active ? "Deactivate" : "Activate"}</button><button onClick={() => setRedemptionCoupon(redemptionCoupon === coupon.id ? "" : coupon.id)}>Redemptions</button><button className="danger" onClick={() => setRemoveId(coupon.id)}>Delete</button></div>{redemptionCoupon === coupon.id && <State loading={redemptions.isLoading} error={redemptions.error} empty={!redemptions.data?.length}><div className="audit-list">{redemptions.data?.map((row) => <div className="line-item" key={String(row.id)}><span>Order {String(row.order_id).slice(0, 8)} · {dateTime(String(row.created_at))}</span><b>{money(Number(row.discount_amount_applied))}</b></div>)}</div></State>}</Card>)}</div></State></div>}<ConfirmDialog open={Boolean(removeId)} title="Delete coupon?" description="The offer will no longer be available to customers." destructive confirmLabel="Delete coupon" onCancel={() => setRemoveId("")} onConfirm={() => remove.mutate(removeId)} /></>;
}

export function SubscriptionPage() {
  const queryClient = useQueryClient();
  const subscription = useQuery({ queryKey: ["subscription"], queryFn: merchantApi.subscription, retry: false });
  const invoices = useQuery({ queryKey: ["invoices"], queryFn: merchantApi.invoices });
  const commissions = useQuery({ queryKey: ["commissions"], queryFn: merchantApi.commissions });
  const subscribe = useMutation({ mutationFn: merchantApi.subscribe, onSuccess: refresh(queryClient, "subscription") });
  const renew = useMutation({ mutationFn: merchantApi.renew, onSuccess: refresh(queryClient, "subscription") });
  return <><PageHeader eyebrow="Plan and billing" title="Subscription, invoices and commissions" /><div className="split-grid"><Card><h2>{subscription.data ? "Current subscription" : "Choose a plan"}</h2>{subscription.data ? <><div className="detail-grid"><span>Plan <b>{subscription.data.plan_tier}</b></span><span>Billing <b>{subscription.data.billing_cycle}</b></span><span>Status <StatusPill value={subscription.data.status} /></span><span>Commission <b>{subscription.data.commission_rate_percentage}%</b></span><span>Branch allowance <b>{subscription.data.max_branches}</b></span><span>Renews <b>{dateTime(subscription.data.valid_until)}</b></span></div><SmartForm compact fields={[{ name: "plan_tier", label: "Plan tier", type: "select", options: ["BASIC", "PROFESSIONAL", "ENTERPRISE"], defaultValue: subscription.data.plan_tier }, { name: "duration_months", label: "Months", type: "number", defaultValue: 1 }]} submitLabel="Renew subscription" busy={renew.isPending} error={renew.error} onSubmit={(values) => renew.mutate(values)} /></> : <SmartForm fields={[{ name: "plan_tier", label: "Plan tier", type: "select", required: true, options: ["BASIC", "PROFESSIONAL", "ENTERPRISE"] }, { name: "billing_cycle", label: "Billing cycle", type: "select", required: true, options: ["MONTHLY", "ANNUAL"] }]} submitLabel="Start subscription" busy={subscribe.isPending} error={subscribe.error} onSubmit={(values) => subscribe.mutate(values)} />}</Card><Card><h2>Invoices</h2><State loading={invoices.isLoading} error={invoices.error} empty={!invoices.data?.length}>{invoices.data?.map((invoice) => <div className="line-item" key={String(invoice.invoice_number)}><span><b>{String(invoice.invoice_number)}</b><small>{String(invoice.plan_tier)} · {dateTime(String(invoice.issued_at))}</small></span><b>{money(Number(invoice.amount))}</b></div>)}</State></Card></div><Card><h2>Commission ledger</h2><State loading={commissions.isLoading} error={commissions.error} empty={!commissions.data?.length}>{commissions.data?.map((row) => <div className="line-item" key={String(row.id)}><span>Order {String(row.order_id).slice(0, 8)} · {dateTime(String(row.created_at))}</span><b>{money(Number(row.commission_amount))}</b></div>)}</State></Card></>;
}

export function MerchantPaymentsPage() {
  const queryClient = useQueryClient();
  const { branches } = useMerchantData();
  const [branchId, setBranchId] = useState("");
  const [page, setPage] = useState(1);
  const [refundPayment, setRefundPayment] = useState<Payment>();
  const [refundValues, setRefundValues] = useState<Record<string, unknown>>();
  const payments = useQuery({ queryKey: ["payments", branchId, page], queryFn: () => merchantApi.payments(branchId, page), enabled: Boolean(branchId) });
  const refund = useMutation({ mutationFn: () => merchantApi.refund(refundPayment!.id, refundValues), onSuccess: () => { setRefundPayment(undefined); setRefundValues(undefined); void queryClient.invalidateQueries({ queryKey: ["payments", branchId] }); } });
  return <><PageHeader eyebrow="Transactions" title="Payments, refunds and history" action={<BranchPicker branches={branches.data} value={branchId} onChange={(value) => { setBranchId(value); setPage(1); }} />} /><State loading={payments.isLoading} error={payments.error} empty={!payments.data?.items.length}><div className="stack">{payments.data?.items.map((payment) => <Card key={payment.id}><div className="card-heading"><div><h3>Order {payment.order_id.slice(0, 8)}</h3><small>{payment.provider} · {dateTime(payment.created_at)}</small></div><b>{money(payment.amount)}</b></div>{payment.transactions.map((tx) => <div className="line-item" key={tx.id}><span>{tx.transaction_type} · {dateTime(tx.created_at)}</span><StatusPill value={tx.status} /></div>)}<SmartForm compact fields={[{ name: "amount", label: "Refund amount", type: "number", required: true }, { name: "reason", label: "Reason", defaultValue: "ORDER_CANCELLED", required: true }]} submitLabel="Prepare refund" busy={refund.isPending} error={refund.error} onSubmit={(values) => { setRefundPayment(payment); setRefundValues(values); }} /></Card>)}</div></State>{payments.data && <PaginationControls page={page} pages={payments.data.pages} total={payments.data.total} onPageChange={setPage} />}<ConfirmDialog open={Boolean(refundPayment)} title="Confirm financial refund" description={`Issue ${money(Number(refundValues?.amount))} against order ${refundPayment?.order_id.slice(0, 8)}? This action is recorded.`} destructive confirmLabel="Issue refund" onCancel={() => { setRefundPayment(undefined); setRefundValues(undefined); }} onConfirm={() => refund.mutate()} /></>;
}

export function MerchantStaffPage() {
  const queryClient = useQueryClient();
  const { branches } = useMerchantData();
  const [removeId, setRemoveId] = useState("");
  const staff = useQuery({ queryKey: ["merchant-staff"], queryFn: merchantApi.staff });
  const invite = useMutation({ mutationFn: merchantApi.inviteStaff, onSuccess: refresh(queryClient, "merchant-staff") });
  const update = useMutation({ mutationFn: ({ id, values }: { id: string; values: Record<string, unknown> }) => merchantApi.updateStaff(id, values), onSuccess: refresh(queryClient, "merchant-staff") });
  const remove = useMutation({ mutationFn: merchantApi.removeStaff, onSuccess: () => { setRemoveId(""); void queryClient.invalidateQueries({ queryKey: ["merchant-staff"] }); } });
  const branchOptions = branches.data?.map((branch) => ({ value: branch.id, label: branch.name })) || [];
  return <><PageHeader eyebrow="Team access" title="Staff invitations and assignments" description="Invite operational roles and assign only the branches they should access." /><div className="split-grid"><Card><h2>Invite staff member</h2><SmartForm fields={[{ name: "email", label: "Email", type: "email", required: true }, { name: "role", label: "Role", type: "select", options: ["BranchManager", "KitchenStaff"], required: true }, { name: "branch_id", label: "Assigned branch", type: "select", options: branchOptions, required: true }]} submitLabel="Send invitation" busy={invite.isPending} error={invite.error} onSubmit={(values, form) => { const { branch_id, ...rest } = values; invite.mutate({ ...rest, branch_ids: [branch_id] }, { onSuccess: () => form.reset() }); }} />{invite.data?.preview_token && <Notice title="Development invitation link"><a href={`/auth/invitations/accept?token=${encodeURIComponent(invite.data.preview_token)}`}>Accept invitation for {invite.data.email}</a></Notice>}</Card><State loading={staff.isLoading} error={staff.error} empty={!staff.data?.length}><div className="stack">{staff.data?.map((member) => <Card key={member.id}><div className="card-heading"><div><h3>{member.email}</h3><small>{member.role} · {member.branch_ids.length} assigned branch(es)</small></div><StatusPill value={member.is_active} /></div><SmartForm compact fields={[{ name: "role", label: "Role", type: "select", options: ["BranchManager", "KitchenStaff"], defaultValue: member.role }, { name: "branch_id", label: "Branch", type: "select", options: branchOptions, defaultValue: member.branch_ids[0] }, { name: "is_active", label: "Active", type: "checkbox", defaultValue: member.is_active }]} submitLabel="Save assignment" busy={update.isPending} onSubmit={(values) => { const { branch_id, ...rest } = values; update.mutate({ id: member.id, values: { ...rest, branch_ids: branch_id ? [branch_id] : [] } }); }} /><button className="danger" onClick={() => setRemoveId(member.id)}>Remove access</button></Card>)}</div></State></div><ConfirmDialog open={Boolean(removeId)} title="Remove staff access?" description="The staff member will immediately lose all merchant and branch assignments." destructive confirmLabel="Remove staff" onCancel={() => setRemoveId("")} onConfirm={() => remove.mutate(removeId)} /></>;
}

export function ReportsPage() {
  const { branches } = useMerchantData();
  const [branchId, setBranchId] = useState("");
  const sales = useQuery({ queryKey: ["sales-report", branchId], queryFn: () => merchantApi.salesReport(branchId), enabled: Boolean(branchId) });
  const performance = useQuery({ queryKey: ["branch-report", branchId], queryFn: () => merchantApi.branchReport(branchId), enabled: Boolean(branchId) });
  const payments = useQuery({ queryKey: ["payment-report", branchId], queryFn: () => merchantApi.paymentReport(branchId), enabled: Boolean(branchId) });
  const values = sales.data && performance.data && payments.data ? [
    ["Orders", sales.data.order_count], ["Gross sales", money(sales.data.gross_sales)],
    ["Net sales", money(sales.data.net_sales)], ["Average order", money(sales.data.average_order_value)],
    ["Completed", performance.data.completed_orders], ["Cancelled", performance.data.cancelled_orders],
    ["Payments", payments.data.payment_count], ["Refunds", money(payments.data.refund_amount)],
  ] : [];
  return <><PageHeader eyebrow="Performance" title="Branch reports" action={<BranchPicker branches={branches.data} value={branchId} onChange={setBranchId} />} />{!branchId ? <Notice title="Choose an assigned branch">Reports are always scoped by backend assignment.</Notice> : <State loading={sales.isLoading || performance.isLoading || payments.isLoading} error={sales.error || performance.error || payments.error} empty={!values.length}><div className="metric-grid">{values.map(([label, value]) => <Card key={String(label)}><span>{label}</span><b>{value}</b></Card>)}</div></State>}</>;
}

export function MerchantOrderDetailPage() {
  const { orderId = "" } = useParams();
  const queryClient = useQueryClient();
  const order = useQuery({ queryKey: ["merchant-order", orderId], queryFn: () => merchantApi.order(orderId), enabled: Boolean(orderId) });
  const transition = useMutation({ mutationFn: (status: string) => merchantApi.orderStatus(orderId, status), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["merchant-order", orderId] }) });
  return <><PageHeader eyebrow="Order detail" title={`Order ${orderId.slice(0, 8)}`} action={<Link className="product-button" to="..">Back to orders</Link>} /><State loading={order.isLoading} error={order.error} empty={!order.data}>{order.data && <div className="split-grid"><Card><div className="card-heading"><h2>Items</h2><StatusPill value={order.data.status} /></div>{order.data.items.map((item) => <div className="line-item" key={item.id}><span>{item.quantity} × {item.item_name_snapshot}</span><b>{money(item.quantity * item.unit_price_snapshot)}</b></div>)}<div className="line-item"><b>Total</b><b>{money(order.data.total_amount)}</b></div><OrderTransitionControls status={order.data.status} busy={transition.isPending} onTransition={(value) => transition.mutate(value)} /></Card><Card><h2>Status timeline</h2><OrderTimeline order={order.data} />{order.data.cancellation_reason && <Notice title="Cancellation reason">{order.data.cancellation_reason}</Notice>}</Card></div>}</State></>;
}

export function BranchManagerDashboard() {
  const branches = useQuery({ queryKey: ["assigned-branches"], queryFn: merchantApi.assignedBranches });
  return <><PageHeader eyebrow="Branch manager" title="Assigned operations" description="Every control and report below is limited to your active backend assignments." /><State loading={branches.isLoading} error={branches.error} empty={!branches.data?.length}><div className="metric-grid"><Card><span>Assigned branches</span><b>{branches.data?.length || 0}</b></Card><Card><span>Online branches</span><b>{branches.data?.filter((branch) => branch.is_active).length || 0}</b></Card></div></State></>;
}

export function BranchSettingsPage() {
  const queryClient = useQueryClient();
  const branches = useQuery({ queryKey: ["assigned-branches"], queryFn: merchantApi.assignedBranches });
  const update = useMutation({ mutationFn: ({ id, values }: { id: string; values: Record<string, unknown> }) => merchantApi.updateBranch(id, values), onSuccess: refresh(queryClient, "assigned-branches") });
  const toggle = useMutation({ mutationFn: ({ id, active }: { id: string; active: boolean }) => merchantApi.branchStatus(id, active), onSuccess: refresh(queryClient, "assigned-branches") });
  return <><PageHeader eyebrow="Assigned locations" title="Branch settings" /><State loading={branches.isLoading} error={branches.error} empty={!branches.data?.length}><div className="stack">{branches.data?.map((branch) => <Card key={branch.id}><div className="card-heading"><div><h3>{branch.name}</h3><p>{branch.address_text}</p></div><StatusPill value={branch.is_active} /></div><SmartForm compact fields={[{ name: "name", label: "Branch name", defaultValue: branch.name, required: true }, { name: "address_text", label: "Address", defaultValue: branch.address_text, required: true }, { name: "opening_time", label: "Opening", defaultValue: branch.opening_time }, { name: "closing_time", label: "Closing", defaultValue: branch.closing_time }]} submitLabel="Save settings" busy={update.isPending} onSubmit={(values) => update.mutate({ id: branch.id, values })} /><button onClick={() => toggle.mutate({ id: branch.id, active: !branch.is_active })}>{branch.is_active ? "Take offline" : "Bring online"}</button></Card>)}</div></State></>;
}
