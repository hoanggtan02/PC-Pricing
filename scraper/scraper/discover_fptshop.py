"""Scraper khám phá giá FPT Shop (fptshop.com.vn) (Playwright + proxy Việt Nam).

FPT Shop chặn theo vùng địa lý các IP ngoài Việt Nam (Cloudflare 403), nên đoạn này định tuyến
qua proxy VN (use_proxy=True). Kết quả được render bằng JS (Next.js).

Selector đã xác minh (DOM đã render):
    card  : .cardInfo
    link  : a[href^="/may-tinh-xach-tay/"]   (slug kết thúc bằng mã Dell, vd "...-cph99")
    name  : title của anchor / <h3> của card
    price : <p class="b1-semibold"> giá hiện tại; <span> gạch ngang là giá cũ.

Chỉ đối chiếu (match-only): chỉ ghi nhận giá cho các SKU đã có trong `products` (catalog của TNC).

MODE A (weekend discovery) — CHỈ GHI GIÁ CHO SKU MỚI: kịch bản này chạy cuối tuần để tìm sản
phẩm MỚI, không phải để cào lại giá của mọi sản phẩm đã biết — giá đó Mode B (sync_prices, chạy
hàng ngày) đã cào đều đặn rồi. Vì vậy SKU nào ĐÃ có source ở competitor này (fetch_existing_source_skus)
thì chỉ được refresh URL (upsert_sources), KHÔNG ghi thêm dòng price_history trùng lặp.

Cách dùng:
    python -m scraper.discover_fptshop --dry
    python -m scraper.discover_fptshop
"""

from __future__ import annotations

import argparse
import re
import sys

from .brand import name_match_term
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

COMPETITOR = "FPT Shop"
BASE_URL = "https://fptshop.com.vn"
# Trang kết quả "khám phá" (kham-pha) phân trang qua &page=N; lặp đến khi một trang không thêm gì mới.
BRANDS = {
    "dell": (
        "https://fptshop.com.vn/tim-kiem?tab=kham-pha&s=laptop+dell"
        "&sort=noi-bat&categories=may-tinh-xach-tay&page={page}"
    ),
    "lenovo": (
        "https://fptshop.com.vn/tim-kiem?tab=kham-pha&s=laptop+lenovo"
        "&sort=noi-bat&categories=may-tinh-xach-tay&page={page}"
    ),
    "apple": (
        "https://fptshop.com.vn/tim-kiem?tab=kham-pha&s=macbook"
        "&sort=noi-bat&categories=may-tinh-xach-tay&page={page}"
    ),
    "hp": (
        "https://fptshop.com.vn/tim-kiem?tab=kham-pha&s=laptop+hp"
        "&sort=noi-bat&categories=may-tinh-xach-tay&page={page}"
    ),
    "asus": (
        "https://fptshop.com.vn/tim-kiem?tab=kham-pha&s=laptop+asus"
        "&sort=noi-bat&categories=may-tinh-xach-tay&page={page}"
    ),
    "acer": (
        "https://fptshop.com.vn/tim-kiem?tab=kham-pha&s=laptop+acer"
        "&sort=noi-bat&categories=may-tinh-xach-tay&page={page}"
    ),
    "msi": (
        "https://fptshop.com.vn/tim-kiem?tab=kham-pha&s=laptop+msi"
        "&sort=noi-bat&categories=may-tinh-xach-tay&page={page}"
    ),
    "gigabyte": (
        "https://fptshop.com.vn/tim-kiem?tab=kham-pha&s=laptop+gigabyte"
        "&sort=noi-bat&categories=may-tinh-xach-tay&page={page}"
    ),
}
PAGE_CAP = 50  # chốt an toàn; phân trang tự dừng sớm khi trang không thêm sản phẩm. Chạm cap = cảnh báo.

CARD_SELECTOR = ".cardInfo"


