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

Chỉ khớp (LAPTOP): chỉ ghi lại giá cho các SKU đã có sẵn trong `products` (danh mục của TNC).

MODE A (weekend discovery) — CHỈ GHI GIÁ CHO SKU MỚI: kịch bản này chạy cuối tuần để tìm sản
phẩm MỚI, không phải để cào lại giá của mọi sản phẩm đã biết — giá đó Mode B (sync_prices, chạy
hàng ngày) đã cào đều đặn rồi. Vì vậy SKU nào ĐÃ có source ở competitor này (fetch_existing_source_skus)
thì chỉ được refresh URL (upsert_sources), KHÔNG check_stock lại và KHÔNG ghi thêm dòng
price_history trùng lặp — điều này còn giúp job chạy nhanh hơn vì bỏ được bước check_stock
(mỗi lần tải một trang sản phẩm) cho toàn bộ sku cũ.

CẬP NHẬT (2026-09) — CÁC CATEGORY KHÁC LAPTOP: CÀO TOÀN BỘ DANH MỤC + LƯU SẢN PHẨM KHÔNG KHỚP,
theo đúng mẫu discover_anphat.py / discover_phongvu.py. `discover()` ở nhánh category vốn ĐÃ cào
TOÀN BỘ trang danh mục (không lọc theo "đã khớp SKU nào chưa" — chỉ lọc name_match/name_exclude),
nên đóng đúng vai trò `discover_category_full()` như An Phát/Phong Vũ. `_run_category()` mới đối
chiếu SKU với catalog TNC:
  - SKU khớp catalog TNC (`tracked`)     -> ghi source/price như cũ (chỉ SKU MỚI mới ghi giá,
    kèm check_stock() như luồng cũ).
  - SKU không suy ra được HOẶC không có trong TNC -> upsert vào bảng `missing_products` (xem
    scraper/db.py: upsert_missing_products / resolve_missing_products) để xem lại tay.
  - Một URL trước đây từng nằm trong `missing_products` mà giờ ĐÃ khớp (TNC vừa bổ sung đúng SKU
    đó) sẽ được đánh dấu resolved=true qua `resolve_missing_products()`.

Nhánh LAPTOP (`--category laptop`, mặc định) GIỮ NGUYÊN luồng CŨ (match-only, không đưa vào
missing_products) — không đổi để không ảnh hưởng scrape.yml (leg `kind: laptop`).

Cách dùng:
    python -m scraper.discover_gearvn --dry
    python -m scraper.discover_gearvn
    python -m scraper.discover_gearvn --category ram --dry
    python -m scraper.discover_gearvn --category ram
    python -m scraper.discover_gearvn --all --dry
