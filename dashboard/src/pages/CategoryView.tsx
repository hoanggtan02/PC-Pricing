import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Card,
  Title,
  Text,
  Metric,
  Grid,
  Badge,
  Table,
  TableHead,
  TableHeaderCell,
  TableBody,
  TableRow,
  TableCell,
} from "@tremor/react";
import {
  vnd,
  brandToSlug,
  useProductOverviewByCategory,
  useComparableCoverage,
  useOutOfStockGap,
  statsFor,
  needsAttentionFor,
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

// How much MORE we cost than the cheapest competitor (₫ + %) — the metric the list is sorted by, so
// it decreases monotonically down the table. Always a positive gap here (list = products we're beaten
// on); shown red.
function OverLowest({ our, lowest }: { our: number | null; lowest: number | null }) {
  if (our == null || lowest == null || lowest <= 0) return <>—</>;
  const pct = Math.round(((our - lowest) / lowest) * 100); // số nguyên, ví dụ "+12%"
  return <Badge color="red">+{pct}%</Badge>;
}

export default function CategoryView() {
  const { name = "" } = useParams();
  // Server-filtered: only this category's rows cross the wire (?category=ilike.<slug>).
  const { rows: catRows, loading, error } = useProductOverviewByCategory(name);

  // The stored label (e.g. "Monitor") — take it from the first row; fall back to the URL slug.
  const categoryLabel = catRows[0]?.category ?? name;
  const categoryName = categoryDisplay(categoryLabel); // tên hiển thị đẹp (SSD, PC, Access Point…)

  const stats = statsFor(catRows);

  // Lead section: products where an in-stock competitor undercuts us, worst-first. catRows is already
  // scoped to this category, so pass its own label; needsAttentionFor applies the we_are_lowest filter.
  const attention = useMemo(
    () => needsAttentionFor(catRows, categoryLabel),
    [catRows, categoryLabel],
  );
  const [showAllAttention, setShowAllAttention] = useState(false);
  const ATTENTION_PREVIEW = 10;
  const visibleAttention = showAllAttention ? attention : attention.slice(0, ATTENTION_PREVIEW);

  // "Ta hết hàng, đối thủ còn hàng" — chỉ trong danh mục này (server lọc ?category=ilike.<slug>).
  const oosGap = useOutOfStockGap(name);
  const [showAllOos, setShowAllOos] = useState(false);
  const OOS_PREVIEW = 10;
  const visibleOos = showAllOos ? oosGap : oosGap.slice(0, OOS_PREVIEW);

  // Per-brand summary within this category.
  const brandSummaries = useMemo(() => {
    const byBrand = new Map<string, typeof catRows>();
    for (const r of catRows) {
      const arr = byBrand.get(r.brand) ?? [];
      arr.push(r);
      byBrand.set(r.brand, arr);
    }
    return Array.from(byBrand.entries())
      .map(([brand, brandRows]) => ({ brand, ...statsFor(brandRows) }))
      .sort((a, b) => b.count - a.count);
  }, [catRows]);

  // Độ phủ đối thủ — Postgres (view comparable_coverage) đã đếm "đối thủ có giá cho bao nhiêu sản
  // phẩm ta CÒN HÀNG". Frontend chỉ đọc; mẫu số comparable_total = tổng sản phẩm ta còn hàng.
  const competitors = useComparableCoverage(name);
  const trackedInCat = competitors[0]?.comparable_total ?? stats.count;

  return (
    <main className="mx-auto max-w-screen-2xl p-6 space-y-6">
      <div>
        <Link to="/" className="text-sm text-blue-600 hover:underline">
          ← Trang chủ
        </Link>
        <Title className="mt-1">{categoryName}</Title>
        <Text>Giá đối thủ cho Thành Nhân Computer.</Text>
      </div>

      {loading && <Text>Đang tải…</Text>}
      {error && (
        <Card decoration="left" decorationColor="red">
          <Text>Không thể tải dữ liệu: {error}</Text>
        </Card>
      )}

      {!loading && !error && catRows.length === 0 && (
        <Card>
          <Text>
            Không tìm thấy sản phẩm nào cho danh mục “{name}”.{" "}
            <Link to="/" className="text-blue-600 hover:underline">
              Về trang chủ
            </Link>
            .
          </Text>
        </Card>
      )}

      {!loading && !error && catRows.length > 0 && (
        <>
          {/* Category KPI row */}
          <Grid numItemsSm={3} className="gap-4">
            <Card>
              <Text>Sản phẩm (còn hàng)</Text>
              <Metric>{stats.count}</Metric>
            </Card>
            <Card>
              <Text>Trung bình so với thị trường</Text>
              <Metric
                className={
                  stats.avgVsMarket == null
                    ? undefined
                    : stats.avgVsMarket > 0
                      ? "text-red-600"
                      : "text-green-600"
                }
              >
                {stats.avgVsMarket == null
                  ? "—"
                  : `${stats.avgVsMarket > 0 ? "+" : ""}${stats.avgVsMarket}%`}
              </Metric>
            </Card>
            <Card>
              <Text>Bị đối thủ bán rẻ hơn</Text>
              <Metric className={stats.beatenCount > 0 ? "text-red-600" : "text-green-600"}>
                {stats.beatenCount}
              </Metric>
            </Card>
          </Grid>

          {/* 1. LEAD: products we're outcompeted on, worst-first */}
          <Card>
            <Title>⚠️ {attention.length} sản phẩm bị đối thủ bán rẻ hơn</Title>
            <Text>Có đối thủ đang bán rẻ hơn ta (bất kể chênh lệch lớn hay nhỏ). Chênh nhiều nhất trước.</Text>
            {attention.length === 0 ? (
              <Text className="mt-4">Không sản phẩm nào bị đối thủ bán rẻ hơn — ta đang có giá tốt nhất trong danh mục này.</Text>
            ) : (
              <>
                <Table className="mt-4">
                  <TableHead>
                    <TableRow>
                      <TableHeaderCell>Sản phẩm</TableHeaderCell>
                      <TableHeaderCell>SKU</TableHeaderCell>
                      <TableHeaderCell className="text-right">Giá của ta</TableHeaderCell>
                      <TableHeaderCell className="text-right">Rẻ nhất (đối thủ)</TableHeaderCell>
                      <TableHeaderCell className="text-right">Ta đắt hơn</TableHeaderCell>
                      <TableHeaderCell className="text-right">Đối thủ</TableHeaderCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {visibleAttention.map((s) => (
                      <TableRow key={s.sku}>
                        <TableCell className="max-w-xs truncate" title={s.product_name}>
                          <Link
                            to={`/brand/${brandToSlug(s.brand)}?category=${encodeURIComponent(categoryLabel)}&sku=${encodeURIComponent(s.sku)}`}
                            className="text-blue-600 hover:underline"
                          >
                            {s.product_name}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <Badge>{s.sku}</Badge>
                        </TableCell>
                        <TableCell className="text-right font-medium">
                          {s.our_price != null ? vnd(s.our_price) : "—"}
                        </TableCell>
                        <TableCell className="text-right">
                          {s.lowest_price != null ? vnd(s.lowest_price) : "—"}
                        </TableCell>
                        <TableCell className="text-right">
                          <OverLowest our={s.our_price} lowest={s.lowest_price} />
                        </TableCell>
                        <TableCell className="text-right">{s.num_sources ?? 0}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                {attention.length > ATTENTION_PREVIEW && (
                  <button
                    type="button"
                    onClick={() => setShowAllAttention((v) => !v)}
                    className="mt-3 text-sm font-medium text-blue-600 hover:underline"
                  >
                    {showAllAttention ? "Thu gọn ▴" : `Xem tất cả ${attention.length} ▾`}
                  </button>
                )}
              </>
            )}
          </Card>

          {/* 2. Ta hết hàng, đối thủ còn hàng — cơ hội bị mất doanh số (chỉ danh mục này) */}
          <Card>
            <Title>🚫 {oosGap.length} sản phẩm ta hết hàng nhưng đối thủ còn</Title>
            <Text>
              Ta đang hết hàng (Liên hệ) trong khi ít nhất một đối thủ vẫn còn — cơ hội bị mất doanh
              số. Nhiều đối thủ còn hàng nhất xếp trước.
            </Text>
            {oosGap.length === 0 ? (
              <Text className="mt-4">
                Không có — mọi sản phẩm {categoryName} ta theo dõi đều còn hàng, hoặc đối thủ cũng hết.
              </Text>
            ) : (
              <>
                <Table className="mt-4">
                  <TableHead>
                    <TableRow>
                      <TableHeaderCell>Sản phẩm</TableHeaderCell>
                      <TableHeaderCell>SKU</TableHeaderCell>
                      <TableHeaderCell className="text-right">Đối thủ còn hàng</TableHeaderCell>
                      <TableHeaderCell>Rẻ nhất</TableHeaderCell>
                      <TableHeaderCell className="text-right">Giá</TableHeaderCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {visibleOos.map((g) => (
                      <TableRow key={g.sku}>
                        <TableCell className="max-w-xs truncate" title={g.product_name}>
                          {g.our_url ? (
                            <a
                              href={g.our_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-blue-600 hover:underline"
                            >
                              {g.product_name}
                            </a>
                          ) : (
                            g.product_name
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge>{g.sku}</Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Badge color="amber">{g.competitors_in_stock}</Badge>
                        </TableCell>
                        <TableCell>
                          {g.cheapest_competitor_url ? (
                            <a
                              href={g.cheapest_competitor_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-blue-600 hover:underline"
                            >
                              {g.cheapest_competitor ?? "—"}
                            </a>
                          ) : (
                            (g.cheapest_competitor ?? "—")
                          )}
                        </TableCell>
                        <TableCell className="text-right font-medium">
                          {g.cheapest_competitor_price != null
                            ? vnd(g.cheapest_competitor_price)
                            : "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                {oosGap.length > OOS_PREVIEW && (
                  <button
                    type="button"
                    onClick={() => setShowAllOos((v) => !v)}
                    className="mt-3 text-sm font-medium text-blue-600 hover:underline"
                  >
                    {showAllOos ? "Thu gọn ▴" : `Xem tất cả ${oosGap.length} ▾`}
                  </button>
                )}
              </>
            )}
          </Card>

          {/* 3. Competitor coverage for this category */}
          {competitors.length > 0 && (
            <Card>
              <Title>Độ phủ của đối thủ</Title>
              <Text>
                Mỗi đối thủ có giá cho bao nhiêu trong {trackedInCat} sản phẩm {categoryName} ta
                còn hàng (so sánh được).
              </Text>
              <div className="mt-4 space-y-2">
                {competitors.map((c) => {
                    const pct = trackedInCat
                      ? Math.min((c.products_matched / trackedInCat) * 100, 100)
                      : 0;
                    return (
                      <div key={c.name} className="flex items-center gap-3">
                        <div className="w-40 shrink-0 truncate text-sm text-gray-700" title={c.name}>
                          {c.name}
                        </div>
                        <div className="h-3 flex-1 rounded bg-gray-100">
                          <div
                            className="h-3 rounded bg-blue-500"
                            style={{ width: `${Math.max(pct, 1)}%` }}
                          />
                        </div>
                        <div className="w-28 shrink-0 text-right text-sm tabular-nums text-gray-600">
                          {c.products_matched} / {trackedInCat}
                          <span className="ml-1 text-gray-400">({Math.round(pct)}%)</span>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </Card>
          )}

          {/* 3. Brand grid within this category */}
          <div>
            <Title className="mb-2">Xem theo thương hiệu</Title>
            <Grid numItemsSm={2} numItemsLg={4} className="gap-4">
              {brandSummaries.map((b) => (
                <Link
                  key={b.brand}
                  to={`/brand/${brandToSlug(b.brand)}?category=${encodeURIComponent(categoryLabel)}`}
                  className="block"
                >
                  <Card className="transition hover:ring-2 hover:ring-indigo-400">
                    <div className="flex items-center justify-between">
                      <Title>{b.brand}</Title>
                      <Badge color="indigo">{b.count}</Badge>
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <Text>Trung bình so với thị trường</Text>
                      <VsMarket pct={b.avgVsMarket} />
                    </div>
                    <Text className="mt-1">
                      {b.beatenCount > 0
                        ? `${b.beatenCount} sản phẩm bị đối thủ bán rẻ hơn`
                        : "không có sản phẩm nào bị đối thủ bán rẻ hơn"}
                    </Text>
                  </Card>
                </Link>
              ))}
            </Grid>
          </div>
        </>
      )}
    </main>
  );
}
