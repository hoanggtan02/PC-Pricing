"""Scraper khám phá dữ liệu bằng tìm kiếm cho HACOM / Hà Nội Computer (hacom.vn) (Playwright).

HACOM là một ứng dụng Next.js — kết quả tìm kiếm được render bằng JavaScript (HTML thô không có
sản phẩm nào), nên ta phải điều khiển một trình duyệt headless. Các class CSS của nó là các
utility Tailwind đã hash (không ổn định), nên ta parse theo CẤU TRÚC: mỗi sản phẩm là một
<a href="/laptop-dell-..."> có <h3 title> là tên; giá hiện tại được đọc từ nội dung text của
thẻ, lấy giá KHÔNG bị gạch ngang.

Chỉ khớp: chỉ ghi lại giá cho các SKU đã có sẵn trong `products` (danh mục của TNC).

MODE A (weekend discovery) — CHỈ GHI GIÁ CHO SKU MỚI: kịch bản này chạy cuối tuần để tìm sản
phẩm MỚI, không phải để cào lại giá của mọi sản phẩm đã biết — giá đó Mode B (sync_prices, chạy
hàng ngày) đã cào đều đặn rồi. Vì vậy SKU nào ĐÃ có source ở competitor này (fetch_existing_source_skus)
thì chỉ được refresh URL (upsert_sources), KHÔNG check_stock lại và KHÔNG ghi thêm dòng
price_history trùng lặp — điều này còn giúp job chạy nhanh hơn vì bỏ được bước check_stock
(mỗi lần tải một trang sản phẩm) cho toàn bộ sku cũ.

Cách dùng:
    python -m scraper.discover_hacom --dry
    python -m scraper.discover_hacom
"""

from __future__ import annotations

import argparse
import re
import sys

from playwright.sync_api import sync_playwright

from .browser import goto_with_retry
from .config import categories, name_exclude_re, name_match_re, resolve_url
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

COMPETITOR = "Hà Nội Computer"
BASE_URL = "https://hacom.vn"
BRANDS = {
    "dell": "https://hacom.vn/tim?q=laptop+dell&scat_id=141",
    "lenovo": "https://hacom.vn/tim?q=Laptop+Lenovo&scat_id=149",
    "apple": "https://hacom.vn/tim?q=Macbook&scat_id=145",
    "hp": "https://hacom.vn/tim?q=Laptop+HP&scat_id=148",
    "asus": "https://hacom.vn/tim?q=Laptop+Asus&scat_id=142",
    "acer": "https://hacom.vn/tim?q=Laptop+Acer&scat_id=144",
    "msi": "https://hacom.vn/tim?q=Laptop+MSI&scat_id=540",
    "gigabyte": "https://hacom.vn/tim?q=Laptop+Gigabyte&scat_id=2480",
}

# Laptop: thẻ sản phẩm là anchor /laptop-* (brand áp bằng khớp SKU). Danh mục khác chờ h3[title]
# (tiêu đề sản phẩm — phần tử hiển thị được), giữ lại theo name_match ở phía Python.
# Lưu ý: KHÔNG chờ 'a[href^="/"]' — phần tử khớp đầu tiên có thể ẩn (skip-link/menu), khiến
# wait_for_selector (mặc định chờ visible) timeout dù trang đã render đầy đủ.
CARD_SELECTOR = 'a[href^="/laptop"]'
CARD_SELECTOR_CAT = "h3[title]"


