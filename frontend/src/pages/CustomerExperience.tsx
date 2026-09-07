import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { customerApi, discoveryApi } from "../api/modules";
import type { Address, CheckoutQuote, NotificationPreferences, PaymentIntent } from "../api/types";
import {
  addressLabel, canCheckout, checkoutIssueSummary, isMockProviderOrder, paymentState,
} from "../customerExperience";
import { useToast } from "../components/toastContext";
import {
  ApiErrorPanel, Card, ConfirmDialog, dateTime, money, Notice, OrderTimeline, PageHeader,
  PaginationControls, SmartForm, State, StatusPill,
} from "../components/ui";

const invalidate = (client: ReturnType<typeof useQueryClient>, key: string) =>
  () => client.invalidateQueries({ queryKey: [key] });

export function CustomerDashboard() {
  const orders = useQuery({ queryKey: ["orders"], queryFn: () => customerApi.orders() });
  const cart = useQuery({ queryKey: ["cart"], queryFn: customerApi.cart, retry: false });
  return <><PageHeader eyebrow="Customer workspace" title="Good food starts here" description="Your active cart and latest orders at a glance." /><State loading={orders.isLoading || cart.isLoading} error={orders.error} empty={false}><div className="metric-grid"><Card><span>Cart total</span><b>{money(cart.data?.subtotal)}</b><small>{cart.data?.total_items || 0} items</small></Card><Card><span>Total orders</span><b>{orders.data?.length || 0}</b><small>Across all branches</small></Card><Card><span>Latest status</span><b>{orders.data?.[0]?.status || "No orders"}</b><small>{orders.data?.[0] ? dateTime(orders.data[0].updated_at) : "Start discovering"}</small></Card></div><div className="dashboard-actions"><Link className="product-button primary" to="/discover">Browse kitchens</Link><Link className="product-button" to="/customer/cart">Open cart</Link></div></State></>;
}

export function ProfilePage() {
  const client = useQueryClient();
  const { notify } = useToast();
  const query = useQuery({ queryKey: ["profile"], queryFn: customerApi.profile });
  const mutation = useMutation({ mutationFn: customerApi.updateProfile, onSuccess: () => { void invalidate(client, "profile")(); notify("Profile updated."); } });
  return <><PageHeader eyebrow="Account" title="Your profile" description="Keep contact information current for order updates." /><State loading={query.isLoading} error={query.error} empty={false}><Card><SmartForm key={query.data?.id} fields={[{ name: "full_name", label: "Full name", required: true, defaultValue: query.data?.full_name }, { name: "phone_number", label: "Phone number", defaultValue: query.data?.phone_number }]} submitLabel="Save profile" busy={mutation.isPending} error={mutation.error} onSubmit={(values) => mutation.mutate(values)} /></Card><div className="dashboard-actions"><Link className="product-button" to="/account/security">Password and sessions</Link></div></State></>;
}

