"""Scraper khám phá dữ liệu bằng tìm kiếm cho GearVN (gearvn.com) (Playwright, không cần proxy).

GearVN truy cập trực tiếp được (không bị chặn theo vùng địa lý). Lưu ý: GearVN chuyên về build
PC và ít/không bán laptop Dell — tìm kiếm "laptop dell" trên trang này chủ yếu ra phụ kiện
(chuột, màn hình). Đây là điều dự kiến và bình thường: ta lọc theo tên để lấy đúng laptop và ghi
lại bất cứ thứ gì (nếu có) xuất hiện.

Các selector đã xác nhận (DOM sau khi render):
    card  : một phần tử chứa .proloop-price và một link /products/
    name  : h3 / .proloop-name
    price : .proloop-price--highlight (giá sale) hoặc --default / --normal; KHÔNG phải --compare (giá cũ)

Chỉ khớp: chỉ ghi lại giá cho các SKU đã có sẵn trong `products` (danh mục của TNC).

Cách dùng:
    python -m scraper.discover_gearvn --dry
    python -m scraper.discover_gearvn
"""

from __future__ import annotations

import argparse
import re
import sys

from .browser import browser_page, goto_with_retry
from .config import categories, name_exclude_re, name_match_re, resolve_url
from .db import ensure_competitor, fetch_catalog_skus, get_client, insert_prices, upsert_sources
from .sku import derive_sku

COMPETITOR = "GearVN"
BASE_URL = "https://gearvn.com"
BRANDS = {
    "dell": "https://gearvn.com/search?q=laptop%20dell",
    "lenovo": "https://gearvn.com/search?q=laptop%20lenovo",
    "apple": "https://gearvn.com/search?q=macbook",
    "hp": "https://gearvn.com/search?q=laptop%20hp",
    "asus": "https://gearvn.com/collections/laptop-asus-hoc-tap-va-lam-viec",
    "acer": "https://gearvn.com/collections/laptop-acer-hoc-tap-va-lam-viec",
    "msi": "https://gearvn.com/collections/laptop-msi-hoc-tap-va-lam-viec",
    "gigabyte": "https://gearvn.com/collections/laptop-gaming-gigabyte",
}

PRICE_SELECTOR = ".proloop-price"


def _digits_to_int(text: str) -> int | None:
    # Chỉ lấy giá được nhóm ĐẦU TIÊN (giá sale), bỏ qua phần đuôi kiểu "-14%" v.v.
    m = re.search(r"\d{1,3}(?:\.\d{3})+", text or "")
    return int(m.group(0).replace(".", "")) if m else None


def discover(brand: str = "dell", category: str = "laptop") -> list[dict]:
    """Trả về [{name, price, url}] cho các sản phẩm trên trang tìm kiếm đã render.

    Laptop (mặc định) dùng URL per-brand + lọc /^laptop|macbook/. Các danh mục khác chạy theo
    danh mục: tìm cả danh mục, giữ mọi card sản phẩm, lọc theo name_match ở Python.
    """
    is_laptop = category == "laptop"
    excl_re = name_exclude_re(category)
    if is_laptop:
        search_url, name_re = BRANDS[brand], None
    else:
        search_url = resolve_url("gearvn", category)
        name_re = name_match_re(category)
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
                  if (card.querySelector('a[href*="/products/"]') &&
                      card.querySelector('h3, .proloop-name, [class*="name"]')) break;
                }
                const a = card.querySelector('a[href*="/products/"]');
                const nm = card.querySelector('h3, .proloop-name, [class*="name"]');
                if (!a || !nm) continue;
                const href = (a.getAttribute('href') || '').split('?')[0];
                if (!href || seen.has(href)) continue;
                const name = nm.innerText.trim();
                // Laptop: bỏ qua phụ kiện/màn hình/PC. Danh mục khác lọc ở Python (name_match).
                if (isLaptop && !/^(laptop|macbook)/i.test(name)) continue;
                // giá hiện tại: highlight (sale) > default/normal; không bao giờ lấy --compare (giá cũ)
                const hp = card.querySelector(
                  '.proloop-price--highlight, .proloop-price--default, .proloop-price--normal');
                const priceTxt = hp ? hp.innerText.trim() : '';
                if (!priceTxt) continue;
                seen.add(href);
                out.push({ name, price: priceTxt, url: href });
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
                results.append({"name": name, "price": price, "url": url})
    return results



def check_stock(urls: list[str]) -> dict[str, bool]:
    """Với mỗi URL sản phẩm, trả về việc GearVN có còn hàng hay không.

    Tín hiệu của GearVN nằm ở trang SẢN PHẨM (không phải trang danh sách): một sản phẩm còn hàng
    sẽ hiển thị nút mua ngay "MUA NGAY" (name="buy-now") và data-s="available"; khi hết hàng nút
    đó bị gỡ bỏ, chỉ còn lại div liên hệ với data-s="sold-out". Vậy một sản phẩm còn hàng nếu nó
    có nút buy-now HOẶC một phần tử data-s="available". Nếu có lỗi, ta mặc định coi là còn hàng.
    """
    status: dict[str, bool] = {}
    if not urls:
        return status
    with browser_page(use_proxy=False) as page:
        for url in urls:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(800)
                in_stock = page.evaluate(
                    """() => {
                        const buy = document.querySelector('[name="buy-now"]');
                        const avail = document.querySelector('[data-s="available"]');
                        return !!buy || !!avail;
                    }"""
                )
                status[url] = bool(in_stock)
            except Exception:
                status[url] = True  # nếu có lỗi, không gắn cờ sai là hết hàng
    return status


def main() -> int:
    ap = argparse.ArgumentParser(description="Discover GearVN prices by brand and category.")
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
    fallback_url = BRANDS[args.brand] if args.category == "laptop" else resolve_url("gearvn", args.category)
    # Chỉ giữ lại các sản phẩm đã khớp, sau đó kiểm tra tồn kho cho riêng chúng (tín hiệu của GearVN theo từng trang).
    matched = [
        {**item, "sku": derive_sku(item["name"], item.get("url"), category_label)}
        for item in found
        if derive_sku(item["name"], item.get("url"), category_label) in tracked
    ]
    stock = check_stock([m["url"] for m in matched if m.get("url")])

    source_rows, price_rows = [], []
    for item in matched:
        sku = item["sku"]
        in_stock = stock.get(item.get("url"), True)
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
