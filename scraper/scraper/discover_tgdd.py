"""Scraper khám phá giá Thế Giới Di Động (thegioididong.com) (Playwright + proxy Việt Nam).

TGDĐ chặn theo vùng địa lý các IP ngoài Việt Nam — nhưng ở tầng TLS (reset kết nối), không phải
HTTP 403. Proxy VN vượt qua được nên đoạn này định tuyến qua use_proxy=True. Trang danh sách
được render phía server, nên các selector ổn định và sạch.

Selector đã xác minh (DOM đã render):
    card  : li.item   (chứa một liên kết sản phẩm laptop)
    name  : h3
    url   : a[href*="laptop"] / anchor sản phẩm của card (slug kết thúc bằng mã Dell)
    price : .price    (một giá hiện tại duy nhất, vd "20.590.000₫")

Chỉ đối chiếu (match-only): chỉ ghi nhận giá cho các SKU đã có trong `products` (catalog của TNC).

Cách dùng:
    python -m scraper.discover_tgdd --dry
    python -m scraper.discover_tgdd
"""

from __future__ import annotations

import argparse
import re
import sys

from .brand import name_match_term
from .browser import browser_page, goto_with_retry
from .config import categories, name_exclude_re, name_match_re, resolve_url
from .db import ensure_competitor, fetch_catalog_skus, get_client, insert_prices, upsert_sources
from .sku import derive_sku

COMPETITOR = "Thế Giới Di Động"
BASE_URL = "https://www.thegioididong.com"
BRANDS = {
    "dell": "https://www.thegioididong.com/laptop-dell",
    "lenovo": "https://www.thegioididong.com/laptop-lenovo",
    "apple": "https://www.thegioididong.com/laptop-apple-macbook",
    "hp": "https://www.thegioididong.com/laptop-hp-compaq",
    "asus": "https://www.thegioididong.com/laptop-asus",
    "acer": "https://www.thegioididong.com/laptop-acer",
    "msi": "https://www.thegioididong.com/laptop-msi",
    "gigabyte": "https://www.thegioididong.com/laptop-gigabyte",
}

CARD_SELECTOR = "li.item"


def _digits_to_int(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def discover(brand: str = "dell", category: str = "laptop") -> list[dict]:
    """Trả về [{name, price, url}] cho các sản phẩm trên trang danh sách đã render.

    Laptop (mặc định) dùng URL danh mục laptop per-brand + lọc theo brand. Các danh mục khác dùng
    URL `paths.tgdd` của danh mục và giữ lại theo name_match (TGDĐ không có ô tìm kiếm).
    """
    is_laptop = category == "laptop"
    excl_re = name_exclude_re(category)
    if is_laptop:
        list_url, name_re = BRANDS[brand], None
    else:
        list_url = resolve_url("tgdd", category)
        name_re = name_match_re(category)
    if not list_url:
        return []
    results: list[dict] = []
    with browser_page(use_proxy=True) as page:
        if not goto_with_retry(page, list_url, f"{CARD_SELECTOR} .price", label=COMPETITOR):
            return results

        # Hầu hết laptop nằm sau nút "Xem thêm"; bấm cho đến khi nút biến mất / không thêm card mới.
        stale = 0
        for _ in range(40):
            btn = page.query_selector(".view-more")
            if not btn or not btn.is_visible():
                break  # nút biến mất = đã tải hết
            before = len(page.query_selector_all(CARD_SELECTOR))
            try:
                page.click(".view-more", timeout=5000)
            except Exception:
                break
            page.wait_for_timeout(2200)  # chờ lô mới (việc tải có thể bị trễ)
            after = len(page.query_selector_all(CARD_SELECTOR))
            # chỉ bỏ cuộc sau vài lần bấm liên tiếp không tăng thêm card
            stale = stale + 1 if after == before else 0
            if stale >= 3:
                break

        items = page.eval_on_selector_all(
            CARD_SELECTOR,
            """
            (cards, opts) => {
              const [term, isLaptop] = opts;
              const out = [];
              const seen = new Set();
              const re = new RegExp('\\\\b(?:laptop|' + term + ')\\\\b', 'i');
              for (const li of cards) {
                // Laptop: anchor chứa "laptop". Danh mục khác: ưu tiên anchor sản phẩm THẬT — anchor
                // có data-name (trên trang tìm-kiếm, li.item còn có anchor "trả chậm" không phải sản
                // phẩm), fallback anchor[href] đầu tiên.
                const a = isLaptop
                  ? li.querySelector('a[href*="laptop"]')
                  : (li.querySelector('a[data-name]') || li.querySelector('a[href]'));
                const priceEl = li.querySelector('.price');
                const h3 = li.querySelector('h3');
                if (!a || !priceEl) continue;
                const href = a.getAttribute('href');
                if (!href || seen.has(href)) continue;
                // Tên: h3 → data-name → title (trang tìm-kiếm để tên ở data-name, h3 rỗng).
                const name = ((h3 && h3.innerText) || a.getAttribute('data-name')
                              || a.getAttribute('title') || '').trim();
                if (isLaptop && !re.test(name)) continue;  // danh mục khác lọc ở Python
                // hết hàng: TGDĐ hiển thị "Hàng sắp về" trong .item-txt-online trên card
                const online = li.querySelector('.item-txt-online');
                const inStock = !(online && /sắp về|hết hàng/i.test(online.innerText || ''));
                seen.add(href);
                out.push({ name, price: priceEl.innerText.trim(), url: href, in_stock: inStock });
              }
              return out;
            }
            """,
            [name_match_term(brand), is_laptop],
        )
        for it in items:
            name = it["name"]
            if (excl_re and excl_re.search(name)) or (not is_laptop and not (name_re and name_re.search(name))):
                continue
            price = _digits_to_int(it["price"])
            href = it["url"]
            url = (BASE_URL + href) if href and href.startswith("/") else href
            if price:
                results.append(
                    {"name": name, "price": price, "url": url, "in_stock": it["in_stock"]}
                )
    return results



def main() -> int:
    ap = argparse.ArgumentParser(description="Discover Thế Giới Di Động prices by brand and category.")
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
        f"Discovering '{COMPETITOR}' (via VN proxy) — {args.category}/{args.brand}"
        f"{' (dry run)' if args.dry else ''}...\n"
    )
    found = discover(args.brand, args.category)
    print(f"{len(found)} unique product(s) parsed; matching against {len(tracked)} TNC SKU(s).\n")

    category_label = args.category.capitalize()
    fallback_url = BRANDS[args.brand] if args.category == "laptop" else resolve_url("tgdd", args.category)
    source_rows, price_rows = [], []
    for item in found:
        sku = derive_sku(item["name"], item.get("url"), category_label)
        if sku is None or sku not in tracked:
            continue
        in_stock = item.get("in_stock", True)
        flag = "" if in_stock else "  [OUT OF STOCK]"
        print(f"- {sku}: {item['price']:,} VND{flag}  ({item['name'][:50]})")
        source_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "url": item.get("url") or fallback_url}
        )
        price_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "price": item["price"], "in_stock": in_stock}
        )

    if not args.dry:
        upsert_sources(client, source_rows)
        insert_prices(client, price_rows)

    print(f"\nDone. {len(price_rows)} TNC-catalog SKU(s) matched on {COMPETITOR}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
