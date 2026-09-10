"""Scraper khám phá dữ liệu bằng tìm kiếm cho Memoryzone (memoryzone.com.vn) (Playwright, không cần proxy).

Memoryzone truy cập trực tiếp được. Giống GearVN, trang này chuyên về linh kiện/PC và ít/không
bán laptop Dell — tìm kiếm "laptop dell" trên trang này chủ yếu ra phụ kiện (balo, túi, v.v.).
Ta lọc theo tên để lấy đúng laptop và ghi lại bất cứ thứ gì xuất hiện (thường là không có gì, và
điều đó vẫn ổn).

QUAN TRỌNG — HAI THEME KHÁC NHAU trên cùng site (phát hiện 2026-08 từ bug thật: category
"software" timeout hàng loạt ở PRICE_SELECTOR cũ):
  1. Trang TÌM KIẾM (dùng cho laptop, /search?query=...) — markup cũ, đã xác nhận:
         card  : (không có selector card riêng, quét ngược từ phần tử giá)
         price : .ae-price--primary
  2. Trang CATEGORY TĨNH (dùng cho mọi category khác qua `paths.memoryzone`, ví dụ
     /phan-mem-ban-quyen) — theme Bizweb/Sapo (bizweb.dktcdn.net), markup HOÀN TOÀN KHÁC, xác
     nhận từ HTML thật của https://memoryzone.com.vn/phan-mem-ban-quyen:
         card  : .item_product_main
         name  : .product-name a
         price : .price-box .price      (giá hiện tại; .compare-price là giá gốc gạch ngang)
     .ae-price--primary KHÔNG TỒN TẠI trên các trang này — dùng nhầm selector khiến
     goto_with_retry() chờ đủ timeout rồi bỏ cuộc cho MỌI category không phải laptop, không phải
     lỗi mạng/chặn bot. Hai nhánh selector dưới đây tách riêng cho từng loại trang.

CẬP NHẬT (2026-09) — CÁC CATEGORY KHÁC LAPTOP: CÀO TOÀN BỘ DANH MỤC + LƯU SẢN PHẨM KHÔNG KHỚP,
theo đúng mẫu discover_anphat.py / discover_phongvu.py / discover_gearvn.py. `_discover_category()`
vốn ĐÃ cào TOÀN BỘ trang danh mục tĩnh (không lọc theo "đã khớp SKU nào chưa" — chỉ lọc
name_match/name_exclude), nên nó đóng đúng vai trò `discover_category_full()` như các scraper kia.
`_run_category()` mới đối chiếu SKU với catalog TNC:
  - SKU khớp catalog TNC (`tracked`)     -> ghi source/price như cũ (chỉ SKU MỚI mới ghi giá).
  - SKU không suy ra được HOẶC không có trong TNC -> upsert vào bảng `missing_products` (xem
    scraper/db.py: upsert_missing_products / resolve_missing_products) để xem lại tay.
  - Một URL trước đây từng nằm trong `missing_products` mà giờ ĐÃ khớp (TNC vừa bổ sung đúng SKU
    đó) sẽ được đánh dấu resolved=true qua `resolve_missing_products()`.

Nhánh LAPTOP (`--category laptop`, mặc định) GIỮ NGUYÊN luồng CŨ (match-only qua trang tìm kiếm,
không đưa vào missing_products) — không đổi để không ảnh hưởng scrape.yml (leg `kind: laptop`).

Chỉ khớp (LAPTOP): chỉ ghi lại giá cho các SKU đã có sẵn trong `products` (danh mục của TNC).

MODE A (weekend discovery) — CHỈ GHI GIÁ CHO SKU MỚI: kịch bản này chạy cuối tuần để tìm sản
phẩm MỚI, không phải để cào lại giá của mọi sản phẩm đã biết — giá đó Mode B (sync_prices, chạy
hàng ngày) đã cào đều đặn rồi. Vì vậy SKU nào ĐÃ có source ở competitor này (fetch_existing_source_skus)
thì chỉ được refresh URL (upsert_sources), KHÔNG ghi thêm dòng price_history trùng lặp.

Cách dùng:
    python -m scraper.discover_memoryzone --dry
    python -m scraper.discover_memoryzone
    python -m scraper.discover_memoryzone --category software --dry
    python -m scraper.discover_memoryzone --category software
    python -m scraper.discover_memoryzone --all --dry
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
from .stock import is_in_stock as stock_is_in
from .sku import derive_sku

COMPETITOR = "Memoryzone"
BASE_URL = "https://memoryzone.com.vn"
BRANDS = {
    "dell": "https://memoryzone.com.vn/search?query=laptop%20dell",
    "lenovo": "https://memoryzone.com.vn/search?query=laptop%20lenovo",
    "apple": "https://memoryzone.com.vn/search?query=macbook",
    "hp": "https://memoryzone.com.vn/search?query=laptop%20hp",
    "asus": "https://memoryzone.com.vn/search?query=laptop%20asus",
    "acer": "https://memoryzone.com.vn/search?query=laptop%20acer",
    "msi": "https://memoryzone.com.vn/search?query=laptop%20msi",
    "gigabyte": "https://memoryzone.com.vn/laptop-gigabyte",
}

# Trang TÌM KIẾM (laptop) — markup cũ, đã xác nhận hoạt động, GIỮ NGUYÊN.
PRICE_SELECTOR = ".ae-price--primary"

# Trang CATEGORY TĨNH (mọi category khác qua paths.memoryzone) — theme Bizweb/Sapo, xác nhận từ
# HTML thật của /phan-mem-ban-quyen (xem docstring đầu file). KHÔNG dùng chung với PRICE_SELECTOR.
CATEGORY_CARD_SELECTOR = ".item_product_main"
CATEGORY_NAME_SELECTOR = ".product-name a"
CATEGORY_PRICE_SELECTOR = ".price-box .price"
CATEGORY_PAGE_CAP = 30  # chốt an toàn cho phân trang ?page=N; dừng sớm khi trang không thêm gì mới.


def _digits_to_int(text: str) -> int | None:
    m = re.search(r"\d{1,3}(?:\.\d{3})+", text or "")
    return int(m.group(0).replace(".", "")) if m else None


def _discover_laptop(page, brand: str) -> list[dict]:
    """Trang tìm kiếm laptop — logic CŨ, không đổi (đã xác nhận hoạt động)."""
    search_url = BRANDS[brand]
    if not goto_with_retry(page, search_url, PRICE_SELECTOR, label=COMPETITOR):
        return []

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
        (prices) => {
          const out = [];
          const seen = new Set();
          for (const p of prices) {
            let card = p;
            for (let i = 0; i < 6 && card.parentElement; i++) {
              card = card.parentElement;
              if (card.querySelector('a[href]') && card.querySelector('h3')) break;
            }
            const a = card.querySelector('a[href]');
            const h3 = card.querySelector('h3');
            if (!a || !h3) continue;
            const href = (a.getAttribute('href') || '').split('?')[0];
            if (!href || seen.has(href)) continue;
            const name = h3.innerText.trim();
            if (!/^(laptop|macbook)/i.test(name)) continue;
            seen.add(href);
            out.push({ name, price: p.innerText.trim(), url: href, card_text: (card.textContent || '') });
          }
          return out;
        }
        """,
    )
    results: list[dict] = []
    for it in items:
        price = _digits_to_int(it["price"])
        href = it["url"]
        url = (BASE_URL + href) if href and href.startswith("/") else href
        if price:
            in_stock = stock_is_in(it.get("card_text"))
            results.append({"name": it["name"], "price": price, "url": url, "in_stock": in_stock})
    return results


