import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
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
  useProductOverviewByBrand,
  statsFor,
  categoryDisplay,
  useSkuPriceTrend7d,
  trendKey,
  type SkuPriceTrend,
} from "../data";

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

// Diễn biến giá 7 ngày của MỘT sản phẩm tại MỘT cửa hàng: hướng (tăng/giảm/không đổi) + net % + số
// lần đổi. Không có dữ liệu = cửa hàng đó không đổi giá trong 7 ngày → "—".
// Lưu ý: giá bật lên rồi về chỗ cũ cho direction='flat' nhưng changes=2 — nên vẫn hiện số lần đổi.
function Trend7d({ t }: { t: SkuPriceTrend | undefined }) {
  // Không có dòng trong view = cửa hàng không đổi giá lần nào trong 7 ngày.
  if (!t)
    return (
      <span className="text-gray-300" title="Không đổi giá lần nào trong 7 ngày gần nhất">
        —
      </span>
    );
  const { direction, pct_change, changes } = t;
  const arrow = direction === "up" ? "▲" : direction === "down" ? "▼" : "●";
  // Tăng giá = đỏ (đắt lên), giảm giá = xanh (rẻ đi), đi ngang = xám.
  const color =
    direction === "up" ? "text-red-600" : direction === "down" ? "text-green-600" : "text-gray-500";
  const pct = pct_change == null ? null : Math.abs(pct_change);
  // Tooltip nói RÕ nghĩa — nhất là ca "●": đổi nhiều lần nhưng về đúng giá cũ, dễ bị hiểu nhầm
  // thành "không đổi giá".
  const tip =
    direction === "flat"
      ? `Đổi giá ${changes} lần trong 7 ngày nhưng quay về đúng giá ban đầu (giá nhảy lên xuống)`
      : `Giá ${direction === "up" ? "TĂNG" : "GIẢM"} ${pct}% trong 7 ngày — đổi ${changes} lần`;
  return (
    <span className={`whitespace-nowrap ${color}`} title={tip}>
      {arrow}
      {pct != null && pct > 0 ? ` ${pct}%` : ""}
      <span className="ml-1 text-xs text-gray-400">({changes}×)</span>
    </span>
  );
}

