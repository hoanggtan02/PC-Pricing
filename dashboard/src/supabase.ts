import { createClient } from "@supabase/supabase-js";

// Use the *anon* (public) key — the dashboard only reads data. Never the service_role key here.
const url = import.meta.env.VITE_SUPABASE_URL as string;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

if (!url || !key) {
  console.warn(
    "Missing VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY. Copy .env.example to .env and fill them in.",
  );
}

export const supabase = createClient(url ?? "", key ?? "");

// One display-ready row per product from the `product_overview` view; the SQL does all the work.
export type ProductOverview = {
  sku: string;
  product_name: string;
  brand: string;
  category: string;
  // ordered cheapest-first by SQL — render as-is
  prices_by_store: {
    store: string;
    price: number;
    is_self: boolean;
    url: string | null;
    in_stock: boolean;
    is_flash_sale?: boolean;
  }[];
  cheapest_competitor: string | null;
  lowest_store: string | null;
  we_are_lowest: boolean | null;
  our_price: number | null;
  // when this product's prices were last scraped (newest across its stores), ISO timestamp
  last_scraped: string | null;
  // null for products no competitor stocks
  num_sources: number | null;
  mean_price: number | null;
  median_price: number | null;
  lowest_price: number | null;
  highest_price: number | null;
  delta_vs_mean: number | null;
  pct_vs_mean: number | null;
};

// `brand` is set when read from competitor_coverage (per-brand), undefined from the _all rollup.
// `category` is present on the all-category views (competitor_coverage_all), used to filter per tab.
export type CompetitorCoverage = {
  name: string;
  is_self: boolean;
  brand?: string;
  category?: string;
  products_matched: number;
  avg_price: number;
};

// One row per product where WE are out of stock but a competitor is in stock (out_of_stock_gap view).
export type OutOfStockGap = {
  sku: string;
  product_name: string;
  brand: string;
  category: string;
  competitors_in_stock: number;
  cheapest_competitor: string | null;
  cheapest_competitor_price: number | null;
  cheapest_competitor_url: string | null;
  our_url: string | null;
};