export function AddressesPage() {
  const client = useQueryClient();
  const { notify } = useToast();
  const [editing, setEditing] = useState<Address>();
  const [deleting, setDeleting] = useState<Address>();
  const query = useQuery({ queryKey: ["addresses"], queryFn: customerApi.addresses });
  const refresh = () => void client.invalidateQueries({ queryKey: ["addresses"] });
  const save = useMutation({ mutationFn: (values: Record<string, unknown>) =>
    editing ? customerApi.updateAddress(editing.id, values) : customerApi.addAddress(values),
  onSuccess: () => { refresh(); setEditing(undefined); notify("Address saved."); } });
  const primary = useMutation({ mutationFn: customerApi.primaryAddress, onSuccess: () => { refresh(); notify("Primary address updated."); } });
  const remove = useMutation({ mutationFn: customerApi.deleteAddress, onSuccess: () => { refresh(); setDeleting(undefined); notify("Address deleted."); } });
  return <><PageHeader eyebrow="Delivery" title="Saved addresses" description="Use friendly labels for quicker checkout." /><div className="split-grid"><Card><h2>{editing ? "Edit address" : "Add an address"}</h2><SmartForm key={editing?.id || "new"} fields={[{ name: "address_line", label: "Address line", required: true, defaultValue: editing?.address_line }, { name: "building_name", label: "Building or label", defaultValue: editing?.building_name }, { name: "campus_zone", label: "Campus zone", required: true, defaultValue: editing?.campus_zone }, { name: "is_primary", label: "Set as primary", type: "checkbox", defaultValue: editing?.is_primary }]} submitLabel={editing ? "Save changes" : "Add address"} busy={save.isPending} error={save.error} onSubmit={(values, form) => save.mutate(values, { onSuccess: () => form.reset() })} />{editing && <button onClick={() => setEditing(undefined)}>Cancel editing</button>}</Card><State loading={query.isLoading} error={query.error} empty={!query.data?.length}><div className="stack">{query.data?.map((address) => <Card key={address.id}><div className="card-heading"><div><h3>{address.building_name || address.campus_zone}</h3><p>{address.address_line}</p><small>{address.campus_zone}</small></div>{address.is_primary && <StatusPill value="Primary" />}</div><div className="card-actions"><button onClick={() => setEditing(address)}>Edit</button>{!address.is_primary && <button onClick={() => primary.mutate(address.id)}>Make primary</button>}<button className="danger" onClick={() => setDeleting(address)}>Delete</button></div></Card>)}</div></State></div><ConfirmDialog open={Boolean(deleting)} title="Delete this address?" description={deleting ? addressLabel(deleting) : ""} confirmLabel="Delete address" destructive onCancel={() => setDeleting(undefined)} onConfirm={() => deleting && remove.mutate(deleting.id)} /></>;
}

export function FavoritesPage() {
  const client = useQueryClient();
  const { notify } = useToast();
  const favorites = useQuery({ queryKey: ["favorites"], queryFn: customerApi.favorites });
  const branches = useQuery({ queryKey: ["branches"], queryFn: () => discoveryApi.branches() });
  const remove = useMutation({ mutationFn: customerApi.deleteFavorite, onSuccess: () => { void invalidate(client, "favorites")(); notify("Removed from favorites."); } });
  return <><PageHeader eyebrow="Saved" title="Favorite branches" description="Your shortcut back to familiar menus." /><State loading={favorites.isLoading || branches.isLoading} error={favorites.error || branches.error} empty={!favorites.data?.length}><div className="stack">{favorites.data?.map((favorite) => { const branch = branches.data?.find((candidate) => candidate.id === favorite.branch_id); return <Card key={favorite.id}><div className="card-heading"><div><h3>{branch?.name || "Saved location"}</h3><p>{branch?.address_text || "Location details unavailable"}</p></div><StatusPill value={branch?.is_active ?? false} /></div><div className="card-actions"><Link to={`/branches/${favorite.branch_id}`}>View menu</Link><button className="danger" onClick={() => remove.mutate(favorite.branch_id)}>Remove</button></div></Card>; })}</div></State></>;
}

