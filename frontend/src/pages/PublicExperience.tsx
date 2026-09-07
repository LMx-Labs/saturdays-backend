import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { customerApi, discoveryApi } from "../api/modules";
import type { Branch, MenuItem, SearchItem } from "../api/types";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { useToast } from "../components/toastContext";
import {
  Card, ConfirmDialog, money, Notice, PageHeader, PaginationControls, State, StatusPill,
} from "../components/ui";
import { hasCrossBranchConflict, searchQuery } from "../customerExperience";

const PAGE_SIZE = 9;

function BranchCard({ branch, brandName }: { branch: Branch; brandName?: string }) {
  return <Link className="restaurant-card" to={`/branches/${branch.id}`}>
    <div className="restaurant-visual"><span>{branch.name.slice(0, 1)}</span><StatusPill value={branch.is_active} /></div>
    <div><small>{brandName}</small><h3>{branch.name}</h3><p>{branch.address_text}</p><small>{branch.opening_time}–{branch.closing_time}</small></div>
  </Link>;
}

export function HomePage() {
  const [banner, setBanner] = useState(0);
  const banners = useQuery({ queryKey: ["banners"], queryFn: discoveryApi.banners });
  const branches = useQuery({ queryKey: ["branches"], queryFn: () => discoveryApi.branches() });
  useEffect(() => {
    if (!banners.data || banners.data.length < 2) return;
    const timer = window.setInterval(() => setBanner((value) => (value + 1) % banners.data.length), 6000);
    return () => window.clearInterval(timer);
  }, [banners.data]);
  return <main className="public-main">
    <section className="product-hero"><div><span className="product-eyebrow">Made for campus life</span><h1>Your next meal,<br />right on time.</h1><p>Explore trusted kitchens, order from live menus, and follow every step from prep to pickup.</p><div className="hero-actions"><Link className="product-button primary" to="/discover">Find food</Link><Link className="product-button" to="/auth/register">Create account</Link></div></div><div className="hero-art"><b>Fresh<br />every<br />Saturday.</b></div></section>
    <State loading={banners.isLoading} error={banners.error} empty={!banners.data?.length}>
      {banners.data?.length ? <section className="banner-carousel" aria-roledescription="carousel">
        <a href={banners.data[banner].target_url || "/discover"} style={{ backgroundImage: `linear-gradient(90deg,#173e27dd,#173e2788),url(${banners.data[banner].image_url})` }}><span>Featured</span><h2>{banners.data[banner].title}</h2></a>
        <div>{banners.data.map((item, index) => <button aria-label={`Show ${item.title}`} className={index === banner ? "selected" : ""} key={item.id} onClick={() => setBanner(index)} />)}</div>
      </section> : null}
    </State>
    <PageHeader eyebrow="Nearby" title="Popular around you" description="Active branches currently accepting orders." action={<Link to="/discover">View all</Link>} />
    <State loading={branches.isLoading} error={branches.error} empty={!branches.data?.length}><div className="restaurant-grid">{branches.data?.slice(0, 6).map((item) => <BranchCard branch={item} key={item.id} />)}</div></State>
  </main>;
}

export function DiscoverPage() {
  const [params, setParams] = useSearchParams();
  const brandId = params.get("brand") || "";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const brands = useQuery({ queryKey: ["brands"], queryFn: () => discoveryApi.brands() });
  const branches = useQuery({ queryKey: ["branches", brandId], queryFn: () => discoveryApi.branches(brandId || undefined) });
  const filtered = branches.data || [];
  const pages = Math.ceil(filtered.length / PAGE_SIZE);
  const setFilter = (brand = brandId, targetPage = 1) => setParams({ ...(brand && { brand }), ...(targetPage > 1 && { page: String(targetPage) }) });
  return <main className="public-main"><PageHeader eyebrow="Storefront" title="Discover kitchens" description="Browse active Saturdays locations by brand." />
    <State loading={brands.isLoading} error={brands.error} empty={false}><div className="filter-row"><button className={!brandId ? "selected" : ""} onClick={() => setFilter("")}>All brands</button>{brands.data?.map((brand) => <button className={brandId === brand.id ? "selected" : ""} key={brand.id} onClick={() => setFilter(brand.id)}>{brand.name}</button>)}</div></State>
    <State loading={branches.isLoading} error={branches.error} empty={!filtered.length}><div className="restaurant-grid">{filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).map((item) => <BranchCard branch={item} brandName={brands.data?.find((brand) => brand.id === item.brand_id)?.name} key={item.id} />)}</div><PaginationControls page={page} pages={pages} total={filtered.length} onPageChange={(next) => setFilter(brandId, next)} /></State>
  </main>;
}