def _discover_category(page, category: str) -> list[dict]:
    """Trang category tĩnh (theme Bizweb/Sapo) — markup KHÁC hẳn trang tìm kiếm, xem docstring
    đầu file. Phân trang qua ?page=N (kiểu Bizweb phổ biến); dừng khi trang không thêm sản phẩm
    mới nào, hoặc chạm CATEGORY_PAGE_CAP.

    QUAN TRỌNG: hàm này cào TOÀN BỘ sản phẩm của danh mục — KHÔNG lọc theo SKU đã khớp catalog
    TNC hay chưa (việc đó do caller — `_run_category()` — tự đối chiếu sau). Đây chính là vai trò
    tương đương `discover_category_full()` bên discover_anphat.py.
    """
    search_url = resolve_url("memoryzone", category)
    if not search_url:
        return []
    excl_re = name_exclude_re(category)
    name_re = name_match_re(category)

    results: list[dict] = []
    seen_urls: set[str] = set()
    for page_num in range(1, CATEGORY_PAGE_CAP + 1):
        if page_num == 1:
            if not goto_with_retry(page, search_url, CATEGORY_CARD_SELECTOR, label=COMPETITOR):
                break
        else:
            joiner = "&" if "?" in search_url else "?"
            page_url = f"{search_url}{joiner}page={page_num}"
            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector(CATEGORY_CARD_SELECTOR, timeout=10000)
            except Exception:
                break  # trang chậm/lỗi/hết trang — dừng, giữ lại những gì đã thu thập được

        items = page.eval_on_selector_all(
            CATEGORY_CARD_SELECTOR,
            """
            (cards) => {
                const out = [];
                for (const card of cards) {
                    const nameEl = card.querySelector('.product-name a');
                    const priceEl = card.querySelector('.price-box .price');
                    if (!nameEl || !priceEl) continue;
                    const name = nameEl.innerText.trim();
                    const href = nameEl.getAttribute('href') || '';
                    const price = priceEl.innerText.trim();
                    out.push({ name, price, url: href, card_text: (card.innerText || '') });
                }
                return out;
            }
            """,
        )

        new_on_page = 0
        for it in items:
            name = it["name"]
            if excl_re and excl_re.search(name):
                continue
            if name_re and not name_re.search(name):
                continue
            price = _digits_to_int(it["price"])
            href = it["url"]
            url = (BASE_URL + href) if href and href.startswith("/") else href
            if not price or not url or url in seen_urls:
                continue
            seen_urls.add(url)
            new_on_page += 1
            in_stock = stock_is_in(it.get("card_text"))
            results.append({"name": name, "price": price, "url": url, "in_stock": in_stock})

        if new_on_page == 0:  # trang cuối / không phân trang
            break
    return results


