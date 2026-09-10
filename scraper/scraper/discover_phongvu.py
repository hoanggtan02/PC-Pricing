"""Scraper khám phá giá Phong Vũ (phongvu.vn) (Playwright + proxy Việt Nam).

Phong Vũ chặn theo vùng địa lý các IP ngoài Việt Nam (Cloudflare 403), nên scraper này định
tuyến qua proxy VN (use_proxy=True; xem browser.py / .env). Kết quả được render bằng JS.

Selector đã xác minh (DOM đã render):
    price : .att-product-detail-latest-price   (giá hiện tại; KHÔNG phải .att-product-detail-retail-price)
    url   : anchor sản phẩm /laptop-dell-...--s<id>   (SKU = token slug trước "--s")

LAPTOP (--category laptop, mặc định) — GIỮ NGUYÊN luồng CŨ, match-only: chỉ ghi source/giá cho
SKU đã có sẵn trong catalog TNC (`tracked`). Không đưa vào flow missing_products.

CÁC CATEGORY KHÁC (--category <cat>) — LUỒNG MỚI (2026-09), theo đúng mẫu discover_anphat.py:
`discover()` ở nhánh category vốn ĐÃ cào TOÀN BỘ trang danh mục (không lọc theo SKU đã khớp,
chỉ lọc name_match/name_exclude) — nên không cần thêm hàm "discover_category_full" riêng như An
Phát, `discover()` hiện tại đã đóng đúng vai trò đó. `_run_category()` đối chiếu SKU với catalog
TNC:
  - SKU khớp catalog TNC (`tracked`)     -> ghi source/price như cũ (chỉ SKU MỚI mới ghi giá).
  - SKU không suy ra được HOẶC không có trong TNC -> upsert vào bảng `missing_products` (xem
    scraper/db.py: upsert_missing_products / resolve_missing_products) để xem lại tay.
  - Một URL trước đây từng nằm trong `missing_products` mà giờ ĐÃ khớp (TNC vừa bổ sung đúng SKU
    đó) sẽ được đánh dấu resolved=true qua `resolve_missing_products()`.

Phong Vũ đã có sẵn tín hiệu `in_stock` ngay trên TRANG DANH SÁCH (dò "Liên hệ" trong text của
card — xem JS trong `discover()`), khác với An Phát (phải ghé từng trang sản phẩm qua
`check_stock()`). Vì vậy `_run_category()` ở đây dùng thẳng `item.get("in_stock", True)`, không
cần bước kiểm tồn kho riêng.

DÙNG browser_session (KHÔNG dùng browser_page): trang này cần proxy VN, và một lượt khám phá có
thể tốn nhiều phút (cuộn tải lazy-load). Nếu proxy hết hạn GIỮA lượt chạy, goto_with_retry() cần
relaunch được browser với proxy khác NGAY — xem ghi chú "BUG ĐÃ SỬA" ở đầu browser.py.

Cách dùng:
    python -m scraper.discover_phongvu --dry
    python -m scraper.discover_phongvu
    python -m scraper.discover_phongvu --category ram --dry
    python -m scraper.discover_phongvu --category ram
"""

from __future__ import annotations

import argparse
import re
import sys
from argparse import Namespace

from .brand import brand_of
from .browser import browser_session, goto_with_retry
from .config import categories, is_old_listing_name, name_exclude_re, name_match_re, resolve_url
from .db import (
    ensure_competitor,
    fetch_catalog_skus,
    fetch_existing_source_skus,
    get_client,
    insert_prices,
    resolve_missing_products,
    upsert_missing_products,
    upsert_sources,
)
from .sku import derive_sku

COMPETITOR = "Phong Vũ"
BASE_URL = "https://phongvu.vn"
BRANDS = {
    "dell": "https://phongvu.vn/c/laptop-dell",
    "lenovo": "https://phongvu.vn/c/laptop-lenovo",
    "apple": "https://phongvu.vn/c/mac",
    "hp": "https://phongvu.vn/c/laptop-hp",
    "asus": "https://phongvu.vn/c/laptop-asus",
    "acer": "https://phongvu.vn/c/laptop-acer",
    "msi": "https://phongvu.vn/c/laptop-msi",
    "gigabyte": "https://phongvu.vn/c/laptop-gigabyte",
}

PRICE_SELECTOR = ".att-product-detail-latest-price"


