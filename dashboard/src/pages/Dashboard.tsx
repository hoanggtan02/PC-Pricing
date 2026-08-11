import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Card,
  Title,
  Text,
  Metric,
  Grid,
  Badge,
  BarChart,
  Select,
  SelectItem,
} from "@tremor/react";
import {
  timeAgo,
  categoryToSlug,
  useProductOverview,
  useCoverageAll,
  useOutOfStockGapCounts,
  useLastRefreshed,
  usePriceActivity,
  type PriceActivity,
  statsFor,
  useCategorySummaries,
  isEnabledCategory,
  categoryDisplay,
} from "../data";

// Green when we're at/under market (good), red when priced above.
function VsMarket({ pct }: { pct: number | null }) {
  if (pct == null) return <>—</>;
  const above = pct > 0;
  return (
    <Badge color={above ? "red" : "green"}>
      {above ? "+" : ""}
      {pct}%
    </Badge>
  );
}

// "2026-07-14" → "14–20 Th7" (khoảng thứ Hai → Chủ nhật của tuần) cho nhãn dropdown.
function weekLabel(weekStart: string): string {
  const mon = new Date(weekStart + "T00:00:00");
  const sun = new Date(mon);
  sun.setDate(mon.getDate() + 6);
  const d = (x: Date) => x.getDate();
  return `${d(mon)}–${d(sun)} Th${sun.getMonth() + 1}`;
}

// Tooltip của bar chart: ngoài con số cuối cùng, hiện luôn SỐ LIỆU THÔ tạo ra nó — bao nhiêu lần đổi
// giá trên bao nhiêu sản phẩm — kèm phép tính, để người xem tự kiểm chứng.
function ActivityTooltip({
  active,
  label,
  rows,
}: {
  active?: boolean;
  label?: string | number;
  rows: Map<string, PriceActivity>;
}) {
  if (!active || label == null) return null;
  const r = rows.get(String(label));
  if (!r) return null;
  return (
    <div className="rounded-tremor-default border border-tremor-border bg-tremor-background p-2 text-sm shadow-tremor-dropdown">
      <p className="font-medium text-tremor-content-emphasis">{r.competitor}</p>
      <p className="mt-1 text-tremor-content">
        <span className="font-medium">{r.price_changes}</span> lần đổi giá
      </p>
      <p className="text-tremor-content">
        trên <span className="font-medium">{r.products}</span> sản phẩm
      </p>
      <p className="mt-1 border-t border-tremor-border pt-1 font-mono text-xs text-tremor-content">
        {r.price_changes} ÷ {r.products} × 100 ={" "}
        <span className="font-medium">{r.changes_per_100_products_week}</span>
      </p>
      <p className="mt-1 text-xs text-tremor-content">
        → <span className="font-medium">{r.changes_per_100_products_week}</span> lần đổi giá trên
        mỗi <span className="font-medium">100 sản phẩm</span>
      </p>
    </div>
  );
}

