import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthLayout, PublicLayout, WorkspaceLayout } from "./layouts";
import { RoleGuard, WorkbenchGuard } from "./guards";
import { apiWorkbenchEnabled } from "./routing";
import {
  AdminCouponsPage, AdminDashboard, AdminPaymentsPage, AdminReportsPage, AdminUsersPage,
  ApprovalsPage, AuditPage, BannersPage, FeatureFlagsPage, ModerationPage, SystemStatusPage,
} from "../pages/AdminPages";
import {
  AddressesPage, CartPage, CheckoutPage, CustomerDashboard, FavoritesPage, NotificationsPage,
  OrderDetailPage, OrdersPage, PaymentPage, ProfilePage,
} from "../pages/CustomerExperience";
import { AuthFlowPage, SecurityPage } from "../pages/AuthPages";
import { KitchenBoardPage, KitchenInventoryPage, KitchenOrderLookupPage } from "../pages/KitchenPages";
import {
  BranchManagerDashboard, BranchSettingsPage, InventoryPage, KitchensPage, MenuManagementPage,
  MerchantBranchesPage, MerchantBrandsPage, MerchantCouponsPage, MerchantDashboard, MerchantOrderDetailPage,
  MerchantOrdersPage, MerchantPaymentsPage, MerchantReviewsPage, MerchantStaffPage,
  OnboardingPage, ReportsPage, SubscriptionPage,
} from "../pages/MerchantPages";
import {
  BranchPage, BrandDetailPage, BrandsPage, CouponsPage, DiscoverPage, HomePage, SearchPage,
} from "../pages/PublicExperience";

const ApiWorkbench = lazy(() => import("../App"));
const workbenchEnabled = apiWorkbenchEnabled(import.meta.env.MODE, import.meta.env.VITE_ENABLE_API_WORKBENCH);
const allRoles = ["Customer", "KitchenStaff", "BranchManager", "MerchantOwner", "PlatformAdmin"] as const;

const workspace = (children: React.ReactNode) => <Route element={<WorkspaceLayout />}>{children}</Route>;

export function ProductRoutes() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<HomePage />} />
        <Route path="discover" element={<DiscoverPage />} />
        <Route path="brands" element={<BrandsPage />} />
        <Route path="brands/:brandId" element={<BrandDetailPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="coupons" element={<CouponsPage />} />
        <Route path="branches/:branchId" element={<BranchPage />} />
      </Route>
      <Route element={<AuthLayout />}>
        <Route path="auth" element={<Navigate to="/auth/login" replace />} />
        <Route path="auth/login" element={<AuthFlowPage mode="login" />} />
        <Route path="auth/register" element={<AuthFlowPage mode="register" />} />
        <Route path="auth/forgot-password" element={<AuthFlowPage mode="forgot" />} />
        <Route path="auth/reset-password" element={<AuthFlowPage mode="reset" />} />
        <Route path="auth/verify-email" element={<AuthFlowPage mode="verify" />} />
        <Route path="auth/resend-verification" element={<AuthFlowPage mode="resend" />} />
        <Route path="auth/invitations/accept" element={<AuthFlowPage mode="invitation" />} />
      </Route>
      <Route element={<RoleGuard roles={["Customer"]} />}>{workspace(<>
        <Route path="customer" element={<CustomerDashboard />} />
        <Route path="customer/profile" element={<ProfilePage />} />
        <Route path="customer/addresses" element={<AddressesPage />} />
        <Route path="customer/favorites" element={<FavoritesPage />} />
        <Route path="customer/cart" element={<CartPage />} />
        <Route path="customer/checkout" element={<CheckoutPage />} />
        <Route path="customer/orders" element={<OrdersPage />} />
        <Route path="customer/orders/:orderId" element={<OrderDetailPage />} />
        <Route path="customer/notifications" element={<NotificationsPage />} />
        <Route path="customer/payments/new" element={<PaymentPage />} />
      </>)}</Route>
      <Route element={<RoleGuard roles={["MerchantOwner"]} />}>{workspace(<>
        <Route path="merchant" element={<MerchantDashboard />} />
        <Route path="merchant/onboarding" element={<OnboardingPage />} />
        <Route path="merchant/brands" element={<MerchantBrandsPage />} />
        <Route path="merchant/branches" element={<MerchantBranchesPage />} />
        <Route path="merchant/kitchens" element={<KitchensPage />} />
        <Route path="merchant/menu" element={<MenuManagementPage />} />
        <Route path="merchant/inventory" element={<InventoryPage />} />
        <Route path="merchant/orders" element={<MerchantOrdersPage />} />
        <Route path="merchant/orders/:orderId" element={<MerchantOrderDetailPage />} />
        <Route path="merchant/reviews" element={<MerchantReviewsPage />} />
        <Route path="merchant/coupons" element={<MerchantCouponsPage />} />
        <Route path="merchant/staff" element={<MerchantStaffPage />} />
        <Route path="merchant/reports" element={<ReportsPage />} />
        <Route path="merchant/subscription" element={<SubscriptionPage />} />
        <Route path="merchant/payments" element={<MerchantPaymentsPage />} />
      </>)}</Route>
      <Route element={<RoleGuard roles={["KitchenStaff"]} />}>{workspace(<>
        <Route path="kitchen" element={<KitchenBoardPage />} />
        <Route path="kitchen/orders/:orderId" element={<KitchenOrderLookupPage />} />
        <Route path="kitchen/inventory" element={<KitchenInventoryPage />} />
      </>)}</Route>
      <Route element={<RoleGuard roles={["BranchManager"]} />}>{workspace(<>
        <Route path="branch-manager" element={<BranchManagerDashboard />} />
        <Route path="branch-manager/settings" element={<BranchSettingsPage />} />
        <Route path="branch-manager/kitchens" element={<KitchensPage />} />
        <Route path="branch-manager/menu" element={<MenuManagementPage />} />
        <Route path="branch-manager/inventory" element={<InventoryPage />} />
        <Route path="branch-manager/orders" element={<MerchantOrdersPage />} />
        <Route path="branch-manager/orders/:orderId" element={<MerchantOrderDetailPage />} />
        <Route path="branch-manager/payments" element={<MerchantPaymentsPage />} />
        <Route path="branch-manager/coupons" element={<MerchantCouponsPage />} />
        <Route path="branch-manager/reports" element={<ReportsPage />} />
      </>)}</Route>
      <Route element={<RoleGuard roles={["PlatformAdmin"]} />}>{workspace(<>
        <Route path="admin" element={<AdminDashboard />} />
        <Route path="admin/approvals" element={<ApprovalsPage />} />
        <Route path="admin/users" element={<AdminUsersPage />} />
        <Route path="admin/moderation" element={<ModerationPage />} />
        <Route path="admin/reports" element={<AdminReportsPage />} />
        <Route path="admin/banners" element={<BannersPage />} />
        <Route path="admin/coupons" element={<AdminCouponsPage />} />
        <Route path="admin/flags" element={<FeatureFlagsPage />} />
        <Route path="admin/payments" element={<AdminPaymentsPage />} />
        <Route path="admin/audit" element={<AuditPage />} />
        <Route path="admin/status" element={<SystemStatusPage />} />
        <Route element={<WorkbenchGuard enabled={workbenchEnabled} />}>
          <Route path="dev/api" element={<Suspense fallback={<div className="full-loader">Loading API workbench...</div>}><ApiWorkbench /></Suspense>} />
        </Route>
      </>)}</Route>
      <Route element={<RoleGuard roles={[...allRoles]} />}>{workspace(<Route path="account/security" element={<SecurityPage />} />)}</Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
