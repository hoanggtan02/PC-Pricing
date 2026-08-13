"""Scraper khám phá dữ liệu bằng tìm kiếm cho TNC (Thành Nhân / tnc.com.vn) (Playwright).

Đây là trang web CỦA CHÍNH CHÚNG TA. Giống như CellphoneS, kết quả tìm kiếm được render bằng
JavaScript, nên ta phải điều khiển một trình duyệt headless. Các sản phẩm khám phá được lưu với
is_self=true trên nguồn của chúng, để dashboard coi giá của ta là mốc so sánh (được loại trừ khỏi
các thống kê thị trường).

Các selector đã xác nhận (DOM sau khi render):
    card  : .cr-product-details
    name  : a[href*=".html"]   (nội dung text của thẻ anchor)
    price : .new-price          (giá hiện tại; KHÔNG phải .old-price - giá gạch ngang)

Cách dùng:
    python -m scraper.discover_tnc --dry    # in ra, không ghi vào DB
    python -m scraper.discover_tnc          # ghi vào Supabase
"""

from __future__ import annotations

import argparse
import re
import sys

from playwright.sync_api import sync_playwright

from .brand import brand_of
from .browser import goto_with_retry
from .config import categories, name_exclude_re, name_match_re, resolve_url, tnc_urls
from .db import ensure_competitor, get_client, insert_prices, upsert_products, upsert_sources
from .sku import apple_incomplete, apple_name, derive_sku

COMPETITOR = "Thành Nhân"
BASE_URL = "https://www.tnc.com.vn"
# Danh mục "laptop chính hãng" theo từng brand, có phân trang (?p=N). Thêm brand bằng cách thêm URL vào đây.
BRANDS = {
    "dell": "https://www.tnc.com.vn/laptop-dell-chinh-hang.html?p={page}",
    "lenovo": "https://www.tnc.com.vn/laptop-lenovo-chinh-hang.html?p={page}",
    "apple": "https://www.tnc.com.vn/laptop-apple-chinh-hang.html?p={page}",
    "hp": "https://www.tnc.com.vn/laptop-hp-chinh-hang.html?p={page}",
    "asus": "https://www.tnc.com.vn/laptop-asus-chinh-hang.html?p={page}",
    "acer": "https://www.tnc.com.vn/laptop-acer-chinh-hang.html?p={page}",
    "msi": "https://www.tnc.com.vn/laptop-msi-chinh-hang.html?p={page}",
}
PAGE_CAP = 50  # chốt an toàn chống lặp vô hạn; phân trang bình thường TỰ DỪNG sớm hơn (trang hết/
               # không thêm sản phẩm mới). Chạm cap = cảnh báo. (Trước là 15 → cắt nhầm man-hình ≥25 trang.)

CARD_SELECTOR = ".cr-product-details"
PRICE_SELECTOR = ".new-price"