export default function Dashboard() {
  const { rows: allRows, loading, error } = useProductOverview();
  const coverage = useCoverageAll();
  // Chỉ tính danh mục ĐANG BẬT (ẩn danh mục đã tắt trong A/B test khỏi mọi KPI + thẻ).
  const rows = allRows.filter((r) => isEnabledCategory(r.category));
  const categories = useCategorySummaries(rows);

  // Distinct competitors across all categories (the _all coverage view repeats a store per category).
  const competitorNames = new Set(coverage.filter((c) => !c.is_self).map((c) => c.name));

  const totalCatalog = rows.length;
  const overall = statsFor(rows);
  const totalBeaten = overall.beatenCount;

  // Newest scrape across all products = when the last run finished (latest_prices is run-scoped).
  const lastScraped = rows.reduce<string | null>(
    (max, r) => (r.last_scraped && (!max || r.last_scraped > max) ? r.last_scraped : max),
    null,
  );

  // Số sản phẩm "ta hết hàng, đối thủ còn" theo danh mục — Postgres đã group+count sẵn
  // (out_of_stock_gap_by_category), landing chỉ nhận ~11 dòng cho các thẻ danh mục. Chi tiết OOS
  // nằm trong từng trang danh mục.
  const oosByCategory = useOutOfStockGapCounts();

  // "Cập nhật lần cuối" = lúc bảng cache latest_prices_cache refresh gần nhất (sau lần scrape cuối).
  // Ưu tiên refreshed_at (mốc refresh thật); nếu chưa có thì lùi về last_scraped của dữ liệu.
  const lastRefreshed = useLastRefreshed();
  const freshness = lastRefreshed ?? lastScraped;

  // Tần suất đổi giá / sản phẩm / tuần cho mỗi cửa hàng (Postgres tính sẵn, đã chuẩn hoá theo độ
  // phủ). Mỗi cửa hàng được tô MÀU THƯƠNG HIỆU riêng. tremor tô màu theo "category" (chuỗi dữ liệu),
  // không theo từng cột — nên ta xoay dữ liệu: mỗi cửa hàng thành MỘT category riêng (chỉ có giá trị
  // ở đúng cột của mình, các cột khác null) → mỗi cửa hàng ra một cột màu riêng. categories/colors
  // giữ cùng thứ tự để màu khớp cửa hàng.
  const BRAND_COLOR: Record<string, string> = {
    "Thế Giới Di Động": "yellow",
    "FPT Shop": "red",
    "An Phát PC": "purple",
    "Thành Nhân": "green", // TNC — cửa hàng của ta
    "Phong Vũ": "blue",
    CellphoneS: "orange",
    HACOM: "cyan",
    "Hà Nội Computer": "cyan",
    GearVN: "lime",
    Memoryzone: "pink",
  };
  // Tên rút gọn cho nhãn trục x (tên đầy đủ quá dài, đè lên nhau). Cửa hàng nào không có trong map
  // thì giữ nguyên tên gốc.
  const SHORT_NAME: Record<string, string> = {
    "Thế Giới Di Động": "TGĐĐ",
    "FPT Shop": "FPT",
    "An Phát PC": "An Phát",
    "Thành Nhân": "TNC",
    "Phong Vũ": "Phong Vũ",
    CellphoneS: "CellphoneS",
    "Hà Nội Computer": "HACOM",
    GearVN: "GearVN",
    Memoryzone: "MemoryZ",
  };
  const priceActivity = usePriceActivity();
  // Các tuần có dữ liệu (mới → cũ). Dropdown CHỈ hiện 4 tuần gần nhất (view trả về tất cả các tuần
  // và tăng dần theo thời gian; giới hạn 4 để dropdown gọn, chỉ nhìn xu hướng gần đây).
  const WEEKS_SHOWN = 4;
  const activityWeeks = [...new Set(priceActivity.map((r) => r.week_start))]
    .sort((a, b) => b.localeCompare(a))
    .slice(0, WEEKS_SHOWN);
  const [selectedWeek, setSelectedWeek] = useState<string>("");
  // Mặc định = tuần mới nhất (khi dữ liệu đã tải mà chưa chọn gì).
  const activeWeek = selectedWeek || activityWeeks[0] || "";
  const weekRows = priceActivity
    .filter((r) => r.week_start === activeWeek)
    .sort((a, b) => b.changes_per_100_products_week - a.changes_per_100_products_week);

  // Nhãn = tên rút gọn (mỗi cột có tên riêng trên trục x). Không thêm "(chúng ta)" cho TNC nữa —
  // đã phân biệt bằng màu xanh lá.
  const activityStores = weekRows.map((r) => SHORT_NAME[r.competitor] ?? r.competitor);
  const activityColors = weekRows.map((r) => BRAND_COLOR[r.competitor] ?? "indigo");
  // Một dòng cho mỗi cửa hàng; chỉ cột tên cửa hàng đó có giá trị, còn lại bỏ trống → mỗi cửa hàng
  // là một chuỗi riêng nên nhận đúng màu riêng của mình.
  const activityChart = weekRows.map((r, i) => ({
    store: activityStores[i],
    [activityStores[i]]: r.changes_per_100_products_week,
  }));
  // Tra ngược nhãn rút gọn → dòng gốc, để tooltip hiện cả SỐ LIỆU THÔ (số lần đổi giá + số sản phẩm)
  // chứ không chỉ con số cuối cùng — người xem tự kiểm chứng được phép tính.
  const activityByLabel = new Map(weekRows.map((r, i) => [activityStores[i], r]));

  return (
    <main className="mx-auto max-w-screen-2xl p-6 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Title>Bảng giá PC</Title>
          <Text>Giá đối thủ theo danh mục cho Thành Nhân Computer.</Text>
        </div>
        {freshness && (
          <Card className="w-auto shrink-0 px-4 py-2">
            <Text className="text-xs text-gray-500">Cập nhật lần cuối</Text>
            <Text className="text-sm font-medium text-gray-700">{timeAgo(freshness)}</Text>
            <Text className="text-xs text-gray-400">
              {new Date(freshness).toLocaleString("vi-VN", {
                timeZone: "Asia/Ho_Chi_Minh",
                hour: "2-digit",
                minute: "2-digit",
                day: "2-digit",
                month: "2-digit",
              })}
            </Text>
          </Card>
        )}
      </div>

      {loading && <Text>Đang tải…</Text>}
      {error && (
        <Card decoration="left" decorationColor="red">
          <Text>Không thể tải dữ liệu: {error}</Text>
          <Text className="mt-1">
            Kiểm tra Supabase đã thiết lập, schema đã áp dụng, và các khóa trong .env đúng chưa.
          </Text>
        </Card>
      )}

      {!loading && !error && rows.length === 0 && (
        <Card>
          <Text>
            Chưa có dữ liệu giá. Áp dụng <code>supabase/schema.sql</code> + <code>seed.sql</code>,
            rồi chạy scraper.
          </Text>
        </Card>
      )}

      {!loading && !error && rows.length > 0 && (
        <>
          {/* 1. Overall market KPIs — across ALL categories */}
          <Grid numItemsSm={2} numItemsLg={4} className="gap-4">
            <Card>
              <Text>Sản phẩm theo dõi</Text>
              <Metric>{totalCatalog}</Metric>
              <Text className="mt-1">trên {categories.length} danh mục</Text>
            </Card>
            <Card>
              <Text>Đối thủ</Text>
              <Metric>{competitorNames.size}</Metric>
            </Card>
            <Card>
              <Text>Trung bình so với thị trường</Text>
              <Metric
                className={
                  overall.avgVsMarket == null
                    ? undefined
                    : overall.avgVsMarket > 0
                      ? "text-red-600"
                      : "text-green-600"
                }
              >
                {overall.avgVsMarket == null
                  ? "—"
                  : `${overall.avgVsMarket > 0 ? "+" : ""}${overall.avgVsMarket}%`}
              </Metric>
              <Text className="mt-1">trên các sản phẩm có đối thủ</Text>
            </Card>
            <Card>
              <Text>Bị đối thủ bán rẻ hơn</Text>
              <Metric className={totalBeaten > 0 ? "text-red-600" : "text-green-600"}>
                {totalBeaten}
              </Metric>
              <Text className="mt-1">có đối thủ (còn hàng) bán rẻ hơn ta</Text>
            </Card>
          </Grid>

          {/* 2. Tần suất đổi giá — đối thủ nào điều chỉnh giá nhiều nhất, ta phản ứng chậm cỡ nào.
              Chuẩn hoá theo ĐỘ PHỦ (lần đổi / SẢN PHẨM / tuần) nên không lệch vì ta theo dõi cửa
              hàng nào nhiều hơn — cột cao = cửa hàng đổi giá năng động nhất, không phải cửa hàng ta
              theo dõi nhiều nhất. */}
          {activityWeeks.length > 0 && (
            <Card>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <Title>Tần suất đổi giá theo cửa hàng</Title>
                  {/* Đơn vị phải LUÔN thấy được: nếu không, cột "41" dễ bị đọc nhầm thành "41 lần
                      đổi giá" thay vì "41 lần trên mỗi 100 sản phẩm". */}
                  <Text className="mt-1 font-medium text-gray-600">
                    Số lần đổi giá trên mỗi <span className="text-gray-900">100 sản phẩm</span>,
                    trong tuần đã chọn
                  </Text>
                </div>
                <div className="shrink-0 sm:w-48">
                  <Text className="mb-1 text-xs text-gray-500">Chọn tuần</Text>
                  <Select value={activeWeek} onValueChange={setSelectedWeek} enableClear={false}>
                    {activityWeeks.map((w) => (
                      <SelectItem key={w} value={w}>
                        {weekLabel(w)}
                      </SelectItem>
                    ))}
                  </Select>
                </div>
              </div>
              <BarChart
                className="mt-4 h-80"
                data={activityChart}
                index="store"
                categories={activityStores}
                colors={activityColors}
                valueFormatter={(v) => (v == null ? "" : String(v))}
                yAxisWidth={56}
                yAxisLabel="Lần đổi giá / 100 sản phẩm"
                showLegend={false}
                stack
                customTooltip={(props) => (
                  <ActivityTooltip
                    active={props.active}
                    label={props.label}
                    rows={activityByLabel}
                  />
                )}
              />

              {/* Chú thích cách tính — gập lại mặc định, mở ra khi cần hiểu con số. */}
              <details className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                <summary className="cursor-pointer font-semibold text-amber-900">
                  ⓘ Cách tính con số này
                </summary>
                <div className="mt-2 space-y-2">
                  <p>
                    <strong>Công thức:</strong> (số lần đổi giá trong tuần ÷ số sản phẩm theo dõi) ×
                    100.
                  </p>
                  <p>
                    <strong>Ví dụ:</strong> một cửa hàng ta theo dõi <strong>10 sản phẩm</strong>.
                    Trong tuần, tổng cộng có <strong>5 lần đổi giá</strong> (một &quot;lần đổi&quot; =
                    một lần scrape có giá khác lần scrape ngay trước đó):
                  </p>
                  <p className="rounded bg-white px-3 py-2 font-mono text-xs">
                    5 lần đổi ÷ 10 sản phẩm = 0.5 &nbsp;→&nbsp; × 100 = <strong>50</strong>
                  </p>
                  <p>
                    Cột hiện <strong>50</strong>: &quot;cứ 100 sản phẩm thì có ~50 lần đổi giá trong
                    tuần.&quot;
                  </p>
                  <p>
                    <strong>Vì sao chia cho số sản phẩm?</strong> Để so sánh công bằng: cửa hàng ta
                    theo dõi 3.000 sản phẩm đương nhiên có nhiều lần đổi hơn cửa hàng ta chỉ theo dõi
                    40 — dù cửa hàng nhỏ đổi giá thường xuyên hơn. Chia cho số sản phẩm đo đúng
                    &quot;một sản phẩm điển hình đổi giá bao lâu một lần&quot;, không thiên lệch vì độ
                    phủ. Nhân 100 chỉ để ra số nguyên dễ đọc thay vì phân số dưới 1.
                  </p>
                </div>
              </details>
            </Card>
          )}

          {/* 3. Category cards — mỗi thẻ là cửa vào một PHÒNG BAN. Click để xem brand + giá + OOS. */}
          <div>
            <Title className="mb-2">Danh mục — chọn phòng ban của bạn</Title>
            <Grid numItemsSm={2} numItemsLg={3} className="gap-4">
              {categories.map((c) => {
                const oos = oosByCategory.get(c.category) ?? 0;
                return (
                  <Link
                    key={c.category}
                    to={`/category/${categoryToSlug(c.category)}`}
                    className="block"
                  >
                    <Card className="transition hover:ring-2 hover:ring-indigo-400">
                      <div className="flex items-center justify-between">
                        <Title>{categoryDisplay(c.category)}</Title>
                        <Badge color="indigo">{c.count} sản phẩm</Badge>
                      </div>
                      <div className="mt-3 flex items-center justify-between">
                        <Text>TB so với thị trường</Text>
                        <VsMarket pct={c.avgVsMarket} />
                      </div>
                      <div className="mt-2 flex items-center justify-between">
                        <Text>Bị đối thủ bán rẻ hơn</Text>
                        <Text
                          className={
                            c.beatenCount > 0
                              ? "font-medium text-red-600"
                              : "font-medium text-green-600"
                          }
                        >
                          {c.beatenCount}
                        </Text>
                      </div>
                      <div className="mt-2 flex items-center justify-between">
                        <Text>🚫 Ta hết hàng, đối thủ còn</Text>
                        {oos > 0 ? (
                          <Badge color="amber">{oos}</Badge>
                        ) : (
                          <Text className="font-medium text-green-600">0</Text>
                        )}
                      </div>
                      <Text className="mt-3 text-right text-sm font-medium text-indigo-600">
                        Vào xem chi tiết →
                      </Text>
                    </Card>
                  </Link>
                );
              })}
            </Grid>
          </div>

        </>
      )}
    </main>
  );
}