export function CartPage() {
  const client = useQueryClient();
  const { notify } = useToast();
  const [clearOpen, setClearOpen] = useState(false);
  const [removing, setRemoving] = useState<string>();
  const query = useQuery({ queryKey: ["cart"], queryFn: customerApi.cart, retry: false });
  const validation = useQuery({ queryKey: ["cart-validation"], queryFn: customerApi.validateCart, enabled: Boolean(query.data?.items.length) });
  const refresh = () => { void client.invalidateQueries({ queryKey: ["cart"] }); void client.invalidateQueries({ queryKey: ["cart-validation"] }); };
  const update = useMutation({ mutationFn: ({ id, quantity }: { id: string; quantity: number }) => customerApi.updateCartItem(id, { quantity }), onSuccess: refresh });
  const remove = useMutation({ mutationFn: customerApi.removeCartItem, onSuccess: () => { refresh(); setRemoving(undefined); notify("Item removed."); } });
  const clear = useMutation({ mutationFn: customerApi.clearCart, onSuccess: () => { refresh(); setClearOpen(false); notify("Cart cleared."); } });
  return <><PageHeader eyebrow="Your basket" title="Cart" description="Availability and pricing are checked live." action={query.data?.items.length ? <button className="danger" onClick={() => setClearOpen(true)}>Clear cart</button> : undefined} /><State loading={query.isLoading} error={query.error} empty={!query.data?.items.length}>{query.data && <div className="cart-layout"><div className="stack">{query.data.items.map((item) => <Card className={`cart-line ${item.is_available === false ? "unavailable" : ""}`} key={item.id}><div><h3>{item.menu_item_name || "Menu item"}</h3><p>{item.is_available === false ? "Currently unavailable" : `${money(item.unit_price)} each`}</p>{item.selected_modifiers?.map((modifier) => <small key={modifier.id || modifier.name}>{modifier.name}{modifier.price_delta ? ` (+${money(modifier.price_delta)})` : ""}</small>)}</div><div className="quantity"><button aria-label={`Decrease ${item.menu_item_name}`} disabled={item.quantity <= 1} onClick={() => update.mutate({ id: item.id, quantity: item.quantity - 1 })}>−</button><b>{item.quantity}</b><button aria-label={`Increase ${item.menu_item_name}`} onClick={() => update.mutate({ id: item.id, quantity: item.quantity + 1 })}>+</button></div><b>{money(item.subtotal)}</b><button className="danger" onClick={() => setRemoving(item.id)}>Remove</button></Card>)}{validation.data && !validation.data.is_valid && <section className="issue-panel" role="alert"><h2>Cart needs attention</h2>{validation.data.issues.map((issue) => <p key={`${issue.code}-${issue.item_id}`}>{issue.message}</p>)}</section>}</div><Card className="cart-summary"><span>Items <b>{query.data.total_items}</b></span><span>Subtotal <b>{money(query.data.subtotal)}</b></span><StatusPill value={validation.data?.is_valid ? "Validated" : "Checking"} /><Link aria-disabled={!validation.data?.is_valid} className={`product-button primary ${!validation.data?.is_valid ? "disabled" : ""}`} to={validation.data?.is_valid ? "/customer/checkout" : "#"}>Continue to checkout</Link></Card></div>}</State><ConfirmDialog open={clearOpen} title="Clear your cart?" description="All items and selected extras will be removed." confirmLabel="Clear cart" destructive onCancel={() => setClearOpen(false)} onConfirm={() => clear.mutate()} /><ConfirmDialog open={Boolean(removing)} title="Remove this item?" description="You can add it again from the branch menu." confirmLabel="Remove item" destructive onCancel={() => setRemoving(undefined)} onConfirm={() => removing && remove.mutate(removing)} /></>;
}

function QuoteCard({ quote, onConfirm, busy }: { quote: CheckoutQuote; onConfirm: () => void; busy: boolean }) {
  const expired = Boolean(quote.quote_expires_at && new Date(quote.quote_expires_at) <= new Date());
  return <Card className="checkout-summary"><div className="card-heading"><h2>Order quote</h2><StatusPill value={expired ? "Expired" : quote.is_valid ? "Ready" : "Action needed"} /></div>{quote.issues.length > 0 && <section className="issue-panel" role="alert"><h3>Resolve before ordering</h3>{checkoutIssueSummary(quote).map((issue) => <div key={issue.code}><b>{issue.title}</b><p>{issue.message}</p></div>)}</section>}{quote.items.map((item) => <div className="line-item" key={item.menu_item_id}><span>{item.quantity} × {item.name}{!item.is_available && " (unavailable)"}</span><b>{money(item.subtotal)}</b></div>)}<div className="financial-lines"><span>Subtotal <b>{money(quote.subtotal)}</b></span><span>Discount <b>−{money(quote.discount_amount)}</b></span><span>Tax <b>{money(quote.tax_amount)}</b></span><span>Delivery <b>{money(quote.delivery_fee)}</b></span><span className="total">Total <b>{money(quote.final_payable_amount)}</b></span></div>{quote.coupon_code && <Notice title="Coupon applied">{quote.coupon_code} saved you {money(quote.discount_amount)}.</Notice>}<small>{quote.quote_expires_at ? `Quote expires ${dateTime(quote.quote_expires_at)}` : "No active quote was created."}</small><button className="primary" disabled={!quote.is_valid || expired || !quote.quote_id || busy} onClick={onConfirm}>{busy ? "Placing order..." : "Confirm order"}</button></Card>;
}

