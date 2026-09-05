"""Scraper khám phá dữ liệu bằng tìm kiếm cho An Khang Computer (ankhang.vn).

An Khang có giao diện Web tĩnh SSR siêu nhanh, trả về HTML đầy đủ sản phẩm và giá qua
URL `https://www.ankhang.vn/tim?q={query}`.

Chỉ khớp: chỉ ghi lại giá cho các SKU đã có sẵn trong `products` (danh mục của TNC).

MODE A (weekend discovery) — CHỈ GHI GIÁ CHO SKU MỚI: kịch bản này chạy cuối tuần để tìm sản
phẩm MỚI, không phải để cào lại giá của mọi sản phẩm đã biết — giá đó Mode B (sync_prices, chạy
hàng ngày) đã cào đều đặn rồi. Vì vậy SKU nào ĐÃ có source ở competitor này (fetch_existing_source_skus)
thì chỉ được refresh URL (upsert_sources), KHÔNG check_stock lại và KHÔNG ghi thêm dòng
price_history trùng lặp.

Cách dùng:
    python -m scraper.discover_ankhang --dry
    python -m scraper.discover_ankhang --category laptop
    python -m scraper.discover_ankhang
"""

from __future__ import annotations

import argparse
import re
import sys
import requests
from bs4 import BeautifulSoup

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .config import categories, is_old_listing_name, name_exclude_re, name_match_re, resolve_url
from .db import (
    ensure_competitor,
    fetch_catalog_skus,
    fetch_existing_source_skus,
    get_client,
    insert_prices,
    upsert_sources,
)
from .sku import derive_sku

COMPETITOR = "An Khang"
BASE_URL = "https://www.ankhang.vn"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def _clean_price(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def discover(category: str = "laptop", brand: str | None = None) -> list[dict]:
    """Trả về [{name, price, url}] cho các sản phẩm An Khang tìm thấy theo danh mục."""
    search_url = resolve_url("ankhang", category)
    if not search_url:
        search_url = f"https://www.ankhang.vn/tim?q={category}"

    match_re = name_match_re(category)
    excl_re = name_exclude_re(category)

    results: list[dict] = []
    try:
        r = requests.get(search_url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "html.parser")
        
        cards = soup.select(".p-item, .product-item, .item")
        if not cards:
            cards = [p.find_parent("div") for p in soup.select(".p-price")]

        for card in cards:
            if not card:
                continue
            a = card.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            if not href.endswith(".html") or "/tim" in href:
                continue
            url = (BASE_URL + href) if href.startswith("/") else href

            name_el = card.select_one(".p-name, .product-name, h3, h2, .name")
            name = name_el.text.strip() if name_el else a.text.strip()
            if not name:
                name = a.get("title", "").strip()
            if not name:
                continue

            # Lọc theo name_match / name_exclude
            if match_re and not match_re.search(name):
                continue
            if excl_re and excl_re.search(name):
                continue

            price_el = card.select_one(".p-price, .price, .giakuyenmai")
            price = _clean_price(price_el.text) if price_el else None
            if not price or price < 1000:
                continue

            results.append({
                "name": name,
                "price": price,
                "url": url,
            })
    except Exception as e:
        print(f"Error fetching An Khang category '{category}': {e}")

    return results


def check_stock(urls: list[str]) -> dict[str, bool]:
    """Kiểm tra tình trạng còn hàng / hết hàng trên từng URL sản phẩm của An Khang.
    An Khang khi CÒN HÀNG: có nút `.now_cart` ('MUA NGAY').
    An Khang khi HẾT HÀNG: có nút `.btn-contact-shop` ('Liên hệ cửa hàng') và KHÔNG có `.now_cart`.
    """
    status: dict[str, bool] = {}
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code != 200:
                status[url] = True
                continue
            text = r.text
            has_buy_now = "now_cart" in text or "btn-buy-now" in text or "add_cart" in text
            has_contact = "btn-contact-shop" in text or "tạm hết hàng" in text.lower() or "ngừng kinh doanh" in text.lower()
            
            if has_buy_now:
                status[url] = True
            elif has_contact:
                status[url] = False
            else:
                status[url] = True
        except Exception:
            status[url] = True
    return status


def main() -> int:
    ap = argparse.ArgumentParser(description="Discover An Khang prices by category.")
    ap.add_argument(
        "--category", default="laptop", choices=sorted(categories()),
        help="product category to scrape",
    )
    ap.add_argument("--dry", action="store_true", help="print results, don't write to DB")
    args = ap.parse_args()

    client = get_client()
    ensure_competitor(client, COMPETITOR)
    tracked = fetch_catalog_skus(client, args.category.capitalize())
    if not tracked:
        print(f"No tracked products found for category '{args.category}'.")
        return 0

    print(f"[{COMPETITOR}] Discovering category '{args.category}'...")
    raw = discover(category=args.category)
    print(f"  Found {len(raw)} raw items on An Khang search page.")

    category_label = args.category.capitalize()
    matched: dict[str, dict] = {}
    for item in raw:
        sku = derive_sku(item["name"], item.get("url"), category_label)
        if sku and sku in tracked and sku not in matched:
            matched[sku] = item

    print(f"  Matched {len(matched)} SKUs against TNC catalog.")
    if not matched:
        return 0

    existing_skus = fetch_existing_source_skus(client, COMPETITOR)
    new_items = {k: v for k, v in matched.items() if k not in existing_skus}
    existing_items = {k: v for k, v in matched.items() if k in existing_skus}

    print(f"  New SKUs to insert: {len(new_items)} | Existing SKUs to update URL: {len(existing_items)}")

    # Check stock cho SKU MỚI
    new_stock = check_stock([v["url"] for v in new_items.values()]) if new_items else {}

    if args.dry:
        print("\n--- DRY RUN RESULTS ---")
        for sku, item in matched.items():
            is_new = sku in new_items
            in_s = new_stock.get(item["url"], True) if is_new else True
            is_u = is_old_listing_name(item["name"])
            u_tag = " [HÀNG CŨ/DEMO]" if is_u else ""
            print(f"  • {sku:<30} | {item['price']:,} VND | {'Còn hàng' if in_s else 'HẾT HÀNG'}{u_tag} | {item['url']}")
        return 0

    # Upsert sources
    source_rows = [
        {"product_sku": sku, "competitor": COMPETITOR, "url": item["url"], "active": True}
        for sku, item in matched.items()
    ]
    upsert_sources(client, source_rows)

    # Insert price history & update price cache cho SKU MỚI
    price_rows = []
    for sku, item in new_items.items():
        in_s = new_stock.get(item["url"], True)
        is_u = is_old_listing_name(item["name"])
        price_rows.append({
            "product_sku": sku,
            "competitor": COMPETITOR,
            "price": item["price"],
            "in_stock": in_s,
            "is_used": is_u,
        })

    if price_rows:
        insert_prices(client, price_rows)
        print(f"✅ Successfully inserted {len(price_rows)} new prices for An Khang!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
