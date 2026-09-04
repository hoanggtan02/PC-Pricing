"""Báo cáo các SKU BẤT THƯỜNG trong một danh mục để xem lại TAY — CHỈ ĐỌC, không ghi/sửa gì vào
DB (khác audit_category.py, vốn cào lại giá + tự bật/tắt source). Dùng cái này để rà nhanh trước
khi quyết định có cần chạy audit_category.py để cào lại xác minh không.

Ba loại bất thường:
  1. INACTIVE_BUT_PRICED — source đang TẮT (active=false) nhưng lần cào GẦN NHẤT vẫn có giá hợp
     lệ (>0) và còn hàng.

     GIỚI HẠN QUAN TRỌNG: mọi nơi gọi deactivate_source() (sync_prices.py, audit_category.py) đều
     ghi kèm một dòng giá price=0/in_stock=False NGAY TẠI THỜI ĐIỂM TẮT, và fetch_active_sources()
     (Mode B — sync hàng ngày) chỉ cào các source active=True. Nghĩa là MỘT KHI source đã tắt, nó
     KHÔNG BAO GIỜ được cào lại giá nữa qua Mode B — giá "gần nhất" của nó trong price_history mãi
     mãi đứng yên ở 0 (hoặc hoàn toàn không có bản ghi nào nếu chưa từng được cào thành công trước
     khi tắt). Vì vậy nhánh này gần như LUÔN LUÔN ra rỗng — để phát hiện "tắt nhầm" một cách đáng
     tin, phải CÀO LẠI THẬT: dùng `audit_category.py --dry` và tìm dòng "BẬT LẠI" trong output/report
     của nó (nó tự mở lại trang, đọc giá thật, và tự bật lại nếu còn hàng).

  2. PRICE_OUTLIER — giá của MỘT cửa hàng lệch quá xa (mặc định >= 1.6x) so với median giá các
     cửa hàng khác đang bán CÙNG SKU (chỉ so trong tập active + còn hàng + không phải hàng
     cũ/demo). KHÔNG chắc là giá sai — có thể là (a) sai khớp SKU (hai sản phẩm khác nhau gộp
     nhầm — xem audit_category.py phần NGHI SAI KHỚP, vốn so TÊN chứ không so GIÁ), (b) bug parse
     giá (vd bug "giá x10" từng gặp ở sync_prices.py/_price_value_to_int), hoặc (c) cửa hàng đó
     thật sự bán đắt/rẻ hơn hẳn (khuyến mãi, hết chương trình...). Cần xem tay để phân loại.

  3. PRICE_ZERO_IN_STOCK — bản ghi giá GẦN NHẤT có price<=0 NHƯNG in_stock=True. Đây là một tổ hợp
     MÂU THUẪN theo quy ước toàn hệ thống (xem stock.py: stock_from_price() — có giá = còn hàng,
     "Liên hệ"/không đọc được giá = price=None/0 = hết hàng). price=0 + in_stock=True nhiều khả
     năng là BUG PARSE GIÁ (trang đọc được tín hiệu "còn hàng" nhưng không đọc được số giá thật,
     rơi vào nhánh mặc định sai) — không phân biệt active/inactive, vì đây là lỗi DỮ LIỆU, áp dụng
     cho mọi bản ghi bất kể source đang bật hay tắt.

Cách dùng:
    python -m scraper.find_anomalies --category Mainboard
    python -m scraper.find_anomalies --category Mainboard --competitor GearVN
    python -m scraper.find_anomalies --category Mainboard --outlier-ratio 1.5 --report out.tsv
    python -m scraper.find_anomalies --category Printer --debug --min-competitors 2
"""

from __future__ import annotations

import argparse
import statistics
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .db import fetch_all_sources, fetch_latest_prices, get_client

DEFAULT_OUTLIER_RATIO = 1.6   # giá lệch >= 1.6x median các cửa hàng khác -> flag
DEFAULT_MIN_COMPETITORS = 2   # cần ít nhất 2 cửa hàng có giá hợp lệ mới so được outlier

