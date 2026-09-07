export type Cart = {
  id: string;
  branch_id: string;
  total_items: number;
  subtotal: number;
  is_expired: boolean;
  items: Array<{
    id: string;
    menu_item_id: string;
    menu_item_name?: string;
    quantity: number;
    unit_price?: number;
    subtotal?: number;
    is_available?: boolean;
    selected_modifiers?: Array<{ id?: string; name: string; price_delta?: number }>;
  }>;
};

export type CartValidation = {
  is_valid: boolean;
  subtotal: number;
  total_items: number;
  issues: Array<{ code: string; message: string; item_id?: string; menu_item_id?: string }>;
};

export type CheckoutQuote = {
  is_valid: boolean;
  quote_id?: string;
  quote_expires_at?: string;
  currency: string;
  customer_id: string;
  branch_id: string;
  branch_name: string;
  kitchen_id?: string;
  cart_id: string;
  subtotal: number;
  tax_amount: number;
  delivery_fee: number;
  discount_amount: number;
  final_payable_amount: number;
  coupon_code?: string;
  items: Array<{
    menu_item_id: string;
    name: string;
    unit_price: number;
    quantity: number;
    subtotal: number;
    is_available: boolean;
  }>;
  issues: Array<{ code: string; message: string }>;
};

export const orderStatuses = ["PLACED", "ACCEPTED", "PREPARING", "READY", "COMPLETED", "CANCELLED"] as const;
export type OrderStatus = typeof orderStatuses[number];

export type Order = {
  id: string;
  branch_id: string;
  total_amount: number;
  subtotal?: number;
  discount_amount?: number;
  tax_amount?: number;
  delivery_fee?: number;
  currency?: string;
  status: OrderStatus;
  cancellation_reason?: string;
  delivery_address_snapshot: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  items: Array<{ id: string; item_name_snapshot: string; quantity: number; unit_price_snapshot: number }>;
  status_logs: Array<{ id: string; previous_status?: string; new_status: OrderStatus; created_at: string }>;
};

export type Address = {
  id: string;
  address_line: string;
  building_name?: string;
  campus_zone: string;
  is_primary: boolean;
};

export type PaymentTransaction = {
  id: string;
  transaction_type: string;
  amount: number;
  status: string;
  razorpay_payment_id?: string;
  created_at: string;
};

export type Payment = {
  id: string;
  order_id: string;
  amount: number;
  currency: string;
  provider: string;
  provider_order_id?: string;
  created_at: string;
  transactions: PaymentTransaction[];
};

export type PaymentIntent = {
  payment_id: string;
  order_id: string;
  razorpay_order_id: string;
  amount: number;
  currency: string;
  provider: string;
  provider_key_id?: string;
};

export type NotificationPreferences = {
  email_enabled: boolean;
  sms_enabled: boolean;
  push_enabled: boolean;
  order_updates: boolean;
  marketing: boolean;
};

export type Review = {
  id: string;
  order_id: string;
  branch_id: string;
  rating: number;
  comment?: string;
  merchant_reply?: string;
  is_hidden: boolean;
  created_at: string;
};

export type Coupon = {
  id: string;
  code: string;
  discount_type: string;
  discount_value: number;
  min_order_amount: number;
  valid_until: string;
  branch_id?: string;
  is_active: boolean;
  is_platform_coupon: boolean;
};

export type Notification = {
  id: string;
  channel: string;
  subject?: string;
  body: string;
  status: string;
  is_read: boolean;
  read_at?: string;
  created_at: string;
};
