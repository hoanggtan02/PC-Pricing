"""Chạy một lượt thu thập dữ liệu: scrape mọi source đang active và lưu giá hiện tại của nó.

Cách dùng:
    python -m scraper.run          # scrape tất cả source active, ghi vào Supabase
    python -m scraper.run --dry    # scrape và in giá ra, nhưng KHÔNG ghi vào DB

Cờ --dry rất hữu ích để test các adapter trước khi kết nối database xong.
"""

from __future__ import annotations

import argparse
import sys
import time

import httpx

from .adapters import ADAPTERS
from .db import fetch_active_sources, get_client, insert_price

# Một User-Agent giống trình duyệt thật; nhiều trang chặn User-Agent mặc định của httpx.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# Lịch sự một chút: tạm dừng ngắn giữa các request để không dồn dập tấn công trang của đối thủ.
DELAY_SECONDS = 2.0


def scrape_source(http: httpx.Client, source: dict) -> int | None:
    """Fetch trang của một source và parse giá của nó. Trả về giá bằng VND hoặc None."""
    competitor = source["competitor"]
    parser = ADAPTERS.get(competitor)
    if parser is None:
        print(f"  ! no adapter registered for '{competitor}' — skipping")
        return None

    try:
        resp = http.get(source["url"], headers=HEADERS, follow_redirects=True, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"  ! fetch failed: {exc}")
        return None

    return parser(resp.text, source["url"])


def main() -> int:
    arg_parser = argparse.ArgumentParser(description="Scrape competitor prices.")
    arg_parser.add_argument(
        "--dry", action="store_true", help="scrape and print, but don't write to the database"
    )
    args = arg_parser.parse_args()

    client = get_client()
    sources = fetch_active_sources(client)
    if not sources:
        print("No active sources found. Add rows to the 'sources' table first.")
        return 0

    print(f"Scraping {len(sources)} source(s){' (dry run)' if args.dry else ''}...\n")

    ok = 0
    with httpx.Client() as http:
        for source in sources:
            competitor = source["competitor"]
            product_sku = source["product_sku"]
            print(f"- {competitor} · {product_sku}")

            price = scrape_source(http, source)
            if price is None:
                print("  → no price found")
            else:
                print(f"  → {price:,} VND")
                if not args.dry:
                    insert_price(client, product_sku, competitor, price)
                ok += 1

            time.sleep(DELAY_SECONDS)

    print(f"\nDone. {ok}/{len(sources)} source(s) returned a price.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