_REPORT_COLUMNS = [
    "issue", "sku", "product_name", "competitor", "price", "in_stock",
    "active", "is_used", "context", "url",
]


def _valid_for_comparison(entry: dict | None, source_active: bool) -> bool:
    """Giá có đáng tin để đưa vào so sánh outlier không: có bản ghi giá, giá > 0, còn hàng, không
    phải hàng cũ/demo, và source đang active (source inactive có thể đang tắt vì lý do khác,
    không nên kéo vào làm lệch median của các cửa hàng đang bán thật)."""
    if not entry or not source_active:
        return False
    price = entry.get("price")
    if not price or price <= 0:
        return False
    if entry.get("in_stock") is False:
        return False
    if entry.get("is_used"):
        return False
    return True


def find_anomalies(
    category: str,
    competitor_filter: str | None,
    outlier_ratio: float,
    min_competitors: int,
    debug: bool = False,
) -> list[dict]:
    client = get_client()

    print(f"Đang đọc source + giá gần nhất cho danh mục '{category}'...")
    all_sources = fetch_all_sources(client, category=category)
    if not all_sources:
        print(f"Không tìm thấy source nào trong danh mục '{category}'.")
        return []

    skus = sorted({s["product_sku"] for s in all_sources})
    latest = fetch_latest_prices(client, skus)

    print(
        f"{len(all_sources)} source(s), {len(skus)} SKU, "
        f"{len(latest)} bản ghi giá gần nhất được nạp.\n"
    )

    rows: list[dict] = []

    # ── Flag 1: INACTIVE_BUT_PRICED ─────────────────────────────────────────────────────────
    # Xem giới hạn quan trọng ở docstring đầu file — nhánh này gần như luôn rỗng theo thiết kế
    # hiện tại (source inactive không còn được Mode B cào lại). Vẫn giữ lại vì KHÔNG PHẢI zero
    # tuyệt đối: source bị tắt qua đường khác (tắt tay/bug cũ) vẫn có thể lọt qua đây.
    for s in all_sources:
        sku, competitor = s["product_sku"], s["competitor"]
        if s.get("active"):
            continue
        if s.get("is_used"):  # hàng cũ/demo bị tắt là ĐÚNG chủ đích, không phải bất thường
            continue
        entry = latest.get((sku, competitor))
        if not entry:
            continue
        price = entry.get("price")
        if not price or price <= 0:
            continue
        if entry.get("in_stock") is False:
            continue
        if entry.get("is_used"):
            continue
        if competitor_filter and competitor != competitor_filter:
            continue
        product_name = (s.get("products") or {}).get("name", "")
        rows.append({
            "issue": "INACTIVE_BUT_PRICED",
            "sku": sku,
            "product_name": product_name,
            "competitor": competitor,
            "price": price,
            "in_stock": entry.get("in_stock"),
            "active": False,
            "is_used": False,
            "context": "Source tắt nhưng lần cào gần nhất vẫn có giá hợp lệ + còn hàng",
            "url": s.get("url", ""),
        })

    # ── Flag 3: PRICE_ZERO_IN_STOCK ──────────────────────────────────────────────────────────
    # Tổ hợp mâu thuẫn price<=0 + in_stock=True — xem docstring đầu file. Quét TOÀN BỘ source
    # (không lọc active) vì đây là lỗi dữ liệu, không phụ thuộc trạng thái bật/tắt.
    source_map = {(s["product_sku"], s["competitor"]): s for s in all_sources}
    for s in all_sources:
        sku, competitor = s["product_sku"], s["competitor"]
        if competitor_filter and competitor != competitor_filter:
            continue
        entry = latest.get((sku, competitor))
        if not entry:
            continue
        price = entry.get("price")
        if price is not None and price <= 0 and entry.get("in_stock") is True:
            product_name = (s.get("products") or {}).get("name", "")
            rows.append({
                "issue": "PRICE_ZERO_IN_STOCK",
                "sku": sku,
                "product_name": product_name,
                "competitor": competitor,
                "price": price,
                "in_stock": True,
                "active": s.get("active"),
                "is_used": entry.get("is_used"),
                "context": "Giá=0 nhưng in_stock=True — mâu thuẫn quy ước, nghi bug parse giá",
                "url": s.get("url", ""),
            })

    # ── Flag 2: PRICE_OUTLIER ────────────────────────────────────────────────────────────────
    by_sku: dict[str, list[tuple[str, dict]]] = {}
    for (sku, competitor), entry in latest.items():
        source = source_map.get((sku, competitor))
        if not source or not _valid_for_comparison(entry, bool(source.get("active"))):
            continue
        by_sku.setdefault(sku, []).append((competitor, entry))

    if debug:
        n_with_enough = sum(1 for entries in by_sku.values() if len(entries) >= min_competitors)
        n_with_1 = sum(1 for entries in by_sku.values() if len(entries) == 1)
        n_zero = len(skus) - len(by_sku)
        print(
            f"[DEBUG] {len(by_sku)}/{len(skus)} SKU có ít nhất 1 giá hợp lệ để so sánh "
            f"({n_with_enough} SKU có >= {min_competitors} cửa hàng hợp lệ — SẼ được so outlier, "
            f"{n_with_1} SKU chỉ có 1 cửa hàng hợp lệ — KHÔNG đủ để so, "
            f"{n_zero} SKU không có giá hợp lệ nào)."
        )
        # In vài SKU mẫu bị loại vì chỉ có 1 (hoặc 0) cửa hàng hợp lệ, kèm lý do các source khác
        # bị loại (inactive/hết hàng/hàng cũ/chưa từng có giá) — giúp biết ngay tại sao 0 outlier.
        sample_skus = [sku for sku in skus if len(by_sku.get(sku, [])) < min_competitors][:8]
        for sku in sample_skus:
            all_for_sku = [s for s in all_sources if s["product_sku"] == sku]
            print(f"  [DEBUG] {sku}: {len(all_for_sku)} source(s) tổng, chi tiết:")
            for s in all_for_sku:
                e = latest.get((sku, s["competitor"]))
                if e:
                    print(
                        f"      - {s['competitor']}: active={s.get('active')} "
                        f"price={e.get('price')} in_stock={e.get('in_stock')} "
                        f"is_used={e.get('is_used')}"
                    )
                else:
                    print(
                        f"      - {s['competitor']}: active={s.get('active')} "
                        f"(chưa có giá nào trong price_history)"
                    )
        print()

        # Phân bố tỉ lệ lệch giá THỰC TẾ trong tập SKU đủ điều kiện so sánh — giúp biết ngưỡng
        # --outlier-ratio hiện tại có hợp lý không, thay vì đoán mù khi thấy 0 kết quả.
        ratios: list[tuple[float, str, str, float, float]] = []
        for sku, entries in by_sku.items():
            if len(entries) < min_competitors:
                continue
            prices = [e["price"] for _, e in entries]
            median = statistics.median(prices)
            if median <= 0:
                continue
            for competitor, entry in entries:
                r = max(entry["price"] / median, median / entry["price"])
                ratios.append((r, sku, competitor, entry["price"], median))
        ratios.sort(key=lambda t: t[0], reverse=True)
        print(
            f"[DEBUG] Top 10 tỉ lệ lệch giá cao nhất trong {len(by_sku)} SKU đủ điều kiện so sánh "
            f"(ngưỡng hiện tại --outlier-ratio={outlier_ratio}):"
        )
        for r, sku, competitor, price, median in ratios[:10]:
            flag = " <- SẼ bị gắn cờ" if r >= outlier_ratio else ""
            print(f"    {r:.2f}x  {sku} · {competitor}: {price:,.0f} vs median {median:,.0f}{flag}")
        print()

    for sku, entries in by_sku.items():
        if len(entries) < min_competitors:
            continue
        prices = [e["price"] for _, e in entries]
        median = statistics.median(prices)
        if median <= 0:
            continue
        for competitor, entry in entries:
            if competitor_filter and competitor != competitor_filter:
                continue
            price = entry["price"]
            ratio = max(price / median, median / price)
            if ratio < outlier_ratio:
                continue
            source = source_map.get((sku, competitor)) or {}
            product_name = (source.get("products") or {}).get("name", "")
            others = ", ".join(
                f"{c}={e['price']:,}" for c, e in sorted(entries, key=lambda x: x[1]["price"])
                if c != competitor
            )
            rows.append({
                "issue": "PRICE_OUTLIER",
                "sku": sku,
                "product_name": product_name,
                "competitor": competitor,
                "price": price,
                "in_stock": entry.get("in_stock"),
                "active": source.get("active"),
                "is_used": entry.get("is_used"),
                "context": f"lệch {ratio:.2f}x so median={median:,.0f} | các cửa hàng khác: {others}",
                "url": source.get("url", ""),
            })

    rows.sort(key=lambda r: (r["issue"], r["sku"], r["competitor"]))
    return rows


