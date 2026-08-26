"""Scraper khám phá dữ liệu bằng tìm kiếm cho Memoryzone (memoryzone.com.vn) (Playwright, không cần proxy).

Memoryzone truy cập trực tiếp được. Giống GearVN, trang này chuyên về linh kiện/PC và ít/không
bán laptop Dell — tìm kiếm "laptop dell" trên trang này chủ yếu ra phụ kiện (balo, túi, v.v.).
Ta lọc theo tên để lấy đúng laptop và ghi lại bất cứ thứ gì xuất hiện (thường là không có gì, và
điều đó vẫn ổn).

QUAN TRỌNG — HAI THEME KHÁC NHAU trên cùng site (phát hiện 2026-08 từ bug thật: category
"software" timeout hàng loạt ở PRICE_SELECTOR cũ):
  1. Trang TÌM KIẾM (dùng cho laptop, /search?query=...) — markup cũ, đã xác nhận:
         card  : (không có selector card riêng, quét ngược từ phần tử giá)
         price : .ae-price--primary
  2. Trang CATEGORY TĨNH (dùng cho mọi category khác qua `paths.memoryzone`, ví dụ
     /phan-mem-ban-quyen) — theme Bizweb/Sapo (bizweb.dktcdn.net), markup HOÀN TOÀN KHÁC, xác
     nhận từ HTML thật của https://memoryzone.com.vn/phan-mem-ban-quyen:
         card  : .item_product_main
         name  : .product-name a
         price : .price-box .price      (giá hiện tại; .compare-price là giá gốc gạch ngang)
     .ae-price--primary KHÔNG TỒN TẠI trên các trang này — dùng nhầm selector khiến
     goto_with_retry() chờ đủ timeout rồi bỏ cuộc cho MỌI category không phải laptop, không phải
     lỗi mạng/chặn bot. Hai nhánh selector dưới đây tách riêng cho từng loại trang.

Chỉ khớp: chỉ ghi lại giá cho các SKU đã có sẵn trong `products` (danh mục của TNC).

MODE A (weekend discovery) — CHỈ GHI GIÁ CHO SKU MỚI: kịch bản này chạy cuối tuần để tìm sản
phẩm MỚI, không phải để cào lại giá của mọi sản phẩm đã biết — giá đó Mode B (sync_prices, chạy
hàng ngày) đã cào đều đặn rồi. Vì vậy SKU nào ĐÃ có source ở competitor này (fetch_existing_source_skus)
thì chỉ được refresh URL (upsert_sources), KHÔNG ghi thêm dòng price_history trùng lặp.

Cách dùng:
    python -m scraper.discover_memoryzone --dry
    python -m scraper.discover_memoryzone
    python -m scraper.discover_memoryzone --category software --dry
"""

from __future__ import annotations

import argparse
import re
import sys

from .browser import browser_page, goto_with_retry
from .config import categories, is_old_listing_name, name_exclude_re, name_match_re, resolve_url
from .db import (
    ensure_competitor,
    fetch_catalog_skus,
    fetch_existing_source_skus,
    get_client,
    insert_prices,
    upsert_sources,
)
from .stock import is_in_stock as stock_is_in
from .sku import derive_sku

COMPETITOR = "Memoryzone"
BASE_URL = "https://memoryzone.com.vn"
BRANDS = {
    "dell": "https://memoryzone.com.vn/search?query=laptop%20dell",
    "lenovo": "https://memoryzone.com.vn/search?query=laptop%20lenovo",
    "apple": "https://memoryzone.com.vn/search?query=macbook",
    "hp": "https://memoryzone.com.vn/search?query=laptop%20hp",
    "asus": "https://memoryzone.com.vn/search?query=laptop%20asus",
    "acer": "https://memoryzone.com.vn/search?query=laptop%20acer",
    "msi": "https://memoryzone.com.vn/search?query=laptop%20msi",
    "gigabyte": "https://memoryzone.com.vn/laptop-gigabyte",
}