def _digits_to_int(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def discover(brand: str = "dell", category: str = "laptop") -> list[dict]:
    """Trả về [{name, price, url}] cho các sản phẩm trên trang tìm kiếm đã render.

    Laptop (mặc định) tìm theo brand qua URL cũ và giữ các anchor /laptop-*. Các danh mục khác
    chạy theo danh mục: tìm cả danh mục, giữ mọi anchor sản phẩm, lọc theo name_match ở Python.
    """
    is_laptop = category == "laptop"
    excl_re = name_exclude_re(category)
    if is_laptop:
        search_url, card_sel, name_re = BRANDS[brand], CARD_SELECTOR, None
    else:
        search_url, card_sel = resolve_url("hacom", category), CARD_SELECTOR_CAT
        name_re = name_match_re(category)
    if not search_url:
        return []
    results: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            # BẮT BUỘC phải dùng viewport desktop đầy đủ — với viewport headless mặc định nhỏ,
            # lưới responsive của HACOM chỉ render một vài thẻ.
            viewport={"width": 1920, "height": 1080},
        )
        if not goto_with_retry(page, search_url, card_sel, label=COMPETITOR):
            browser.close()
            return results

        # HACOM (bản Next.js mới) phân trang kết quả bằng NÚT "Xem thêm N kết quả" — cuộn KHÔNG tự
        # nạp thêm. Phải bấm đúng nút đó (chứa chữ "kết quả") lặp lại tới khi nó biến mất. Lưu ý:
        # còn ~90 thẻ <a>"Xem thêm" khác ở sidebar là bộ lọc danh mục — KHÔNG bấm (lọc theo "kết quả").
        # Mỗi lần bấm chỉ nạp ~12 sản phẩm; một tìm kiếm rộng ("pc") có ~500 kết quả → cần ~40 lần
        # bấm để nạp HẾT. range(60) chỉ là TRẦN an toàn — vòng lặp thoát sớm khi:
        #   (a) nút "kết quả" biến mất (đã nạp hết), HOẶC
        #   (b) số thẻ KHÔNG tăng sau một lần bấm (nút kẹt/không nạp thêm) → tránh bấm nút chết mãi.
        prev_count = -1
        for _ in range(60):
            btn = page.query_selector("xpath=//button[contains(., 'kết quả')]")
            if not btn:
                break
            count = page.eval_on_selector_all("h3[title]", "(els)=>els.length")
            if count == prev_count:   # lần bấm trước không thêm thẻ nào → dừng
                break
            prev_count = count
            try:
                btn.scroll_into_view_if_needed()
                btn.click()
                page.wait_for_timeout(1800)
            except Exception:
                # nút có thể bị re-render giữa chừng; thử lại 1 nhịp thay vì bỏ cuộc.
                page.wait_for_timeout(1000)
        # Cuộn thêm vài nhịp để chắc chắn lưới responsive render nốt các thẻ vừa nạp.
        for _ in range(3):
            page.mouse.wheel(0, 6000)
            page.wait_for_timeout(800)

        # Duyệt qua các h3 title (một cho mỗi sản phẩm) — tránh vấn đề anchor trùng lặp khi
        # link ảnh/tiêu đề/giá đều trỏ đến cùng một sản phẩm. Leo lên thẻ cha để lấy URL + giá.
        # `hrefPrefix` giới hạn anchor sản phẩm (laptop giữ /laptop; danh mục khác nhận mọi anchor).
        items = page.eval_on_selector_all(
            'h3[title]',
            """
            (h3s, opts) => {
              const [hrefPrefix, isLaptop] = opts;
              const out = [];
              const seen = new Set();
              const sel = 'a[href^="' + hrefPrefix + '"]';
              for (const h3 of h3s) {
                const name = h3.getAttribute('title') || '';
                if (!name) continue;
                // Laptop giữ nguyên bộ lọc tên cũ; danh mục khác lọc ở Python (name_match).
                if (isLaptop && !/^(laptop|macbook)/i.test(name)) continue;
                // leo lên vài cấp đến thẻ cha chứa cả link lẫn giá
                let card = h3;
                for (let i = 0; i < 5 && card.parentElement; i++) {
                  card = card.parentElement;
                  if (card.querySelector(sel) && card.querySelector('span')) break;
                }
                const a = card.querySelector(sel);
                const href = a ? a.getAttribute('href') : null;
                if (!href || seen.has(href)) continue;
                // giá hiện tại = span đầu tiên có dạng giá mà KHÔNG bị gạch ngang (line-through).
                // Tình trạng hết hàng KHÔNG có trên thẻ danh sách → kiểm ở trang sản phẩm (check_stock).
                let price = '';
                for (const s of card.querySelectorAll('span')) {
                  const txt = (s.textContent || '').trim();
                  if (!/[0-9]\\.[0-9]{3}\\.[0-9]{3}/.test(txt)) continue;
                  if ((s.getAttribute('class') || '').includes('line-through')) continue;
                  price = txt;
                  break;
                }
                if (!price) continue;
                seen.add(href);
                out.push({ name, price, url: href });
              }
              return out;
            }
            """,
            ["/laptop" if is_laptop else "/", is_laptop],
        )
        for it in items:
            name = it["name"]
            # Laptop: JS đã lọc theo /laptop. Danh mục: giữ tên khớp name_match của danh mục.
            if (excl_re and excl_re.search(name)) or (not is_laptop and not (name_re and name_re.search(name))):
                continue
            price = _digits_to_int(it["price"])
            href = it["url"]
            url = (BASE_URL + href) if href and href.startswith("/") else href
            if price:
                results.append({"name": name, "price": price, "url": url})
        browser.close()
    return results