"""

from __future__ import annotations

import argparse
import re
import sys
from argparse import Namespace

from .brand import brand_of
from .browser import browser_page, goto_with_retry
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

    QUAN TRỌNG (nhánh category): hàm này cào TOÀN BỘ sản phẩm của danh mục — KHÔNG lọc theo SKU
    đã khớp catalog TNC hay chưa (việc đó do caller — `_run_category()` — tự đối chiếu sau). Đây
    chính là vai trò tương đương `discover_category_full()` bên discover_anphat.py.

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


def _run_laptop(client, args) -> int:
    """Luồng CŨ (match-only) cho laptop — GIỮ NGUYÊN hành vi hiện tại, không đưa vào
    missing_products (giống cách discover_anphat.py/discover_phongvu.py giữ nguyên nhánh laptop
    của chúng)."""
    tracked = fetch_catalog_skus(client, "Laptop")
    if not tracked:
        print("No tracked products yet. Run the TNC scraper first to populate the catalog.")
        return 0

    # SKU nào đã có source ở GearVN -> đã được Mode B (daily sync) theo dõi giá. Chỉ ghi giá cho
    # SKU MỚI (chưa có trong tập này); sku cũ chỉ refresh URL, KHÔNG check_stock lại (tốn thời gian).
    existing = fetch_existing_source_skus(client, COMPETITOR)

    print(
        f"Discovering '{COMPETITOR}' — laptop/{args.brand}"
        f"{' (dry run)' if args.dry else ''}...\n"
    )
    found = discover(args.brand, "laptop")
    print(
        f"{len(found)} product(s) parsed; matching against {len(tracked)} TNC SKU(s), "
        f"{len(existing)} đã có source (daily sync lo giá).\n"
    )

    fallback_url = BRANDS[args.brand]
    # Chỉ giữ lại các sản phẩm đã khớp SKU.
    matched = [
        {**item, "sku": derive_sku(item["name"], item.get("url"), "Laptop")}
        for item in found
        if derive_sku(item["name"], item.get("url"), "Laptop") in tracked
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
        is_used = is_old_listing_name(item.get("name", ""))
        print(f"- [MỚI] {sku}: {item['price']:,} VND{flag}  ({item['name'][:50]})")
        source_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "url": item.get("url") or fallback_url, "is_used": is_used}
        )
        price_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "price": item["price"], "in_stock": in_stock, "is_used": is_used}
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


def _run_category(client, args) -> int:
    """Luồng MỚI (mọi category ngoài laptop): cào TOÀN BỘ trang danh mục (`discover()` đã tự làm
    việc này), đối chiếu SKU với TNC — khớp thì ghi giá (chỉ SKU mới, kèm check_stock() như luồng
    cũ); không khớp (không suy được SKU, hoặc TNC chưa bán) thì lưu vào `missing_products` để xem
    lại tay. Mẫu y hệt `_run_category()` trong discover_anphat.py / discover_phongvu.py."""
    category = args.category
    category_label = category.capitalize()

    tracked = fetch_catalog_skus(client, category_label)
    existing = fetch_existing_source_skus(client, COMPETITOR)

    list_url = resolve_url("gearvn", category)
    print(
        f"Discovering '{COMPETITOR}' — category '{category}' qua trang danh mục "
        f"(KHÔNG lọc theo catalog TNC trước){' (dry run)' if args.dry else ''}...\n"
    )
    if not list_url:
        print(f"  ⚠️  Chưa cấu hình paths.gearvn cho category '{category}' trong sources.yaml — bỏ qua.")
        return 0

    found = discover(category=category)
    print(f"{len(found)} sản phẩm tìm thấy trên trang danh mục.\n")

    if not tracked:
        print(
            f"  ⚠️  Catalog TNC chưa có SKU nào trong danh mục '{category_label}' — MỌI sản phẩm "
            f"tìm được sẽ được coi là 'chưa khớp' và lưu vào missing_products.\n"
        )

    fallback_url = list_url

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

    # Chỉ kiểm tồn kho (tốn 1 lượt tải trang mỗi sản phẩm) cho SKU MỚI KHỚP — SKU cũ daily sync tự
    # lo, sản phẩm không khớp (missing_products) không cần biết tồn kho.
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
    """Cào TOÀN BỘ GearVN trong một lần chạy: mọi brand laptop (luồng cũ, match-only) + mọi
    category đang bật khác (luồng mới, có missing_products). Chậm hơn nhiều so với chạy từng
    --category một (mở/đóng browser cho mỗi brand/category) — cân nhắc --dry trước, hoặc chạy
    song song qua CI matrix (xem scrape.yml) nếu cần nhanh. Một brand/category lỗi KHÔNG làm dừng
    cả lượt chạy — in lỗi rồi chạy tiếp cái kế. Mẫu y hệt `_run_all()` trong discover_anphat.py /
    discover_phongvu.py.
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
            "Discover GearVN: laptop theo brand (match-only, luồng cũ); các category khác qua "
            "TRANG DANH MỤC (cào toàn bộ) + lưu sản phẩm không khớp SKU vào missing_products "
            "(luồng mới)."
        )
    )
    ap.add_argument("--brand", default="dell", help="brand to scrape (e.g. dell, samsung)")
    ap.add_argument(
        "--category", default="laptop", choices=["laptop", *sorted(categories())],
        help="product category to scrape",
    )
    ap.add_argument("--dry", action="store_true", help="print results, don't write to the DB")
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