export type Brand = {
  id: string;
  merchant_id: string;
  name: string;
  logo_url?: string;
  banner_url?: string;
  description?: string;
  cuisine_types?: string[];
};

export type Branch = {
  id: string;
  brand_id: string;
  name: string;
  address_text: string;
  latitude?: number;
  longitude?: number;
  is_active: boolean;
  opening_time: string;
  closing_time: string;
};

export type MenuItem = {
  id: string;
  category_id: string;
  name: string;
  description?: string;
  base_price: number;
  image_url?: string;
  is_available: boolean;
  is_veg: boolean;
  modifiers: Array<{ id: string; name: string; price_delta: number }>;
};

export type Menu = {
  id: string;
  branch_id: string;
  name: string;
  is_active: boolean;
  categories: Array<{ id: string; name: string; display_order: number; items: MenuItem[] }>;
};

export type SearchItem = {
  entity_type: string;
  id: string;
  title: string;
  description?: string;
  branch_id?: string;
  branch_name?: string;
  brand_name?: string;
  price?: number;
  is_veg?: boolean;
  is_available: boolean;
  image_url?: string;
  cuisine_types?: string[];
  distance_km?: number;
};

export type SearchResponse = {
  query: string;
  total: number;
  restaurants: SearchItem[];
  dishes: SearchItem[];
  categories: SearchItem[];
  results: SearchItem[];
};
