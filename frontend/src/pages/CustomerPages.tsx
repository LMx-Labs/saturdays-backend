import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { customerApi, discoveryApi } from "../api/modules";
import type { Cart } from "../api/types";
import { Card, dateTime, money, Notice, OrderTimeline, PageHeader, SmartForm, State, StatusPill } from "../components/ui";

function invalidate(queryClient: ReturnType<typeof useQueryClient>, key: string) {
  return () => queryClient.invalidateQueries({ queryKey: [key] });
}

export function CustomerDashboard() {
  const orders = useQuery({ queryKey: ["orders"], queryFn: () => customerApi.orders() });
  const cart = useQuery({ queryKey: ["cart"], queryFn: customerApi.cart, retry: false });
  return <><PageHeader eyebrow="Customer workspace" title="Good food starts here" description="Your active cart and latest orders at a glance." /><div className="metric-grid"><Card><span>Cart total</span><b>{money(cart.data?.subtotal)}</b><small>{cart.data?.total_items || 0} items</small></Card><Card><span>Total orders</span><b>{orders.data?.length || 0}</b><small>Across all branches</small></Card><Card><span>Latest status</span><b>{orders.data?.[0]?.status || "No orders"}</b><small>{orders.data?.[0] ? dateTime(orders.data[0].updated_at) : "Start discovering"}</small></Card></div><div className="dashboard-actions"><Link className="product-button primary" to="/discover">Browse kitchens</Link><Link className="product-button" to="/customer/cart">Open cart</Link></div></>;
}

export function ProfilePage() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["profile"], queryFn: customerApi.profile });
  const mutation = useMutation({ mutationFn: customerApi.updateProfile, onSuccess: invalidate(queryClient, "profile") });
  return <><PageHeader eyebrow="Account" title="Your profile" description="Keep contact information current for order updates." /><State loading={query.isLoading} error={query.error} empty={false}><Card><SmartForm key={query.data?.id} fields={[{ name: "full_name", label: "Full name", required: true, defaultValue: query.data?.full_name }, { name: "phone_number", label: "Phone number", defaultValue: query.data?.phone_number }]} submitLabel="Save profile" busy={mutation.isPending} error={mutation.error} onSubmit={(values) => mutation.mutate(values)} /></Card></State></>;
}

export function AddressesPage() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["addresses"], queryFn: customerApi.addresses });
  const add = useMutation({ mutationFn: customerApi.addAddress, onSuccess: invalidate(queryClient, "addresses") });
  const primary = useMutation({ mutationFn: customerApi.primaryAddress, onSuccess: invalidate(queryClient, "addresses") });
  const remove = useMutation({ mutationFn: customerApi.deleteAddress, onSuccess: invalidate(queryClient, "addresses") });
  return <><PageHeader eyebrow="Delivery" title="Saved addresses" description="Choose a primary drop-off point for faster checkout." /><div className="split-grid"><Card><h2>Add an address</h2><SmartForm fields={[{ name: "address_line", label: "Address line", required: true }, { name: "building_name", label: "Building name" }, { name: "campus_zone", label: "Campus zone", required: true }, { name: "is_primary", label: "Set as primary", type: "checkbox" }]} submitLabel="Add address" busy={add.isPending} error={add.error} onSubmit={(values, form) => add.mutate(values, { onSuccess: () => form.reset() })} /></Card><State loading={query.isLoading} error={query.error} empty={!query.data?.length}><div className="stack">{query.data?.map((address) => <Card key={address.id}><div className="card-heading"><div><h3>{address.building_name || address.campus_zone}</h3><p>{address.address_line}</p><small>{address.campus_zone}</small></div>{address.is_primary && <StatusPill value="Primary" />}</div><div className="card-actions">{!address.is_primary && <button onClick={() => primary.mutate(address.id)}>Make primary</button>}<button className="danger" onClick={() => remove.mutate(address.id)}>Delete</button></div></Card>)}</div></State></div></>;
}

export function FavoritesPage() {
  const queryClient = useQueryClient();
  const favorites = useQuery({ queryKey: ["favorites"], queryFn: customerApi.favorites });
  const branches = useQuery({ queryKey: ["branches"], queryFn: () => discoveryApi.branches() });
  const remove = useMutation({ mutationFn: customerApi.deleteFavorite, onSuccess: invalidate(queryClient, "favorites") });
  return <><PageHeader eyebrow="Saved" title="Favorite branches" description="Your shortcut back to familiar menus." /><State loading={favorites.isLoading || branches.isLoading} error={favorites.error || branches.error} empty={!favorites.data?.length}><div className="stack">{favorites.data?.map((favorite) => { const branch = branches.data?.find((item) => item.id === favorite.branch_id); return <Card key={favorite.id}><div className="card-heading"><div><h3>{branch?.name || "Saved branch"}</h3><p>{branch?.address_text || favorite.branch_id}</p></div><StatusPill value={branch?.is_active ?? false} /></div><div className="card-actions"><Link to={`/branches/${favorite.branch_id}`}>View menu</Link><button className="danger" onClick={() => remove.mutate(favorite.branch_id)}>Remove</button></div></Card>; })}</div></State></>;
}

