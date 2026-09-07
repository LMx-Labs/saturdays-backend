import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { discoveryApi, customerApi } from "../api/modules";
import type { Branch, SearchItem } from "../api/types";
import { useAuth, roleHome } from "../auth/AuthProvider";
import { Card, money, Notice, PageHeader, SmartForm, State, StatusPill } from "../components/ui";

function BranchCard({ branch }: { branch: Branch }) {
  return (
    <Link className="restaurant-card" to={`/branches/${branch.id}`}>
      <div className="restaurant-visual"><span>{branch.name.slice(0, 1)}</span><StatusPill value={branch.is_active} /></div>
      <div><h3>{branch.name}</h3><p>{branch.address_text}</p><small>{branch.opening_time}–{branch.closing_time}</small></div>
    </Link>
  );
}

export function HomePage() {
  const banners = useQuery({ queryKey: ["banners"], queryFn: discoveryApi.banners });
  const branches = useQuery({ queryKey: ["branches"], queryFn: () => discoveryApi.branches() });
  return (
    <main className="public-main">
      <section className="product-hero">
        <div>
          <span className="product-eyebrow">Made for campus life</span>
          <h1>Your next meal,<br />right on time.</h1>
          <p>Explore trusted kitchens, order from live menus, and follow every step from prep to pickup.</p>
          <div className="hero-actions"><Link className="product-button primary" to="/discover">Find food</Link><Link className="product-button" to="/auth/register">Create account</Link></div>
        </div>
        <div className="hero-art"><span className="hero-orbit one" /><span className="hero-orbit two" /><b>Fresh<br />every<br />Saturday.</b></div>
      </section>
      {banners.data?.[0] && (
        <a className="campaign" href={banners.data[0].target_url || "#"}>
          <span>Now serving</span><h2>{banners.data[0].title}</h2>
        </a>
      )}
      <PageHeader eyebrow="Nearby" title="Popular around you" description="Active branches currently accepting discovery traffic." action={<Link to="/discover">View all</Link>} />
      <State loading={branches.isLoading} error={branches.error} empty={!branches.data?.length}>
        <div className="restaurant-grid">{branches.data?.slice(0, 6).map((branch) => <BranchCard branch={branch} key={branch.id} />)}</div>
      </State>
    </main>
  );
}

export function DiscoverPage() {
  const [params, setParams] = useSearchParams();
  const brandId = params.get("brand") || "";
  const brands = useQuery({ queryKey: ["brands"], queryFn: () => discoveryApi.brands() });
  const branches = useQuery({ queryKey: ["branches", brandId], queryFn: () => discoveryApi.branches(brandId || undefined) });
  return (
    <main className="public-main">
      <PageHeader eyebrow="Storefront" title="Discover kitchens" description="Browse every active Saturdays location." />
      <div className="filter-row">
        <button className={!brandId ? "selected" : ""} onClick={() => setParams({})}>All</button>
        {brands.data?.map((brand) => <button className={brandId === brand.id ? "selected" : ""} key={brand.id} onClick={() => setParams({ brand: brand.id })}>{brand.name}</button>)}
      </div>
      <State loading={branches.isLoading} error={branches.error} empty={!branches.data?.length}>
        <div className="restaurant-grid">{branches.data?.map((branch) => <BranchCard branch={branch} key={branch.id} />)}</div>
      </State>
    </main>
  );
}

export function BrandsPage() {
  const query = useQuery({ queryKey: ["brands"], queryFn: () => discoveryApi.brands() });
  return <main className="public-main"><PageHeader eyebrow="Our partners" title="Restaurant brands" description="Meet the food makers across the platform." />
    <State loading={query.isLoading} error={query.error} empty={!query.data?.length}><div className="brand-grid">{query.data?.map((brand) =>
      <Link to={`/brands/${brand.id}`} className="brand-tile" key={brand.id}><span>{brand.name.slice(0, 2).toUpperCase()}</span><div><h3>{brand.name}</h3><p>{brand.description || "Local food, prepared with care."}</p><small>{brand.cuisine_types?.join(" · ") || "Multi-cuisine"}</small></div></Link>)}</div></State>
  </main>;
}

function ResultCard({ item }: { item: SearchItem }) {
  return <Card className="result-card"><div><span className="product-eyebrow">{item.entity_type}</span><h3>{item.title}</h3><p>{item.description || item.branch_name || item.brand_name}</p></div>{item.price !== undefined && <b>{money(item.price)}</b>}{item.branch_id && <Link to={`/branches/${item.branch_id}`}>View menu</Link>}</Card>;
}

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") || "";
  const [draft, setDraft] = useState(q);
  const results = useQuery({ queryKey: ["search", q, params.toString()], queryFn: () => discoveryApi.search({ q, type: params.get("type") || "all", is_veg: params.get("veg") === "true" || undefined, sort_by: params.get("sort") || "relevance" }) });
  return <main className="public-main"><PageHeader eyebrow="Search" title="What are you craving?" />
    <form className="search-hero" onSubmit={(event) => { event.preventDefault(); setParams({ q: draft, type: params.get("type") || "all" }); }}><input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Search restaurants, dishes or cuisines" /><button className="product-button primary">Search</button></form>
    <div className="filter-row"><select value={params.get("type") || "all"} onChange={(event) => setParams({ q, type: event.target.value })}><option value="all">Everything</option><option value="restaurant">Restaurants</option><option value="dish">Dishes</option><option value="category">Categories</option></select><label><input type="checkbox" checked={params.get("veg") === "true"} onChange={(event) => setParams({ q, type: params.get("type") || "all", veg: String(event.target.checked) })} /> Vegetarian</label></div>
    <State loading={results.isLoading} error={results.error} empty={!results.data?.results.length}><p className="result-count">{results.data?.total} results for “{results.data?.query}”</p><div className="result-grid">{results.data?.results.map((item) => <ResultCard item={item} key={`${item.entity_type}-${item.id}`} />)}</div></State>
  </main>;
}

