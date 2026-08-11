import { useEffect, useMemo, useState } from "react";
import {
  supabase,
  type ProductOverview,
  type CompetitorCoverage,
  type OutOfStockGap,
} from "./supabase";

export const vnd = (n: number) =>
  new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" }).format(n);

// Relative age of a scraped_at timestamp, e.g. "2h ago", "Today 06:35", "Yesterday", "3d ago".
// latest_prices only shows the most recent run, so this is normally very fresh.
export function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const then = new Date(iso);
  const mins = Math.round((Date.now() - then.getTime()) / 60000);
  if (mins < 1) return "Just Now";
  if (mins < 60) return `${mins}m trước`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h trước`;
  const days = Math.round(hrs / 24);
  return `${days} ngày trước`;
}

// True when a price is older than `hours` (default 24h) — for a "stale" badge.
export function isStale(iso: string | null, hours = 24): boolean {
  if (!iso) return false;
  return Date.now() - new Date(iso).getTime() > hours * 3600_000;
}

// Brands are stored capitalized ("Dell", "MSI"); the URL path uses lowercase.
export const brandToSlug = (b: string) => b.toLowerCase();
// Category is stored capitalized ("Laptop", "Monitor"); the URL path uses lowercase.
export const categoryToSlug = (c: string) => c.toLowerCase();

// Tên hiển thị đẹp cho danh mục — DB lưu dạng .capitalize() ("Ssd", "Pc", "Accesspoint") nên viết
// tắt bị xấu ("Ssd"). Map các trường hợp cần sửa; còn lại giữ nguyên nhãn DB.
const CATEGORY_DISPLAY: Record<string, string> = {
  ssd: "SSD",
  hdd: "HDD",
  pc: "PC",
  cpu: "CPU",
  vga: "Card màn hình",
  mainboard: "Mainboard",
  usb: "USB",
  ram: "RAM",
  memcard: "Thẻ nhớ",
  accesspoint: "Access Point",
  wlan_controller: "WLAN Controller",
  printer: "Máy in",
  scanner: "Máy scan",
  ups: "UPS",
  projector: "Máy chiếu",
  tv: "Tivi",
  tablet: "Máy tính bảng",
};
export const categoryDisplay = (c: string) => CATEGORY_DISPLAY[c.toLowerCase()] ?? c;

// Danh mục ĐANG BẬT hiển thị trên dashboard. Khớp với `enabled` trong scraper/config/sources.yaml.
// Set RỖNG = hiện TẤT CẢ danh mục có trong DB (đang bật hết). Muốn ẩn bớt để A/B test thì thêm tên
// danh mục CẦN ẨN vào DISABLED_CATEGORIES (chữ thường), ví dụ ["mouse","router",…].
const DISABLED_CATEGORIES = new Set<string>([
  "keyboard", "mouse", "combo", "usb", "webcam", // giá rẻ/ít giá trị
  "accesspoint", "wlan_controller",              // gear doanh nghiệp, đối thủ ít bán → ít match
]);
export const isEnabledCategory = (c: string) => !DISABLED_CATEGORIES.has(c.toLowerCase());

// Fetch product_overview, optionally FILTERED ON THE SERVER by an equality column (category/brand).
// Filtering in Postgres (via ?col=eq.val) means only the needed rows cross the wire — the landing
// still fetches everything (it needs all categories for the summary cards), but a category/brand
// page pulls just its slice instead of downloading the whole catalog to filter in JS.
type EqFilter = { column: "category" | "brand"; value: string } | null;

function useProductOverviewFiltered(filter: EqFilter, columns: string = "*") {
  const [rows, setRows] = useState<ProductOverview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const col = filter?.column;
  const val = filter?.value;
  useEffect(() => {
    (async () => {
      setLoading(true);
      // PostgREST trả TỐI ĐA 1000 dòng mỗi request. product_overview (đa danh mục) đã vượt 1000,
      // nên .select("*") trần chỉ lấy 1000 đầu → "Sản phẩm theo dõi" và thẻ danh mục bị thiếu.
      // Phân trang bằng .range() cho tới khi trang ngắn hơn PAGE (hết dữ liệu). Trang lọc theo
      // danh mục/brand thường <1000 nên chỉ 1 vòng, nhưng vẫn an toàn nếu về sau vượt ngưỡng.
      // `columns`: landing chỉ cần vài cột (KHÔNG cần blob prices_by_store ~1.1KB/dòng × 2000 dòng)
      // → truyền cột gọn để giảm ~90% payload; trang danh mục/brand vẫn dùng "*" vì có render giá.
      const PAGE = 1000;
      const all: ProductOverview[] = [];
      let from = 0;
      let failed: string | null = null;
      for (;;) {
        let query = supabase.from("product_overview").select(columns);
        // Case-INSENSITIVE exact match (no % wildcards) → ?<col>=ilike.<val>. Lets us pass the URL
        // slug ("monitor", "msi") straight through without reconstructing the stored label's exact
        // casing ("Monitor", "MSI") — which .capitalize() can't do for acronyms/multi-word names.
        if (col && val) query = query.ilike(col, val);
        const { data, error } = await query.range(from, from + PAGE - 1);
        if (error) {
          failed = error.message;
          break;
        }
        // `columns` động khiến PostgREST mất suy luận kiểu → cast qua unknown. Landing chỉ đọc các
        // cột đã yêu cầu (category/pct_vs_mean/last_scraped); các cột không select là undefined.
        const batch = (data ?? []) as unknown as ProductOverview[];
        all.push(...batch);
        if (batch.length < PAGE) break; // trang cuối → hết
        from += PAGE;
      }
      if (failed) setError(failed);
      else setRows(all);
      setLoading(false);
    })();
  }, [col, val]);

  return { rows, loading, error };
}

// Landing page: cần MỌI danh mục cùng lúc cho thẻ tổng kết, nhưng CHỈ đọc category/pct_vs_mean/
// last_scraped (đếm, TB so thị trường, "cập nhật lúc"). KHÔNG cần prices_by_store & các cột giá →
// chỉ select 3 cột này để bỏ ~90% payload (blob prices_by_store ~1.1KB × 2000 dòng).
// + our_price,lowest_price: cần cho beatenCount ("bị đối thủ bán rẻ hơn" = our_price > lowest_price).
// Hai cột số nhỏ — thứ nặng cần tránh là blob prices_by_store (~1.1KB/dòng), vẫn không select.
const LANDING_COLUMNS = "category,brand,pct_vs_mean,last_scraped,our_price,lowest_price";
export function useProductOverview() {
  return useProductOverviewFiltered(null, LANDING_COLUMNS);
}

// Category page: only this category's rows, filtered in Postgres. `category` is the DB label
// ("Monitor", "Ssd") — resolved from the URL slug by the caller.
export function useProductOverviewByCategory(category: string | null) {
  return useProductOverviewFiltered(category ? { column: "category", value: category } : null);
}

// Brand page: only this brand's rows, filtered in Postgres.
export function useProductOverviewByBrand(brand: string | null) {
  return useProductOverviewFiltered(brand ? { column: "brand", value: brand } : null);
}

// Per-competitor coverage across ALL categories (carries `category`); pages filter it client-side.
export function useCoverageAll() {
  const [coverage, setCoverage] = useState<CompetitorCoverage[]>([]);
  useEffect(() => {
    (async () => {
      const { data } = await supabase.from("competitor_coverage_all").select("*");
      setCoverage((data ?? []) as CompetitorCoverage[]);
    })();
  }, []);
  return coverage;
}

// Comparable coverage for ONE category — Postgres đã đếm "đối thủ có giá cho bao nhiêu sản phẩm ta
// còn hàng" (view comparable_coverage). Frontend chỉ đọc kết quả, không tự lặp prices_by_store.
export type ComparableCoverage = { name: string; products_matched: number; comparable_total: number };
export function useComparableCoverage(category: string | null) {
  const [rows, setRows] = useState<ComparableCoverage[]>([]);
  useEffect(() => {
    if (!category) return;
    (async () => {
      const { data } = await supabase
        .from("comparable_coverage")
        .select("name, products_matched, comparable_total")
        .ilike("category", category)
        .order("products_matched", { ascending: false });
      setRows((data ?? []) as ComparableCoverage[]);
    })();
  }, [category]);
  return rows;
}

// Products where WE are out of stock but a competitor is in stock — from the out_of_stock_gap view,
// already ranked (most competitors first, then cheapest). Pass a `category` (URL slug or DB label)
// to fetch only that department's gap, filtered IN POSTGRES (?category=ilike.<cat>); omit for all.
export function useOutOfStockGap(category?: string | null) {
  const [rows, setRows] = useState<OutOfStockGap[]>([]);
  useEffect(() => {
    (async () => {
      let query = supabase.from("out_of_stock_gap").select("*");
      if (category) query = query.ilike("category", category);
      const { data } = await query;
      setRows((data ?? []) as OutOfStockGap[]);
    })();
  }, [category]);
  return rows;
}

// Thời điểm bảng cache latest_prices_cache được refresh gần nhất (sau lần scrape cuối). Đọc 1 dòng
// refreshed_at → dashboard hiện "cập nhật lúc ...". Tự động lấy dữ liệu mới khi user reload trang (mỗi
// lần mount hook chạy lại query). Trong lúc DB đang refresh, user vẫn thấy giá cũ (delete+insert
// nguyên tử), tới khi reload sau khi refresh xong mới thấy giá mới.
export function useLastRefreshed(): string | null {
  const [ts, setTs] = useState<string | null>(null);
  useEffect(() => {
    (async () => {
      const { data } = await supabase
        .from("latest_prices_cache")
        .select("refreshed_at")
        .limit(1);
      setTs((data?.[0] as { refreshed_at?: string } | undefined)?.refreshed_at ?? null);
    })();
  }, []);
  return ts;
}

// OOS-gap COUNT per category — from the out_of_stock_gap_by_category view (Postgres does the
// group+count, returns ~11 rows). The landing only needs these numbers for its category cards,
// so it reads this instead of pulling every OOS row to count client-side.
export function useOutOfStockGapCounts(): Map<string, number> {
  const [counts, setCounts] = useState<Map<string, number>>(new Map());
  useEffect(() => {
    (async () => {
      const { data } = await supabase.from("out_of_stock_gap_by_category").select("category, n");
      const m = new Map<string, number>();
      for (const r of (data ?? []) as { category: string; n: number }[]) m.set(r.category, r.n);
      setCounts(m);
    })();
  }, []);
  return counts;
}

// price_activity: mỗi cửa hàng đổi giá bao nhiêu lần / sản phẩm / tuần (trung bình). Đã chuẩn hoá
// theo ĐỘ PHỦ (chia cho số sản phẩm) nên không lệch vì ta theo dõi cửa hàng nào nhiều hơn — đo đúng
// HÀNH VI đổi giá. is_self đánh dấu TNC để chart tô màu "chúng ta" khác đối thủ. Postgres tính sẵn.
export type PriceActivity = {
  competitor: string;
  is_self: boolean;
  week_start: string; // thứ Hai đầu tuần ISO (yyyy-mm-dd) — mốc để dropdown chọn tuần
  price_changes: number;
  products: number;
  // Số lần đổi giá trên mỗi 100 sản phẩm trong TUẦN đó (số nguyên) — chuẩn hoá theo độ phủ nhưng
  // nhân 100 để ra số nguyên dễ đọc thay vì phân số <1.
  changes_per_100_products_week: number;
};
// Trả về TẤT CẢ các dòng (cửa hàng × tuần). Dashboard lọc theo tuần được chọn ở dropdown, nên chỉ
// cần một truy vấn cho mọi tuần rồi lọc client-side (~9 cửa hàng × 3-4 tuần = vài chục dòng).
export function usePriceActivity(): PriceActivity[] {
  const [rows, setRows] = useState<PriceActivity[]>([]);
  useEffect(() => {
    (async () => {
      const { data } = await supabase
        .from("price_activity")
        .select("competitor, is_self, week_start, price_changes, products, changes_per_100_products_week")
        .order("week_start", { ascending: false });
      setRows((data ?? []) as PriceActivity[]);
    })();
  }, []);
  return rows;
}

// sku_price_trend_7d: diễn biến giá 7 ngày của TỪNG sản phẩm tại TỪNG cửa hàng — hiện cạnh giá của
// mỗi cửa hàng trong bảng sản phẩm. direction so giá ĐẦU vs CUỐI cửa sổ (net): giá bật lên rồi về chỗ
// cũ → changes=2 nhưng direction='flat'. View chỉ trả cặp CÓ đổi giá; cặp không có = không đổi ("—").
export type SkuPriceTrend = {
  product_sku: string;
  competitor: string;
  changes: number;
  increases: number;
  decreases: number;
  direction: "up" | "down" | "flat";
  pct_change: number | null;
};
// Khoá tra cứu: `${sku}|${competitor}` — bảng sản phẩm tra O(1) cho từng ô giá.
export function trendKey(sku: string, competitor: string): string {
  return `${sku}|${competitor}`;
}
export function useSkuPriceTrend7d(): Map<string, SkuPriceTrend> {
  const [map, setMap] = useState<Map<string, SkuPriceTrend>>(new Map());
  useEffect(() => {
    (async () => {
      // Phân trang như useProductOverview: PostgREST trả tối đa 1000 dòng/request.
      const PAGE = 1000;
      const all: SkuPriceTrend[] = [];
      let from = 0;
      for (;;) {
        const { data, error } = await supabase
          .from("sku_price_trend_7d")
          .select("product_sku, competitor, changes, increases, decreases, direction, pct_change")
          .range(from, from + PAGE - 1);
        if (error) break;
        const batch = (data ?? []) as SkuPriceTrend[];
        all.push(...batch);
        if (batch.length < PAGE) break;
        from += PAGE;
      }
      setMap(new Map(all.map((r) => [trendKey(r.product_sku, r.competitor), r])));
    })();
  }, []);
  return map;
}

// The "we're outcompeted" list for one category, sorted worst-first — straight from rows we already
// have (no extra query). Mirrors the needs_attention view: an IN-STOCK competitor is cheaper than us
// (we_are_lowest === false && num_sources >= 1), any margin — no 5% cushion. num_sources >= 1 drops
// products whose only cheaper "competitor" is out of stock (num_sources counts in-stock competitors).
// Worst-first = biggest price gap (our_price - lowest_price) descending.
// Ta bị đối thủ (CÒN HÀNG) bán rẻ hơn khi our_price > lowest_price. lowest_price (từ price_stats) chỉ
// tính đối thủ CÒN HÀNG, nên đây là so đúng với giá mua được. KHÔNG dùng we_are_lowest: cột đó tính cả
// đối thủ HẾT HÀNG → một giá OOS rẻ hơn làm we_are_lowest=false dù ta thật sự đang rẻ nhất trong hàng
// còn bán (đó là lý do trước đây lọt các dòng +0%/-1%). Giá bằng nhau (our=lowest) KHÔNG tính là bị cắt.
const beaten = (r: ProductOverview) =>
  r.our_price != null && r.lowest_price != null && r.our_price > r.lowest_price;

export function needsAttentionFor(rows: ProductOverview[], category: string): ProductOverview[] {
  // Sort by % ta đắt hơn đối thủ rẻ nhất (khớp cột hiển thị chỉ-%, giảm dần).
  const gapPct = (r: ProductOverview) => {
    const our = r.our_price ?? 0;
    const low = r.lowest_price ?? 0;
    return low > 0 ? (our - low) / low : 0;
  };
  return rows
    .filter((r) => r.category === category && beaten(r))
    .sort((a, b) => gapPct(b) - gapPct(a));
}

// pct_vs_mean is null for products with no competitor — excluded from the average.
// beatenCount counts products where an IN-STOCK competitor undercuts us (matches needsAttentionFor /
// the needs_attention view): we_are_lowest === false && num_sources >= 1. avgVsMarket stays the mean-
// based average (a separate, still-useful stat).
export type BrandStats = {
  count: number;
  avgVsMarket: number | null;
  beatenCount: number;
};

export function statsFor(rows: ProductOverview[]): BrandStats {
  const compared = rows.filter((r) => r.pct_vs_mean != null);
  const avg =
    compared.length > 0
      ? compared.reduce((s, r) => s + (r.pct_vs_mean ?? 0), 0) / compared.length
      : null;
  return {
    count: rows.length,
    avgVsMarket: avg == null ? null : Math.round(avg * 10) / 10,
    beatenCount: rows.filter(beaten).length,
  };
}

export function useBrandSummaries(rows: ProductOverview[]) {
  return useMemo(() => {
    const byBrand = new Map<string, ProductOverview[]>();
    for (const r of rows) {
      const arr = byBrand.get(r.brand) ?? [];
      arr.push(r);
      byBrand.set(r.brand, arr);
    }
    return Array.from(byBrand.entries())
      .map(([brand, brandRows]) => ({ brand, ...statsFor(brandRows) }))
      .sort((a, b) => b.count - a.count);
  }, [rows]);
}

// One summary row per category (count / avg-vs-market / # outcompeted) for the landing page.
export function useCategorySummaries(rows: ProductOverview[]) {
  return useMemo(() => {
    const byCat = new Map<string, ProductOverview[]>();
    for (const r of rows) {
      if (!isEnabledCategory(r.category)) continue; // ẩn danh mục đã tắt (A/B test)
      const arr = byCat.get(r.category) ?? [];
      arr.push(r);
      byCat.set(r.category, arr);
    }
    return Array.from(byCat.entries())
      .map(([category, catRows]) => ({ category, ...statsFor(catRows) }))
      .sort((a, b) => b.count - a.count);
  }, [rows]);
}
