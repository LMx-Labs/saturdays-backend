import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { authClient, authenticatedWebSocket } from "../api/client";
import { customerApi, merchantApi } from "../api/modules";
import { Card, dateTime, money, Notice, OrderTimeline, OrderTransitionControls, PageHeader, SmartForm, State, StatusPill } from "../components/ui";

export function KitchenBoardPage() {
  const queryClient = useQueryClient();
  const [branchId, setBranchId] = useState(() => sessionStorage.getItem("saturdays.kitchenBranch") || "");
  const [connection, setConnection] = useState("Disconnected");
  const branches = useQuery({ queryKey: ["assigned-branches"], queryFn: merchantApi.assignedBranches });
  const orders = useQuery({
    queryKey: ["kitchen-orders", branchId],
    queryFn: () => merchantApi.orders(branchId),
    enabled: Boolean(branchId),
    refetchInterval: 10000,
  });
  const transition = useMutation({
    mutationFn: ({ id, state }: { id: string; state: string }) => merchantApi.orderStatus(id, state),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["kitchen-orders", branchId] }),
  });

  useEffect(() => {
    if (!branchId) return;
    sessionStorage.setItem("saturdays.kitchenBranch", branchId);
    const token = authClient.getAccessToken();
    if (!token) return;
    let socket: WebSocket | undefined;
    let timer: number | undefined;
    let stopped = false;
    const connect = () => {
      setConnection(socket ? "Reconnecting" : "Connecting");
      socket = authenticatedWebSocket(`/ws/branches/${encodeURIComponent(branchId)}/orders`, token);
      socket.onopen = () => setConnection("Live");
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(String(event.data)) as { event?: string };
          setConnection(message.event === "RESYNC_REQUIRED" ? "Resyncing" : "Live");
        } catch { setConnection("Live"); }
        void queryClient.invalidateQueries({ queryKey: ["kitchen-orders", branchId] }).then(() => setConnection("Live"));
      };
      socket.onerror = () => setConnection("Polling");
      socket.onclose = () => {
        if (stopped) return;
        setConnection("Polling");
        timer = window.setTimeout(connect, 3000);
      };
    };
    connect();
    return () => { stopped = true; if (timer) window.clearTimeout(timer); socket?.close(); };
  }, [branchId, queryClient]);

  const active = orders.data?.filter((order) => !["COMPLETED", "CANCELLED"].includes(order.status)) || [];
  return <><PageHeader eyebrow="Kitchen display system" title="Live order board" description="Authenticated live events trigger a full resync; polling remains active as fallback." action={<div className="picker-row"><select value={branchId} onChange={(event) => setBranchId(event.target.value)}><option value="">Choose assigned branch</option>{branches.data?.map((branch) => <option value={branch.id} key={branch.id}>{branch.name}</option>)}</select><StatusPill value={connection} /></div>} />{!branchId ? <Notice title="Select your assigned branch">Only branches returned by your authenticated assignment endpoint are available.</Notice> : <State loading={orders.isLoading} error={orders.error} empty={!active.length}><div className="kanban">{["PLACED", "ACCEPTED", "PREPARING", "READY"].map((column) => <section key={column}><h2>{column}<span>{active.filter((order) => order.status === column).length}</span></h2>{active.filter((order) => order.status === column).map((order) => <Card className="ticket" key={order.id}><div className="card-heading"><b>#{order.id.slice(0, 6)}</b><small>{dateTime(order.created_at)}</small></div>{order.items.map((item) => <div className="ticket-item" key={item.id}><b>{item.quantity}</b><span>{item.item_name_snapshot}</span></div>)}<div className="ticket-total">{money(order.total_amount)}</div><Link className="product-button" to={`/kitchen/orders/${order.id}`}>View detail</Link><OrderTransitionControls status={order.status} busy={transition.isPending} onTransition={(state) => transition.mutate({ id: order.id, state })} /></Card>)}</section>)}</div></State>}</>;
}

export function KitchenOrderLookupPage() {
  const { orderId = "" } = useParams();
  const order = useQuery({ queryKey: ["order", orderId], queryFn: () => customerApi.order(orderId), enabled: Boolean(orderId), retry: false });
  return <><PageHeader eyebrow="Fulfilment" title={`Order ${orderId.slice(0, 8)}`} action={<Link className="product-button" to="/kitchen">Back to board</Link>} /><State loading={order.isLoading} error={order.error} empty={!order.data}>{order.data && <div className="split-grid"><Card><div className="card-heading"><h2>Items</h2><StatusPill value={order.data.status} /></div>{order.data.items.map((item) => <div className="line-item" key={item.id}><span>{item.quantity} × {item.item_name_snapshot}</span><b>{money(item.unit_price_snapshot * item.quantity)}</b></div>)}</Card><Card><h2>Timeline</h2><OrderTimeline order={order.data} /></Card></div>}</State></>;
}

export function KitchenInventoryPage() {
  const queryClient = useQueryClient();
  const [branchId, setBranchId] = useState("");
  const branches = useQuery({ queryKey: ["assigned-branches"], queryFn: merchantApi.assignedBranches });
  const inventory = useQuery({ queryKey: ["kitchen-inventory", branchId], queryFn: () => merchantApi.inventory(branchId), enabled: Boolean(branchId) });
  const stock = useMutation({ mutationFn: ({ id, values }: { id: string; values: Record<string, unknown> }) => merchantApi.stock(id, values), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["kitchen-inventory", branchId] }) });
  return <><PageHeader eyebrow="Assigned supply" title="Inventory" action={<select value={branchId} onChange={(event) => setBranchId(event.target.value)}><option value="">Choose assigned branch</option>{branches.data?.map((branch) => <option value={branch.id} key={branch.id}>{branch.name}</option>)}</select>} /><State loading={inventory.isLoading} error={inventory.error} empty={!inventory.data?.length}><div className="stack">{inventory.data?.map((item) => <Card key={item.id}><div className="card-heading"><div><h3>{item.menu_item.name}</h3><small>{item.quantity} units</small></div><StatusPill value={item.is_in_stock} /></div><SmartForm compact fields={[{ name: "quantity", label: "Quantity", type: "number", required: true, defaultValue: item.quantity }, { name: "reason", label: "Reason", required: true, defaultValue: "KITCHEN_COUNT" }]} submitLabel="Update stock" busy={stock.isPending} error={stock.error} onSubmit={(values) => stock.mutate({ id: item.id, values })} /></Card>)}</div></State></>;
}