export function CheckoutPage() {
  const navigate = useNavigate();
  const [input, setInput] = useState({ address: "", coupon: "" });
  const cart = useQuery({ queryKey: ["cart"], queryFn: customerApi.cart });
  const addresses = useQuery({ queryKey: ["addresses"], queryFn: customerApi.addresses });
  const validation = useQuery({ queryKey: ["cart-validation"], queryFn: customerApi.validateCart, enabled: Boolean(cart.data?.items.length) });
  useEffect(() => { const primary = addresses.data?.find((address) => address.is_primary); if (primary && !input.address) setInput((current) => ({ ...current, address: primary.id })); }, [addresses.data, input.address]);
  const quote = useMutation({ mutationFn: () => customerApi.checkout({ cart_id: cart.data?.id, coupon_code: input.coupon || undefined, delivery_address_id: input.address }) });
  const create = useMutation({ mutationFn: () => {
    if (!quote.data?.quote_id) throw new Error("Refresh the quote before ordering.");
    return customerApi.createOrder({ quote_id: quote.data.quote_id });
  }, onSuccess: (order) => navigate(`/customer/payments/new?order=${order.id}`, { replace: true }) });
  if (!cart.isLoading && !cart.data?.items.length) return <><PageHeader title="Checkout" /><Notice title="Your cart is empty">Add food before starting checkout.</Notice><Link className="product-button primary" to="/discover">Browse kitchens</Link></>;
  return <><PageHeader eyebrow="Checkout" title="Review and place order" description="A short-lived server quote locks the trusted financial breakdown." /><Notice title="Payment safety">The browser never receives provider secrets or creates signatures.</Notice><State loading={cart.isLoading || addresses.isLoading || validation.isLoading} error={cart.error || addresses.error || validation.error} empty={false}><div className="checkout-layout"><Card><label className="labeled-control"><span>Delivery address</span><select value={input.address} onChange={(event) => { setInput({ ...input, address: event.target.value }); quote.reset(); }}><option value="">Choose an address</option>{addresses.data?.map((address) => <option value={address.id} key={address.id}>{addressLabel(address)}</option>)}</select></label>{!addresses.data?.length && <Link to="/customer/addresses">Add a delivery address</Link>}<label className="labeled-control"><span>Coupon code</span><input value={input.coupon} onChange={(event) => { setInput({ ...input, coupon: event.target.value.toUpperCase() }); quote.reset(); }} placeholder="Optional" /></label><button className="primary" disabled={!canCheckout(cart.data, input.address, validation.data?.is_valid) || quote.isPending} onClick={() => quote.mutate()}>{quote.data ? "Refresh quote" : "Create quote"}</button>{quote.error && <ApiErrorPanel error={quote.error} title="Could not create quote" />}</Card>{quote.data && <QuoteCard quote={quote.data} busy={create.isPending} onConfirm={() => create.mutate()} />}</div>{create.error && <ApiErrorPanel error={create.error} title="Order was not placed" />}</State></>;
}