def _digits_to_int(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def discover(brand: str = "dell", category: str = "laptop") -> list[dict]:
    """Trả về [{name, price, url, in_stock}] cho các sản phẩm trên trang danh sách đã render.

    Laptop (mặc định) dùng URL danh mục laptop per-brand. Các danh mục khác dùng URL `paths.phongvu`
    của danh mục và giữ lại theo name_match (Phong Vũ không có ô tìm kiếm).

    QUAN TRỌNG: ở nhánh category, hàm này cào TOÀN BỘ sản phẩm của danh mục — KHÔNG lọc theo SKU
    đã khớp catalog TNC hay chưa (việc đó do caller — `_run_category()` — tự đối chiếu sau). Đây
    chính là vai trò tương đương `discover_category_full()` bên discover_anphat.py.
    """
    is_laptop = category == "laptop"
    excl_re = name_exclude_re(category)
    if is_laptop:
        list_url, name_re = BRANDS[brand], None
    else:
        list_url = resolve_url("phongvu", category)
        name_re = name_match_re(category)
    if not list_url:
        return []
    results: list[dict] = []
    with browser_session(use_proxy=True) as session:
        if not goto_with_retry(session, list_url, PRICE_SELECTOR, label=COMPETITOR):
            return results

        # session.page có thể đã đổi (rebuild giữa chừng nếu proxy chết) — đọc LẠI sau
        # goto_with_retry, rồi dùng biến `page` cục bộ cho phần còn lại (không có thêm điều hướng
        # trang nào bên dưới nên không cần đọc lại session.page thêm lần nào nữa).
        page = session.page

        # Cuộn để tải các card render trễ (lazy) cho đến khi số lượng ổn định.
        last, stable = -1, 0
        for _ in range(40):
            count = page.eval_on_selector_all(PRICE_SELECTOR, "(els)=>els.length")
            stable = stable + 1 if count == last else 0
            if stable >= 4:
                break
            last = count
            page.keyboard.press("End")
            page.mouse.wheel(0, 6000)
            page.wait_for_timeout(1500)

        # Với mỗi phần tử giá hiện tại, đi ngược lên anchor sản phẩm của card và đọc name+url.
        items = page.eval_on_selector_all(
            PRICE_SELECTOR,
            """
            (prices) => {
              const out = [];
              const seen = new Set();
              for (const p of prices) {
                let el = p, a = null;
                for (let i = 0; i < 8 && el; i++) {
                  el = el.parentElement;
                  if (el) { const link = el.querySelector('a[href*="--s"]'); if (link) { a = link; break; } }
                }
                if (!a) continue;
                const href = a.getAttribute('href');
                if (!href || seen.has(href)) continue;
                // Tên: ưu tiên title / <h3> / alt của ảnh; a.innerText là phương án cuối vì trên
                // card màn hình nó bắt đầu bằng blurb "TIẾT KIỆM ..." chứ không phải tên sản phẩm.
                const h3 = a.querySelector('h3');
                const img = a.querySelector('img');
                const name = (a.getAttribute('title') ||
                              (h3 && h3.innerText) ||
                              (img && img.getAttribute('alt')) ||
                              a.innerText || '').trim();
                // hết hàng: Phong Vũ hiển thị "Liên hệ" thay vì nút mua hàng.
                const in_stock = !/liên hệ/i.test((el && el.innerText) || '');
                seen.add(href);
                out.push({ name, price: p.innerText.trim(), url: href, in_stock });
              }
              return out;
            }
            """,
        )
        for it in items:
            name = it["name"]
            # Danh mục (không phải laptop): giữ tên khớp name_match — URL /c/ có thể lẫn phụ kiện.
            if (excl_re and excl_re.search(name)) or (not is_laptop and not (name_re and name_re.search(name))):
                continue
            price = _digits_to_int(it["price"])
            href = it["url"]
            url = (BASE_URL + href) if href and href.startswith("/") else href
            if price:
                results.append(
                    {"name": name, "price": price, "url": url,
                     "in_stock": it.get("in_stock", True)}
                )
    return results


def _run_laptop(client, args) -> int:
    """Luồng CŨ (match-only) cho laptop — GIỮ NGUYÊN hành vi hiện tại, không đưa vào
    missing_products (giống cách discover_anphat.py giữ nguyên nhánh laptop của nó)."""
    tracked = fetch_catalog_skus(client, "Laptop")
    if not tracked:
        print("No tracked products yet. Run the TNC scraper first to populate the catalog.")
        return 0

    existing = fetch_existing_source_skus(client, COMPETITOR)

    print(
        f"Discovering '{COMPETITOR}' (via VN proxy) — laptop/{args.brand}"
        f"{' (dry run)' if args.dry else ''}...\n"
    )
    found = discover(args.brand, "laptop")
    print(
        f"{len(found)} unique product(s) parsed; matching against {len(tracked)} TNC SKU(s), "
        f"{len(existing)} đã có source (daily sync lo giá).\n"
    )

    fallback_url = BRANDS[args.brand]
    source_rows, price_rows = [], []
    new_count = 0
    for item in found:
        sku = derive_sku(item["name"], item.get("url"), "Laptop")
        if sku is None or sku not in tracked:
            continue
        in_stock = item.get("in_stock", True)
        flag = "" if in_stock else "  [OUT OF STOCK]"
        is_new = sku not in existing
        is_used = is_old_listing_name(item.get("name", ""))
        tag = "[MỚI] " if is_new else ""
        print(f"- {tag}{sku}: {item['price']:,} VND{flag}  ({(item['name'] or item['url'])[:45]})")
        source_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "url": item.get("url") or fallback_url, "is_used": is_used}
        )
        # Chỉ ghi giá cho SKU CHƯA từng có source ở competitor này (sản phẩm mới phát hiện).
        if is_new:
            price_rows.append(
                {"product_sku": sku, "competitor": COMPETITOR, "price": item["price"], "in_stock": in_stock, "is_used": is_used}
            )
            new_count += 1

    if not args.dry:
        upsert_sources(client, source_rows)
        insert_prices(client, price_rows)

    print(
        f"\nDone. {new_count} SKU MỚI được ghi giá trên {COMPETITOR} "
        f"({len(source_rows) - new_count} SKU cũ chỉ refresh URL, không ghi giá lại)."
    )
    return 0