# Trang TÌM KIẾM (laptop) — markup cũ, đã xác nhận hoạt động, GIỮ NGUYÊN.
PRICE_SELECTOR = ".ae-price--primary"

# Trang CATEGORY TĨNH (mọi category khác qua paths.memoryzone) — theme Bizweb/Sapo, xác nhận từ
# HTML thật của /phan-mem-ban-quyen (xem docstring đầu file). KHÔNG dùng chung với PRICE_SELECTOR.
CATEGORY_CARD_SELECTOR = ".item_product_main"
CATEGORY_NAME_SELECTOR = ".product-name a"
CATEGORY_PRICE_SELECTOR = ".price-box .price"
CATEGORY_PAGE_CAP = 30  # chốt an toàn cho phân trang ?page=N; dừng sớm khi trang không thêm gì mới.


def _digits_to_int(text: str) -> int | None:
    m = re.search(r"\d{1,3}(?:\.\d{3})+", text or "")
    return int(m.group(0).replace(".", "")) if m else None


def _discover_laptop(page, brand: str) -> list[dict]:
    """Trang tìm kiếm laptop — logic CŨ, không đổi (đã xác nhận hoạt động)."""
    search_url = BRANDS[brand]
    if not goto_with_retry(page, search_url, PRICE_SELECTOR, label=COMPETITOR):
        return []

    last, stable = -1, 0
    for _ in range(40):
        count = page.eval_on_selector_all(PRICE_SELECTOR, "(els)=>els.length")
        stable = stable + 1 if count == last else 0
        if stable >= 4:
            break
        last = count
        page.mouse.wheel(0, 6000)
        page.wait_for_timeout(1500)

    items = page.eval_on_selector_all(
        PRICE_SELECTOR,
        """
        (prices) => {
          const out = [];
          const seen = new Set();
          for (const p of prices) {
            let card = p;
            for (let i = 0; i < 6 && card.parentElement; i++) {
              card = card.parentElement;
              if (card.querySelector('a[href]') && card.querySelector('h3')) break;
            }
            const a = card.querySelector('a[href]');
            const h3 = card.querySelector('h3');
            if (!a || !h3) continue;
            const href = (a.getAttribute('href') || '').split('?')[0];
            if (!href || seen.has(href)) continue;
            const name = h3.innerText.trim();
            if (!/^(laptop|macbook)/i.test(name)) continue;
            seen.add(href);
            out.push({ name, price: p.innerText.trim(), url: href, card_text: (card.textContent || '') });
          }
          return out;
        }
        """,
    )
    results: list[dict] = []
    for it in items:
        price = _digits_to_int(it["price"])
        href = it["url"]
        url = (BASE_URL + href) if href and href.startswith("/") else href
        if price:
            in_stock = stock_is_in(it.get("card_text"))
            results.append({"name": it["name"], "price": price, "url": url, "in_stock": in_stock})
    return results