export function OrdersPage() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") || "";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const query = useQuery({ queryKey: ["orders", status], queryFn: () => customerApi.orders(status || undefined), refetchInterval: 15000 });
  const filtered = status ? query.data?.filter((order) => order.status === status) : query.data;
  const pages = Math.ceil((filtered?.length || 0) / 10);
  return <><PageHeader eyebrow="Order history" title="Your orders" description="Order status refreshes every 15 seconds." /><div className="filter-row"><select aria-label="Filter order status" value={status} onChange={(event) => setParams(event.target.value ? { status: event.target.value } : {})}><option value="">All statuses</option>{["PLACED", "ACCEPTED", "PREPARING", "READY", "COMPLETED", "CANCELLED"].map((value) => <option key={value}>{value}</option>)}</select></div><State loading={query.isLoading} error={query.error} empty={!filtered?.length}><div className="stack">{filtered?.slice((page - 1) * 10, page * 10).map((order) => <Link to={`/customer/orders/${order.id}`} className="order-row" key={order.id}><div><b>Order {order.id.slice(0, 8).toUpperCase()}</b><span>{dateTime(order.created_at)} · {order.items.length} items</span></div><strong>{money(order.total_amount)}</strong><StatusPill value={order.status} /></Link>)}</div><PaginationControls page={page} pages={pages} total={filtered?.length} onPageChange={(next) => setParams({ ...(status && { status }), page: String(next) })} /></State></>;
}