def check_stock(urls: list[str]) -> dict[str, bool]:
    """Tình trạng còn/hết hàng cho từng URL sản phẩm HACOM. Tín hiệu KHÔNG có trên thẻ danh sách —
    chỉ ở TRANG SẢN PHẨM: khi hết hàng, HACOM đổi nút mua thành "ĐĂNG KÝ MUA / Nhận thông báo khi có
    hàng". Vậy hết hàng nếu trang chứa "đăng ký mua" (hoặc "liên hệ"/"hết hàng"). Lỗi -> coi còn hàng.
    Chỉ gọi cho các SKU ĐÃ KHỚP (mỗi cái tải một trang) để không tốn request thừa."""
    status: dict[str, bool] = {}
    if not urls:
        return status
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        for url in urls:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1200)
                # Tín hiệu CỤ THỂ: hết hàng khi có NÚT "ĐĂNG KÝ MUA" (Nhận thông báo khi có hàng).
                # KHÔNG dò "liên hệ" trên toàn trang — cụm đó xuất hiện ở footer CSKH của MỌI trang
                # ("Quý khách có thể liên hệ tổng đài...") nên gây báo hết hàng nhầm.
                oos = page.evaluate(
                    """() => {
                        const els = Array.from(document.querySelectorAll('button, a'));
                        return els.some(e => /đăng ký mua|nhận thông báo khi có hàng/i
                            .test((e.textContent || '')));
                    }"""
                )
                status[url] = not oos
            except Exception:
                status[url] = True  # lỗi -> không gắn cờ sai là hết hàng
        browser.close()
    return status



def main() -> int:
    ap = argparse.ArgumentParser(description="Discover HACOM prices by brand and category.")
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

    # SKU nào đã có source ở HACOM -> đã được Mode B (daily sync) theo dõi giá. Chỉ ghi giá cho
    # SKU MỚI (chưa có trong tập này); sku cũ chỉ refresh URL, KHÔNG check_stock lại (tốn thời gian).
    existing = fetch_existing_source_skus(client, COMPETITOR)

    print(
        f"Discovering '{COMPETITOR}' — {args.category}/{args.brand}"
        f"{' (dry run)' if args.dry else ''}...\n"
    )
    found = discover(args.brand, args.category)
    print(
        f"{len(found)} unique product(s) parsed; matching against {len(tracked)} TNC SKU(s), "
        f"{len(existing)} đã có source (daily sync lo giá).\n"
    )

    category_label = args.category.capitalize()
    fallback_url = BRANDS[args.brand] if args.category == "laptop" else None

    # Chỉ giữ các sản phẩm ĐÃ KHỚP SKU.
    matched = []
    for item in found:
        sku = derive_sku(item["name"], item.get("url"), category_label)
        if sku is None or sku not in tracked:
            continue
        matched.append({**item, "sku": sku})
    new_items = [m for m in matched if m["sku"] not in existing]
    known_items = [m for m in matched if m["sku"] in existing]

    # Chỉ kiểm tồn kho (tín hiệu OOS chỉ có ở trang sản phẩm — nút "ĐĂNG KÝ MUA") cho SKU MỚI —
    # SKU cũ daily sync tự lo, khỏi tải thêm N trang sản phẩm không cần thiết.
    stock = check_stock([m["url"] for m in new_items if m.get("url")])

    source_rows, price_rows = [], []
    for item in new_items:
        sku = item["sku"]
        in_stock = stock.get(item.get("url"), True)
        flag = "" if in_stock else "  [OUT OF STOCK]"
        print(f"- [MỚI] {sku}: {item['price']:,} VND{flag}  ({item['name'][:55]})")
        source_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "url": item.get("url") or fallback_url}
        )
        price_rows.append({
            "product_sku": sku, "competitor": COMPETITOR, "price": item["price"],
            "in_stock": in_stock,
        })

    # SKU cũ: chỉ refresh URL, KHÔNG ghi giá/tồn kho lại.
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