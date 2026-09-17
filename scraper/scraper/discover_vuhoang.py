"""Scraper khám phá dữ liệu cho Vũ Hoàng Telecom (vuhoangtelecom.vn).

Chuyên cung cấp thiết bị mạng, router wifi, switch poe, camera quan sát.
Trang dùng WordPress, phản hồi nhanh và không bị chặn Cloudflare.

Cách dùng:
    python -m scraper.discover_vuhoang --dry
    python -m scraper.discover_vuhoang
    python -m scraper.discover_vuhoang --category router
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
from bs4 import BeautifulSoup

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
from .brand import brand_of
from .sku import derive_sku

COMPETITOR = "Vũ Hoàng Telecom"
BASE_URL = "https://vuhoangtelecom.vn"

CATEGORY_PATHS = {
    "router": "https://vuhoangtelecom.vn/bo-phat-song-wifi/",
    "switch": "https://vuhoangtelecom.vn/thiet-bi-mang-switch/",
    "camera": "https://vuhoangtelecom.vn/camera-quan-sat/",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "vi,en;q=0.9",
}


def _digits_to_int(text: str) -> Optional[int]:
    m = re.search(r"\d{1,3}(?:[.,]\d{3})+", text or "")
    if m:
        digits = re.sub(r"[^\d]", "", m.group(0))
        val = int(digits) if digits else None
        return val if (val and val < 1_000_000_000) else None
    digits = re.sub(r"[^\d]", "", text or "")
    if digits and len(digits) <= 9:
        val = int(digits)
        return val if val < 1_000_000_000 else None
    return None


def discover(category: str = "router", max_pages: int = 15) -> list[dict]:
    base_url = CATEGORY_PATHS.get(category) or resolve_url("vuhoang", category)
    if not base_url:
        return []

    name_re = name_match_re(category)
    excl_re = name_exclude_re(category)

    results: list[dict] = []
    seen_urls: set[str] = set()

    with httpx.Client(headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
        for page in range(1, max_pages + 1):
            if page == 1:
                url = base_url
            else:
                url = f"{base_url.rstrip('/')}/page/{page}/"

            try:
                r = client.get(url)
                if r.status_code != 200:
                    break
            except Exception as e:
                print(f"  Lỗi tải trang {url}: {e}")
                break

            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select(".az-product-item, .product-small, .type-product")
            if not cards:
                break

            new_in_page = 0
            for card in cards:
                link_el = card.select_one("a.az-box-product-des, a.nt-img, a")
                if not link_el:
                    continue

                href = link_el.get("href", "")
                if not href or href in seen_urls:
                    continue
                seen_urls.add(href)

                title_el = card.select_one("h3.az-title-post, .az-title, h2, h3")
                name = title_el.text.strip() if title_el else ""
                if not name:
                    img = card.select_one("img")
                    if img and img.get("alt"):
                        name = img["alt"].strip()

                if not name:
                    continue

                if is_old_listing_name(name):
                    continue
                if name_re and not name_re.search(name):
                    continue
                if excl_re and excl_re.search(name):
                    continue

                price = None
                price_el = card.select_one(".az-price ins, .az-price, .price ins, .price")
                if price_el:
                    price = _digits_to_int(price_el.text)

                in_stock = (price is not None and price > 0)
                card_text = card.text.lower()
                if "liên hệ" in card_text or "hết hàng" in card_text:
                    in_stock = False

                if price:
                    results.append({
                        "name": name,
                        "price": price,
                        "url": href,
                        "in_stock": in_stock
                    })
                    new_in_page += 1

            if new_in_page == 0 and page > 2:
                break

    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Khám phá giá từ Vũ Hoàng Telecom.")
    ap.add_argument("--dry", action="store_true", help="Chạy thử, không ghi DB")
    ap.add_argument("--category", choices=list(CATEGORY_PATHS.keys()), default="router", help="Danh mục cào")
    args = ap.parse_args()

    client = get_client()
    ensure_competitor(client, COMPETITOR)

    cat = args.category
    print(f"Bắt đầu cào {COMPETITOR} - Danh mục: {cat}...")
    items = discover(cat)
    print(f"Tìm thấy {len(items)} sản phẩm từ {COMPETITOR}.")

    if not items:
        return 0

    catalog_skus = fetch_catalog_skus(client)
    existing_sources = fetch_existing_source_skus(client, COMPETITOR)
    category_label = cat.capitalize()

    matched_sources = []
    matched_prices = []
    missing_rows: list[dict] = []
    resolved_urls: list[str] = []

    for it in items:
        sku = derive_sku(it["name"], it["url"], cat)
        if not sku or sku not in catalog_skus:
            reason = "Không suy được SKU" if not sku else "TNC chưa bán sản phẩm này"
            missing_rows.append({
                "competitor": COMPETITOR,
                "category": category_label,
                "brand": brand_of(it["name"]) or None,
                "name": it["name"],
                "price": it.get("price"),
                "url": it.get("url") or "",
                "is_used": is_old_listing_name(it.get("name", "")),
                "reason": reason,
            })
            continue

        resolved_urls.append(it["url"])
        matched_sources.append({
            "product_sku": sku,
            "competitor": COMPETITOR,
            "url": it["url"],
            "active": True
        })

        if sku not in existing_sources:
            matched_prices.append({
                "product_sku": sku,
                "competitor": COMPETITOR,
                "price": it["price"],
                "in_stock": it["in_stock"]
            })

    print(
        f"Khớp {len(matched_sources)} sản phẩm với catalog TNC ({len(matched_prices)} sản phẩm mới chưa có giá), "
        f"{len(missing_rows)} sản phẩm không khớp."
    )

    if args.dry:
        for s in matched_sources[:10]:
            print(f"  [DRY] {s['product_sku']} -> {s['url']}")
        for row in missing_rows[:10]:
            price_s = f"{row['price']:,} VND" if row.get("price") else "?"
            print(f"  [MISSING] ({row['reason']}) {row['name'][:60]} — {price_s}")
        if len(missing_rows) > 10:
            print(f"  ... và {len(missing_rows) - 10} sản phẩm không khớp khác.")
        return 0

    if matched_sources:
        upsert_sources(client, matched_sources)
        print(f"Đã lưu {len(matched_sources)} nguồn cào vào database.")

    if matched_prices:
        insert_prices(client, matched_prices)
        print(f"Đã lưu {len(matched_prices)} bản ghi giá mới.")

    if missing_rows:
        upsert_missing_products(client, missing_rows)
        print(f"Đã lưu {len(missing_rows)} sản phẩm không khớp vào missing_products.")

    if resolved_urls:
        resolve_missing_products(client, COMPETITOR, resolved_urls)

    return 0


if __name__ == "__main__":
    sys.exit(main())
