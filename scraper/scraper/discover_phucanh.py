"""Scraper khám phá dữ liệu bằng tìm kiếm cho Phúc Anh (phucanh.vn) (Playwright).

Các selector đã xác nhận:
    card  : .p-item-group
    name  : .p-name
    url   : a.p-img (href)
    price : .p-price2 (giá hiện tại, cần check visible)
    stock : .p-bottom chứa "✔ Có hàng"
"""

from __future__ import annotations

import argparse
import re

from .browser import browser_page, goto_with_retry
from .config import is_old_listing_name, name_exclude_re, name_match_re, resolve_url
from .db import (
    ensure_competitor,
    fetch_catalog_skus,
    fetch_existing_source_skus,
    get_client,
    upsert_sources,
)
from .stock import is_in_stock as stock_is_in
from .sku import derive_sku

COMPETITOR = "Phúc Anh"
BASE_URL = "https://www.phucanh.vn"

BRANDS = {
    "dell": "https://www.phucanh.vn/may-tinh-xach-tay-laptop-dell.html",
    "asus": "https://www.phucanh.vn/may-tinh-xach-tay-laptop-asus.html",
    "hp": "https://www.phucanh.vn/may-tinh-xach-tay-laptop-hp.html",
    "lenovo": "https://www.phucanh.vn/may-tinh-xach-tay-laptop-lenovo.html",
    "acer": "https://www.phucanh.vn/may-tinh-xach-tay-laptop-acer.html",
    "msi": "https://www.phucanh.vn/may-tinh-xach-tay-laptop-msi.html",
    "apple": "https://www.phucanh.vn/laptop-apple.html",
    "gigabyte": "https://www.phucanh.vn/laptop-gigabyte.html",
}

def _digits_to_int(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None

def discover(brand: str = "dell", category: str = "laptop") -> list[dict]:
    """Trả về [{name, price, url, in_stock}] cho các sản phẩm trên trang tìm kiếm đã render."""
    is_laptop = category == "laptop"
    excl_re = name_exclude_re(category)
    if is_laptop:
        base_search_url = BRANDS.get(brand)
        name_re = None
    else:
        base_search_url = resolve_url("phucanh", category)
        name_re = name_match_re(category)
        
    if not base_search_url:
        return []

    results: list[dict] = []
    
    with browser_page(use_proxy=False) as page:
        for page_num in range(1, 15):
            url = base_search_url
            if page_num > 1:
                joiner = "&" if "?" in url else "?"
                url = f"{url}{joiner}page={page_num}"
                
            if not goto_with_retry(page, url, ".p-item-group", label=COMPETITOR):
                break
                
            items = page.eval_on_selector_all(
                ".p-item-group",
                """
                (cards) => {
                    const out = [];
                    for (const card of cards) {
                        const name_el = card.querySelector('.p-name');
                        const url_el = card.querySelector('a.p-img') || card.querySelector('a');
                        const price_els = card.querySelectorAll('.p-price2');
                        let price_text = '';
                        for (const el of price_els) {
                            if (window.getComputedStyle(el).display !== 'none') {
                                price_text = el.innerText.trim();
                                break;
                            }
                        }
                        const stock_el = card.querySelector('.p-bottom');
                        
                        if (!name_el) continue;
                        out.push({
                            name: name_el.innerText.trim(),
                            price: price_text,
                            url: url_el ? url_el.getAttribute('href') : '',
                            card_text: stock_el ? stock_el.innerText.trim() : card.innerText.trim()
                        });
                    }
                    return out;
                }
                """
            )
            
            if not items:
                break
                
            for it in items:
                name = it["name"]
                if (excl_re and excl_re.search(name)) or (not is_laptop and not (name_re and name_re.search(name))):
                    continue
                
                price = _digits_to_int(it["price"])
                href = it["url"]
                item_url = (BASE_URL + href) if href and href.startswith("/") else href
                
                card_text_lower = it.get("card_text", "").lower()
                in_stock = stock_is_in(it["price"]) and not any(
                    term in card_text_lower for term in ["hết hàng", "liên hệ"]
                )
                
                if price:
                    results.append({"name": name, "price": price, "url": item_url, "in_stock": in_stock})
            
            if len(items) < 10:
                break
                
    return results

def main() -> int:
    ap = argparse.ArgumentParser(description="Discover Phuc Anh prices.")
    ap.add_argument("--brand", default="dell")
    ap.add_argument("--category", default="laptop")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    client = get_client()
    ensure_competitor(client, COMPETITOR)
    tracked = fetch_catalog_skus(client, args.category.capitalize())
    if not tracked:
        print("No tracked products yet.")
        return 0

    existing = fetch_existing_source_skus(client, COMPETITOR)

    print(f"Discovering '{COMPETITOR}' — {args.category}/{args.brand}{' (dry run)' if args.dry else ''}...\n")
    found = discover(args.brand, args.category)
    print(f"{len(found)} product(s) parsed; matching against {len(tracked)} SKU(s), {len(existing)} existing.\n")

    category_label = args.category.capitalize()
    fallback_url = BRANDS.get(args.brand) if args.category == "laptop" else resolve_url("phucanh", args.category)
    source_rows = []
    
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

    if not args.dry and source_rows:
        upsert_sources(client, source_rows)
        print(f"\nSaved {len(source_rows)} source(s) to DB.")

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