def _digits_to_int(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def _name_from_slug(href: str | None) -> str:
    """Dựng lại tên sản phẩm từ slug URL — dùng làm phương án dự phòng khi text hiển thị của anchor
    là một nhãn trên thẻ chứ không phải tên (ví dụ "FORM LCD"). Slug luôn sạch và nhất quán:
    "/man-hinh-lcd-viewsonic-td2423.html" → "man hinh lcd viewsonic td2423". derive_sku/brand_of
    không phụ thuộc dấu tiếng Việt nên bản ASCII này vẫn cho ra đúng SKU/brand.
    """
    if not href:
        return ""
    slug = href.rstrip("/").split("/")[-1].split("?")[0].removesuffix(".html")
    return slug.replace("-", " ").strip()


def discover(brand: str = "dell", category: str = "laptop") -> list[dict]:
    """Trả về [{name, price, url, in_stock}] cho mọi sản phẩm `brand` của `category`.

    Tự động phân trang ?p=1,2,... cho đến khi một trang không còn SẢN PHẨM mới (while loop, tự dừng;
    PAGE_CAP=50 chỉ là chốt an toàn).
    Laptop: lọc theo brand. Danh mục khác: một URL cho cả danh mục, giữ lại theo name_match.

    Hàng hết ("Liên hệ"): TNC vẫn LIỆT KÊ các sản phẩm hết hàng (đẩy về cuối danh sách), nhưng ô
    `.new-price` của chúng ghi "Liên hệ" thay vì một con số. Ta VẪN thu thập chúng với
    `in_stock=False` (và price=None) thay vì bỏ qua — để về sau có thể cảnh báo khi đối thủ còn hàng
    mà ta thì không. Quan trọng: một sản phẩm hết hàng vẫn tính là "có sản phẩm trên trang", nên một
    trang TOÀN hàng hết không bị nhầm là "hết trang" khiến dừng phân trang sớm.
    """
    # Laptop giữ nguyên BRANDS map per-brand + bộ lọc brand. Các danh mục khác chạy theo danh mục:
    # một URL cho cả danh mục, giữ lại theo name_match của danh mục.
    if category == "laptop":
        url_tpls, want, name_re, excl_re = [BRANDS[brand]], brand.lower(), None, None
    else:
        # Một category có thể gộp NHIỀU trang catalog TNC (vd router = wireless + router doanh nghiệp).
        url_tpls, want = tnc_urls(category), None
        name_re = name_match_re(category)
        excl_re = name_exclude_re(category)   # loại tên khớp name_exclude (vd PC build của TNC)
    if not url_tpls:
        return []
    results: list[dict] = []
    seen: set[str] = set()   # dedup XUYÊN các trang TNC (sản phẩm xuất hiện ở >1 trang chỉ tính 1 lần)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        )
        for url_tpl in url_tpls:   # quét lần lượt từng trang catalog của category
            # Phân trang tối đa PAGE_CAP trang; DỪNG SỚM khi một trang không thêm sản phẩm mới (bình
            # thường), hoặc trang lỗi/trống. Nếu quét HẾT PAGE_CAP mà trang cuối VẪN đầy sản phẩm →
            # danh mục còn dài hơn → cảnh báo để nâng PAGE_CAP (trước là 15 → cắt nhầm màn hình).
            for n in range(1, PAGE_CAP + 1):
                # domcontentloaded, không phải networkidle — các tracker của TNC khiến mạng luôn bận
                # nên networkidle sẽ bị timeout. Trang 1 được thử lại (nếu hỏng là lỗi thật, dẫn tới 0
                # kết quả); trang 2+ hỏng chỉ nghĩa là đã hết trang nên dừng bình thường.
                if n == 1:
                    if not goto_with_retry(page, url_tpl.format(page=n), PRICE_SELECTOR, label=COMPETITOR):
                        break
                else:
                    try:
                        page.goto(url_tpl.format(page=n), wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_selector(PRICE_SELECTOR, timeout=20000)
                    except Exception:
                        break  # trang chậm/rỗng/trang cuối

                new_on_page = 0
                for card in page.query_selector_all(CARD_SELECTOR):
                    price_el = card.query_selector(PRICE_SELECTOR)
                    link_el = card.query_selector('a[href*=".html"]')
                    if not price_el or not link_el:
                        continue
                    name = (link_el.inner_text() or "").strip()
                    href = link_el.get_attribute("href")
                    url = (BASE_URL + href) if href and href.startswith("/") else href
                    # Đôi khi text hiển thị của anchor là một nhãn trên thẻ (ví dụ "FORM LCD"), không
                    # phải tên sản phẩm — nó có thể vẫn khớp name_match ("LCD") nhưng thiếu mã model.
                    # Tín hiệu đáng tin: tên sản phẩm thật LUÔN có token chứa chữ số (mã model). Nếu
                    # text anchor không có, dựng lại tên từ slug URL (luôn sạch, chứa cả brand + model).
                    if category != "laptop" and not re.search(r"\d", name):
                        slug_name = _name_from_slug(href)
                        if re.search(r"\d", slug_name):
                            name = slug_name
                    key = url or name
                    # Laptop: giữ đúng brand. Danh mục khác: giữ tên khớp name_match.
                    keep = (brand_of(name).lower() == want) if want else bool(name_re and name_re.search(name))
                    # Loại tên khớp name_exclude (vd "PC TNC ..." — hàng build riêng của shop).
                    if excl_re and excl_re.search(name):
                        keep = False
                    if not name or not keep or key in seen:
                        continue
                    # "Liên hệ" -> không có chữ số -> price None -> hết hàng; còn số -> còn hàng.
                    # VẪN thu thập hàng hết (không bỏ qua) để đánh dấu OOS về sau.
                    price = _digits_to_int(price_el.inner_text())
                    in_stock = price is not None
                    # Cờ khuyến mãi: thẻ có .promo-container thì trang sản phẩm CÓ THỂ có "Giá cuối"
                    # (flash sale) THẤP HƠN .new-price. Giá cuối chỉ hiện ở TRANG SẢN PHẨM (không có
                    # trên thẻ danh sách), nên chỉ ghé thăm những sản phẩm có cờ này để lấy giá thật.
                    has_promo = card.query_selector(".promo-container") is not None
                    seen.add(key)
                    new_on_page += 1
                    results.append({"name": name, "price": price, "url": url,
                                    "in_stock": in_stock, "has_promo": has_promo})

                if new_on_page == 0:  # không còn sản phẩm nào (kể cả hàng hết) -> hết trang thật sự
                    break
            else:
                # for..else: chạy khi vòng lặp KHÔNG break — tức đã quét đủ PAGE_CAP trang mà trang
                # cuối vẫn còn sản phẩm mới → danh mục dài hơn PAGE_CAP, đang bị cắt. Cảnh báo để nâng.
                print(f"  ⚠️  {url_tpl.split('/')[-1]}: chạm PAGE_CAP={PAGE_CAP} trang mà vẫn còn sản "
                      f"phẩm — danh mục còn dài hơn, cân nhắc nâng PAGE_CAP.")
        browser.close()
    return results



def enrich_apple(items: list[dict]) -> None:
    """Với các MacBook có tên hiển thị thiếu thông tin RAM/dung lượng lưu trữ, truy cập trang sản
    phẩm và thay `name` bằng tiêu đề H1 đầy đủ hơn để derive_sku có thể tạo ra key APPLE-...
    hoàn chỉnh. Thay đổi items tại chỗ (mutate in place); giữ nguyên tên gốc nếu có lỗi.
    """
    todo = [it for it in items if apple_incomplete(derive_sku(it["name"], it.get("url"))) and it.get("url")]
    if not todo:
        return
    print(f"  enriching {len(todo)} MacBook(s) with incomplete specs from their product pages...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        )
        for it in todo:
            try:
                page.goto(it["url"], wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(600)
                h1 = page.query_selector("h1")  # chứa "(M5/ Ram 16GB/ SSD 1TB)"
                rich = (h1.inner_text() or "").strip() if h1 else ""
                if rich and not apple_incomplete(derive_sku(rich, it.get("url"))):
                    it["name"] = rich
            except Exception:
                pass
        browser.close()


def apply_flash_prices(items: list[dict]) -> None:
    """Lấy GIÁ CUỐI (flash sale) từ TRANG SẢN PHẨM và thay cho .new-price nếu thấp hơn.

    TNC hiện "Giá cuối" (.deal-price-value) — giá bán THẬT khi có khuyến mãi — CHỈ ở trang sản phẩm,
    KHÔNG có trên thẻ danh sách. Thẻ chỉ có cờ .promo-container. Vì vậy: chỉ ghé thăm sản phẩm CÓ cờ
    khuyến mãi + còn hàng, đọc .deal-price-value, và nếu nó < giá listing thì DÙNG giá đó (giá bán
    thực tế). Mutate items tại chỗ; giữ nguyên giá cũ nếu lỗi hoặc không có giá cuối.
    """
    todo = [it for it in items if it.get("has_promo") and it.get("in_stock") and it.get("url")]
    if not todo:
        return
    print(f"  checking {len(todo)} promo product(s) for flash-sale (Giá cuối) prices...")
    updated = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        )
        for it in todo:
            try:
                page.goto(it["url"], wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(600)
                el = page.query_selector(".deal-price-value")
                deal = _digits_to_int(el.inner_text()) if el else None
                # Chỉ thay khi giá cuối HỢP LỆ và THẤP HƠN giá listing (flash sale thật, không phải
                # giá cao hơn do lỗi parse).
                if deal and (it.get("price") is None or deal < it["price"]):
                    it["price"] = deal
                    it["is_flash_sale"] = True   # đánh dấu để lưu cờ vào price_history
                    updated += 1
            except Exception:
                pass
        browser.close()
    if updated:
        print(f"  applied flash-sale price to {updated} product(s).")


def main() -> int:
    ap = argparse.ArgumentParser(description="Discover our own (TNC) prices by brand and category.")
    ap.add_argument("--brand", default="dell", help="brand to scrape (e.g. dell, samsung)")
    ap.add_argument(
        "--category", default="laptop", choices=["laptop", *sorted(categories())],
        help="product category to scrape",
    )
    ap.add_argument("--dry", action="store_true", help="print results, don't write to the DB")
    args = ap.parse_args()

    client = get_client()
    ensure_competitor(client, COMPETITOR, is_self=True)
    print(
        f"Discovering '{COMPETITOR}' (our site) — {args.category}/{args.brand}"
        f"{' (dry run)' if args.dry else ''}...\n"
    )
    found = discover(args.brand, args.category)
    print(f"{len(found)} unique product(s) parsed.\n")

    if args.category == "laptop" and args.brand == "apple":
        enrich_apple(found)

    # Áp GIÁ CUỐI (flash sale) từ trang sản phẩm — chỉ cho sản phẩm có cờ khuyến mãi (xem
    # apply_flash_prices). Chạy cả dry-run để in ra giá thật sẽ ghi.
    apply_flash_prices(found)

    category_label = args.category.capitalize()
    product_rows, source_rows, price_rows = [], [], []
    oos = 0
    for item in found:
        sku = derive_sku(item["name"], item.get("url"), category_label)
        brand = brand_of(item["name"])
        # Danh mục không phải laptop có thể không tạo được định danh (token-less) — bỏ qua, không đoán.
        if sku is None:
            print(f"- SKIP (no SKU): {item['name'][:60]}")
            continue
        # Bỏ qua các MacBook vẫn còn thiếu thông số — key '?' sẽ gây trùng lặp giữa các cấu hình khác nhau.
        if apple_incomplete(sku):
            print(f"- SKIP (incomplete specs): {item['name'][:60]}")
            continue
        # MacBook được đặt tên tổng hợp sạch sẽ (tên gốc từ TNC không nhất quán/có lỗi chính tả); các brand khác giữ nguyên tên.
        display_name = apple_name(item["name"]) or item["name"]
        in_stock = item.get("in_stock", True)
        # Hàng hết ("Liên hệ") không có giá — lưu price=0, in_stock=false. Cột price của price_history
        # là NOT NULL nên dùng 0; các view phải loại in_stock=false khỏi thống kê giá thị trường.
        price = item["price"] if in_stock else 0
        if not in_stock:
            oos += 1
        # In từng dòng sản phẩm CHỈ khi --dry (để kiểm tra tay); lúc chạy thật thì im lặng để dòng
        # THỐNG KÊ tổng kết ("Done. N sản phẩm...") nổi bật, không bị chôn giữa hàng trăm dòng.
        if args.dry:
            flag = f"{price:,} VND" if in_stock else "HẾT HÀNG (Liên hệ)"
            print(f"- {sku}: {flag}  ({display_name[:55]})")
        product_rows.append(
            {"sku": sku, "name": display_name, "brand": brand, "category": category_label}
        )
        fallback_url = BRANDS[args.brand].format(page=1) if args.category == "laptop" else None
        source_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "url": item.get("url") or fallback_url}
        )
        price_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR, "price": price, "in_stock": in_stock,
             "is_flash_sale": bool(item.get("is_flash_sale"))}
        )

    if not args.dry:
        upsert_products(client, product_rows)
        upsert_sources(client, source_rows)
        insert_prices(client, price_rows)

    n = len(price_rows)
    print(f"\nDone. {n} product(s) {'parsed' if args.dry else 'recorded'} ({oos} hết hàng).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