def _discover_category(page, category: str) -> list[dict]:
    """Trang category tĩnh (theme Bizweb/Sapo) — markup KHÁC hẳn trang tìm kiếm, xem docstring
    đầu file. Phân trang qua ?page=N (kiểu Bizweb phổ biến); dừng khi trang không thêm sản phẩm
    mới nào, hoặc chạm CATEGORY_PAGE_CAP."""
    search_url = resolve_url("memoryzone", category)
    if not search_url:
        return []
    excl_re = name_exclude_re(category)
    name_re = name_match_re(category)

    results: list[dict] = []
    seen_urls: set[str] = set()
    for page_num in range(1, CATEGORY_PAGE_CAP + 1):
        if page_num == 1:
            if not goto_with_retry(page, search_url, CATEGORY_CARD_SELECTOR, label=COMPETITOR):
                break
        else:
            joiner = "&" if "?" in search_url else "?"
            page_url = f"{search_url}{joiner}page={page_num}"
            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector(CATEGORY_CARD_SELECTOR, timeout=10000)
            except Exception:
                break  # trang chậm/lỗi/hết trang — dừng, giữ lại những gì đã thu thập được

        items = page.eval_on_selector_all(
            CATEGORY_CARD_SELECTOR,
            """
            (cards) => {
                const out = [];
                for (const card of cards) {
                    const nameEl = card.querySelector('.product-name a');
                    const priceEl = card.querySelector('.price-box .price');
                    if (!nameEl || !priceEl) continue;
                    const name = nameEl.innerText.trim();
                    const href = nameEl.getAttribute('href') || '';
                    const price = priceEl.innerText.trim();
                    out.push({ name, price, url: href, card_text: (card.innerText || '') });
                }
                return out;
            }
            """,
        )

        new_on_page = 0
        for it in items:
            name = it["name"]
            if excl_re and excl_re.search(name):
                continue
            if name_re and not name_re.search(name):
                continue
            price = _digits_to_int(it["price"])
            href = it["url"]
            url = (BASE_URL + href) if href and href.startswith("/") else href
            if not price or not url or url in seen_urls:
                continue
            seen_urls.add(url)
            new_on_page += 1
            in_stock = stock_is_in(it.get("card_text"))
            results.append({"name": name, "price": price, "url": url, "in_stock": in_stock})

        if new_on_page == 0:  # trang cuối / không phân trang
            break
    return results


def discover(brand: str = "dell", category: str = "laptop") -> list[dict]:
    """Trả về [{name, price, url, in_stock}] cho các sản phẩm tìm được.

    Laptop (mặc định) dùng URL per-brand + lọc /^laptop|macbook/ trên trang TÌM KIẾM. Các danh
    mục khác dùng URL category TĨNH của `paths.memoryzone` — theme khác hẳn, xem docstring đầu
    file — nên dùng hàm trích xuất riêng (_discover_category).
    """
    is_laptop = category == "laptop"
    with browser_page(use_proxy=False) as page:
        if is_laptop:
            return _discover_laptop(page, brand)
        return _discover_category(page, category)


def main() -> int:
    ap = argparse.ArgumentParser(description="Discover Memoryzone prices by brand and category.")
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

    # SKU nào đã có source ở Memoryzone -> đã được Mode B (daily sync) theo dõi giá. Chỉ ghi giá
    # cho SKU MỚI (chưa có trong tập này); sku cũ chỉ refresh URL.
    existing = fetch_existing_source_skus(client, COMPETITOR)

    print(
        f"Discovering '{COMPETITOR}' — {args.category}/{args.brand}"
        f"{' (dry run)' if args.dry else ''}...\n"
    )
    found = discover(args.brand, args.category)
    print(
        f"{len(found)} product(s) parsed; matching against {len(tracked)} TNC SKU(s), "
        f"{len(existing)} đã có source (daily sync lo giá).\n"
    )

    category_label = args.category.capitalize()
    fallback_url = BRANDS[args.brand] if args.category == "laptop" else resolve_url("memoryzone", args.category)
    source_rows, price_rows = [], []
    new_count = 0
    for item in found:
        sku = derive_sku(item["name"], item.get("url"), category_label)
        if sku is None or sku not in tracked:
            continue
        is_new = sku not in existing
        is_used = is_old_listing_name(item.get("name", ""))
        tag = "[MỚI] " if is_new else ""
        flag = "" if item.get("in_stock", True) else "  [OUT OF STOCK]"
        print(f"- {tag}{sku}: {item['price']:,} VND{flag}  ({item['name'][:55]})")
        source_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "url": item.get("url") or fallback_url, "is_used": is_used}
        )
        # Chỉ ghi giá cho SKU CHƯA từng có source ở competitor này (sản phẩm mới phát hiện).
        if is_new:
            price_rows.append({
                "product_sku": sku, "competitor": COMPETITOR, "price": item["price"],
                "in_stock": item.get("in_stock", True), "is_used": is_used,
            })
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