def discover(brand: str = "dell", category: str = "laptop") -> list[dict]:
    """Trả về [{name, price, url, in_stock}] cho các sản phẩm tìm được.

    Laptop (mặc định) dùng URL per-brand + lọc /^laptop|macbook/ trên trang TÌM KIẾM. Các danh
    mục khác dùng URL category TĨNH của `paths.memoryzone` — theme khác hẳn, xem docstring đầu
    file — nên dùng hàm trích xuất riêng (_discover_category), vốn cào TOÀN BỘ danh mục.
    """
    is_laptop = category == "laptop"
    with browser_page(use_proxy=False) as page:
        if is_laptop:
            return _discover_laptop(page, brand)
        return _discover_category(page, category)


def _run_laptop(client, args) -> int:
    """Luồng CŨ (match-only) cho laptop — GIỮ NGUYÊN hành vi hiện tại, không đưa vào
    missing_products (giống cách discover_anphat.py/discover_phongvu.py/discover_gearvn.py giữ
    nguyên nhánh laptop của chúng)."""
    tracked = fetch_catalog_skus(client, "Laptop")
    if not tracked:
        print("No tracked products yet. Run the TNC scraper first to populate the catalog.")
        return 0

    # SKU nào đã có source ở Memoryzone -> đã được Mode B (daily sync) theo dõi giá. Chỉ ghi giá
    # cho SKU MỚI (chưa có trong tập này); sku cũ chỉ refresh URL.
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
    source_rows, price_rows = [], []
    new_count = 0
    for item in found:
        sku = derive_sku(item["name"], item.get("url"), "Laptop")
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
        # Chỉ ghi giá cho SKU CHƯA từng có source ở competitor này (sản phẩm mới phát hiện).
        if is_new:
            price_rows.append({
                "product_sku": sku, "competitor": COMPETITOR, "price": item["price"],
                "in_stock": item.get("in_stock", True), "is_used": is_used,
            })
            new_count += 1

    if not args.dry:
        upsert_sources(client, source_rows)
        insert_prices(client, price_rows)

    print(
        f"\nDone. {new_count} SKU MỚI được ghi giá trên {COMPETITOR} "
        f"({len(source_rows) - new_count} SKU cũ chỉ refresh URL, không ghi giá lại)."
    )
    return 0


def _run_category(client, args) -> int:
    """Luồng MỚI (mọi category ngoài laptop): cào TOÀN BỘ trang danh mục (`discover()` -> nhánh
    `_discover_category()` đã tự làm việc này), đối chiếu SKU với TNC — khớp thì ghi giá (chỉ SKU
    mới); không khớp (không suy được SKU, hoặc TNC chưa bán) thì lưu vào `missing_products` để
    xem lại tay. Mẫu y hệt `_run_category()` trong discover_anphat.py / discover_phongvu.py /
    discover_gearvn.py."""
    category = args.category
    category_label = category.capitalize()

    tracked = fetch_catalog_skus(client, category_label)
    existing = fetch_existing_source_skus(client, COMPETITOR)

    list_url = resolve_url("memoryzone", category)
    print(
        f"Discovering '{COMPETITOR}' — category '{category}' qua trang danh mục "
        f"(KHÔNG lọc theo catalog TNC trước){' (dry run)' if args.dry else ''}...\n"
    )
    if not list_url:
        print(f"  ⚠️  Chưa cấu hình paths.memoryzone cho category '{category}' trong sources.yaml — bỏ qua.")
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

    source_rows, price_rows = [], []
    for item in matched_new:
        sku = item["sku"]
        in_stock = item.get("in_stock", True)
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
    """Cào TOÀN BỘ Memoryzone trong một lần chạy: mọi brand laptop (luồng cũ, match-only) + mọi
    category đang bật khác (luồng mới, có missing_products). Chậm hơn nhiều so với chạy từng
    --category một (mở/đóng browser cho mỗi brand/category) — cân nhắc --dry trước, hoặc chạy
    song song qua CI matrix (xem scrape.yml) nếu cần nhanh. Một brand/category lỗi KHÔNG làm dừng
    cả lượt chạy — in lỗi rồi chạy tiếp cái kế. Mẫu y hệt `_run_all()` trong discover_anphat.py /
    discover_phongvu.py / discover_gearvn.py.
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
            "Discover Memoryzone: laptop theo brand (tìm kiếm, luồng cũ, match-only); các "
            "category khác qua TRANG DANH MỤC TĨNH (cào toàn bộ) + lưu sản phẩm không khớp SKU "
            "vào missing_products (luồng mới)."
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