def _run_category(client, args) -> int:
    """Luồng MỚI (mọi category ngoài laptop): cào TOÀN BỘ trang danh mục (`discover()` đã tự làm
    việc này), đối chiếu SKU với TNC — khớp thì ghi giá (chỉ SKU mới); không khớp (không suy được
    SKU, hoặc TNC chưa bán) thì lưu vào `missing_products` để xem lại tay. Mẫu y hệt
    `_run_category()` trong discover_anphat.py."""
    category = args.category
    category_label = category.capitalize()

    tracked = fetch_catalog_skus(client, category_label)
    existing = fetch_existing_source_skus(client, COMPETITOR)

    list_url = resolve_url("phongvu", category)
    print(
        f"Discovering '{COMPETITOR}' (via VN proxy) — category '{category}' qua trang danh mục "
        f"(KHÔNG lọc theo catalog TNC trước){' (dry run)' if args.dry else ''}...\n"
    )
    if not list_url:
        print(f"  ⚠️  Chưa cấu hình paths.phongvu cho category '{category}' trong sources.yaml — bỏ qua.")
        return 0

    found = discover(category=category)
    print(f"{len(found)} sản phẩm tìm thấy trên trang danh mục.\n")

    if not tracked:
        print(
            f"  ⚠️  Catalog TNC chưa có SKU nào trong danh mục '{category_label}' — MỌI sản phẩm "
            f"tìm được sẽ được coi là 'chưa khớp' và lưu vào missing_products.\n"
        )

    fallback_url = list_url

    matched_new: list[dict] = []
    matched_known: list[dict] = []
    missing_rows: list[dict] = []
    resolved_urls: list[str] = []

    for item in found:
        sku = derive_sku(item["name"], item.get("url"), category_label)
        is_used = is_old_listing_name(item.get("name", ""))
        if sku and sku in tracked:
            resolved_urls.append(item["url"])  # từng "thiếu" (nếu có) nay đã khớp -> resolve
            row = {**item, "sku": sku, "is_used": is_used}
            (matched_known if sku in existing else matched_new).append(row)
        else:
            reason = "Không suy được SKU" if not sku else "TNC chưa bán sản phẩm này"
            missing_rows.append({
                "competitor": COMPETITOR,
                "category": category_label,
                "brand": brand_of(item["name"]) or None,
                "name": item["name"],
                "price": item.get("price"),
                "url": item.get("url") or "",
                "is_used": is_used,
                "reason": reason,
            })

    source_rows, price_rows = [], []
    for item in matched_new:
        sku = item["sku"]
        in_stock = item.get("in_stock", True)
        flag = "" if in_stock else "  [OUT OF STOCK]"
        print(f"- [MỚI][KHỚP] {sku}: {item['price']:,} VND{flag}  ({item['name'][:55]})")
        source_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "url": item.get("url") or fallback_url, "is_used": item["is_used"]}
        )
        price_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "price": item["price"], "in_stock": in_stock, "is_used": item["is_used"]}
        )

    for item in matched_known:
        source_rows.append(
            {"product_sku": item["sku"], "competitor": COMPETITOR, "url": item.get("url") or fallback_url}
        )

    if args.dry:
        print(
            f"\n[DRY] {len(matched_new)} SKU MỚI khớp TNC, {len(matched_known)} SKU cũ (chỉ refresh URL), "
            f"{len(missing_rows)} sản phẩm KHÔNG khớp (sẽ lưu vào missing_products nếu chạy thật)."
        )
        for row in missing_rows[:15]:
            price_s = f"{row['price']:,} VND" if row.get("price") else "?"
            print(f"  - [MISSING] ({row['reason']}) {row['name'][:60]} — {price_s}")
        if len(missing_rows) > 15:
            print(f"  ... và {len(missing_rows) - 15} sản phẩm không khớp khác.")
        return 0

    if source_rows:
        upsert_sources(client, source_rows)
    if price_rows:
        insert_prices(client, price_rows)
    if missing_rows:
        upsert_missing_products(client, missing_rows)
    if resolved_urls:
        resolve_missing_products(client, COMPETITOR, resolved_urls)

    print(
        f"\nDone. {len(matched_new)} SKU MỚI được ghi giá, {len(matched_known)} SKU cũ chỉ refresh "
        f"URL, {len(missing_rows)} sản phẩm KHÔNG khớp được lưu vào missing_products "
        f"({len(resolved_urls)} sản phẩm trước đây thiếu nay đã khớp -> đánh dấu resolved)."
    )
    return 0