export default function BrandView() {
  const { name = "" } = useParams();
  const [searchParams] = useSearchParams();
  const focusSku = searchParams.get("sku"); // deep-linked product to scroll to + highlight
  const category = searchParams.get("category"); // scope to one category when arriving from a category page
  // Server-filtered: only this brand's rows cross the wire (?brand=ilike.<slug>).
  const { rows: allBrandRows, loading, error } = useProductOverviewByBrand(name);
  // Nếu tới từ một trang danh mục (?category=...), CHỈ hiện sản phẩm của brand TRONG danh mục đó —
  // nếu không "Dell" sẽ trộn laptop + màn hình + PC lẫn lộn. Slice của brand nhỏ nên lọc ở client.
  const brandRows = category
    ? allBrandRows.filter((r) => r.category.toLowerCase() === category.toLowerCase())
    : allBrandRows;

  // Diễn biến giá 7 ngày cho từng (sku × cửa hàng) — Postgres tính sẵn, tra O(1) khi vẽ bảng giá.
  const trend7d = useSkuPriceTrend7d();

  // Stored label (e.g. "MSI", "Dell") — from the first row; fall back to the URL slug.
  const brandLabel = brandRows[0]?.brand ?? name;
  const categoryLabel = brandRows[0]?.category ?? category ?? "";

  const stats = statsFor(brandRows);

  // Arriving via ?sku=... (a "needs attention" link): scroll that product into view and flash it.
  const focusRef = useRef<HTMLDivElement | null>(null);
  const [flash, setFlash] = useState(false);
  useEffect(() => {
    if (!focusSku || brandRows.length === 0 || !focusRef.current) return;
    focusRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    setFlash(true);
    const t = setTimeout(() => setFlash(false), 2200);
    return () => clearTimeout(t);
  }, [focusSku, brandRows.length]);

  return (
    <main className="mx-auto max-w-screen-2xl p-6 space-y-6">
      <div>
        {category ? (
          <Link
            to={`/category/${category.toLowerCase()}`}
            className="text-sm text-blue-600 hover:underline"
          >
            ← {categoryDisplay(categoryLabel)}
          </Link>
        ) : (
          <Link to="/" className="text-sm text-blue-600 hover:underline">
            ← Trang chủ
          </Link>
        )}
        <Title className="mt-1">
          {brandLabel}
          {categoryLabel ? ` — ${categoryDisplay(categoryLabel)}` : ""}
        </Title>
        <Text>Giá đối thủ cho Thành Nhân Computer.</Text>
      </div>

      {loading && <Text>Đang tải…</Text>}
      {error && (
        <Card decoration="left" decorationColor="red">
          <Text>Không thể tải dữ liệu: {error}</Text>
        </Card>
      )}

      {!loading && !error && brandRows.length === 0 && (
        <Card>
          <Text>
            Không tìm thấy sản phẩm nào cho “{name}”.{" "}
            <Link to="/" className="text-blue-600 hover:underline">
              Về trang chủ
            </Link>
            .
          </Text>
        </Card>
      )}

      {!loading && !error && brandRows.length > 0 && (
        <>
          {/* Brand KPI row */}
          <Grid numItemsSm={3} className="gap-4">
            <Card>
              <Text>Sản phẩm</Text>
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

          {/* Price statistics table (brand-scoped) */}
          <Card>
            <Title>Thống kê giá</Title>
            <Text>
              Trung Bình, thấp nhất và cao nhất chỉ tính <strong>đối thủ</strong> (không tính giá của ta).
            </Text>
            <Table className="mt-4">
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Sản phẩm</TableHeaderCell>
                  <TableHeaderCell>SKU</TableHeaderCell>
                  <TableHeaderCell className="text-right">Đối thủ</TableHeaderCell>
                  <TableHeaderCell className="text-right">Giá của ta</TableHeaderCell>
                  <TableHeaderCell className="text-right">so với TT</TableHeaderCell>
                  <TableHeaderCell className="text-right">Trung Bình</TableHeaderCell>
                  <TableHeaderCell className="text-right">Thấp nhất</TableHeaderCell>
                  <TableHeaderCell className="text-right">Cao nhất</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {brandRows.map((s) => (
                  <TableRow key={s.sku}>
                    <TableCell className="max-w-xs truncate" title={s.product_name}>
                      {s.product_name}
                    </TableCell>
                    <TableCell>
                      <Badge>{s.sku}</Badge>
                    </TableCell>
                    <TableCell className="text-right">{s.num_sources ?? 0}</TableCell>
                    <TableCell className="text-right font-medium">
                      {s.our_price != null ? vnd(s.our_price) : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <VsMarket pct={s.pct_vs_mean} />
                    </TableCell>
                    <TableCell className="text-right">
                      {s.mean_price != null ? vnd(s.mean_price) : "—"}
                    </TableCell>
                    <TableCell className="text-right text-green-600">
                      {s.lowest_price != null ? vnd(s.lowest_price) : "—"}
                    </TableCell>
                    <TableCell className="text-right text-red-600">
                      {s.highest_price != null ? vnd(s.highest_price) : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>

          {/* Per-competitor breakdown */}
          <Card>
            <Title>Giá tại từng đối thủ</Title>
            <Text className="mt-1">
              Cột <span className="font-medium">&quot;Đổi giá 7 ngày&quot;</span> cho biết cửa hàng
              đó có điều chỉnh giá sản phẩm này trong 7 ngày gần nhất hay không.
            </Text>

            {/* Chú giải ký hiệu — gập lại mặc định. Không có chú giải thì "●(4×)" đọc không hiểu. */}
            <details className="mt-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              <summary className="cursor-pointer font-semibold text-amber-900">
                ❓ Các ký hiệu nghĩa là gì?
              </summary>
              <div className="mt-3 space-y-2">
                <div className="flex items-start gap-3">
                  <span className="w-20 shrink-0 whitespace-nowrap font-medium text-red-600">
                    ▲ 3.6% (1×)
                  </span>
                  <span>
                    Giá <strong>TĂNG</strong> 3.6% so với đầu tuần, đã đổi 1 lần. (đắt lên)
                  </span>
                </div>
                <div className="flex items-start gap-3">
                  <span className="w-20 shrink-0 whitespace-nowrap font-medium text-green-600">
                    ▼ 6.3% (2×)
                  </span>
                  <span>
                    Giá <strong>GIẢM</strong> 6.3% so với đầu tuần, đã đổi 2 lần. (rẻ đi)
                  </span>
                </div>
                <div className="flex items-start gap-3">
                  <span className="w-20 shrink-0 whitespace-nowrap font-medium text-gray-500">
                    ● (4×)
                  </span>
                  <span>
                    Đã đổi giá <strong>4 lần</strong> nhưng cuối cùng quay về <strong>đúng giá
                    ban đầu</strong> — giá nhảy lên nhảy xuống. Cửa hàng này rất hay chỉnh giá, dù
                    tính ra không đổi.
                  </span>
                </div>
                <div className="flex items-start gap-3">
                  <span className="w-20 shrink-0 whitespace-nowrap font-medium text-gray-300">—</span>
                  <span>
                    <strong>Không đổi giá</strong> lần nào trong 7 ngày. (khác với ● ở trên: ● là có
                    đổi nhiều lần rồi về chỗ cũ)
                  </span>
                </div>
                <p className="mt-2 border-t border-amber-300 pt-2 text-xs">
                  Số trong ngoặc <strong>(N×)</strong> = số lần đổi giá. % so sánh giá đầu và cuối
                  của 7 ngày. Lúc hết hàng không được tính là đổi giá.
                </p>
              </div>
            </details>
            <div className="mt-4 space-y-4">
              {brandRows.map((s) => {
                const stores = s.prices_by_store ?? [];
                const focused = s.sku === focusSku;
                return (
                  <div
                    key={s.sku}
                    ref={focused ? focusRef : undefined}
                    className={
                      focused && flash
                        ? "-mx-2 rounded-lg bg-amber-100 px-2 py-2 ring-2 ring-amber-400 transition-colors duration-700"
                        : "-mx-2 rounded-lg px-2 py-2 transition-colors duration-700"
                    }
                  >
                    <Text className="font-medium">{s.product_name}</Text>
                    {/* table-fixed + width rõ ràng: cột Giá luôn ĐỨNG YÊN dù cột Cửa hàng có nhãn
                        "out of stock" (nếu để bảng tự co giãn, nhãn làm cột cửa hàng rộng thêm →
                        cột Giá bị đẩy sang phải ở những dòng khác, trông như bị "lệch"). */}
                    <Table className="mt-1 table-fixed">
                      <TableHead>
                        <TableRow>
                          <TableHeaderCell className="w-1/2">Cửa hàng</TableHeaderCell>
                          <TableHeaderCell className="text-right">Giá</TableHeaderCell>
                          <TableHeaderCell
                            className="w-28 text-right"
                            title="Thay đổi giá trong 7 ngày gần nhất: ▲ tăng, ▼ giảm, ● đổi nhiều lần rồi về giá cũ, — không đổi. Số trong ngoặc = số lần đổi."
                          >
                            Đổi giá 7 ngày
                          </TableHeaderCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {stores.map(({ store, price, is_self, url, in_stock, is_flash_sale }) => {
                          const isLowest = store === s.lowest_store;
                          return (
                            <TableRow
                              key={store}
                              className={is_self ? "bg-blue-50 font-medium" : undefined}
                            >
                              <TableCell>
                                {/* Tên cửa hàng + nhãn trên CÙNG một dòng nhưng cho phép xuống hàng
                                    (flex-wrap): nhãn "out of stock" KHÔNG kéo giãn cột (whitespace-
                                    nowrap mặc định của tremor làm cột rộng thêm ở dòng có nhãn → các
                                    dòng khác trông bị "lệch phải"). */}
                                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 whitespace-normal">
                                  {url ? (
                                    <a
                                      href={url}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="text-blue-600 hover:underline"
                                    >
                                      {store}
                                    </a>
                                  ) : (
                                    <span>{store}</span>
                                  )}
                                  {isLowest && in_stock && <Badge color="green">lowest</Badge>}
                                  {is_flash_sale && in_stock && (
                                    <Badge color="red">⚡ flash sale</Badge>
                                  )}
                                  {!in_stock && <Badge color="amber">out of stock</Badge>}
                                </div>
                              </TableCell>
                              <TableCell
                                className={
                                  in_stock
                                    ? "text-right"
                                    : "text-right text-gray-400 line-through"
                                }
                              >
                                {vnd(price)}
                              </TableCell>
                              <TableCell className="text-right">
                                <Trend7d t={trend7d.get(trendKey(s.sku, store))} />
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                );
              })}
            </div>
          </Card>
        </>
      )}
    </main>
  );
}
