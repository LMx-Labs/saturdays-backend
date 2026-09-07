export type Merchant = {
  id: string;
  owner_user_id: string;
  business_name: string;
  legal_entity_name: string;
  fssai_license_number: string;
  gstin?: string;
  bank_account_number?: string;
  bank_ifsc_code?: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type InventoryItem = {
  id: string;
  branch_id: string;
  menu_item_id: string;
  quantity: number;
  is_in_stock: boolean;
  created_at: string;
  updated_at: string;
};

export type InventoryDetail = InventoryItem & {
  menu_item: {
    id: string;
    name: string;
    base_price: number;
    is_available: boolean;
  };
};

export type InventoryLog = {
  id: string;
  inventory_item_id: string;
  change_amount: number;
  previous_quantity: number;
  new_quantity: number;
  reason: string;
  created_at: string;
};

export type Kitchen = {
  id: string;
  branch_id: string;
  name: string;
  is_active: boolean;
};

export type Subscription = {
  id: string;
  merchant_id: string;
  plan_tier: string;
  billing_cycle: string;
  status: string;
  commission_rate_percentage: number;
  max_branches: number;
  valid_until: string;
  created_at: string;
  updated_at: string;
};

export type SalesSummary = {
  order_count: number;
  gross_sales: number;
  discounts: number;
  net_sales: number;
  average_order_value: number;
};

export type BranchPerformance = SalesSummary & {
  branch_id: string;
  completed_orders: number;
  cancelled_orders: number;
};

export type PaymentRefundSummary = {
  payment_count: number;
  payment_amount: number;
  refund_count: number;
  refund_amount: number;
};

export type CommissionSummary = {
  commission_count: number;
  gross_order_amount: number;
  commission_amount: number;
  merchant_net_payout: number;
};

export type PlatformOperations = {
  merchant_count: number;
  approved_merchant_count: number;
  branch_count: number;
  customer_count: number;
  order_count: number;
  gross_sales: number;
  generated_at: string;
};