export function OrderDetailPage() {
  const { orderId = "" } = useParams();
  const client = useQueryClient();
  const { notify } = useToast();
  const [cancelOpen, setCancelOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [reviewId, setReviewId] = useState("");
  const order = useQuery({ queryKey: ["order", orderId], queryFn: () => customerApi.order(orderId), refetchInterval: (query) => ["COMPLETED", "CANCELLED"].includes(query.state.data?.status || "") ? false : 10000 });
  const payment = useQuery({ queryKey: ["payment-order", orderId], queryFn: () => customerApi.paymentByOrder(orderId), retry: false });
  const cancel = useMutation({ mutationFn: () => customerApi.cancelOrder(orderId, reason), onSuccess: () => { void invalidate(client, "order")(); setCancelOpen(false); notify("Order cancelled."); } });
  const reviewDetail = useQuery({ queryKey: ["review", reviewId], queryFn: () => customerApi.reviewDetail(reviewId), enabled: Boolean(reviewId) });
  const review = useMutation({ mutationFn: (body: Record<string, unknown>) => customerApi.review({ ...body, order_id: orderId }), onSuccess: (result) => { setReviewId(result.id); notify("Review submitted."); } });
  const deleteReview = useMutation({ mutationFn: customerApi.deleteReview, onSuccess: () => { setReviewId(""); notify("Review deleted."); } });
  return <>
    <PageHeader eyebrow="Order detail" title={`Order ${orderId.slice(0, 8).toUpperCase()}`} action={order.data && <StatusPill value={order.data.status} />} />
    <State loading={order.isLoading} error={order.error} empty={!order.data}>
      {order.data && <div className="split-grid">
        <div className="stack">
          <Card><h2>Items</h2>{order.data.items.map((item) => <div className="line-item" key={item.id}><span>{item.quantity} × {item.item_name_snapshot}</span><b>{money(item.unit_price_snapshot * item.quantity)}</b></div>)}<div className="financial-lines"><span>Subtotal <b>{money(order.data.subtotal)}</b></span><span>Discount <b>−{money(order.data.discount_amount)}</b></span><span>Tax <b>{money(order.data.tax_amount)}</b></span><span>Delivery <b>{money(order.data.delivery_fee)}</b></span><span className="total">Total <b>{money(order.data.total_amount)}</b></span></div></Card>
          <Card><h2>Status timeline</h2><OrderTimeline order={order.data} /></Card>
        </div>
        <div className="stack">
          <Card><h2>Payment</h2><StatusPill value={paymentState(payment.data)} /><p>{payment.data ? `${money(payment.data.amount)} · ${payment.data.transactions.length} updates` : "Payment has not started."}</p><Link className="product-button" to={`/customer/payments/new?order=${order.data.id}`}>{paymentState(payment.data) === "FAILED" ? "Retry payment" : "View payment"}</Link></Card>
          <Card><h2>Actions</h2>{["PLACED", "ACCEPTED"].includes(order.data.status) ? <><label className="cancel-reason"><span>Cancellation reason (optional)</span><input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Tell the restaurant why" /></label><button className="danger" onClick={() => setCancelOpen(true)}>Cancel order</button></> : <p>This order can no longer be cancelled.</p>}</Card>
          {order.data.status === "COMPLETED" && <Card><h2>Review this order</h2>{reviewDetail.data ? <><p><b>{reviewDetail.data.rating} / 5</b></p><p>{reviewDetail.data.comment || "Rating only"}</p>{reviewDetail.data.merchant_reply && <Notice title="Restaurant reply">{reviewDetail.data.merchant_reply}</Notice>}<button className="danger" disabled={deleteReview.isPending} onClick={() => deleteReview.mutate(reviewDetail.data.id)}>Delete my review</button></> : <SmartForm fields={[{ name: "rating", label: "Rating", type: "select", required: true, options: ["5", "4", "3", "2", "1"] }, { name: "comment", label: "Comment", type: "textarea" }]} submitLabel="Submit review" busy={review.isPending} error={review.error} onSubmit={(values, form) => review.mutate({ ...values, rating: Number(values.rating) }, { onSuccess: () => form.reset() })} />}</Card>}
        </div>
      </div>}
    </State>
    <ConfirmDialog open={cancelOpen} title="Cancel this order?" description={reason ? `Reason: ${reason}` : "No reason provided. Cancellation is only legal before preparation begins."} confirmLabel="Cancel order" destructive onCancel={() => setCancelOpen(false)} onConfirm={() => cancel.mutate()} />
  </>;
}

export function NotificationsPage() {
  const client = useQueryClient();
  const { notify } = useToast();
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["notifications"], queryFn: customerApi.notifications, refetchInterval: 30000 });
  const preferences = useQuery({ queryKey: ["notification-preferences"], queryFn: customerApi.notificationPreferences });
  const read = useMutation({ mutationFn: customerApi.markNotificationRead, onSuccess: invalidate(client, "notifications") });
  const readAll = useMutation({ mutationFn: customerApi.markAllNotificationsRead, onSuccess: (result) => { void invalidate(client, "notifications")(); notify(`${result.updated} notifications marked read.`); } });
  const save = useMutation({ mutationFn: customerApi.updateNotificationPreferences, onSuccess: (result) => { client.setQueryData(["notification-preferences"], result); notify("Notification preferences saved."); } });
  const unread = query.data?.filter((item) => !item.is_read).length || 0;
  return <><PageHeader eyebrow="Inbox" title="Notifications" description={`${unread} unread`} action={unread ? <button onClick={() => readAll.mutate()}>Mark all read</button> : undefined} /><div className="split-grid"><State loading={query.isLoading} error={query.error} empty={!query.data?.length}><div className="stack">{query.data?.slice((page - 1) * 10, page * 10).map((item) => <Card className={!item.is_read ? "notification-unread" : ""} key={item.id}><div className="card-heading"><div><h3>{item.subject || "Saturdays update"}</h3><p>{item.body}</p><small>{dateTime(item.created_at)} · {item.channel}</small></div>{!item.is_read ? <button onClick={() => read.mutate(item.id)}>Mark read</button> : <StatusPill value="Read" />}</div></Card>)}<PaginationControls page={page} pages={Math.ceil((query.data?.length || 0) / 10)} total={query.data?.length} onPageChange={setPage} /></div></State><Card><h2>Preferences</h2><State loading={preferences.isLoading} error={preferences.error} empty={false}>{preferences.data && <SmartForm key={JSON.stringify(preferences.data)} fields={[{ name: "email_enabled", label: "Email", type: "checkbox", defaultValue: preferences.data.email_enabled }, { name: "sms_enabled", label: "SMS", type: "checkbox", defaultValue: preferences.data.sms_enabled }, { name: "push_enabled", label: "Push", type: "checkbox", defaultValue: preferences.data.push_enabled }, { name: "order_updates", label: "Order updates", type: "checkbox", defaultValue: preferences.data.order_updates }, { name: "marketing", label: "Offers and marketing", type: "checkbox", defaultValue: preferences.data.marketing }]} submitLabel="Save preferences" busy={save.isPending} error={save.error} onSubmit={(values) => save.mutate(values as NotificationPreferences)} />}</State></Card></div></>;
}

declare global { interface Window { Razorpay?: new (options: Record<string, unknown>) => { open: () => void }; } }

