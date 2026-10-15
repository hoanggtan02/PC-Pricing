"""Scraper khám phá dữ liệu sản phẩm cho Laptop World (laptopworld.vn).

Laptop World có giao diện Web tĩnh SSR tải cực nhanh qua requests/httpx.
Hỗ trợ cả danh mục Laptop (theo Brand/Category) và các danh mục linh kiện (Monitor, PC, v.v.).

Cách dùng:
    python -m scraper.discover_laptopworld --dry
    python -m scraper.discover_laptopworld --category laptop
    python -m scraper.discover_laptopworld --brand dell
    python -m scraper.discover_laptopworld --all
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .brand import brand_of
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

COMPETITOR = "Laptop World"
BASE_URL = "https://laptopworld.vn"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Các đường dẫn danh mục chính của Laptop World
LAPTOP_BRANDS = {
    "dell": "https://laptopworld.vn/may-tinh-xach-tay/laptop-dell.html?page={page}",
    "asus": "https://laptopworld.vn/may-tinh-xach-tay/laptop-asus.html?page={page}",
    "lenovo": "https://laptopworld.vn/laptop-lenovo?page={page}",
    "hp": "https://laptopworld.vn/laptop-hp.html?page={page}",
    "acer": "https://laptopworld.vn/laptop-acer?page={page}",
    "msi": "https://laptopworld.vn/laptop-msi?page={page}",
    "apple": "https://laptopworld.vn/san-pham-apple/laptop-apple.html?page={page}",
}

PAGE_CAP = 10  # Quét tối đa 10 trang cho mỗi thương hiệu/danh mục


def _clean_price(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    if not digits:
        return None
    val = int(digits)
    return val if val > 100000 else None


def discover(category: str = "laptop", brand: str | None = None) -> list[dict]:
    """Trả về [{name, price, url}] cho các sản phẩm Laptop World tìm thấy theo danh mục/brand."""
    results: list[dict] = []
    seen_urls: set[str] = set()

    is_laptop = (category == "laptop")
    match_re = name_match_re(category)
    excl_re = name_exclude_re(category)

    # Xác định các URL cần duyệt
    target_urls: list[str] = []
    if is_laptop:
        if brand and brand.lower() in LAPTOP_BRANDS:
            target_urls.append(LAPTOP_BRANDS[brand.lower()])
        else:
            target_urls.extend(LAPTOP_BRANDS.values())
    else:
        cat_url = resolve_url("laptopworld", category)
        if cat_url:
            sep = "&" if "?" in cat_url else "?"
            target_urls.append(f"{cat_url}{sep}page={{page}}")
        else:
            # Fallback sang tìm kiếm theo search_term của danh mục
            term = category
            target_urls.append(f"https://laptopworld.vn/tim?q={term}&page={{page}}")

    for url_tpl in target_urls:
        for page_num in range(1, PAGE_CAP + 1):
            url = url_tpl.format(page=page_num)
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                if r.status_code != 200:
                    break
                soup = BeautifulSoup(r.text, "html.parser")
                cards = soup.select(".p-item")
                if not cards:
                    break

                new_on_page = 0
                for card in cards:
                    img = card.select_one("img")
                    name = (img.get("alt") if img else "") or ""
                    if not name:
                        name_el = card.select_one(".p-name, h4, h3, a.p-img")
                        name = name_el.get_text(strip=True) if name_el else ""
                    if not name:
                        continue

                    # Lọc exclude
                    if excl_re and excl_re.search(name):
                        continue
                    if not is_laptop and match_re and not match_re.search(name):
                        continue

                    # URL chi tiết
                    a = card.select_one("a.p-img, a[href]")
                    if not a or not a.get("href"):
                        continue
                    item_url = urljoin(BASE_URL, a["href"])
                    if item_url in seen_urls:
                        continue

                    # Giá niêm yết
                    p_el = card.select_one(".p-price, .price, .price-border")
                    price_text = p_el.get_text(strip=True) if p_el else ""
                    price = _clean_price(price_text)

                    # Bỏ qua nếu là "Liên hệ" hoặc không có giá hợp lệ
                    if not price:
                        continue

                    seen_urls.add(item_url)
                    new_on_page += 1
                    results.append({
                        "name": name,
                        "price": price,
                        "url": item_url,
                    })

                if new_on_page == 0:
                    break

                # Nghỉ ngắn giữa các trang
                time.sleep(0.3)
            except Exception as e:
                print(f"  ⚠️ Lỗi khi cào Laptop World {url}: {e}")
                break

    return results


def check_stock(urls: list[str]) -> dict[str, bool]:
    """Kiểm tra tình trạng còn hàng trên từng URL sản phẩm của Laptop World.
    1. Check nhãn Tình trạng: Hết hàng / Liên hệ (trong .product-info / .list-top-dt)
    2. Check ô giá .js-this-product có data-price == 0 hoặc chứa 'liên hệ' / 'hết hàng'
    """
    import unicodedata
    status: dict[str, bool] = {}
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code != 200:
                status[url] = True
                continue
            soup = BeautifulSoup(r.text, "html.parser")

            # 1. Check nhãn Tình trạng cụ thể
            is_out = False
            for el in soup.select(".product-info, .list-top-dt p, .list-top-dt span"):
                t = unicodedata.normalize("NFC", el.get_text() or "").lower()
                if "tình trạng" in t:
                    if "hết hàng" in t or "tạm hết hàng" in t or "liên hệ" in t:
                        is_out = True
                        break

            # 2. Check ô giá chính
            p_el = soup.select_one(".js-this-product")
            if p_el:
                d_price = p_el.get("data-price")
                p_text = unicodedata.normalize("NFC", p_el.get_text() or "").lower()
                if d_price == "0" or "liên hệ" in p_text or "hết hàng" in p_text:
                    is_out = True

            status[url] = not is_out
        except Exception:
            status[url] = True
    return status


def main() -> int:
    ap = argparse.ArgumentParser(description="Discover Laptop World prices by brand and category.")
    ap.add_argument("--brand", default=None, help="brand to scrape (e.g. dell, lenovo, asus, hp)")
    ap.add_argument(
        "--category", default="laptop", choices=["laptop", *sorted(categories())],
        help="product category to scrape",
    )
    ap.add_argument("--all", action="store_true", help="discover all categories")
    ap.add_argument("--dry", action="store_true", help="print results, don't write to DB")
    args = ap.parse_args()

    client = get_client()
    ensure_competitor(client, COMPETITOR)

    cats_to_run = ["laptop", *sorted(categories())] if args.all else [args.category]
    total_inserted = 0

    for cat in cats_to_run:
        category_label = cat.capitalize()
        tracked = fetch_catalog_skus(client, category_label)
        if not tracked:
            continue

        print(f"\n[{COMPETITOR}] Discovering category '{cat}' (brand={args.brand or 'all'})...")
        raw = discover(category=cat, brand=args.brand)
        print(f"  Found {len(raw)} raw items on Laptop World.")

        existing_skus = fetch_existing_source_skus(client, COMPETITOR)

        matched_new: list[dict] = []
        matched_known: list[dict] = []
        missing_rows: list[dict] = []
        resolved_urls: list[str] = []

        for item in raw:
            sku = derive_sku(item["name"], item.get("url"), category_label)
            if sku and sku in tracked:
                resolved_urls.append(item.get("url") or "")
                if sku not in existing_skus:
                    matched_new.append({**item, "sku": sku})
                else:
                    matched_known.append({**item, "sku": sku})
            else:
                reason = "Không suy được SKU" if not sku else "TNC chưa bán sản phẩm này"
                missing_rows.append({
                    "competitor": COMPETITOR,
                    "category": category_label,
                    "brand": brand_of(item["name"]) or None,
                    "name": item["name"],
                    "price": item.get("price"),
                    "url": item.get("url") or "",
                    "is_used": is_old_listing_name(item.get("name", "")),
                    "reason": reason,
                })

        print(
            f"  Matched {len(matched_new) + len(matched_known)} SKUs ({len(matched_new)} mới, "
            f"{len(matched_known)} cũ refresh URL), {len(missing_rows)} không khớp."
        )

        # Check stock cho SKU MỚI
        new_stock = {item["url"]: True for item in matched_new}
        if matched_new:
            new_stock = check_stock([item["url"] for item in matched_new])

        if args.dry:
            print("\n--- DRY RUN RESULTS ---")
            for item in matched_new:
                in_s = new_stock.get(item["url"], True)
                is_u = is_old_listing_name(item["name"])
                u_tag = " [HÀNG CŨ/DEMO]" if is_u else ""
                print(f"  • {item['sku']:<30} | {item['price']:,} VND | {'Còn hàng' if in_s else 'HẾT HÀNG'}{u_tag} | {item['url']}")
            for row in missing_rows[:10]:
                price_s = f"{row['price']:,} VND" if row.get("price") else "?"
                print(f"  - [MISSING] ({row['reason']}) {row['name'][:60]} — {price_s}")
            if len(missing_rows) > 10:
                print(f"  ... và {len(missing_rows) - 10} sản phẩm không khớp khác.")
            continue

        # Upsert sources (cả mới lẫn cũ)
        source_rows = [
            {"product_sku": item["sku"], "competitor": COMPETITOR, "url": item["url"], "active": True}
            for item in matched_new + matched_known
        ]
        if source_rows:
            upsert_sources(client, source_rows)

        # Insert price history cho SKU MỚI
        price_rows = []
        for item in matched_new:
            in_s = new_stock.get(item["url"], True)
            is_u = is_old_listing_name(item["name"])
            price_rows.append({
                "product_sku": item["sku"],
                "competitor": COMPETITOR,
                "price": item["price"],
                "in_stock": in_s,
                "is_used": is_u,
            })
        if price_rows:
            insert_prices(client, price_rows)
            total_inserted += len(price_rows)
            print(f"✅ Inserted {len(price_rows)} new prices for Laptop World ({cat}).")

        if missing_rows:
            upsert_missing_products(client, missing_rows)
        if resolved_urls:
            resolve_missing_products(client, COMPETITOR, resolved_urls)

        print(
            f"  {len(missing_rows)} sản phẩm KHÔNG khớp lưu vào missing_products "
            f"({len(resolved_urls)} sản phẩm thiếu nay đã khớp -> đánh dấu resolved)."
        )

    print(f"\n🎉 Finished discovery for Laptop World! Total new prices inserted: {total_inserted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
