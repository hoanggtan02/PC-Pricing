"""Script cào giá đồng bộ theo link đã có trong Database (Mode B).
Cách dùng:
    python -m scraper.sync_prices          # cào tất cả active sources, ghi vào Supabase
    python -m scraper.sync_prices --dry    # cào và in ra, không ghi vào DB
"""

from __future__ import annotations

import os
import argparse
import asyncio
from collections import Counter
import re
import sys
import json
from playwright.async_api import async_playwright, Page

# Windows console encoding fix
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .config import is_old_listing_name
from .db import deactivate_source, get_client, insert_price, fetch_active_sources

CONCURRENCY_LIMIT = 5  # Số luồng cào song song tối đa
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Selector lấy giá cho từng đối thủ (ở trang chi tiết sản phẩm)
SELECTORS = {
    "CellphoneS": [".product__price--show", ".sale-price", "[itemprop='price']"],
    "GearVN": [".product-price", ".pro-price", ".price-current"],
    "Thành Nhân": [".new-price", ".deal-price-value", ".product-price"],
    "An Phát PC": [".p-price", ".d-pro-price", ".price-current"],
    "Phong Vũ": [".css-1755xpx", ".product-price", ".price-current", "span[class*='price']"],
    "Hà Nội Computer": [".dpro-p-price", ".price-current", ".product-price"],
    "Memoryzone": [".product-price", ".price-current"],
    "FPT Shop": [".b1-semibold", ".fpt-price", ".price-current"],
    "Thế Giới Di Động": [".box-price-present", ".price-current"]
}

def clean_price(text: str) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def extract_labeled_price(text: str) -> int | None:
    """Lấy giá ngay sau nhãn giá chính, không lấy giá sản phẩm gợi ý."""
    patterns = (
        r"giá\s+(?:mua\s+online|khuyến\s+mãi|bán|ưu\s+đãi)\s*:?\s*([\d.,]+)\s*(?:đ|vnđ|vnd)",
        r"(?:giá\s+hiện\s+tại|giá\s+sản\s+phẩm)\s*:?\s*([\d.,]+)\s*(?:đ|vnđ|vnd)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        price = clean_price(match.group(1))
        if price and price > 1_000:
            return price
    return None

async def extract_price_generic(page: Page, competitor: str) -> int | None:
    """Sử dụng nhiều chiến lược để trích xuất giá từ trang sản phẩm."""
    html = await page.content()
    
    # 1. Thử lấy giá từ JSON-LD schema (rất phổ biến cho SEO)
    try:
        scripts = await page.locator("script[type='application/ld+json']").all_inner_texts()
        for script_text in scripts:
            try:
                data = json.loads(script_text)
                for node in data if isinstance(data, list) else [data]:
                    if not isinstance(node, dict):
                        continue
                    if node.get("@type") == "Product" or "offers" in node:
                        offers = node.get("offers")
                        if isinstance(offers, dict) and offers.get("price"):
                            p = clean_price(str(offers["price"]))
                            if p and p > 1000:
                                return p
                        elif isinstance(offers, list) and len(offers) > 0:
                            p = clean_price(str(offers[0].get("price")))
                            if p and p > 1000:
                                return p
            except Exception:
                continue
    except Exception:
        pass

    # 2. Thử lấy từ meta tags (og:price, product:price)
    try:
        for meta_name in ["product:price:amount", "og:price:amount", "price"]:
            meta_el = page.locator(f"meta[property='{meta_name}'], meta[name='{meta_name}']")
            if await meta_el.count() > 0:
                content = await meta_el.first.get_attribute("content")
                p = clean_price(content)
                if p and p > 1000:
                    return p
    except Exception:
        pass

    # 3. Lấy theo CSS Selector đặc thù của competitor
    selectors = SELECTORS.get(competitor, [".price-current", ".product-price", "[itemprop='price']"])
    for sel in selectors:
        try:
            locator = page.locator(sel)
            if await locator.count() > 0:
                # Lấy phần tử hiển thị đầu tiên
                for i in range(await locator.count()):
                    el = locator.nth(i)
                    if await el.is_visible():
                        txt = await el.inner_text()
                        p = clean_price(txt)
                        if p and p > 1000:
                            return p
        except Exception:
            continue

    # 4. Thử tìm regex generic trên HTML
    # Nhiều site đổi class giá nhưng vẫn giữ nhãn văn bản (HACOM/TNC/An Phát).
    # Thử body đã render trước, rồi đến HTML thô từ SSR.
    try:
        price = extract_labeled_price(await page.locator("body").inner_text())
        if price:
            return price
    except Exception:
        pass

    price = extract_labeled_price(html)
    if price:
        return price

    match = re.search(r'property="product:price:amount"\s+content="(\d+)"', html)
    if match:
        return int(match.group(1))
        
    return None

async def scrape_source(context, source: dict, dry_run: bool, client) -> bool:
    competitor = source["competitor"]
    url = source["url"]
    sku = source["product_sku"]
    
    if not url or url == "#" or "javascript" in url:
        print(f"  ! Skip {competitor} - {sku}: URL không hợp lệ ({url})")
        return False

    page = await context.new_page()
    # Chặn tài nguyên không cần thiết để tăng tốc
    await page.route("**/*", lambda route: route.abort() if route.request.resource_type in {"image", "media", "font"} else route.continue_())

    try:
        print(f"  → Đang cào {competitor} - {sku}...")
        # Navigate với timeout 30s
        await page.goto(url, wait_until="commit", timeout=30000)
        
        # Đợi thêm 1s để chắc chắn JS render xong
        await page.wait_for_timeout(1500)
        
        # Một URL có thể bị shop đổi sang hàng cũ/demo sau khi đã ghép SKU.
        # Không ghi giá đó và tắt source để cache lần refresh sau loại nó.
        title = await page.title()
        if is_old_listing_name(title):
            print(f"  [OLD] {competitor} - {sku}: tắt source ({title[:80]})")
            if not dry_run:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, deactivate_source, client, sku, competitor)
            return False

        price = await extract_price_generic(page, competitor)
        
        if price:
            print(f"  ✅ {competitor} - {sku}: {price:,} VND")
            if not dry_run:
                # Ghi giá vào DB
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, insert_price, client, sku, competitor, price)
            return True
        else:
            print(f"  ❌ {competitor} - {sku}: Không tìm thấy giá trên trang ({url})")
            return False
            
    except Exception as e:
        msg = str(e).splitlines()[0][:80]
        print(f"  ❌ {competitor} - {sku}: Lỗi cào ({msg})")
        return False
    finally:
        await page.close()