def _digits_to_int(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def discover(brand: str = "dell", category: str = "laptop") -> list[dict]:
    """Trả về [{name, price, url}] cho các sản phẩm trên tất cả các trang kết quả phân trang.

    Laptop (mặc định) dùng URL tìm-kiếm laptop per-brand + lọc theo brand. Các danh mục khác dùng
    URL `paths.fptshop` của danh mục (có {page}) và giữ lại theo name_match.
    """
    is_laptop = category == "laptop"
    excl_re = name_exclude_re(category)
    if is_laptop:
        url_tpl, name_re = BRANDS[brand], None
    else:
        url_tpl = resolve_url("fptshop", category)
        name_re = name_match_re(category)
    if not url_tpl:
        return []
    results: list[dict] = []
    seen_urls: set[str] = set()
    with browser_page(use_proxy=True) as page:
        for n in range(1, PAGE_CAP + 1):
            # Một trang chậm (do proxy) không nên làm hỏng cả lượt chạy — giữ lại các trang đã thu
            # thập được. Trang 1 được thử lại (hỏng là lỗi thật → 0 kết quả); trang 2+ hỏng chỉ nghĩa
            # là đã hết trang nên dừng bình thường.
            if n == 1:
                if not goto_with_retry(
                    page, url_tpl.format(page=n), CARD_SELECTOR,
                    selector_timeout=15000, label=COMPETITOR,
                ):
                    break
            else:
                try:
                    page.goto(url_tpl.format(page=n), wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_selector(CARD_SELECTOR, timeout=15000)
                except Exception:
                    break  # hết thời gian chờ / không có card
            page.wait_for_timeout(2000)

            items = page.eval_on_selector_all(
                CARD_SELECTOR,
                """
            (cards, opts) => {
              const [term, isLaptop] = opts;
              const out = [];
              const seen = new Set();
              const re = new RegExp('\\\\b(?:laptop|' + term + ')\\\\b', 'i');
              for (const card of cards) {
                // Laptop: anchor /may-tinh-xach-tay/. Danh mục khác: anchor sản phẩm đầu tiên.
                const a = isLaptop
                  ? card.querySelector('a[href^="/may-tinh-xach-tay/"]')
                  : card.querySelector('a[href^="/"]');
                if (!a) continue;
                const href = a.getAttribute('href');
                if (!href || seen.has(href)) continue;
                const name = (a.getAttribute('title') ||
                              (card.querySelector('h3') ? card.querySelector('h3').innerText : '')).trim();
                if (isLaptop && !re.test(name)) continue;  // danh mục khác lọc ở Python
                // Giá hiện tại là <p class="text-textOnWhitePrimary ..."> mà nội dung text của
                // chính nó chỉ đúng một giá như "20.990.000đ". Ta tránh: giá cũ gạch ngang,
                // đoạn giảm giá "...-13%", và các dòng tiết kiệm "Giảm ...".
                let price = '';
                const PRICE = /^[0-9]{1,3}\\.[0-9]{3}\\.[0-9]{3}\\s*đ?$/;
                for (const el of card.querySelectorAll('p')) {
                  if (!(el.getAttribute('class') || '').includes('text-textOnWhitePrimary')) continue;
                  const txt = (el.textContent || '').trim();
                  if (PRICE.test(txt)) { price = txt; break; }
                }
                // dự phòng: bất kỳ phần tử nào có text chỉ đúng một giá, không gạch ngang
                if (!price) {
                  for (const el of card.querySelectorAll('p, span')) {
                    const txt = (el.textContent || '').trim();
                    if (!PRICE.test(txt)) continue;
                    if ((el.getAttribute('class') || '').includes('line-through')) continue;
                    price = txt;
                    break;
                  }
                }
                if (!price) continue;
                // hết hàng: FPT hiển thị banner "Hàng sắp về" trong card
                const in_stock = !/hàng sắp về/i.test(card.innerText || '');
                seen.add(href);
                out.push({ name, price, url: href, in_stock });
              }
              return out;
            }
            """,
                [name_match_term(brand), is_laptop],
            )

            new_on_page = 0
            for it in items:
                name = it["name"]
                if (excl_re and excl_re.search(name)) or (not is_laptop and not (name_re and name_re.search(name))):
                    continue
                price = _digits_to_int(it["price"])
                href = it["url"]
                url = (BASE_URL + href) if href and href.startswith("/") else href
                if not price or url in seen_urls:
                    continue
                seen_urls.add(url)
                new_on_page += 1
                results.append(
                    {"name": name, "price": price, "url": url,
                     "in_stock": it.get("in_stock", True)}
                )

            if new_on_page == 0:  # đã đến trang cuối
                break
        else:
            # for..else: chạy khi KHÔNG break → quét hết PAGE_CAP trang mà vẫn còn sản phẩm mới →
            # danh mục dài hơn PAGE_CAP, đang bị cắt. Cảnh báo để cân nhắc nâng PAGE_CAP.
            print(f"  ⚠️  {COMPETITOR}: chạm PAGE_CAP={PAGE_CAP} trang mà vẫn còn sản phẩm — "
                  f"danh mục còn dài hơn, cân nhắc nâng PAGE_CAP.")
    return results



def main() -> int:
    ap = argparse.ArgumentParser(description="Discover FPT Shop prices by brand and category.")
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

    # SKU nào đã có source ở FPT Shop -> đã được Mode B (daily sync) theo dõi giá. Chỉ ghi giá
    # cho SKU MỚI (chưa có trong tập này); sku cũ chỉ refresh URL.
    existing = fetch_existing_source_skus(client, COMPETITOR)

    print(
        f"Discovering '{COMPETITOR}' (via VN proxy) — {args.category}/{args.brand}"
        f"{' (dry run)' if args.dry else ''}...\n"
    )
    found = discover(args.brand, args.category)
    print(
        f"{len(found)} unique product(s) parsed; matching against {len(tracked)} TNC SKU(s), "
        f"{len(existing)} đã có source (daily sync lo giá).\n"
    )

    category_label = args.category.capitalize()
    if args.category == "laptop":
        fallback_url = BRANDS[args.brand].format(page=1)
    else:
        cat_url = resolve_url("fptshop", args.category)
        fallback_url = cat_url.format(page=1) if cat_url else None
    source_rows, price_rows = [], []
    new_count = 0
    for item in found:
        sku = derive_sku(item["name"], item.get("url"), category_label)
        if sku is None or sku not in tracked:
            continue
        in_stock = item.get("in_stock", True)
        flag = "" if in_stock else "  [OUT OF STOCK]"
        is_new = sku not in existing
        tag = "[MỚI] " if is_new else ""
        print(f"- {tag}{sku}: {item['price']:,} VND{flag}  ({item['name'][:50]})")
        source_rows.append(
            {"product_sku": sku, "competitor": COMPETITOR,
             "url": item.get("url") or fallback_url}
        )
        # Chỉ ghi giá cho SKU CHƯA từng có source ở competitor này (sản phẩm mới phát hiện).
        if is_new:
            price_rows.append(
                {"product_sku": sku, "competitor": COMPETITOR, "price": item["price"], "in_stock": in_stock}
            )
            new_count += 1

    if not args.dry:
        upsert_sources(client, source_rows)
        insert_prices(client, price_rows)

    print(
        f"\nDone. {new_count} SKU MỚI được ghi giá trên {COMPETITOR} "
        f"({len(source_rows) - new_count} SKU cũ chỉ refresh URL, không ghi giá lại)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())