export function BranchPage() {
  const { branchId = "" } = useParams();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const branch = useQuery({ queryKey: ["branch", branchId], queryFn: () => discoveryApi.branch(branchId), enabled: Boolean(branchId) });
  const menu = useQuery({ queryKey: ["menu", branchId], queryFn: () => discoveryApi.menu(branchId), enabled: Boolean(branchId) });
  const rating = useQuery({ queryKey: ["rating", branchId], queryFn: () => discoveryApi.rating(branchId), enabled: Boolean(branchId) });
  const reviews = useQuery({ queryKey: ["reviews", branchId], queryFn: () => discoveryApi.reviews(branchId), enabled: Boolean(branchId) });
  const add = useMutation({ mutationFn: (itemId: string) => customerApi.addCartItem({ branch_id: branchId, menu_item_id: itemId, quantity: 1 }), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["cart"] }) });
  const favorite = useMutation({ mutationFn: () => customerApi.addFavorite(branchId) });
  return <main className="public-main"><State loading={branch.isLoading} error={branch.error} empty={!branch.data}>
    {branch.data && <><section className="store-hero"><div><span className="product-eyebrow">Branch storefront</span><h1>{branch.data.name}</h1><p>{branch.data.address_text}</p><div className="store-meta"><StatusPill value={branch.data.is_active} /><span>{rating.data ? `${rating.data.average_rating.toFixed(1)} / 5 · ${rating.data.total_reviews} reviews` : "New on Saturdays"}</span><span>{branch.data.opening_time}–{branch.data.closing_time}</span></div></div>{user?.role === "Customer" && <button className="product-button" onClick={() => favorite.mutate()}>Save favorite</button>}</section>
    {user?.role !== "Customer" && <Notice title="Ordering requires a customer account">Sign in as a customer to add menu items to a cart.</Notice>}
    {add.error && <div className="inline-error">{add.error.message}</div>}
    {favorite.error && <div className="inline-error">{favorite.error.message}</div>}
    <PageHeader eyebrow="Live menu" title={menu.data?.name || "Menu"} />
    <State loading={menu.isLoading} error={menu.error} empty={!menu.data?.categories.length}>{menu.data?.categories.map((category) => <section className="menu-section" key={category.id}><h2>{category.name}</h2><div className="menu-grid">{category.items.map((item) => <Card className="menu-item" key={item.id}><div><h3>{item.name}</h3><p>{item.description || (item.is_veg ? "Vegetarian" : "Non-vegetarian")}</p><b>{money(item.base_price)}</b></div><button className="product-button primary" disabled={!item.is_available || user?.role !== "Customer" || add.isPending} onClick={() => add.mutate(item.id)}>{item.is_available ? "Add" : "Unavailable"}</button></Card>)}</div></section>)}</State>
    <PageHeader eyebrow="Community" title="Guest reviews" />
    <State loading={reviews.isLoading} error={reviews.error} empty={!reviews.data?.length}><div className="review-grid">{reviews.data?.map((review) => <Card key={review.id}><b>{review.rating} / 5</b><p>{review.comment || "No written comment."}</p>{review.merchant_reply && <small>Merchant reply: {review.merchant_reply}</small>}</Card>)}</div></State></>}
  </State></main>;
}

export function CouponsPage() {
  const query = useQuery({ queryKey: ["coupons"], queryFn: () => discoveryApi.coupons() });
  return <main className="public-main"><PageHeader eyebrow="Offers" title="Current coupons" description="Availability and final discount are validated at checkout." /><State loading={query.isLoading} error={query.error} empty={!query.data?.length}><div className="coupon-grid">{query.data?.map((coupon) => <Card className="coupon" key={coupon.id}><span>{coupon.is_platform_coupon ? "Platform offer" : "Restaurant offer"}</span><h2>{coupon.code}</h2><p>{coupon.discount_type === "PERCENTAGE" ? `${coupon.discount_value}% off` : `${money(coupon.discount_value)} off`} · Minimum {money(coupon.min_order_amount)}</p><small>Valid until {new Date(coupon.valid_until).toLocaleDateString("en-IN")}</small></Card>)}</div></State></main>;
}

export function AuthPage() {
  const [mode, setMode] = useState<"login" | "register">(new URLSearchParams(location.search).get("mode") === "register" ? "register" : "login");
  const { login, registerCustomer } = useAuth();
  const navigate = useNavigate();
  const mutation = useMutation({
    mutationFn: (values: Record<string, unknown>) => mode === "login"
      ? login(String(values.email), String(values.password))
      : registerCustomer(String(values.email), String(values.password)),
    onSuccess: (user) => navigate(roleHome(user.role), { replace: true }),
  });
  return <Card className="auth-card"><span className="product-eyebrow">{mode === "login" ? "Welcome back" : "Join Saturdays"}</span><h1>{mode === "login" ? "Sign in to continue" : "Create your customer account"}</h1><p>{mode === "register" ? "Public registration always creates a Customer account. Staff access is provisioned by the platform." : "Your role determines which secure workspace opens."}</p><SmartForm fields={[{ name: "email", label: "Email", type: "email", required: true }, { name: "password", label: "Password", type: "password", required: true }]} submitLabel={mode === "login" ? "Sign in" : "Create account"} busy={mutation.isPending} error={mutation.error} onSubmit={(values) => mutation.mutate(values)} /><button className="text-button" onClick={() => setMode(mode === "login" ? "register" : "login")}>{mode === "login" ? "New here? Create an account" : "Already registered? Sign in"}</button></Card>;
}