function loadRazorpay() {
  if (window.Razorpay) return Promise.resolve();
  return new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-razorpay="checkout"]');
    if (existing) { existing.addEventListener("load", () => resolve(), { once: true }); return; }
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.dataset.razorpay = "checkout";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Could not load secure payment checkout."));
    document.head.appendChild(script);
  });
}

export function PaymentPage() {
  const [params] = useSearchParams();
  const orderId = params.get("order") || "";
  const { notify } = useToast();
  const [localStatus, setLocalStatus] = useState<string>();
  const order = useQuery({ queryKey: ["order", orderId], queryFn: () => customerApi.order(orderId), enabled: Boolean(orderId) });
  const history = useQuery({ queryKey: ["payment-order", orderId], queryFn: () => customerApi.paymentByOrder(orderId), enabled: Boolean(orderId), retry: false, refetchInterval: 5000 });
  const verify = useMutation({ mutationFn: customerApi.verifyPayment, onSuccess: () => { void history.refetch(); setLocalStatus("CAPTURED"); notify("Payment captured."); } });
  const intent = useMutation({ mutationFn: () => customerApi.paymentIntent({ order_id: orderId }), onSuccess: (result) => void startCheckout(result) });
  async function startCheckout(result: PaymentIntent) {
    if (isMockProviderOrder(result.razorpay_order_id)) {
      setLocalStatus("MOCK_PENDING");
      try {
        await customerApi.completeMockPayment(result.order_id);
        setLocalStatus("CAPTURED");
        await history.refetch();
        notify("Local mock payment captured. No money was charged.");
      } catch (error) {
        setLocalStatus("FAILED");
        notify(error instanceof Error ? error.message : "Mock payment failed.", "error");
      }
      return;
    }
    const key = result.provider_key_id || import.meta.env.VITE_RAZORPAY_KEY_ID;
    if (!key) { setLocalStatus("MISSING_PROVIDER_KEY"); return; }
    await loadRazorpay();
    const checkout = new window.Razorpay!({ key, order_id: result.razorpay_order_id, amount: Math.round(result.amount * 100), currency: result.currency, name: "Saturdays", handler: (response: Record<string, string>) => verify.mutate({ order_id: result.order_id, razorpay_order_id: response.razorpay_order_id, razorpay_payment_id: response.razorpay_payment_id, razorpay_signature: response.razorpay_signature }), modal: { ondismiss: () => setLocalStatus("CANCELLED") } });
    checkout.open();
  }
  const state = localStatus || paymentState(history.data);
  return <><PageHeader eyebrow="Payment" title="Payment status" description={order.data ? `Order ${order.data.id.slice(0, 8).toUpperCase()} · ${money(order.data.total_amount)}` : "Secure order payment"} /><Notice title="Secure checkout">Provider signatures are returned directly by Razorpay. You will never be asked to paste one.</Notice><State loading={order.isLoading} error={order.error} empty={!orderId}><div className="split-grid"><Card><h2>Current state</h2><StatusPill value={state} />{state === "MOCK_PENDING" && <p>Completing deterministic local checkout…</p>}{state === "CAPTURED" && <p>Payment captured successfully.</p>}{state === "MISSING_PROVIDER_KEY" && <ApiErrorPanel error={new Error("Razorpay public key is not configured for this frontend.")} />}{["NOT_STARTED", "FAILED", "CANCELLED"].includes(state) && <button className="primary" disabled={intent.isPending || !order.data} onClick={() => intent.mutate()}>{state === "FAILED" ? "Retry payment" : "Pay now"}</button>}{intent.error && <ApiErrorPanel error={intent.error} />}</Card><Card><h2>Payment history</h2>{history.data?.transactions.length ? history.data.transactions.map((transaction) => <div className="line-item" key={transaction.id}><span>{transaction.transaction_type}<small>{dateTime(transaction.created_at)}</small></span><span><b>{money(transaction.amount)}</b> <StatusPill value={transaction.status} /></span></div>) : <p>No server payment updates yet.</p>}</Card></div></State></>;
}
