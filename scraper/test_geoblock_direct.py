"""Test IP hiện tại (KHÔNG proxy) có bị Phong Vũ / FPT Shop / TGDĐ / Phúc Anh chặn hay không.
Không cần DB, không cần proxy. Chạy trên máy bạn (VN) HOẶC trên GitHub Actions (non-VN)
để so sánh trực tiếp.

Cách dùng:
    python test_geoblock_direct.py phongvu
    python test_geoblock_direct.py fptshop
    python test_geoblock_direct.py tgdd
    python test_geoblock_direct.py phucanh

TGDĐ được thêm vào (2026-08) sau khi category "camera" fail 100% trên CI với
net::ERR_CONNECTION_TIMED_OUT / Page.goto timeout — nghi IP dải GitHub Actions runner bị TGDĐ
chặn/rate-limit tạm thời khi nhiều leg matrix (scrape.yml) cùng lúc gõ vào. Test này trả lời dứt
khoát: chạy TRÊN CHÍNH runner CI (qua workflow test-geoblock.yml) xem TGDĐ có chặn/timeout hay
không, KHÔNG cần chờ cả lượt scrape.yml đầy đủ (30 leg, hàng giờ) mới biết.

Phúc Anh được thêm vào (2026-08) sau khi category "audio" fail 100% trên CI với
Page.wait_for_selector timeout (5/5 lần thử) — goto() KHÔNG lỗi (trang tải về bình thường) nhưng
selector .p-item-group không bao giờ xuất hiện. Cùng triệu chứng với vụ TGDĐ tái chặn: nghi trang
trả về nội dung chặn/challenge (HTTP 200 nhưng markup khác) cho IP ngoài VN, thay vì trang danh
mục thật. Test này xác nhận dứt khoát trước khi đổi discover_phucanh.py/sync_prices.py sang proxy.
"""
from __future__ import annotations

import re
import sys

from playwright.sync_api import sync_playwright

TARGETS = {
    "phongvu": {
        "url": "https://phongvu.vn/c/laptop-dell",
        "selector": ".att-product-detail-latest-price",
    },
    "fptshop": {
        "url": "https://fptshop.com.vn/tim-kiem?tab=kham-pha&s=laptop+dell"
               "&sort=noi-bat&categories=may-tinh-xach-tay&page=1",
        "selector": ".cardInfo",
    },
    "tgdd": {
        "url": "https://www.thegioididong.com/camera-giam-sat",
        "selector": "li.item .price",
    },
    "phucanh": {
        "url": "https://www.phucanh.vn/tainghe.html",
        "selector": ".p-item-group",
    },
}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_BLOCK_SIGNS = re.compile(
    r"just a moment|attention required|access denied|are you a human|"
    r"checking your browser|cloudflare|forbidden|một chút nữa|xin chờ",
    re.IGNORECASE,
)


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "phongvu"
    target = TARGETS[name]
    url, selector = target["url"], target["selector"]

    print(f"=== Test [{name}] KHÔNG proxy ===")
    print(f"URL: {url}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT, viewport={"width": 1920, "height": 1080})

        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            status = resp.status if resp else None
        except Exception as e:
            print(f"❌ goto() LỖI: {e}")
            print(f"\n>>> KẾT LUẬN [{name}]: BỊ CHẶN (lỗi kết nối/timeout ở tầng network) — CẦN PROXY VN.")
            browser.close()
            sys.exit(1)

        title = page.title()
        html = page.content()
        blocked = bool(_BLOCK_SIGNS.search(title or "")) or bool(_BLOCK_SIGNS.search(html[:5000]))

        print(f"HTTP status : {status}")
        print(f"Page title  : {title!r}")
        print(f"Nghi bị chặn (title/html): {blocked}")

        try:
            page.wait_for_selector(selector, timeout=15000)
            count = page.eval_on_selector_all(selector, "(els) => els.length")
            print(f"✅ Tìm thấy {count} phần tử giá.")
            print(f"\n>>> KẾT LUẬN [{name}]: KHÔNG bị chặn — chạy trực tiếp OK, không cần proxy.")
        except Exception:
            print("❌ KHÔNG tìm thấy selector giá trong 15s.")
            page.screenshot(path=f"{name}_evidence.png", full_page=True)
            if blocked or (status and status in (403, 429, 503)):
                print(f"\n>>> KẾT LUẬN [{name}]: BỊ CHẶN (status/HTML đáng ngờ) — CẦN PROXY VN.")
            else:
                print(f"\n>>> KẾT LUẬN [{name}]: KHÔNG RÕ — không thấy dấu hiệu chặn cụ thể, "
                      f"nhưng cũng không load được giá. Xem {name}_evidence.png để biết thêm.")
            browser.close()
            sys.exit(1)

        browser.close()


if __name__ == "__main__":
    main()