export function BrandDetailPage() {
  const { brandId = "" } = useParams();
  const brand = useQuery({ queryKey: ["brand", brandId], queryFn: () => discoveryApi.brand(brandId) });
  const branches = useQuery({ queryKey: ["branches", brandId], queryFn: () => discoveryApi.branches(brandId) });
  return <main className="public-main"><State loading={brand.isLoading} error={brand.error} empty={!brand.data}>{brand.data && <><section className="store-hero" style={brand.data.banner_url ? { backgroundImage: `linear-gradient(100deg,#173e27ee,#173e2788),url(${brand.data.banner_url})` } : undefined}><div><span className="product-eyebrow">Brand</span><h1>{brand.data.name}</h1><p>{brand.data.description || "Food prepared with care."}</p><div className="tag-row">{brand.data.cuisine_types?.map((item) => <span key={item}>{item}</span>)}</div></div></section><PageHeader title="Locations" description="Choose a branch to see its live menu." /><State loading={branches.isLoading} error={branches.error} empty={!branches.data?.length}><div className="restaurant-grid">{branches.data?.map((item) => <BranchCard branch={item} key={item.id} />)}</div></State></>}</State></main>;
}

function ResultCard({ item }: { item: SearchItem }) {
  return <Card className="result-card"><div><span className="product-eyebrow">{item.entity_type}</span><h3>{item.title}</h3><p>{item.description || item.branch_name || item.brand_name}</p>{item.distance_km !== undefined && <small>{item.distance_km.toFixed(1)} km away</small>}</div>{item.price !== undefined && <b>{money(item.price)}</b>}{item.branch_id && <Link to={`/branches/${item.branch_id}`}>View storefront</Link>}</Card>;
}

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const [draft, setDraft] = useState(params.get("q") || "");
  const q = params.get("q") || "";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const number = (name: string) => params.get(name) ? Number(params.get(name)) : undefined;
  const filters = searchQuery({ q, type: params.get("type") || "all", cuisine: params.get("cuisine") || undefined, isVeg: params.get("veg") === "true", minPrice: number("min"), maxPrice: number("max"), latitude: number("lat"), longitude: number("lng"), radiusKm: number("radius"), sortBy: params.get("sort") || "relevance", page, limit: 20 });
  const results = useQuery({ queryKey: ["search", params.toString()], queryFn: () => discoveryApi.search(filters) });
  const suggestions = useQuery({ queryKey: ["suggestions", draft], queryFn: () => discoveryApi.suggestions(draft), enabled: draft.trim().length >= 2 && draft !== q });
  const update = (values: Record<string, string | undefined>) => { const next = new URLSearchParams(params); Object.entries(values).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key)); if (!("page" in values)) next.delete("page"); setParams(next); };
  const locate = () => navigator.geolocation?.getCurrentPosition((position) => update({ lat: String(position.coords.latitude), lng: String(position.coords.longitude) }));
  return <main className="public-main"><PageHeader eyebrow="Search" title="What are you craving?" />
    <form className="search-hero typeahead" onSubmit={(event) => { event.preventDefault(); update({ q: draft }); }}><div><input aria-label="Search food" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Restaurant, dish or cuisine" />{suggestions.data?.suggestions.length ? <div className="suggestions">{suggestions.data.suggestions.map((item) => <button type="button" key={`${item.type}-${item.text}`} onClick={() => { setDraft(item.text); update({ q: item.text }); }}><span>{item.text}</span><small>{item.type}</small></button>)}</div> : null}</div><button className="product-button primary">Search</button></form>
    <div className="advanced-filters"><select aria-label="Result type" value={params.get("type") || "all"} onChange={(event) => update({ type: event.target.value })}><option value="all">Everything</option><option value="restaurant">Restaurants</option><option value="dish">Dishes</option><option value="category">Categories</option></select><input aria-label="Cuisine" value={params.get("cuisine") || ""} onChange={(event) => update({ cuisine: event.target.value })} placeholder="Cuisine" /><input aria-label="Minimum price" type="number" min="0" value={params.get("min") || ""} onChange={(event) => update({ min: event.target.value })} placeholder="Min price" /><input aria-label="Maximum price" type="number" min="0" value={params.get("max") || ""} onChange={(event) => update({ max: event.target.value })} placeholder="Max price" /><select aria-label="Sort results" value={params.get("sort") || "relevance"} onChange={(event) => update({ sort: event.target.value })}><option value="relevance">Most relevant</option><option value="name">Name</option><option value="price_asc">Lowest price</option><option value="price_desc">Highest price</option><option value="distance">Nearest</option></select><label><input type="checkbox" checked={params.get("veg") === "true"} onChange={(event) => update({ veg: event.target.checked ? "true" : undefined })} /> Vegetarian</label><button type="button" onClick={locate}>Use my location</button>{params.get("lat") && <input aria-label="Radius in kilometers" type="number" min=".1" max="100" value={params.get("radius") || "10"} onChange={(event) => update({ radius: event.target.value })} />}</div>
    <State loading={results.isLoading} error={results.error} empty={!results.data?.results.length}><p className="result-count">{results.data?.total} matches{q ? ` for “${q}”` : ""}</p><div className="result-grid">{results.data?.results.map((item) => <ResultCard item={item} key={`${item.entity_type}-${item.id}`} />)}</div>{results.data && <PaginationControls page={page} pages={Math.ceil(results.data.total / 20)} total={results.data.total} onPageChange={(next) => update({ page: String(next) })} />}</State>
  </main>;
}