def _print_summary(rows: list[dict]) -> None:
    n_inactive = sum(1 for r in rows if r["issue"] == "INACTIVE_BUT_PRICED")
    n_outlier = sum(1 for r in rows if r["issue"] == "PRICE_OUTLIER")
    n_zero_stock = sum(1 for r in rows if r["issue"] == "PRICE_ZERO_IN_STOCK")
    print("=== TỔNG KẾT ===")
    print(f"INACTIVE_BUT_PRICED (nghi tắt nhầm)     : {n_inactive}")
    print(f"PRICE_OUTLIER (nghi sai khớp/giá bug)   : {n_outlier}")
    print(f"PRICE_ZERO_IN_STOCK (mâu thuẫn giá=0)   : {n_zero_stock}")
    print(f"Tổng cộng                               : {len(rows)}")
    for r in rows[:40]:
        print(f"  - [{r['issue']}] {r['sku']} · {r['competitor']}: "
              f"{r['price']:,} VND — {r['context']}")
    if len(rows) > 40:
        print(f"  ... và {len(rows) - 40} dòng khác, xem file report.")


def _write_report(path: str, rows: list[dict]) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\t".join(_REPORT_COLUMNS) + "\n")
            for r in rows:
                f.write(
                    "\t".join(str(r.get(c, "")).replace("\t", " ").replace("\n", " ")
                              for c in _REPORT_COLUMNS)
                    + "\n"
                )
        print(f"\nĐã ghi {len(rows)} dòng vào {path}")
    except Exception as e:
        print(f"Lỗi ghi report {path}: {e}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Báo cáo (chỉ đọc) các SKU bất thường: tắt nhầm dù có giá, giá lệch quá xa, "
                     "hoặc giá=0 mâu thuẫn với còn hàng."
    )
    ap.add_argument("--category", required=True, help="Danh mục (vd: Mainboard, Cpu, Laptop)")
    ap.add_argument("--competitor", default=None, help="Chỉ lọc kết quả cho MỘT cửa hàng")
    ap.add_argument(
        "--outlier-ratio", type=float, default=DEFAULT_OUTLIER_RATIO,
        help=f"Ngưỡng lệch giá so median để gắn cờ (mặc định {DEFAULT_OUTLIER_RATIO})",
    )
    ap.add_argument(
        "--min-competitors", type=int, default=DEFAULT_MIN_COMPETITORS,
        help=f"Số cửa hàng tối thiểu có giá để so outlier (mặc định {DEFAULT_MIN_COMPETITORS})",
    )
    ap.add_argument("--report", default="anomalies_report.tsv", help="Đường dẫn file TSV")
    ap.add_argument(
        "--debug", action="store_true",
        help="In chi tiết vì sao SKU bị loại khỏi so sánh outlier + phân bố tỉ lệ lệch giá thực tế",
    )
    args = ap.parse_args()

    rows = find_anomalies(
        category=args.category.capitalize(),
        competitor_filter=args.competitor,
        outlier_ratio=args.outlier_ratio,
        min_competitors=args.min_competitors,
        debug=args.debug,
    )
    _print_summary(rows)
    if rows:
        _write_report(args.report, rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())