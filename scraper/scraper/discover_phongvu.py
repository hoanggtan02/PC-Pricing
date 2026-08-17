"""Scraper khám phá giá Phong Vũ (phongvu.vn) (Playwright + proxy Việt Nam).

Phong Vũ chặn theo vùng địa lý các IP ngoài Việt Nam (Cloudflare 403), nên scraper này định
tuyến qua proxy VN (use_proxy=True; xem browser.py / .env). Kết quả được render bằng JS.

Selector đã xác minh (DOM đã render):
    price : .att-product-detail-latest-price   (giá hiện tại; KHÔNG phải .att-product-detail-retail-price)
    url   : anchor sản phẩm /laptop-dell-...--s<id>   (SKU = token slug trước "--s")

Chỉ đối chiếu (match-only): chỉ ghi nhận giá cho các SKU đã có trong `products` (catalog của TNC).

MODE A (weekend discovery) — CHỈ GHI GIÁ CHO SKU MỚI: kịch bản này chạy cuối tuần để tìm sản
phẩm MỚI, không phải để cào lại giá của mọi sản phẩm đã biết — giá đó Mode B (sync_prices, chạy
hàng ngày) đã cào đều đặn rồi. Vì vậy SKU nào ĐÃ có source ở competitor này (fetch_existing_source_skus)
thì chỉ được refresh URL (upsert_sources), KHÔNG ghi thêm dòng price_history trùng lặp.

Cách dùng:
    python -m scraper.discover_phongvu --dry
    python -m scraper.discover_phongvu
"""

from __future__ import annotations

import argparse
import re
import sys

from .browser import browser_page, goto_with_retry
from .config import categories, name_exclude_re, name_match_re, resolve_url
from .db import (
    ensure_competitor,
    fetch_catalog_skus,
    fetch_existing_source_skus,
    get_client,
    insert_prices,
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
    """Trả về [{name, price, url}] cho các sản phẩm trên trang danh sách đã render.

    Laptop (mặc định) dùng URL danh mục laptop per-brand. Các danh mục khác dùng URL `paths.phongvu`
    của danh mục và giữ lại theo name_match (Phong Vũ không có ô tìm kiếm).
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
    with browser_page(use_proxy=True) as page:
        if not goto_with_retry(page, list_url, PRICE_SELECTOR, label=COMPETITOR):
            return results

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



def main() -> int:
    ap = argparse.ArgumentParser(description="Discover Phong Vũ prices by brand and category.")
    ap.add_argument("--brand", default="dell", help="brand to scrape (e.g. dell, samsung)")
    ap.add_argument(
        "--category", default="laptop", choices=["laptop", *sorted(categories())],
        help="product category to scrape",
    )
    ap.add_argument("--dry", action="store_true", help="print results, don't write to the DB")
    args = ap.parse_args()

    client = get_client()
    ensure_competitor(client, COMPETITOR)
    tracked = fetch_catalog_skus(client, args.category.capitalize())
    if not tracked:
        print("No tracked products yet. Run the TNC scraper first to populate the catalog.")
        return 0

    # SKU nào đã có source ở Phong Vũ -> đã được Mode B (daily sync) theo dõi giá. Chỉ ghi giá
    # cho SKU MỚI (chưa có trong tập này); sku cũ chỉ refresh URL.
    existing = fetch_existing_source_skus(client, COMPETITOR)

    print(
        f"Discovering '{COMPETITOR}' (via VN proxy) — {args.category}/{args.brand}"
        f"{' (dry run)' if args.dry else ''}...\n"
    )
    found = discover(args.brand, args.category)
    print(
        f"{len(found)} unique product(s) parsed; matching against {len(tracked)} TNC SKU(s), "
        f"{len(existing)} đã có source (daily sync lo giá).\n"
    )

    category_label = args.category.capitalize()
    fallback_url = BRANDS[args.brand] if args.category == "laptop" else resolve_url("phongvu", args.category)
    source_rows, price_rows = [], []
    new_count = 0
    for item in found:
        sku = derive_sku(item["name"], item.get("url"), category_label)
        if sku is None or sku not in tracked:
            continue
        in_stock = item.get("in_stock", True)
        flag = "" if in_stock else "  [OUT OF STOCK]"
        is_new = sku not in existing
        tag = "[MỚI] " if is_new else ""
        print(f"- {tag}{sku}: {item['price']:,} VND{flag}  ({(item['name'] or item['url'])[:45]})")
        source_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "url": item.get("url") or fallback_url}
        )
        # Chỉ ghi giá cho SKU CHƯA từng có source ở competitor này (sản phẩm mới phát hiện).
        if is_new:
            price_rows.append(
                {"product_sku": sku, "competitor": COMPETITOR, "price": item["price"], "in_stock": in_stock}
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


if __name__ == "__main__":
    sys.exit(main())