function ItemDialog({ item, onClose, onAdd }: { item: MenuItem; onClose: () => void; onAdd: (modifiers: MenuItem["modifiers"]) => void }) {
  const [selected, setSelected] = useState<string[]>([]);
  const modifiers = item.modifiers.filter((modifier) => selected.includes(modifier.id));
  return <div className="modal-backdrop" role="presentation" onMouseDown={onClose}><section className="item-modal" role="dialog" aria-modal="true" aria-labelledby="item-title" onMouseDown={(event) => event.stopPropagation()}><button className="modal-close" aria-label="Close item details" onClick={onClose}>Close</button><h2 id="item-title">{item.name}</h2><p>{item.description || (item.is_veg ? "Vegetarian" : "Non-vegetarian")}</p><StatusPill value={item.is_available ? "Available" : "Unavailable"} />{item.modifiers.length > 0 && <fieldset><legend>Choose extras</legend>{item.modifiers.map((modifier) => <label key={modifier.id}><input type="checkbox" checked={selected.includes(modifier.id)} onChange={() => setSelected((current) => current.includes(modifier.id) ? current.filter((id) => id !== modifier.id) : [...current, modifier.id])} /> {modifier.name} (+{money(modifier.price_delta)})</label>)}</fieldset>}<div className="card-actions"><b>{money(item.base_price + modifiers.reduce((sum, value) => sum + value.price_delta, 0))}</b><button className="primary" disabled={!item.is_available} onClick={() => onAdd(modifiers)}>Add to cart</button></div></section></div>;
}

