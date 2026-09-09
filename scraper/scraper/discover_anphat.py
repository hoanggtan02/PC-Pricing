"""Scraper khám phá dữ liệu cho An Phát (anphatpc.com.vn) (Playwright).

CẬP NHẬT (2026-09) — CÀO THEO TRANG DANH MỤC, KHÔNG QUA TÌM KIẾM + LƯU SẢN PHẨM KHÔNG KHỚP:

Trước đây mọi category (ngoài laptop) đều bị cào qua Ô TÌM KIẾM của An Phát (`resolve_url("anphat",
category)` rơi xuống `competitors.anphat.search_url` vì `sources.yaml` chưa có `paths.anphat`).
Tìm kiếm theo search_term trả về kết quả nhiễu hơn (lẫn phụ kiện/hàng không liên quan) so với đúng
TRANG DANH MỤC thật của site — và quan trọng hơn, KHÔNG cào được HẾT sản phẩm của một category vì
site giới hạn số kết quả tìm kiếm hiển thị.

Sửa: `scraper/config/sources.yaml` giờ có `paths.anphat` cho từng category — trỏ THẲNG tới (các)
trang danh mục thật lấy từ sitemap An Phát. Danh mục nào An Phát CHIA NHỎ HƠN TNC (ví dụ router =
"bộ phát sóng không dây" + "router wifi 4G" là hai trang riêng) thì `paths.anphat` là một DANH SÁCH
2 URL, gộp lại qua `config.resolve_urls()` — xem ghi chú ở đó.

MODE MỚI — `discover_category_full()`: cào TOÀN BỘ sản phẩm trên (các) trang danh mục, không lọc
theo "đã khớp SKU nào chưa". `main()` (nhánh non-laptop) sau đó tự đối chiếu:
  - SKU khớp catalog TNC (`tracked`)     -> ghi source/price như luồng cũ (chỉ SKU MỚI mới ghi giá).
  - SKU không suy ra được HOẶC không có trong TNC -> upsert vào bảng `missing_products` (xem
    scraper/db.py: upsert_missing_products / resolve_missing_products) để xem lại tay — đây chính
    là bảng Tan vừa tạo để theo dõi sản phẩm An Phát có mà TNC chưa bán.
  - Một URL trước đây từng nằm trong `missing_products` mà giờ ĐÃ khớp (TNC vừa bổ sung đúng SKU
    đó) sẽ được đánh dấu resolved=true qua `resolve_missing_products()`.

Nhánh LAPTOP (`--category laptop`, mặc định) GIỮ NGUYÊN luồng CŨ (tìm kiếm theo brand qua BRANDS,
match-only với catalog TNC) — không đổi để không ảnh hưởng scrape.yml (leg `kind: laptop` vẫn gọi
`--brand <brand>` như trước). Laptop KHÔNG (chưa) được đưa vào flow missing_products ở bản này.

Cách dùng:
    python -m scraper.discover_anphat --brand dell              # laptop, luồng cũ (search)
    python -m scraper.discover_anphat --category ram --dry      # RAM, luồng mới (trang danh mục)
    python -m scraper.discover_anphat --category ram            # ghi DB thật
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from argparse import Namespace

from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright

from .brand import brand_of
from .browser import assert_parsed, goto_with_retry
from .config import (
    categories,
    is_old_listing_name,
    name_exclude_re,
    name_match_re,
    resolve_urls,
)
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

COMPETITOR = "An Phát PC"
BASE_URL = "https://www.anphatpc.com.vn"

# Laptop: GIỮ NGUYÊN — tìm kiếm theo brand (không có trang danh mục per-brand sạch bằng search này).
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

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

CARD_SELECTOR = ".p-text"
NAME_SELECTOR = "a.p-name"
PRICE_SELECTOR = ".p-price"
VIEW_MORE_SELECTOR = ".btn-view-more"


def _digits_to_int(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def _click_load_more(page, max_clicks: int = 60) -> None:
    """Bấm '.btn-view-more' tới khi hết (dùng chung cho cả trang tìm kiếm brand lẫn trang danh mục
    — An Phát dùng chung cơ chế 'tải thêm' này ở mọi nơi trên site)."""
    stale = 0
    for _ in range(max_clicks):
        btn = page.query_selector(VIEW_MORE_SELECTOR)
        if not btn or not btn.is_visible():
            break
        before = len(page.query_selector_all(CARD_SELECTOR))
        try:
            btn.scroll_into_view_if_needed()
            page.click(VIEW_MORE_SELECTOR, timeout=5000)
        except Exception:
            break
        page.wait_for_timeout(2000)
        after = len(page.query_selector_all(CARD_SELECTOR))
        stale = stale + 1 if after == before else 0
        if stale >= 3:
            break


def _extract_cards(page) -> list[dict]:
    """Đọc mọi thẻ .p-text đang có trên trang (đã render + đã bấm hết 'Xem thêm')."""
    out: list[dict] = []
    for card in page.query_selector_all(CARD_SELECTOR):
        name_el = card.query_selector(NAME_SELECTOR)
        price_el = card.query_selector(PRICE_SELECTOR)
        if not name_el or not price_el:
            continue
        name = (name_el.inner_text() or "").strip()
        price = _digits_to_int(price_el.inner_text())
        href = name_el.get_attribute("href")
        url = (BASE_URL + href) if href and href.startswith("/") else href
        if name and price and url:
            out.append({"name": name, "price": price, "url": url})
    return out


def discover(brand: str = "dell") -> list[dict]:
    """[CHỈ DÙNG CHO LAPTOP] Tìm kiếm theo brand, trả về [{name, price, url}] đã lọc đúng brand.

    Đây là luồng CŨ, giữ nguyên để không ảnh hưởng scrape.yml (leg `kind: laptop`). Các category
    khác dùng discover_category_full() bên dưới (trang danh mục thật, không qua tìm kiếm).
    """
    search_url = BRANDS.get(brand)
    if not search_url:
        return []
    want = brand.lower()
    results: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA)
        # domcontentloaded — An Phát không bao giờ đạt trạng thái network-idle.
        if not goto_with_retry(page, search_url, PRICE_SELECTOR, label=COMPETITOR):
            browser.close()
            return results
        page.wait_for_timeout(1500)
        _click_load_more(page)

        cards = page.query_selector_all(CARD_SELECTOR)
        extracted = 0
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
            if name and price and brand_of(name).lower() == want and key not in seen:
                seen.add(key)
                results.append({"name": name, "price": price, "url": url})
        browser.close()
    # Có card nhưng không trích được name+price nào -> selector đã lỗi thời (không phải "0 thật").
    assert_parsed(COMPETITOR, len(cards), extracted)
    return results


def discover_category_full(category: str) -> list[dict]:
    """Cào TOÀN BỘ sản phẩm của một category qua (các) trang DANH MỤC THẬT của An Phát
    (`paths.anphat` trong sources.yaml) — KHÔNG qua tìm kiếm.

    Trả về MỌI sản phẩm tìm thấy (đã lọc name_match/name_exclude của category), kể cả những cái
    SẼ KHÔNG khớp SKU nào của TNC — `main()` mới là nơi đối chiếu và quyết định ghi price_history
    (khớp) hay missing_products (không khớp).

    Một category của An Phát có thể chia nhỏ hơn TNC (ví dụ router = trang wifi gia đình + trang
    router 4G riêng) — `resolve_urls()` trả về DANH SÁCH URL cho category đó (giống cơ chế `tnc:`
    dạng list), ta cào lần lượt từng URL và gộp kết quả (dedupe theo URL sản phẩm).
    """
    urls = resolve_urls("anphat", category)
    if not urls:
        return []
    name_re = name_match_re(category)
    excl_re = name_exclude_re(category)

    results: list[dict] = []
    seen_urls: set[str] = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA)
        for list_url in urls:
            if not goto_with_retry(page, list_url, PRICE_SELECTOR, label=f"{COMPETITOR}/{category}"):
                continue  # trang này lỗi/rỗng — vẫn thử tiếp các URL còn lại của category
            page.wait_for_timeout(1500)
            _click_load_more(page)

            for it in _extract_cards(page):
                name = it["name"]
                if excl_re and excl_re.search(name):
                    continue
                if name_re and not name_re.search(name):
                    continue
                if it["url"] in seen_urls:
                    continue
                seen_urls.add(it["url"])
                results.append(it)
        browser.close()
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
        context = await browser.new_context(user_agent=UA)
        results = await asyncio.gather(*(_check_stock_chunk(context, c) for c in chunks))
        for r in results:
            status.update(r)
        await browser.close()
    return status


def check_stock(urls: list[str]) -> dict[str, bool]:
    """Với mỗi URL sản phẩm, trả về An Phát có thực sự còn hàng hay không.

    An Phát vẫn hiển thị giá kể cả khi hết hàng. Tồn kho showroom (#js-mien-bac / #js-mien-nam) CHỈ có
    ở trang sản phẩm nên phải ghé từng URL. Chia URL cho _STOCK_CONCURRENCY tab chạy SONG SONG (async).
    Wrapper đồng bộ (asyncio.run) để caller không đổi. Lỗi ở URL nào → mặc định còn hàng."""
    if not urls:
        return {}
    return asyncio.run(_check_stock_async(urls))


def _run_laptop(client, args) -> int:
    """Luồng CŨ cho laptop: tìm kiếm theo brand, match-only với catalog TNC, chỉ ghi giá cho SKU
    MỚI (chưa có source ở An Phát) — SKU cũ để Mode B (sync_prices, chạy hàng ngày) tự lo."""
    tracked = fetch_catalog_skus(client, "Laptop")
    if not tracked:
        print("No tracked products yet. Run the TNC scraper first to populate the catalog.")
        return 0

    existing = fetch_existing_source_skus(client, COMPETITOR)

    print(
        f"Discovering '{COMPETITOR}' — laptop/{args.brand}"
        f"{' (dry run)' if args.dry else ''}...\n"
    )
    found = discover(args.brand)
    print(
        f"{len(found)} unique product(s) parsed; matching against {len(tracked)} TNC SKU(s), "
        f"{len(existing)} đã có source (daily sync lo giá).\n"
    )

    fallback_url = BRANDS[args.brand]
    matched = [
        {**item, "sku": derive_sku(item["name"], item.get("url"), "Laptop")}
        for item in found
        if derive_sku(item["name"], item.get("url"), "Laptop") in tracked
    ]
    new_items = [m for m in matched if m["sku"] not in existing]
    known_items = [m for m in matched if m["sku"] in existing]

    stock = check_stock([m["url"] for m in new_items if m.get("url")])

    source_rows, price_rows = [], []
    for item in new_items:
        sku = item["sku"]
        in_stock = stock.get(item.get("url"), True)
        flag = "" if in_stock else "  [OUT OF STOCK]"
        is_used = is_old_listing_name(item.get("name", ""))
        print(f"- [MỚI] {sku}: {item['price']:,} VND{flag}  ({item['name'][:50]})")
        source_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "url": item.get("url") or fallback_url, "is_used": is_used}
        )
        price_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "price": item["price"], "in_stock": in_stock, "is_used": is_used}
        )

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


def _run_category(client, args) -> int:
    """Luồng MỚI (mọi category ngoài laptop): cào TOÀN BỘ trang danh mục, đối chiếu SKU với TNC —
    khớp thì ghi giá (chỉ SKU mới); không khớp (không suy được SKU, hoặc TNC chưa bán) thì lưu vào
    `missing_products` để xem lại tay."""
    category = args.category
    category_label = category.capitalize()

    tracked = fetch_catalog_skus(client, category_label)
    existing = fetch_existing_source_skus(client, COMPETITOR)

    urls = resolve_urls("anphat", category)
    print(
        f"Discovering '{COMPETITOR}' — category '{category}' qua {len(urls)} trang danh mục "
        f"(KHÔNG qua tìm kiếm){' (dry run)' if args.dry else ''}...\n"
    )
    if not urls:
        print(f"  ⚠️  Chưa cấu hình paths.anphat cho category '{category}' trong sources.yaml — bỏ qua.")
        return 0

    found = discover_category_full(category)
    print(f"{len(found)} sản phẩm tìm thấy trên (các) trang danh mục.\n")

    if not tracked:
        print(
            f"  ⚠️  Catalog TNC chưa có SKU nào trong danh mục '{category_label}' — MỌI sản phẩm "
            f"tìm được sẽ được coi là 'chưa khớp' và lưu vào missing_products.\n"
        )

    fallback_url = urls[0]

    matched_new: list[dict] = []
    matched_known: list[dict] = []
    missing_rows: list[dict] = []
    resolved_urls: list[str] = []

    for item in found:
        sku = derive_sku(item["name"], item.get("url"), category_label)
        is_used = is_old_listing_name(item.get("name", ""))
        if sku and sku in tracked:
            resolved_urls.append(item["url"])  # từng "thiếu" (nếu có) nay đã khớp -> resolve
            row = {**item, "sku": sku, "is_used": is_used}
            (matched_known if sku in existing else matched_new).append(row)
        else:
            reason = "Không suy được SKU" if not sku else "TNC chưa bán sản phẩm này"
            missing_rows.append({
                "competitor": COMPETITOR,
                "category": category_label,
                "brand": brand_of(item["name"]) or None,
                "name": item["name"],
                "price": item.get("price"),
                "url": item.get("url") or "",
                "is_used": is_used,
                "reason": reason,
            })

    # Chỉ kiểm tồn kho (tốn 1 lượt tải trang mỗi sản phẩm) cho SKU MỚI KHỚP — SKU cũ daily sync tự lo,
    # sản phẩm không khớp (missing_products) không cần biết tồn kho.
    stock = check_stock([m["url"] for m in matched_new if m.get("url")])

    source_rows, price_rows = [], []
    for item in matched_new:
        sku = item["sku"]
        in_stock = stock.get(item.get("url"), True)
        flag = "" if in_stock else "  [OUT OF STOCK]"
        print(f"- [MỚI][KHỚP] {sku}: {item['price']:,} VND{flag}  ({item['name'][:55]})")
        source_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "url": item.get("url") or fallback_url, "is_used": item["is_used"]}
        )
        price_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "price": item["price"], "in_stock": in_stock, "is_used": item["is_used"]}
        )

    for item in matched_known:
        source_rows.append(
            {"product_sku": item["sku"], "competitor": COMPETITOR, "url": item.get("url") or fallback_url}
        )

    if args.dry:
        print(
            f"\n[DRY] {len(matched_new)} SKU MỚI khớp TNC, {len(matched_known)} SKU cũ (chỉ refresh URL), "
            f"{len(missing_rows)} sản phẩm KHÔNG khớp (sẽ lưu vào missing_products nếu chạy thật)."
        )
        for row in missing_rows[:15]:
            price_s = f"{row['price']:,} VND" if row.get("price") else "?"
            print(f"  - [MISSING] ({row['reason']}) {row['name'][:60]} — {price_s}")
        if len(missing_rows) > 15:
            print(f"  ... và {len(missing_rows) - 15} sản phẩm không khớp khác.")
        return 0

    if source_rows:
        upsert_sources(client, source_rows)
    if price_rows:
        insert_prices(client, price_rows)
    if missing_rows:
        upsert_missing_products(client, missing_rows)
    if resolved_urls:
        resolve_missing_products(client, COMPETITOR, resolved_urls)

    print(
        f"\nDone. {len(matched_new)} SKU MỚI được ghi giá, {len(matched_known)} SKU cũ chỉ refresh "
        f"URL, {len(missing_rows)} sản phẩm KHÔNG khớp được lưu vào missing_products "
        f"({len(resolved_urls)} sản phẩm trước đây thiếu nay đã khớp -> đánh dấu resolved)."
    )
    return 0


def _run_all(client, dry: bool) -> int:
    """Cào TOÀN BỘ An Phát trong một lần chạy: mọi brand laptop (qua tìm kiếm, luồng cũ) + mọi
    category đang bật khác (qua trang danh mục thật, luồng mới). Chậm hơn nhiều so với chạy từng
    --category một (mở/đóng browser cho mỗi brand/category) — cân nhắc --dry trước để coi thử log,
    hoặc chạy song song qua CI matrix (xem scrape.yml) nếu cần nhanh. Một brand/category lỗi
    KHÔNG làm dừng cả lượt chạy — in lỗi rồi chạy tiếp cái kế.
    """
    n_ok, n_fail = 0, 0

    print(f"=== [1/2] Laptop — {len(BRANDS)} brand ===\n")
    for brand in BRANDS:
        print(f"--- laptop/{brand} ---")
        try:
            _run_laptop(client, Namespace(brand=brand, dry=dry))
            n_ok += 1
        except Exception as e:
            print(f"  ❌ Lỗi khi cào laptop/{brand}: {e}")
            n_fail += 1
        print()

    cats = sorted(categories())
    print(f"=== [2/2] {len(cats)} category khác ===\n")
    for cat in cats:
        print(f"--- category/{cat} ---")
        try:
            _run_category(client, Namespace(category=cat, dry=dry))
            n_ok += 1
        except Exception as e:
            print(f"  ❌ Lỗi khi cào category/{cat}: {e}")
            n_fail += 1
        print()

    print(f"=== Hoàn tất --all: {n_ok} pass thành công, {n_fail} pass lỗi ===")
    return 0 if n_fail == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Discover An Phát: laptop theo brand (tìm kiếm, luồng cũ); các category khác theo "
            "TRANG DANH MỤC thật (không qua tìm kiếm) + lưu sản phẩm không khớp SKU vào "
            "missing_products (luồng mới)."
        )
    )
    ap.add_argument("--brand", default="dell", help="brand cho laptop (dell, hp, ...) — chỉ dùng với --category laptop")
    ap.add_argument(
        "--category", default="laptop", choices=["laptop", *sorted(categories())],
        help="category cần cào",
    )
    ap.add_argument("--dry", action="store_true", help="in ra, không ghi vào DB")
    ap.add_argument(
        "--all", action="store_true",
        help="Cào TOÀN BỘ: mọi brand laptop + mọi category đang bật, trong một lần chạy (bỏ qua --brand/--category)",
    )
    args = ap.parse_args()

    client = get_client()
    ensure_competitor(client, COMPETITOR)

    if args.all:
        return _run_all(client, args.dry)

    if args.category == "laptop":
        return _run_laptop(client, args)
    return _run_category(client, args)


if __name__ == "__main__":
    sys.exit(main())