def _run_all(client, dry: bool) -> int:
    """Cào TOÀN BỘ Phong Vũ trong một lần chạy: mọi brand laptop (luồng cũ, match-only) + mọi
    category đang bật khác (luồng mới, có missing_products). Chậm hơn nhiều so với chạy từng
    --category một (mở/đóng browser cho mỗi brand/category) — cân nhắc --dry trước, hoặc chạy
    song song qua CI matrix (xem scrape.yml) nếu cần nhanh. Một brand/category lỗi KHÔNG làm dừng
    cả lượt chạy — in lỗi rồi chạy tiếp cái kế. Mẫu y hệt `_run_all()` trong discover_anphat.py.
    """
    n_ok, n_fail = 0, 0

    print(f"=== [1/2] Laptop — {len(BRANDS)} brand ===\n")
    for brand in BRANDS:
        print(f"--- laptop/{brand} ---")
        try:
            _run_laptop(client, Namespace(brand=brand, dry=dry))
            n_ok += 1
        except Exception as e:
            print(f"  ❌ Lỗi khi cào laptop/{brand}: {e}")
            n_fail += 1
        print()

    cats = sorted(categories())
    print(f"=== [2/2] {len(cats)} category khác ===\n")
    for cat in cats:
        print(f"--- category/{cat} ---")
        try:
            _run_category(client, Namespace(category=cat, dry=dry))
            n_ok += 1
        except Exception as e:
            print(f"  ❌ Lỗi khi cào category/{cat}: {e}")
            n_fail += 1
        print()

    print(f"=== Hoàn tất --all: {n_ok} pass thành công, {n_fail} pass lỗi ===")
    return 0 if n_fail == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Discover Phong Vũ prices by brand and category.")
    ap.add_argument("--brand", default="dell", help="brand to scrape (e.g. dell, samsung)")
    ap.add_argument(
        "--category", default="laptop", choices=["laptop", *sorted(categories())],
        help="product category to scrape",
    )
    ap.add_argument("--dry", action="store_true", help="print results, don't write to the DB")
    ap.add_argument(
        "--all", action="store_true",
        help="Cào TOÀN BỘ: mọi brand laptop + mọi category đang bật, trong một lần chạy (bỏ qua --brand/--category)",
    )
    args = ap.parse_args()

    client = get_client()
    ensure_competitor(client, COMPETITOR)

    if args.all:
        return _run_all(client, args.dry)

    if args.category == "laptop":
        return _run_laptop(client, args)
    return _run_category(client, args)


if __name__ == "__main__":
    sys.exit(main())