"""Scraper khám phá dữ liệu bằng tìm kiếm cho Memoryzone (memoryzone.com.vn) (Playwright, không cần proxy).

Memoryzone truy cập trực tiếp được. Giống GearVN, trang này chuyên về linh kiện/PC và ít/không
bán laptop Dell — tìm kiếm "laptop dell" trên trang này chủ yếu ra phụ kiện (balo, túi, v.v.).
Ta lọc theo tên để lấy đúng laptop và ghi lại bất cứ thứ gì xuất hiện (thường là không có gì, và
điều đó vẫn ổn).

Các selector đã xác nhận (DOM sau khi render):
    name  : h3
    url   : anchor của sản phẩm (slug = phần đuôi mã model)
    price : .ae-price--primary (giá hiện tại); KHÔNG phải .ae-price--compare (giá gốc gạch ngang)

Chỉ khớp: chỉ ghi lại giá cho các SKU đã có sẵn trong `products` (danh mục của TNC).

Cách dùng:
    python -m scraper.discover_memoryzone --dry
    python -m scraper.discover_memoryzone
"""

from __future__ import annotations

import argparse
import re
import sys

from .browser import browser_page, goto_with_retry
from .config import categories, name_exclude_re, name_match_re, resolve_url
from .db import ensure_competitor, fetch_catalog_skus, get_client, insert_prices, upsert_sources
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

PRICE_SELECTOR = ".ae-price--primary"


def _digits_to_int(text: str) -> int | None:
    m = re.search(r"\d{1,3}(?:\.\d{3})+", text or "")
    return int(m.group(0).replace(".", "")) if m else None


def discover(brand: str = "dell", category: str = "laptop") -> list[dict]:
    """Trả về [{name, price, url}] cho các sản phẩm trên trang tìm kiếm đã render.

    Laptop (mặc định) dùng URL per-brand + lọc /^laptop|macbook/. Các danh mục khác chạy theo
    danh mục: tìm cả danh mục, giữ mọi card sản phẩm, lọc theo name_match ở Python.
    """
    is_laptop = category == "laptop"
    if is_laptop:
        search_url, name_re = BRANDS[brand], None
    else:
        search_url = resolve_url("memoryzone", category)
        name_re = name_match_re(category)
        excl_re = name_exclude_re(category)  # loại mực in/cartridge/phụ kiện (trước đây bị bỏ qua)
    if not search_url:
        return []
    results: list[dict] = []
    with browser_page(use_proxy=False) as page:
        if not goto_with_retry(page, search_url, PRICE_SELECTOR, label=COMPETITOR):
            return results

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
            (prices, isLaptop) => {
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
                // Laptop: bỏ qua balo/túi/phụ kiện. Danh mục khác lọc ở Python (name_match).
                if (isLaptop && !/^(laptop|macbook)/i.test(name)) continue;
                seen.add(href);
                // Kèm text thẻ để Python phát hiện hết hàng ("Liên hệ"/"Hết hàng"). DÙNG textContent
                // (KHÔNG innerText): innerText rỗng cho thẻ ngoài màn hình → mất tín hiệu OOS.
                out.push({ name, price: p.innerText.trim(), url: href, card_text: (card.textContent || '') });
              }
              return out;
            }
            """,
            is_laptop,
        )
        for it in items:
            name = it["name"]
            if (excl_re and excl_re.search(name)) or (not is_laptop and not (name_re and name_re.search(name))):
                continue
            price = _digits_to_int(it["price"])
            href = it["url"]
            url = (BASE_URL + href) if href and href.startswith("/") else href
            if price:
                in_stock = stock_is_in(it.get("card_text"))
                results.append({"name": name, "price": price, "url": url, "in_stock": in_stock})
    return results



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

    print(
        f"Discovering '{COMPETITOR}' — {args.category}/{args.brand}"
        f"{' (dry run)' if args.dry else ''}...\n"
    )
    found = discover(args.brand, args.category)
    print(f"{len(found)} product(s) parsed; matching against {len(tracked)} TNC SKU(s).\n")

    category_label = args.category.capitalize()
    fallback_url = BRANDS[args.brand] if args.category == "laptop" else resolve_url("memoryzone", args.category)
    source_rows, price_rows = [], []
    for item in found:
        sku = derive_sku(item["name"], item.get("url"), category_label)
        if sku is None or sku not in tracked:
            continue
        flag = "" if item.get("in_stock", True) else "  [OUT OF STOCK]"
        print(f"- {sku}: {item['price']:,} VND{flag}  ({item['name'][:55]})")
        source_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "url": item.get("url") or fallback_url}
        )
        price_rows.append({
            "product_sku": sku, "competitor": COMPETITOR, "price": item["price"],
            "in_stock": item.get("in_stock", True),
        })

    if not args.dry:
        upsert_sources(client, source_rows)
        insert_prices(client, price_rows)

    print(f"\nDone. {len(price_rows)} TNC-catalog SKU(s) matched on {COMPETITOR}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
