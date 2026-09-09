"""Cào lại giá + tồn kho cho các sản phẩm trong bảng `missing_products` (Mode C).

`missing_products` (xem discover_anphat.py / db.py:upsert_missing_products) lưu các sản phẩm đối
thủ có bán nhưng catalog TNC chưa có SKU khớp — mục đích để người xem cân nhắc có nên nhập hàng
mới hay không. Dữ liệu (tên/giá) chỉ được ghi lại MỖI LẦN discover_anphat.py chạy qua category đó;
giữa hai lần chạy, đối thủ có thể đã HẾT HÀNG chính sản phẩm này. Hiển thị một "cơ hội" đã hết
hàng bên đối thủ chỉ gây nhiễu, nên cần một lượt kiểm tra tồn kho RIÊNG, thường xuyên hơn.

Script này ghé lại từng URL còn `resolved = false`, đọc lại GIÁ + TỒN KHO hiện tại — dùng LẠI
đúng `extract_price_generic()` và các tín hiệu hết hàng riêng từng site (An Phát/HACOM/Phúc Anh/
FPT Shop...) đã có sẵn trong sync_prices.py, để không lệch hành vi giữa hai nơi cùng đọc một
trang — rồi ghi `price` / `in_stock` / `stock_checked_at` qua update_missing_product_stock().

Giao diện (JS/PHP) nên đọc view `missing_products_available` (xem missing_products_stock.sql)
thay vì bảng `missing_products` trực tiếp — sản phẩm vừa được xác nhận HẾT HÀNG sẽ tự động biến
mất khỏi view đó, không cần sửa gì ở tầng hiển thị.

AN TOÀN: lỗi mạng / nghi trang bị chặn bot (Cloudflare, chưa tải xong...) sẽ GIỮ NGUYÊN trạng
thái tồn kho cũ (không ghi gì) — một lần tải lỗi không đủ để kết luận "hết hàng", tránh ẩn nhầm
một cơ hội thật.

Cách dùng:
    python -m scraper.check_missing_stock --dry
    python -m scraper.check_missing_stock
    python -m scraper.check_missing_stock --competitor "An Phát PC"
    python -m scraper.check_missing_stock --limit 50 --dry
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys

from playwright.async_api import async_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .db import fetch_missing_products, get_client, update_missing_product_stock
from .proxy_pool import get_pool, is_proxy_error
from .stock import is_out_of_stock
from .sync_prices import (
    CHROMIUM_STEALTH_ARGS,
    DISCONTINUED_PATTERN,
    GOTO_TIMEOUT_MS,
    PROXY_COMPETITORS,
    SLOW_COMPETITORS,
    SELECTORS,
    _GOOGLEBOT_UA,
    _HTTPX_COMPETITORS,
    _build_proxy_context,
    _extract_price_from_text,
    _wait_price_rendered,
    extract_price_generic,
)

# Số tab chạy song song. Thấp hơn CONCURRENCY_LIMIT của sync_prices.py (5) một chút — script này
# thường chạy sau Mode A/B, không cần gấp, và tránh dồn thêm tải lên các site vốn đã bị cào 2 lần
# (discover_* + sync_prices) trong cùng một ngày.
CONCURRENCY_LIMIT = 4


async def _check_httpx(competitor: str, url: str) -> tuple[int | None, bool]:
    """Kiểm tra giá + tồn kho bằng httpx cho các site Cloudflare Turnstile chặn Playwright nhưng
    cho Googlebot UA qua (vd Wifi.com.vn) — xem _HTTPX_COMPETITORS trong sync_prices.py. Chỉ ĐỌC,
    không đụng tới sources/price_history (missing_products không có khái niệm đó).

    Trả (price, in_stock). Lỗi tải hoặc nghi trang chặn bot -> (None, True): None báo cho caller
    biết "không đọc được gì mới", True để KHÔNG vô tình đổi trạng thái tồn kho (caller vẫn ghi
    stock_checked_at, nhưng chỉ giữ nguyên in_stock nếu trước đó không có kết luận rõ ràng —
    xem cách gọi update_missing_product_stock() trong run_check()).
    """
    import httpx
    from bs4 import BeautifulSoup

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": _GOOGLEBOT_UA}, timeout=15, follow_redirects=True
        ) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            return None, True  # lỗi tải — giữ nguyên trạng thái cũ
        html = resp.text
        if len(html) < 5000:
            return None, True  # nghi trang chặn bot/challenge — giữ nguyên trạng thái cũ

        soup = BeautifulSoup(html, "html.parser")
        price_text = None
        for sel in SELECTORS.get(competitor, []):
            el = soup.select_one(sel)
            if el:
                price_text = el.get_text(strip=True)
                if _extract_price_from_text(price_text) is not None:
                    break
        price = _extract_price_from_text(price_text)

        body_text = soup.get_text(" ", strip=True)
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        if (
            re.search(DISCONTINUED_PATTERN, title, re.IGNORECASE)
            or re.search(DISCONTINUED_PATTERN, body_text, re.IGNORECASE)
            or is_out_of_stock(title)
            or is_out_of_stock(body_text)
        ):
            return price, False

        return price, price is not None and price > 0
    except Exception:
        return None, True


async def _check_playwright(
    context, competitor: str, url: str, proxy: dict | None
) -> tuple[int | None, bool]:
    """Kiểm tra giá + tồn kho bằng Playwright, tái dùng extract_price_generic() của
    sync_prices.py (đã có sẵn tín hiệu OOS riêng cho FPT Shop/Phúc Anh/An Phát/HACOM/An Khang bên
    trong hàm đó). Trả (price, in_stock); (None, True) khi lỗi/không đọc được gì — giữ nguyên
    trạng thái cũ, xem ghi chú ở _check_httpx()."""
    page = await context.new_page()
    await page.route(
        "**/*",
        lambda route: route.abort()
        if route.request.resource_type in {"image", "media", "font"}
        else route.continue_(),
    )
    try:
        goto_timeout = GOTO_TIMEOUT_MS["proxy"] if proxy is not None else GOTO_TIMEOUT_MS["default"]
        await page.goto(url, wait_until="commit", timeout=goto_timeout)

        is_slow = competitor in SLOW_COMPETITORS
        await _wait_price_rendered(page, competitor, timeout=20000 if is_slow else 10000)

        title = await page.title()
        try:
            body_text = await page.locator("body").inner_text()
        except Exception:
            body_text = ""
        if re.search(DISCONTINUED_PATTERN, title, re.IGNORECASE) or re.search(
            DISCONTINUED_PATTERN, body_text, re.IGNORECASE
        ):
            return 0, False  # ngừng kinh doanh -> chắc chắn hết hàng

        price, availability_stock = await extract_price_generic(page, competitor)
        extra_reads = 3 if is_slow else 1
        for _ in range(extra_reads):
            if price is not None:
                break
            await page.wait_for_timeout(1500 if is_slow else 1200)
            price, availability_stock = await extract_price_generic(page, competitor)

        if price is None:
            return None, True  # không đọc được giá — có thể trang lỗi/chặn bot, giữ nguyên cũ

        in_stock = False if price <= 0 else (availability_stock if availability_stock is not None else True)
        return price, in_stock
    except Exception as e:
        msg = str(e).splitlines()[0][:80]
        if proxy is not None and is_proxy_error(msg):
            get_pool().mark_dead(proxy)
        return None, True  # lỗi tải trang — giữ nguyên trạng thái cũ
    finally:
        await page.close()


async def run_check(dry_run: bool, competitor: str | None, limit: int | None) -> None:
    client = get_client()
    rows = fetch_missing_products(client, competitor=competitor)
    if limit:
        rows = rows[:limit]
    if not rows:
        print("Không có sản phẩm nào cần kiểm tra (đã resolved hết, hoặc bảng missing_products rỗng).")
        return

    print(
        f"Kiểm tra tồn kho cho {len(rows)} sản phẩm trong missing_products"
        f"{' (dry run)' if dry_run else ''}...\n"
    )

    proxy_needed = any(r["competitor"] in PROXY_COMPETITORS for r in rows)
    pool = get_pool() if proxy_needed else None
    n_in, n_out, n_unknown = 0, 0, 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=CHROMIUM_STEALTH_ARGS)
        contexts = {
            "direct": await _build_proxy_context(browser, None),
            "proxy": None,
            "proxy_obj": None,
            "lock": asyncio.Lock(),
        }
        if proxy_needed:
            live_proxy = pool.current()
            if live_proxy:
                contexts["proxy"] = await _build_proxy_context(browser, live_proxy)
                contexts["proxy_obj"] = live_proxy

        queue: asyncio.Queue = asyncio.Queue()
        for r in rows:
            await queue.put(r)

        async def worker() -> None:
            nonlocal n_in, n_out, n_unknown
            while True:
                row = await queue.get()
                if row is None:
                    queue.task_done()
                    break

                comp, url = row["competitor"], (row.get("url") or "")
                if not url:
                    queue.task_done()
                    continue

                if comp in _HTTPX_COMPETITORS:
                    price, in_stock_or_unknown = await _check_httpx(comp, url)
                else:
                    needs_proxy = comp in PROXY_COMPETITORS
                    if needs_proxy:
                        live_proxy = pool.current() if pool else None
                        if live_proxy is None:
                            print(f"  ⚠️  Skip {comp} (hết proxy sống): {url}")
                            n_unknown += 1
                            queue.task_done()
                            continue
                        if contexts.get("proxy_obj") != live_proxy:
                            async with contexts["lock"]:
                                if contexts.get("proxy_obj") != live_proxy:
                                    old_ctx = contexts.get("proxy")
                                    contexts["proxy"] = await _build_proxy_context(browser, live_proxy)
                                    contexts["proxy_obj"] = live_proxy
                                    if old_ctx is not None:
                                        try:
                                            await old_ctx.close()
                                        except Exception:
                                            pass
                        ctx, proxy_for_mark = contexts["proxy"], contexts["proxy_obj"]
                    else:
                        ctx, proxy_for_mark = contexts["direct"], None
                    price, in_stock_or_unknown = await _check_playwright(ctx, comp, url, proxy_for_mark)

                if price is None and in_stock_or_unknown is True:
                    print(f"  ❓ KHÔNG XÁC ĐỊNH (giữ nguyên)  [{comp}]  {row['name'][:55]}  ({url})")
                    n_unknown += 1
                    queue.task_done()
                    continue

                in_stock = bool(in_stock_or_unknown)
                tag = "✅ CÒN HÀNG" if in_stock else "🚫 HẾT HÀNG (sẽ ẩn khỏi giao diện)"
                price_s = f"{price:,} VND" if price else "?"
                print(f"  {tag}  [{comp}] {price_s}  {row['name'][:55]}")
                n_in += 1 if in_stock else 0
                n_out += 0 if in_stock else 1

                if not dry_run:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None, update_missing_product_stock, client, comp, url, in_stock, price
                    )
                queue.task_done()

        tasks = [asyncio.create_task(worker()) for _ in range(CONCURRENCY_LIMIT)]
        for _ in tasks:
            await queue.put(None)
        await queue.join()
        await asyncio.gather(*tasks)
        await browser.close()

    if proxy_needed:
        print(f"\nTrạng thái proxy cuối lượt chạy: {pool.status()}")
    print(
        f"\nHoàn tất. Còn hàng: {n_in} | Hết hàng (sẽ ẩn khỏi missing_products_available): {n_out} "
        f"| Không xác định (giữ nguyên): {n_unknown}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Cào lại giá + tồn kho cho link trong missing_products (Mode C). Sản phẩm hết hàng "
            "sẽ bị lọc khỏi view missing_products_available mà giao diện nên đọc."
        )
    )
    ap.add_argument("--competitor", default=None, help="chỉ kiểm tra MỘT competitor")
    ap.add_argument("--limit", type=int, default=None, help="giới hạn số sản phẩm kiểm tra")
    ap.add_argument("--dry", action="store_true", help="chỉ in ra, không ghi vào DB")
    args = ap.parse_args()
    asyncio.run(run_check(dry_run=args.dry, competitor=args.competitor, limit=args.limit))
    return 0


if __name__ == "__main__":
    sys.exit(main())