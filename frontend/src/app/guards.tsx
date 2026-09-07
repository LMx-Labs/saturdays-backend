import { Navigate, Outlet, useLocation } from "react-router-dom";
import type { Role } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { roleHome } from "./routing";

export function RoleGuard({ roles }: { roles: Role[] }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="full-loader" role="status"><span className="loader" />Restoring your session...</div>;
  if (!user) return <Navigate to="/auth/login" replace state={{ from: `${location.pathname}${location.search}` }} />;
  if (!roles.includes(user.role)) return <Navigate to={roleHome(user.role)} replace />;
  return <Outlet />;
}

export function WorkbenchGuard({ enabled }: { enabled: boolean }) {
  const { user } = useAuth();
  if (!enabled || user?.role !== "PlatformAdmin") return <Navigate to={user ? roleHome(user.role) : "/auth/login"} replace />;
  return <Outlet />;
}