export function CartPage() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["cart"], queryFn: customerApi.cart, retry: false });
  const update = useMutation({ mutationFn: ({ id, quantity }: { id: string; quantity: number }) => customerApi.updateCartItem(id, { quantity }), onSuccess: invalidate(queryClient, "cart") });
  const remove = useMutation({ mutationFn: customerApi.removeCartItem, onSuccess: invalidate(queryClient, "cart") });
  const clear = useMutation({ mutationFn: customerApi.clearCart, onSuccess: invalidate(queryClient, "cart") });
  return <><PageHeader eyebrow="Your basket" title="Cart" description="Quantities and availability are revalidated by the server." action={query.data?.items.length ? <button className="danger" onClick={() => clear.mutate()}>Clear cart</button> : undefined} /><State loading={query.isLoading} error={query.error} empty={!query.data?.items.length}>{query.data && <div className="cart-layout"><div className="stack">{query.data.items.map((item) => <Card className="cart-line" key={item.id}><div><h3>{item.menu_item_name || "Menu item"}</h3><p>{money(item.unit_price)} each</p></div><div className="quantity"><button onClick={() => update.mutate({ id: item.id, quantity: Math.max(0, item.quantity - 1) })}>−</button><b>{item.quantity}</b><button onClick={() => update.mutate({ id: item.id, quantity: item.quantity + 1 })}>+</button></div><b>{money(item.subtotal)}</b><button className="danger" onClick={() => remove.mutate(item.id)}>Remove</button></Card>)}</div><Card className="cart-summary"><span>Items <b>{query.data.total_items}</b></span><span>Subtotal <b>{money(query.data.subtotal)}</b></span><Link className="product-button primary" to="/customer/checkout">Continue to checkout</Link></Card></div>}</State></>;
}

function orderPayload(cart: Cart, address: Record<string, unknown>) {
  return {
    branch_id: cart.branch_id,
    items: cart.items.map((item) => ({ menu_item_id: item.menu_item_id, quantity: item.quantity })),
    delivery_address_snapshot: address,
  };
}

export function CheckoutPage() {
  const navigate = useNavigate();
  const [checkoutInput, setCheckoutInput] = useState<Record<string, unknown>>({});
  const cart = useQuery({ queryKey: ["cart"], queryFn: customerApi.cart });
  const addresses = useQuery({ queryKey: ["addresses"], queryFn: customerApi.addresses });
  const validate = useMutation({ mutationFn: (values: Record<string, unknown>) => customerApi.checkout({ cart_id: cart.data?.id, coupon_code: values.coupon_code, delivery_address_id: values.delivery_address_id }) });
  const create = useMutation({ mutationFn: ({ addressId }: { addressId: string }) => { const address = addresses.data?.find((item) => item.id === addressId); if (!cart.data || !address) throw new Error("Choose a valid delivery address."); return customerApi.createOrder(orderPayload(cart.data, address)); }, onSuccess: (order) => navigate(`/customer/orders/${order.id}`) });
  return <><PageHeader eyebrow="Checkout" title="Review and place order" description="The API recalculates price, coupon eligibility, inventory, tax and fees." /><Notice title="Payment safety">The browser creates payment intents but never generates HMAC signatures or stores Razorpay secrets.</Notice><Card><SmartForm fields={[{ name: "delivery_address_id", label: "Delivery address", type: "select", required: true, options: addresses.data?.map((item) => ({ value: item.id, label: `${item.building_name || item.campus_zone} — ${item.address_line}` })) }, { name: "coupon_code", label: "Coupon code" }]} submitLabel="Validate checkout" busy={validate.isPending} error={validate.error} onSubmit={(values) => { setCheckoutInput(values); validate.mutate(values); }} /></Card>{validate.data && <Card className="checkout-summary"><h2>Server checkout summary</h2><pre>{JSON.stringify(validate.data, null, 2)}</pre>{(validate.data as { is_valid?: boolean }).is_valid && <button className="product-button primary" disabled={create.isPending} onClick={() => create.mutate({ addressId: String(checkoutInput.delivery_address_id || "") })}>Place order</button>}{create.error && <div className="inline-error">{create.error.message}</div>}</Card>}</>;
}