async def worker(queue, context, dry_run, client, results):
    while True:
        source = await queue.get()
        if source is None:
            queue.task_done()
            break
        success = await scrape_source(context, source, dry_run, client)
        results["success" if success else "failed"] += 1
        results["by_competitor"][source["competitor"]]["success" if success else "failed"] += 1
        queue.task_done()

async def run_sync(dry_run: bool, limit: int | None = None):
    client = get_client()
    # Lấy các source đang active
    sources = fetch_active_sources(client)
    if not sources:
        print("Không tìm thấy source active nào trong Database.")
        return

    if limit:
        sources = sources[:limit]

    print(f"Bắt đầu đồng bộ giá cho {len(sources)} sources (Concurrency: {CONCURRENCY_LIMIT})...")
    totals = Counter(source["competitor"] for source in sources)
    print("Source active theo cửa hàng: " + ", ".join(
        f"{competitor}={count}" for competitor, count in sorted(totals.items())
    ))
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Sử dụng proxy Việt Nam nếu có định nghĩa trong môi trường (giúp bypass cf của FPT/Phong Vũ)
        proxy_server = os.environ.get("PROXY_SERVER")
        proxy_username = os.environ.get("PROXY_USERNAME")
        proxy_password = os.environ.get("PROXY_PASSWORD")
        
        proxy_cfg = None
        if proxy_server:
            proxy_cfg = {"server": proxy_server}
            if proxy_username:
                proxy_cfg["username"] = proxy_username
                proxy_cfg["password"] = proxy_password
                
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
            proxy=proxy_cfg
        )

        queue = asyncio.Queue()
        for src in sources:
            await queue.put(src)

        results = {
            "success": 0,
            "failed": 0,
            "by_competitor": {
                competitor: {"success": 0, "failed": 0} for competitor in totals
            },
        }
        
        # Tạo worker tasks chạy song song
        tasks = []
        for _ in range(CONCURRENCY_LIMIT):
            task = asyncio.create_task(worker(queue, context, dry_run, client, results))
            tasks.append(task)
            # Thêm tín hiệu dừng cho mỗi worker
            await queue.put(None)

        await queue.join()
        await asyncio.gather(*tasks)
        await browser.close()
        
    print(f"\nHoàn tất đồng bộ giá: Thành công {results['success']}, Thất bại {results['failed']}.")
    print("Kết quả theo cửa hàng:")
    for competitor in sorted(results["by_competitor"]):
        stats = results["by_competitor"][competitor]
        print(f"  - {competitor}: {stats['success']}/{totals[competitor]} thành công, {stats['failed']} thất bại")
    
    # Refresh cả khi chỉ có source bị tắt vì hàng cũ/demo (không có giá mới thành công).
    # Nếu chỉ refresh khi success > 0, giá cũ vẫn kẹt trong snapshot.
    if not dry_run:
        print("Đang làm mới cache Supabase...")
        try:
            client.rpc("refresh_latest_prices").execute()
            print("Làm mới cache thành công.")
        except Exception as e:
            print(f"Lỗi làm mới cache: {e}")

def main():
    import os
    parser = argparse.ArgumentParser(description="Sync prices directly from database source URLs.")
    parser.add_argument("--dry", action="store_true", help="dry run (don't write to DB)")
    parser.add_argument("--limit", type=int, default=None, help="limit the number of sources to scrape")
    args = parser.parse_args()
    
    asyncio.run(run_sync(args.dry, args.limit))

if __name__ == "__main__":
    main()
