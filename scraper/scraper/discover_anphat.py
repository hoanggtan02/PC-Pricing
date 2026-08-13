"""Scraper khám phá dữ liệu bằng tìm kiếm cho An Phát (anphatpc.com.vn) (Playwright).

Giống như CellphoneS, kết quả tìm kiếm được render bằng JavaScript (HTML thô chỉ chứa các
template giá kiểu "${priceFormat}" mà JS sẽ điền vào), nên ta phải điều khiển một trình duyệt
headless. An Phát giữ các kết nối mạng luôn mở (do tracker), nên ta chờ selector giá thay vì chờ
"networkidle".

Chỉ khớp: giá CHỈ được ghi lại cho các SKU đã có sẵn trong `products` (danh mục của TNC). Các
mẫu của An Phát mà TNC không bán sẽ bị bỏ qua.

Các selector đã xác nhận (DOM sau khi render):
    card  : .p-text
    name  : a.p-name           (href = URL sản phẩm, text của <h3> = tên)
    price : .p-price            (giá hiện tại; KHÔNG phải .p-old-price - giá gốc gạch ngang)

Cách dùng:
    python -m scraper.discover_anphat --dry
    python -m scraper.discover_anphat
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys

from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright

from .brand import brand_of
from .browser import assert_parsed, goto_with_retry
from .config import categories, name_exclude_re, name_match_re, resolve_url
from .db import ensure_competitor, fetch_catalog_skus, get_client, insert_prices, upsert_sources
from .sku import derive_sku

COMPETITOR = "An Phát PC"
BASE_URL = "https://www.anphatpc.com.vn"
BRANDS = {
    "dell": "https://www.anphatpc.com.vn/tim?scat_id=&q=laptop+dell",
    "lenovo": "https://www.anphatpc.com.vn/tim?scat_id=&q=laptop+lenovo",
    "apple": "https://www.anphatpc.com.vn/tim?scat_id=&q=macbook",
    "hp": "https://www.anphatpc.com.vn/tim?scat_id=&q=laptop+hp",
    "asus": "https://www.anphatpc.com.vn/tim?scat_id=&q=laptop+asus",
    "acer": "https://www.anphatpc.com.vn/tim?scat_id=&q=laptop+acer",
    "msi": "https://www.anphatpc.com.vn/tim?scat_id=&q=laptop+msi",
    "gigabyte": "https://www.anphatpc.com.vn/tim?scat_id=&q=laptop+gigabyte",
}

CARD_SELECTOR = ".p-text"
NAME_SELECTOR = "a.p-name"
PRICE_SELECTOR = ".p-price"


def _digits_to_int(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def discover(brand: str = "dell", category: str = "laptop") -> list[dict]:
    """Trả về [{name, price, url}] cho các sản phẩm trên trang tìm kiếm đã render.

    Laptop (mặc định) lọc theo một `brand` qua URL per-brand cũ. Các danh mục khác chạy theo
    danh mục: một tìm kiếm cho cả danh mục, giữ lại theo name_match; caller suy ra thương hiệu.
    """
    if category == "laptop":
        search_url, want, name_re, excl_re = BRANDS[brand], brand.lower(), None, None
    else:
        search_url, want = resolve_url("anphat", category), None
        name_re = name_match_re(category)
        excl_re = name_exclude_re(category)   # loại mực in/cartridge/giá treo… (trước đây bị bỏ qua)
    if not search_url:
        return []
    results: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        )
        # domcontentloaded — An Phát không bao giờ đạt trạng thái network-idle. Thử lại khi tải
        # trang thất bại tạm thời, thay vì âm thầm trả về 0 kết quả.
        if not goto_with_retry(page, search_url, PRICE_SELECTOR, label=COMPETITOR):
            browser.close()
            return results
        page.wait_for_timeout(1500)  # chờ các thẻ còn lại render xong

        # Phần sản phẩm còn lại nằm sau nút "Xem thêm" (.btn-view-more), tải thêm qua JS.
        stale = 0
        for _ in range(40):
            btn = page.query_selector(".btn-view-more")
            if not btn or not btn.is_visible():
                break
            before = len(page.query_selector_all(CARD_SELECTOR))
            try:
                page.click(".btn-view-more", timeout=5000)
            except Exception:
                break
            page.wait_for_timeout(2000)  # chờ đợt mới render xong
            after = len(page.query_selector_all(CARD_SELECTOR))
            stale = stale + 1 if after == before else 0
            if stale >= 3:  # chỉ dừng sau khi không tăng liên tục nhiều lần
                break

        cards = page.query_selector_all(CARD_SELECTOR)
        extracted = 0  # số card trích được name+price hợp lệ (trước khi lọc brand)
        seen: set[str] = set()
        for card in cards:
            name_el = card.query_selector(NAME_SELECTOR)
            price_el = card.query_selector(PRICE_SELECTOR)
            if not name_el or not price_el:
                continue
            name = (name_el.inner_text() or "").strip()
            price = _digits_to_int(price_el.inner_text())
            href = name_el.get_attribute("href")
            url = (BASE_URL + href) if href and href.startswith("/") else href
            key = url or name
            if name and price:
                extracted += 1
            # Laptop: giữ một brand. Danh mục: giữ tên khớp name_match của danh mục.
            keep = (brand_of(name).lower() == want) if want else bool(name_re and name_re.search(name))
            if excl_re and excl_re.search(name):   # loại mực in/cartridge/phụ kiện lọt qua name_match
                keep = False
            if name and price and keep and key not in seen:
                seen.add(key)
                results.append({"name": name, "price": price, "url": url})
        browser.close()
    # Có card nhưng không trích được name+price nào -> selector đã lỗi thời (không phải "0 thật").
    assert_parsed(COMPETITOR, len(cards), extracted)
    return results



# Số tab chạy SONG SONG khi kiểm tồn kho. ĐÁNH ĐỔI CHÍNH XÁC vs TỐC ĐỘ: khối tồn kho nạp JS ~5-6s,
# mở QUÁ nhiều tab làm trang chậm render → poll hết giờ → mặc định sai "còn hàng" (GIẤU OOS thật). Đo
# thực (16 url, chạy 2 lần): c=8 → 2 OOS nhưng LỆCH 2 sp giữa 2 lần (không ổn định); c=4 → 11 OOS,
# LỆCH 0 (ổn định, đúng). Chọn 4: chậm hơn chút nhưng phát hiện OOS chính xác — vốn là mục tiêu.
_STOCK_CONCURRENCY = 4

# An Phát đổi cấu trúc (2026-08): còn hàng khi #js-in-stock LIỆT KÊ showroom (các <a> địa chỉ); hết
# hàng khi trống. KHÔNG đọc innerText (luôn có nhãn tĩnh "* Showroom miền Bắc/Nam:" → mọi sp bị coi
# còn hàng, lỗi 0 OOS). Phải ĐẾM số <a href> thực. Đếm link showroom; -1 nếu KHỐI CHƯA RENDER
# (#js-in-stock chưa có) — dùng để poll tới khi số ổn định (block nạp JS ~5-6s, không có sự kiện 'load').
_STOCK_COUNT_JS = """() => {
    const ins = document.querySelector('#js-in-stock');
    return ins ? ins.querySelectorAll('a[href]').length : -1;
}"""


async def _read_stock(page) -> bool:
    """POLL TỚI KHI ỔN ĐỊNH: đếm link showroom nhiều lần, dừng khi số KHÔNG ĐỔI qua 2 lần đọc (block đã
    render xong — không có sự kiện 'load' trên An Phát nên đây là cách chắc chắn nhất "đã tải hẳn").
    Trả về True nếu link>0 (còn hàng), False nếu =0 (hết hàng — block đã render mà không showroom nào có).
    Nếu hết thời gian mà block chưa render (luôn = -1) → True (mặc định còn hàng, không gắn cờ sai)."""
    prev = -2
    for _ in range(24):                     # tối đa ~12s (24 × 500ms)
        n = await page.evaluate(_STOCK_COUNT_JS)
        if n != -1 and n == prev:           # block đã render VÀ số link ổn định qua 2 lần đọc
            return n > 0
        prev = n
        await page.wait_for_timeout(500)
    return prev > 0 if prev != -1 else True  # chưa render kịp → mặc định còn hàng


async def _check_stock_chunk(context, urls: list[str]) -> dict[str, bool]:
    """Kiểm tồn kho một NHÓM URL tuần tự trên MỘT tab (async). Nhiều nhóm chạy song song ở check_stock.
    Lỗi → coi là còn hàng."""
    out: dict[str, bool] = {}
    page = await context.new_page()
    try:
        for url in urls:
            try:
                # An Phát KHÔNG đạt 'domcontentloaded' (tracker giữ kết nối mở) → goto(domcontentloaded)
                # treo tới 30s mỗi url. Dùng 'commit' (~1.7s) rồi POLL tới khi khối tồn kho ổn định.
                await page.goto(url, wait_until="commit", timeout=15000)
                out[url] = await _read_stock(page)
            except Exception:
                out[url] = True  # tải lỗi → mặc định còn hàng (không gắn cờ sai)
    finally:
        await page.close()
    return out


async def _check_stock_async(urls: list[str]) -> dict[str, bool]:
    n = min(_STOCK_CONCURRENCY, len(urls))
    chunks: list[list[str]] = [[] for _ in range(n)]
    for i, u in enumerate(urls):  # round-robin để các tab kết thúc gần cùng lúc
        chunks[i % n].append(u)
    status: dict[str, bool] = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        )
        results = await asyncio.gather(*(_check_stock_chunk(context, c) for c in chunks))
        for r in results:
            status.update(r)
        await browser.close()
    return status


def check_stock(urls: list[str]) -> dict[str, bool]:
    """Với mỗi URL sản phẩm, trả về An Phát có thực sự còn hàng hay không.

    An Phát vẫn hiển thị giá kể cả khi hết hàng. Tồn kho showroom (#js-mien-bac / #js-mien-nam) CHỈ có
    ở trang sản phẩm nên phải ghé từng URL. Trước đây ghé TUẦN TỰ trên MỘT tab → bước chậm nhất toàn
    cron (anphat/monitor ~28 phút). Nay chia URL cho _STOCK_CONCURRENCY tab chạy SONG SONG (async), rút
    ngắn ~N lần. Wrapper đồng bộ (asyncio.run) để caller không đổi. Lỗi ở URL nào → mặc định còn hàng."""
    if not urls:
        return {}
    return asyncio.run(_check_stock_async(urls))


def main() -> int:
    ap = argparse.ArgumentParser(description="Discover An Phát prices by brand and category.")
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
    print(f"{len(found)} unique product(s) parsed; matching against {len(tracked)} TNC SKU(s).\n")

    category_label = args.category.capitalize()
    fallback_url = BRANDS[args.brand] if args.category == "laptop" else None
    # Chỉ giữ lại các sản phẩm đã khớp, sau đó kiểm tra tồn kho cho riêng chúng (mỗi cái tải một trang).
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
