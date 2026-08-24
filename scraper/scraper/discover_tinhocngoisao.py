"""Scraper khám phá dữ liệu bằng tìm kiếm cho Tin Học Ngôi Sao (tinhocngoisao.com) (Playwright).

Các selector đã xác nhận (DOM sau khi render):
    card  : .product-item
    name  : h3.pdLoopName a
    url   : h3.pdLoopName a (href)
    price : .pdPrice span (giá hiện tại)
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

COMPETITOR = "Tin Học Ngôi Sao"
BASE_URL = "https://tinhocngoisao.com"

BRANDS = {
    "dell": "https://tinhocngoisao.com/search?q=laptop+dell",
    "lenovo": "https://tinhocngoisao.com/search?q=laptop+lenovo",
    "apple": "https://tinhocngoisao.com/search?q=macbook",
    "hp": "https://tinhocngoisao.com/search?q=laptop+hp",
    "asus": "https://tinhocngoisao.com/search?q=laptop+asus",
    "acer": "https://tinhocngoisao.com/search?q=laptop+acer",
    "msi": "https://tinhocngoisao.com/search?q=laptop+msi",
    "gigabyte": "https://tinhocngoisao.com/search?q=laptop+gigabyte",
}

PRICE_SELECTOR = ".pdPrice span"
CARD_SELECTOR = ".product-item"


def _digits_to_int(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def discover(brand: str = "dell", category: str = "laptop") -> list[dict]:
    """Trả về [{name, price, url, in_stock}] cho các sản phẩm trên trang tìm kiếm đã render."""
    is_laptop = category == "laptop"
    excl_re = name_exclude_re(category)
    if is_laptop:
        search_url = BRANDS[brand]
        name_re = None
    else:
        search_url = resolve_url("tinhocngoisao", category)
        name_re = name_match_re(category)
    if not search_url:
        return []

    results: list[dict] = []
    # Chạy trực tiếp (không dùng proxy) để đảm bảo tốc độ và tính ổn định
    with browser_page(use_proxy=False) as page:
        if not goto_with_retry(page, search_url, PRICE_SELECTOR, label=COMPETITOR):
            return results

        # Tải thêm bằng cách click nút load more
        stale = 0
        for _ in range(40):
            btn = page.query_selector(".btn-load__more")
            if not btn or not btn.is_visible():
                break
            before = len(page.query_selector_all(CARD_SELECTOR))
            try:
                page.click(".btn-load__more", timeout=5000)
            except Exception:
                break
            page.wait_for_timeout(2000)  # Chờ tải thêm
            after = len(page.query_selector_all(CARD_SELECTOR))
            stale = stale + 1 if after == before else 0
            if stale >= 3:
                break

        # Trích xuất dữ liệu từ các card
        items = page.eval_on_selector_all(
            CARD_SELECTOR,
            """
            (cards) => {
                const out = [];
                for (const card of cards) {
                    const name_el = card.querySelector('h3.pdLoopName a');
                    const price_el = card.querySelector('.pdPrice span');
                    if (!name_el || !price_el) continue;
                    const name = name_el.innerText.trim();
                    const href = name_el.getAttribute('href') || '';
                    const price = price_el.innerText.trim();
                    const card_text = card.innerText || '';
                    out.push({ name, price, url: href, card_text });
                }
                return out;
            }
            """
        )

        for it in items:
            name = it["name"]
            if (excl_re and excl_re.search(name)) or (not is_laptop and not (name_re and name_re.search(name))):
                continue
            price = _digits_to_int(it["price"])
            href = it["url"]
            url = (BASE_URL + href) if href and href.startswith("/") else href
            
            # Kiểm tra xem sản phẩm có hết hàng hay không
            # Mặc định OOS nếu card chứa các cụm từ: hết hàng, liên hệ, sắp về, tạm hết
            card_text_lower = it.get("card_text", "").lower()
            in_stock = stock_is_in(it.get("price")) and not any(
                term in card_text_lower for term in ["hết hàng", "liên hệ", "sắp về", "tạm hết"]
            )
            
            if price:
                results.append({"name": name, "price": price, "url": url, "in_stock": in_stock})
                
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Discover Tin Hoc Ngoi Sao prices.")
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
    fallback_url = BRANDS[args.brand] if args.category == "laptop" else resolve_url("tinhocngoisao", args.category)
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
        if is_new:
            price_rows.append({
                "product_sku": sku, "competitor": COMPETITOR, "price": item["price"],
                "in_stock": item.get("in_stock", True), "is_used": is_used,
            })
            new_count += 1

    if not args.dry:
        upsert_sources(client, source_rows)
        insert_prices(client, price_rows)

    print(f"\nDone. {new_count} SKU MỚI được ghi giá trên {COMPETITOR}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
