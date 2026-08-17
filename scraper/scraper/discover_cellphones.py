"""Scraper khám phá dữ liệu bằng tìm kiếm cho CellphoneS (Playwright).

Trang kết quả tìm kiếm của CellphoneS được render bằng JavaScript — HTML thô không chứa sản
phẩm nào, nên httpx/BeautifulSoup thông thường không thể thấy chúng. Module này điều khiển một
trình duyệt Chromium headless để cho JS của trang chạy, sau đó đọc các thẻ sản phẩm đã render.

Module này KHÁM PHÁ sản phẩm bằng tìm kiếm (không cần URL riêng cho từng sản phẩm): với một
truy vấn như "laptop dell", nó trả về tên + giá hiện tại + URL sản phẩm của mọi thẻ kết quả. Sau
đó ta khớp từng sản phẩm với một SKU đang theo dõi (SKU xuất hiện trong tên/URL sản phẩm) và lưu
giá.

MODE A (weekend discovery) — CHỈ GHI GIÁ CHO SKU MỚI: kịch bản này chạy cuối tuần để tìm sản
phẩm MỚI, không phải để cào lại giá của mọi sản phẩm đã biết — giá đó Mode B (sync_prices, chạy
hàng ngày) đã cào đều đặn rồi. Vì vậy SKU nào ĐÃ có source ở competitor này (fetch_existing_source_skus)
thì chỉ được refresh URL (upsert_sources), KHÔNG ghi thêm dòng price_history trùng lặp.

Cách dùng:
    python -m scraper.discover_cellphones            # khám phá + ghi vào Supabase
    python -m scraper.discover_cellphones --dry      # khám phá + in ra, không ghi vào DB
"""

from __future__ import annotations

import argparse
import re
import sys

from playwright.sync_api import sync_playwright

from .brand import brand_of
from .browser import assert_parsed, goto_with_retry
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

COMPETITOR = "CellphoneS"
BRANDS = {
    "dell": "https://cellphones.com.vn/catalogsearch/result?q=laptop%20dell",
    "lenovo": "https://cellphones.com.vn/catalogsearch/result?q=laptop%20lenovo",
    "apple": "https://cellphones.com.vn/laptop/mac.html",
    "hp": "https://cellphones.com.vn/laptop/hp.html",
    "asus": "https://cellphones.com.vn/laptop/asus.html",
    "acer": "https://cellphones.com.vn/laptop/acer.html",
    "msi": "https://cellphones.com.vn/laptop/msi.html",
    "gigabyte": "https://cellphones.com.vn/laptop/gigabyte.html",
}

# Các selector của thẻ sản phẩm (DOM sau khi render).
CARD_SELECTOR = ".product-info, .product__info, [class*='product-info']"
NAME_SELECTOR = ".product__name"
PRICE_SELECTOR = ".product__price--show"


def _digits_to_int(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def discover(brand: str = "dell", category: str = "laptop") -> list[dict]:
    """Trả về [{name, price, url}] cho các sản phẩm trên trang tìm kiếm đã render.

    Laptop (mặc định) lọc theo một `brand` qua URL per-brand cũ. Các danh mục khác chạy theo
    danh mục: một tìm kiếm cho cả danh mục (mọi thương hiệu), giữ lại theo name_match của danh
    mục; caller suy ra thương hiệu của mỗi sản phẩm từ tên.
    """
    if category == "laptop":
        search_url, want, name_re, excl_re = BRANDS[brand], brand.lower(), None, None
    else:
        search_url, want = resolve_url("cellphones", category), None
        name_re = name_match_re(category)
        excl_re = name_exclude_re(category)
    if not search_url:
        return []
    results: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        )
        if not goto_with_retry(page, search_url, NAME_SELECTOR, label=COMPETITOR):
            browser.close()
            return results

        # Phần sản phẩm còn lại nằm sau nút "Xem thêm" (.load-more-btn), mỗi lần click tải thêm +20.
        stale = 0
        for _ in range(40):
            btn = page.query_selector(".load-more-btn")
            if not btn or not btn.is_visible():
                break
            before = len(page.query_selector_all(NAME_SELECTOR))
            try:
                btn.scroll_into_view_if_needed()
                page.click(".load-more-btn", timeout=5000)
            except Exception:
                break
            page.wait_for_timeout(2000)
            after = len(page.query_selector_all(NAME_SELECTOR))
            stale = stale + 1 if after == before else 0
            if stale >= 3:
                break

        cards = page.query_selector_all(CARD_SELECTOR)
        extracted = 0  # số card trích được name+price hợp lệ (trước khi lọc brand)
        seen: set[str] = set()  # trang render mỗi thẻ hai lần (biến thể desktop + mobile)
        for card in cards:
            name_el = card.query_selector(NAME_SELECTOR)
            price_el = card.query_selector(PRICE_SELECTOR)
            link_el = card.query_selector("a[href]")
            if not name_el or not price_el:
                continue
            name = (name_el.inner_text() or "").strip()
            price = _digits_to_int(price_el.inner_text())
            url = link_el.get_attribute("href") if link_el else None
            key = url or name
            if name and price:
                extracted += 1
           
            notif = card.query_selector(".product__more-info__item.notification")
            in_stock = not (notif and (notif.inner_text() or "").strip())
            # Laptop mode: keep one brand. Category mode: keep names matching the category.
            keep = (brand_of(name).lower() == want) if want else bool(name_re and name_re.search(name))
            if excl_re and excl_re.search(name):
                keep = False
            if name and price and keep and key not in seen:
                seen.add(key)
                results.append({"name": name, "price": price, "url": url, "in_stock": in_stock})
        browser.close()
    # Có card nhưng không trích được name+price nào -> selector đã lỗi thời (không phải "0 thật").
    assert_parsed(COMPETITOR, len(cards), extracted)
    return results



def main() -> int:
    ap = argparse.ArgumentParser(description="Discover CellphoneS prices by brand and category.")
    ap.add_argument("--brand", default="dell", help="brand to scrape (e.g. dell, samsung)")
    ap.add_argument(
        "--category", default="laptop", choices=["laptop", *sorted(categories())],
        help="product category to scrape",
    )
    ap.add_argument("--dry", action="store_true", help="print results, don't write to the DB")
    args = ap.parse_args()

    client = get_client()
    ensure_competitor(client, COMPETITOR)

    # Chỉ khớp: chỉ ghi giá cho các SKU đã có sẵn trong danh mục của TNC.
    tracked = fetch_catalog_skus(client, args.category.capitalize())
    if not tracked:
        print("No tracked products yet. Run the TNC scraper first to populate the catalog.")
        return 0

    # SKU nào đã có source ở CellphoneS -> đã được Mode B (daily sync) theo dõi giá. Chỉ ghi giá
    # cho SKU MỚI (chưa có trong tập này); sku cũ chỉ refresh URL.
    existing = fetch_existing_source_skus(client, COMPETITOR)

    print(
        f"Discovering '{COMPETITOR}' search results — {args.category}/{args.brand}"
        f"{' (dry run)' if args.dry else ''}...\n"
    )
    found = discover(args.brand, args.category)
    print(
        f"{len(found)} unique product(s) parsed; matching against {len(tracked)} TNC SKU(s), "
        f"{len(existing)} đã có source (daily sync lo giá).\n"
    )

    category_label = args.category.capitalize()
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
        print(f"- {tag}{sku}: {item['price']:,} VND{flag}  ({item['name'][:50]})")
        source_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR,
             "url": item.get("url") or (BRANDS[args.brand] if args.category == "laptop" else None)}
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