export function BranchPage() {
  const { branchId = "" } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { notify } = useToast();
  const [item, setItem] = useState<MenuItem>();
  const [pending, setPending] = useState<{ item: MenuItem; modifiers: MenuItem["modifiers"] }>();
  const branch = useQuery({ queryKey: ["branch", branchId], queryFn: () => discoveryApi.branch(branchId) });
  const menu = useQuery({ queryKey: ["menu", branchId], queryFn: () => discoveryApi.menu(branchId) });
  const rating = useQuery({ queryKey: ["rating", branchId], queryFn: () => discoveryApi.rating(branchId) });
  const reviews = useQuery({ queryKey: ["reviews", branchId], queryFn: () => discoveryApi.reviews(branchId) });
  const cart = useQuery({ queryKey: ["cart"], queryFn: customerApi.cart, enabled: user?.role === "Customer", retry: false });
  const add = useMutation({ mutationFn: ({ target, modifiers }: { target: MenuItem; modifiers: MenuItem["modifiers"] }) => customerApi.addCartItem({ branch_id: branchId, menu_item_id: target.id, quantity: 1, selected_modifiers: modifiers }), onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["cart"] }); setItem(undefined); setPending(undefined); notify("Added to cart."); } });
  const favorite = useMutation({ mutationFn: () => customerApi.addFavorite(branchId), onSuccess: () => notify("Saved to favorites.") });
  const requestAdd = (target: MenuItem, modifiers: MenuItem["modifiers"]) => {
    if (user?.role !== "Customer") { navigate("/auth/login", { state: { from: `/branches/${branchId}` } }); return; }
    if (hasCrossBranchConflict(cart.data, branchId)) setPending({ item: target, modifiers }); else add.mutate({ target, modifiers });
  };
  const replaceCart = async () => { if (!pending) return; await customerApi.clearCart(); add.mutate({ target: pending.item, modifiers: pending.modifiers }); };
  return <main className="public-main"><State loading={branch.isLoading} error={branch.error} empty={!branch.data}>{branch.data && <><section className="store-hero"><div><span className="product-eyebrow">Branch storefront</span><h1>{branch.data.name}</h1><p>{branch.data.address_text}</p><div className="store-meta"><StatusPill value={branch.data.is_active} /><span>{rating.data ? `${rating.data.average_rating.toFixed(1)} / 5 · ${rating.data.total_reviews} reviews` : "New"}</span><span>{branch.data.opening_time}–{branch.data.closing_time}</span></div></div>{user?.role === "Customer" && <button onClick={() => favorite.mutate()}>Save favorite</button>}</section><PageHeader eyebrow="Live menu" title={menu.data?.name || "Menu"} /><State loading={menu.isLoading} error={menu.error} empty={!menu.data?.categories.length}>{menu.data?.categories.map((category) => <section className="menu-section" key={category.id}><h2>{category.name}</h2><div className="menu-grid">{category.items.map((menuItem) => <Card className="menu-item" key={menuItem.id}><button className="menu-item-detail" onClick={() => setItem(menuItem)}><h3>{menuItem.name}</h3><p>{menuItem.description || (menuItem.is_veg ? "Vegetarian" : "Non-vegetarian")}</p><b>{money(menuItem.base_price)}</b></button><button className="primary" disabled={!menuItem.is_available || add.isPending} onClick={() => requestAdd(menuItem, [])}>{menuItem.is_available ? "Add" : "Unavailable"}</button></Card>)}</div></section>)}</State>{add.error && <Notice title="Could not add item">{add.error instanceof ApiError ? add.error.message : "Please try again."}</Notice>}<PageHeader eyebrow="Community" title="Ratings and reviews" /><State loading={reviews.isLoading} error={reviews.error} empty={!reviews.data?.length}><div className="review-grid">{reviews.data?.map((review) => <Card key={review.id}><b>{review.rating} / 5</b><p>{review.comment || "Rating only"}</p>{review.merchant_reply && <small>Restaurant reply: {review.merchant_reply}</small>}</Card>)}</div></State></>}</State>{item && <ItemDialog item={item} onClose={() => setItem(undefined)} onAdd={(modifiers) => requestAdd(item, modifiers)} />}<ConfirmDialog open={Boolean(pending)} title="Start a new cart?" description="Your cart contains food from another branch. Keep it, or clear it and add this item." confirmLabel="Clear cart and add" destructive onCancel={() => setPending(undefined)} onConfirm={() => void replaceCart()} /></main>;
}

export function CouponsPage() {
  const [params] = useSearchParams();
  const selected = params.get("coupon");
  const query = useQuery({ queryKey: ["coupons"], queryFn: () => discoveryApi.coupons() });
  const detail = useQuery({ queryKey: ["coupon", selected], queryFn: () => discoveryApi.coupon(selected!), enabled: Boolean(selected) });
  return <main className="public-main"><PageHeader eyebrow="Offers" title="Current coupons" description="Final eligibility is confirmed at checkout." />{selected && <State loading={detail.isLoading} error={detail.error} empty={!detail.data}>{detail.data && <Card className="coupon-detail"><Link to="/coupons">Back to offers</Link><h1>{detail.data.code}</h1><p>{detail.data.discount_type === "PERCENTAGE" ? `${detail.data.discount_value}% off` : `${money(detail.data.discount_value)} off`}</p><span>Minimum order {money(detail.data.min_order_amount)}</span></Card>}</State>}<State loading={query.isLoading} error={query.error} empty={!query.data?.length}><div className="coupon-grid">{query.data?.map((coupon) => <Link to={`/coupons?coupon=${coupon.id}`} key={coupon.id}><Card className="coupon"><span>{coupon.is_platform_coupon ? "Platform offer" : "Restaurant offer"}</span><h2>{coupon.code}</h2><p>{coupon.discount_type === "PERCENTAGE" ? `${coupon.discount_value}% off` : `${money(coupon.discount_value)} off`} · Minimum {money(coupon.min_order_amount)}</p><small>Valid until {new Date(coupon.valid_until).toLocaleDateString("en-IN")}</small></Card></Link>)}</div></State></main>;
}

export { BrandsPage } from "./PublicPages";
