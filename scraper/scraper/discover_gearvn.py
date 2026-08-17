"""Scraper khám phá dữ liệu bằng tìm kiếm cho GearVN (gearvn.com) (Playwright, không cần proxy).

CẬP NHẬT 2026-08: GearVN đổi hẳn giao diện sang Next.js/Tailwind. Các class cũ (.proloop-price,
.proloop-name), cơ chế "cuộn để tải thêm", VÀ route tìm kiếm cũ (/search?q=...) đều không còn
đúng — route tìm kiếm mới là /tim-kiem?q=.... Đây là nguyên nhân scraper cũ trả về 0 kết quả
hàng loạt. Giao diện mới:
    card  : a.product-card (href="/products/...") — class "product-card" là tên thật, ổn định
            (không phải Tailwind arbitrary-value hash như các class màu/kích thước khác).
    name  : <p> DUY NHẤT bên trong thẻ (class line-clamp-2, nhưng ta không dựa vào nó).
    price : span cuối cùng trong thẻ khớp mẫu giá (12.345.678đ) và KHÔNG có class "line-through"
            (giá gạch ngang = giá cũ). Không dựa vào các class màu kiểu
            text-[var(--color-flash-price-sale)] vì đó là Tailwind arbitrary-value, dễ đổi theo
            theme/redesign.
    phân trang: <nav data-testid="collection-pagination"> chứa nút "Trang sau" — là <a href=...>
            khi còn trang kế, là <span aria-disabled="true"> khi đã hết trang. KHÔNG còn cuộn để
            tải thêm.

ƯU TIÊN CATEGORY PAGE HƠN SEARCH: category (/collections/...) cho kết quả sạch hơn (không lẫn
phụ kiện/kết quả không liên quan như search) và đã được xác nhận đúng cấu trúc (a.product-card +
phân trang nav). BRANDS bên dưới dùng category page thật lấy từ menu điều hướng của chính site khi
có; chỉ MacBook dùng /tim-kiem?q=macbook vì không có category page riêng cho Mac trong menu.

GearVN chuyên về build PC và ít/không bán laptop Dell — tìm kiếm/category "laptop dell" trên trang
này chủ yếu ra phụ kiện (chuột, màn hình) nếu category không đúng. Đây là điều dự kiến và bình
thường: ta lọc theo tên để lấy đúng laptop và ghi lại bất cứ thứ gì (nếu có) xuất hiện.

Chỉ khớp: chỉ ghi lại giá cho các SKU đã có sẵn trong `products` (danh mục của TNC).

MODE A (weekend discovery) — CHỈ GHI GIÁ CHO SKU MỚI: kịch bản này chạy cuối tuần để tìm sản
phẩm MỚI, không phải để cào lại giá của mọi sản phẩm đã biết — giá đó Mode B (sync_prices, chạy
hàng ngày) đã cào đều đặn rồi. Vì vậy SKU nào ĐÃ có source ở competitor này (fetch_existing_source_skus)
thì chỉ được refresh URL (upsert_sources), KHÔNG check_stock lại và KHÔNG ghi thêm dòng
price_history trùng lặp — điều này còn giúp job chạy nhanh hơn vì bỏ được bước check_stock
(mỗi lần tải một trang sản phẩm) cho toàn bộ sku cũ.

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
from .db import (
    ensure_competitor,
    fetch_catalog_skus,
    fetch_existing_source_skus,
    get_client,
    insert_prices,
    upsert_sources,
)
from .sku import derive_sku
from .stock import is_out_of_stock

COMPETITOR = "GearVN"
BASE_URL = "https://gearvn.com"

# Ưu tiên category page thật lấy từ menu điều hướng của site (ổn định, sạch hơn search).
# "dell" dùng alias ngắn /collections/laptop-dell đã xác nhận tồn tại. Các brand khác dùng URL
# category "laptop <brand> học tập và làm việc" lấy từ JSON menu điều hướng của site (thấy trong
# gearvn_evidence.html) — đây là danh mục "văn phòng", không gộp dòng gaming riêng của brand đó.
# "apple" KHÔNG có category page riêng cho Mac trong menu -> dùng route tìm kiếm MỚI /tim-kiem
# (route cũ /search đã đổi, không còn dùng được).
BRANDS = {
    "dell": "https://gearvn.com/collections/laptop-dell",
    "lenovo": "https://gearvn.com/collections/laptop-lenovo-hoc-tap-va-lam-viec",
    "apple": "https://gearvn.com/tim-kiem?q=macbook",
    "hp": "https://gearvn.com/collections/laptop-hp-pavilion",
    "asus": "https://gearvn.com/collections/laptop-asus-hoc-tap-va-lam-viec",
    "acer": "https://gearvn.com/collections/laptop-acer-hoc-tap-va-lam-viec",
    "msi": "https://gearvn.com/collections/laptop-msi-hoc-tap-va-lam-viec",
    "gigabyte": "https://gearvn.com/collections/laptop-gaming-gigabyte",
}

# Thẻ sản phẩm: class "product-card" là tên thật ổn định (không phải hash Tailwind). Dự phòng
# thêm a[href*="/products/"] phòng khi một trang nào đó không gắn đúng class này.
CARD_SELECTOR = 'a.product-card, a[href*="/products/"]'
_PRICE_RE = re.compile(r"[0-9]{1,3}(?:\.[0-9]{3})+\s*đ?")

# Nút "Trang sau" trong thanh phân trang mới. Chỉ dùng khi nó là <a href=...> (còn trang kế);
# khi đã hết trang, GearVN đổi nó thành <span aria-disabled="true">.
NEXT_PAGE_SELECTOR = '[data-testid="collection-pagination"] a[aria-label="Trang sau"]'
PAGE_CAP = 60  # chốt an toàn; vòng lặp tự dừng khi hết nút "Trang sau"


def _digits_to_int(text: str) -> int | None:
    m = _PRICE_RE.search(text or "")
    return int(re.sub(r"[^\d]", "", m.group(0))) if m else None


def _extract_page_items(page, is_laptop: bool) -> list[dict]:
    """Đọc mọi thẻ sản phẩm trên trang hiện tại (đã render)."""
    return page.eval_on_selector_all(
        CARD_SELECTOR,
        """
        (cards, isLaptop) => {
          const out = [];
          const seen = new Set();
          const priceRe = /[0-9]{1,3}(?:\\.[0-9]{3})+\\s*đ?/;
          for (const card of cards) {
            const href = (card.getAttribute('href') || '').split('?')[0];
            if (!href || seen.has(href)) continue;
            const nameEl = card.querySelector('p');
            const name = nameEl ? nameEl.innerText.trim() : '';
            if (!name) continue;
            // Laptop: chỉ giữ thẻ tên bắt đầu bằng laptop/macbook. Danh mục khác lọc ở Python.
            if (isLaptop && !/^(laptop|macbook)/i.test(name)) continue;
            // Giá hiện tại = span khớp mẫu giá CUỐI CÙNG trong thẻ mà KHÔNG có class
            // "line-through" (giá gạch ngang = giá cũ). Giá cuối vì thứ tự DOM luôn là
            // [giá cũ gạch ngang?] -> [badge giảm giá?] -> [giá hiện tại] -> [khối khuyến mãi rỗng].
            let price = '';
            for (const s of card.querySelectorAll('span')) {
              const cls = s.getAttribute('class') || '';
              if (cls.includes('line-through')) continue;
              const txt = (s.textContent || '').trim();
              if (priceRe.test(txt)) price = txt;
            }
            if (!price) continue;
            seen.add(href);
            out.push({ name, price, url: href });
          }
          return out;
        }
        """,
        is_laptop,
    )


def discover(brand: str = "dell", category: str = "laptop") -> list[dict]:
    """Trả về [{name, price, url}] cho các sản phẩm trên mọi trang phân trang.

    Laptop (mặc định) dùng URL per-brand (category page hoặc /tim-kiem cho Mac) + lọc
    /^laptop|macbook/. Các danh mục khác chạy theo danh mục: tìm cả danh mục, giữ mọi card sản
    phẩm, lọc theo name_match ở Python.

    Phân trang: GearVN dùng nút "Trang sau" (<a href="...?page=N">) — không còn cuộn để tải
    thêm. Ta điều hướng theo nút đó tới khi nó biến mất (đã hết trang) hoặc chạm PAGE_CAP.
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
    seen_urls: set[str] = set()
    with browser_page(use_proxy=False) as page:
        if not goto_with_retry(page, search_url, CARD_SELECTOR, label=COMPETITOR):
            return results

        for n in range(1, PAGE_CAP + 1):
            items = _extract_page_items(page, is_laptop)
            for it in items:
                name = it["name"]
                if (excl_re and excl_re.search(name)) or (
                    not is_laptop and not (name_re and name_re.search(name))
                ):
                    continue
                price = _digits_to_int(it["price"])
                href = it["url"]
                url = (BASE_URL + href) if href and href.startswith("/") else href
                if price and url not in seen_urls:
                    seen_urls.add(url)
                    results.append({"name": name, "price": price, "url": url})

            next_link = page.query_selector(NEXT_PAGE_SELECTOR)
            if not next_link:
                break  # đã hết trang (nút "Trang sau" đã đổi thành <span disabled>)
            next_href = next_link.get_attribute("href")
            if not next_href:
                break
            next_url = (BASE_URL + next_href) if next_href.startswith("/") else next_href
            try:
                page.goto(next_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector(CARD_SELECTOR, timeout=20000)
            except Exception:
                break  # trang kế chậm/lỗi — dừng, giữ lại những gì đã thu thập được
        else:
            print(f"  ⚠️  {COMPETITOR}: chạm PAGE_CAP={PAGE_CAP} trang mà vẫn còn trang kế — "
                  f"danh mục dài hơn, cân nhắc nâng PAGE_CAP.")
    return results


def check_stock(urls: list[str]) -> dict[str, bool]:
    """Với mỗi URL sản phẩm, trả về GearVN có còn hàng hay không.

    LƯU Ý: sau khi GearVN đổi giao diện (2026-08), CHƯA XÁC MINH được cấu trúc trang sản phẩm chi
    tiết (chỉ có mẫu HTML trang danh mục). Vì vậy hàm này thử các tín hiệu CŨ trước
    ([name="buy-now"] / [data-s="available"]), rồi rơi xuống một kiểm tra chung bằng cụm từ hết
    hàng (is_out_of_stock — "hết hàng"/"liên hệ"/"tạm hết"...) quét trên text của trang, để không
    hoàn toàn phụ thuộc vào selector cũ có thể đã lỗi thời. Nếu có lỗi, mặc định coi là còn hàng
    (an toàn hơn ẩn nhầm sản phẩm còn bán).
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
                        return !!buy || !!avail ? true : null;
                    }"""
                )
                if in_stock is None:
                    # tín hiệu cũ không tìm thấy — quét chung bằng cụm từ hết hàng trên toàn trang
                    body_text = page.inner_text("body")
                    in_stock = not is_out_of_stock(body_text)
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

    # SKU nào đã có source ở GearVN -> đã được Mode B (daily sync) theo dõi giá. Chỉ ghi giá cho
    # SKU MỚI (chưa có trong tập này); sku cũ chỉ refresh URL, KHÔNG check_stock lại (tốn thời gian).
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
    fallback_url = BRANDS[args.brand] if args.category == "laptop" else resolve_url("gearvn", args.category)
    # Chỉ giữ lại các sản phẩm đã khớp SKU.
    matched = [
        {**item, "sku": derive_sku(item["name"], item.get("url"), category_label)}
        for item in found
        if derive_sku(item["name"], item.get("url"), category_label) in tracked
    ]
    new_items = [m for m in matched if m["sku"] not in existing]
    known_items = [m for m in matched if m["sku"] in existing]

    # Chỉ kiểm tồn kho (tốn 1 lượt tải trang mỗi sản phẩm) cho SKU MỚI — SKU cũ daily sync tự lo.
    stock = check_stock([m["url"] for m in new_items if m.get("url")])

    source_rows, price_rows = [], []
    for item in new_items:
        sku = item["sku"]
        in_stock = stock.get(item.get("url"), True)
        flag = "" if in_stock else "  [OUT OF STOCK]"
        print(f"- [MỚI] {sku}: {item['price']:,} VND{flag}  ({item['name'][:50]})")
        source_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "url": item.get("url") or fallback_url}
        )
        price_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "price": item["price"], "in_stock": in_stock}
        )

    # SKU cũ: chỉ refresh URL (bắt kịp nếu shop đổi slug), KHÔNG ghi giá/tồn kho lại.
    for item in known_items:
        source_rows.append(
            {"product_sku": item["sku"], "competitor": COMPETITOR, "url": item.get("url") or fallback_url}
        )

    if not args.dry:
        upsert_sources(client, source_rows)
        insert_prices(client, price_rows)

    print(
        f"\nDone. {len(price_rows)} SKU MỚI được ghi giá trên {COMPETITOR} "
        f"({len(known_items)} SKU cũ chỉ refresh URL, không ghi giá lại)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())