export function OrdersPage() {
  const query = useQuery({ queryKey: ["orders"], queryFn: () => customerApi.orders() });
  return <><PageHeader eyebrow="Order history" title="Your orders" /><State loading={query.isLoading} error={query.error} empty={!query.data?.length}><div className="stack">{query.data?.map((order) => <Link to={`/customer/orders/${order.id}`} className="order-row" key={order.id}><div><b>Order {order.id.slice(0, 8)}</b><span>{dateTime(order.created_at)} · {order.items.length} items</span></div><strong>{money(order.total_amount)}</strong><StatusPill value={order.status} /></Link>)}</div></State></>;
}

export function OrderDetailPage() {
  const { orderId = "" } = useParams();
  const queryClient = useQueryClient();
  const order = useQuery({ queryKey: ["order", orderId], queryFn: () => customerApi.order(orderId) });
  const cancel = useMutation({ mutationFn: () => customerApi.cancelOrder(orderId), onSuccess: invalidate(queryClient, "order") });
  const review = useMutation({ mutationFn: (body: Record<string, unknown>) => customerApi.review({ ...body, order_id: orderId }) });
  return <><PageHeader eyebrow="Order detail" title={`Order ${orderId.slice(0, 8)}`} action={order.data && <StatusPill value={order.data.status} />} /><State loading={order.isLoading} error={order.error} empty={!order.data}>{order.data && <div className="split-grid"><div className="stack"><Card><h2>Items</h2>{order.data.items.map((item) => <div className="line-item" key={item.id}><span>{item.quantity} × {item.item_name_snapshot}</span><b>{money(item.unit_price_snapshot * item.quantity)}</b></div>)}<div className="line-item total"><span>Total</span><b>{money(order.data.total_amount)}</b></div></Card><Card><h2>Status timeline</h2><OrderTimeline order={order.data} /></Card></div><div className="stack"><Card><h2>Actions</h2>{["PLACED", "ACCEPTED"].includes(order.data.status) && <button className="danger" disabled={cancel.isPending} onClick={() => cancel.mutate()}>Cancel order</button>}{cancel.error && <div className="inline-error">{cancel.error.message}</div>}<Link className="product-button" to={`/customer/payments/new?order=${order.data.id}&amount=${order.data.total_amount}`}>Payment status</Link></Card>{order.data.status === "COMPLETED" && <Card><h2>Review this order</h2><SmartForm fields={[{ name: "rating", label: "Rating", type: "select", required: true, options: ["5", "4", "3", "2", "1"] }, { name: "comment", label: "Comment", type: "textarea" }]} submitLabel="Submit review" busy={review.isPending} error={review.error} onSubmit={(values, form) => review.mutate(values, { onSuccess: () => form.reset() })} /></Card>}</div></div>}</State></>;
}

export function NotificationsPage() {
  const query = useQuery({ queryKey: ["notifications"], queryFn: customerApi.notifications });
  return <><PageHeader eyebrow="Inbox" title="Notifications" /><State loading={query.isLoading} error={query.error} empty={!query.data?.length}><div className="stack">{query.data?.map((item) => <Card key={item.id}><div className="card-heading"><div><h3>{item.subject || item.channel}</h3><p>{item.body}</p><small>{dateTime(item.created_at)}</small></div><StatusPill value={item.status} /></div></Card>)}</div></State></>;
}

export function PaymentPage() {
  const params = new URLSearchParams(location.search);
  const intent = useMutation({ mutationFn: customerApi.paymentIntent });
  const verify = useMutation({ mutationFn: customerApi.verifyPayment });
  return <><PageHeader eyebrow="Payment" title="Secure payment status" description="Create an intent, complete payment through your configured provider, then submit provider-returned fields for server verification." /><Notice title="Backend-managed verification">Razorpay signatures must come from Razorpay. This frontend does not calculate HMAC values or expose any secret.</Notice><div className="split-grid"><Card><h2>Create payment intent</h2><SmartForm fields={[{ name: "order_id", label: "Order ID", required: true, defaultValue: params.get("order") || "" }, { name: "amount", label: "Amount", type: "number", required: true, defaultValue: params.get("amount") || "" }, { name: "currency", label: "Currency", defaultValue: "INR" }]} submitLabel="Create intent" busy={intent.isPending} error={intent.error} onSubmit={(values) => intent.mutate(values)} />{Boolean(intent.data) && <pre>{JSON.stringify(intent.data, null, 2)}</pre>}</Card><Card><h2>Verify provider response</h2><SmartForm fields={[{ name: "order_id", label: "Order ID", required: true }, { name: "razorpay_order_id", label: "Razorpay order ID", required: true }, { name: "razorpay_payment_id", label: "Razorpay payment ID", required: true }, { name: "razorpay_signature", label: "Razorpay signature", required: true }]} submitLabel="Verify with server" busy={verify.isPending} error={verify.error} onSubmit={(values) => verify.mutate(values)} />{Boolean(verify.data) && <pre>{JSON.stringify(verify.data, null, 2)}</pre>}</Card></div></>;
}
