import { NavLink, Navigate, Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { customerApi } from "../api/modules";
import { useAuth, roleHome } from "../auth/AuthProvider";
import { roleLabel } from "./capabilities";

const workspaceNav: Record<string, Array<[string, string]>> = {
  "/customer": [
    ["Overview", "/customer"], ["Profile", "/customer/profile"], ["Addresses", "/customer/addresses"],
    ["Favorites", "/customer/favorites"], ["Cart", "/customer/cart"], ["Orders", "/customer/orders"],
    ["Notifications", "/customer/notifications"],
  ],
  "/merchant": [
    ["Overview", "/merchant"], ["Onboarding", "/merchant/onboarding"], ["Brands", "/merchant/brands"],
    ["Branches", "/merchant/branches"], ["Kitchens", "/merchant/kitchens"], ["Menu", "/merchant/menu"],
    ["Inventory", "/merchant/inventory"], ["Orders", "/merchant/orders"], ["Reviews", "/merchant/reviews"],
    ["Coupons", "/merchant/coupons"], ["Staff", "/merchant/staff"], ["Reports", "/merchant/reports"],
    ["Subscription", "/merchant/subscription"], ["Payments", "/merchant/payments"],
  ],
  "/branch-manager": [
    ["Overview", "/branch-manager"], ["Branch settings", "/branch-manager/settings"],
    ["Kitchens", "/branch-manager/kitchens"], ["Menu", "/branch-manager/menu"],
    ["Inventory", "/branch-manager/inventory"], ["Orders", "/branch-manager/orders"],
    ["Coupons", "/branch-manager/coupons"], ["Payments", "/branch-manager/payments"], ["Reports", "/branch-manager/reports"],
  ],
  "/kitchen": [["Live board", "/kitchen"], ["Inventory", "/kitchen/inventory"]],
  "/admin": [
    ["Overview", "/admin"], ["Reports", "/admin/reports"], ["Merchants", "/admin/approvals"],
    ["Users", "/admin/users"], ["Moderation", "/admin/moderation"], ["Banners", "/admin/banners"],
    ["Coupons", "/admin/coupons"], ["Feature flags", "/admin/flags"], ["Payments", "/admin/payments"],
    ["Audit log", "/admin/audit"], ["System status", "/admin/status"],
  ],
};

function Logo() {
  return <NavLink to="/" className="product-logo"><span>S</span><b>Saturdays</b></NavLink>;
}

export function PublicLayout() {
  const { user } = useAuth();
  return (
    <div className="product-root">
      <header className="public-nav">
        <Logo />
        <nav>
          <NavLink to="/discover">Discover</NavLink>
          <NavLink to="/brands">Brands</NavLink>
          <NavLink to="/search">Search</NavLink>
          <NavLink to="/coupons">Offers</NavLink>
        </nav>
        <NavLink className="product-button primary" to={user ? roleHome(user.role) : "/auth/login"}>
          {user ? "Open workspace" : "Sign in"}
        </NavLink>
      </header>
      <Outlet />
      <footer className="product-footer">
        <Logo />
        <span>Campus food, made dependable.</span>
        {user?.role === "PlatformAdmin" && <NavLink to="/dev/api">Developer API</NavLink>}
      </footer>
    </div>
  );
}

export function AuthLayout() {
  const { user } = useAuth();
  const location = useLocation();
  const signedInAllowed = ["/auth/verify-email", "/auth/resend-verification", "/auth/reset-password"];
  if (user && !signedInAllowed.includes(location.pathname)) return <Navigate to={roleHome(user.role)} replace />;
  return <div className="auth-page"><Logo /><Outlet /></div>;
}

export function WorkspaceLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const notifications = useQuery({
    queryKey: ["notifications"],
    queryFn: customerApi.notifications,
    enabled: user?.role === "Customer",
    refetchInterval: 30000,
  });
  const unread = notifications.data?.filter((item) => !item.is_read).length || 0;
  if (!user) return null;
  const root = Object.keys(workspaceNav).find((key) => location.pathname.startsWith(key)) || roleHome(user.role);
  return (
    <div className="workspace">
      <aside className="workspace-sidebar">
        <Logo />
        <div className="workspace-user">
          <span>{user.email.slice(0, 1).toUpperCase()}</span>
          <div><b>{user.email}</b><small>{roleLabel[user.role]}</small></div>
        </div>
        <nav>
          {workspaceNav[root].map(([label, href]) => (
            <NavLink key={href} to={href} end={href === root}>{label}{label === "Notifications" && unread > 0 ? ` (${unread})` : ""}</NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <NavLink to="/discover">Public storefront</NavLink>
          <button onClick={() => void logout()}>Sign out</button>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="workspace-mobile"><Logo /><span>{roleLabel[user.role]}</span></header>
        <main><Outlet /></main>
      </div>
    </div>
  );
}
