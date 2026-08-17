"""Chẩn đoán nhanh trang GearVN — dump title/status, kiểm tra dấu hiệu bị chặn bot, và đếm số
phần tử khớp một loạt selector ứng viên (giá/tên/card sản phẩm). Dùng để tìm ra vì sao
Page.wait_for_selector('.proloop-price') timeout trong discover_gearvn.py — hoặc do GearVN đã đổi
class CSS (site redesign), hoặc do trang bị chặn/che bởi bot-check.

Cách dùng (từ thư mục scraper/):
    python debug_gearvn.py
    python debug_gearvn.py "https://gearvn.com/search?q=laptop%20dell"

Kết quả: in ra console + lưu 2 file evidence (gearvn_evidence.png, gearvn_evidence.html) để xem
thêm nếu cần. Không cần DB, không cần proxy.
"""

from __future__ import annotations

import re
import sys

from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Selector hiện tại của scraper (.proloop-price) + một loạt ứng viên phổ biến khác của theme
# Shopify (gearvn.com chạy trên Shopify — url dạng /collections/.../products/...), để nếu
# .proloop-price đã đổi tên thì ta thấy ngay class mới đang dùng là gì.
CANDIDATE_SELECTORS = [
    ".proloop-price",              # selector hiện tại trong discover_gearvn.py
    ".proloop-price--highlight",
    ".proloop-price--default",
    ".proloop-name",
    ".price",
    ".price-item",
    ".price__regular",
    "[class*='price']",
    "[class*='proloop']",
    ".product-item",
    "[class*='product-item']",
    "a[href*='/products/']",
]

_BLOCK_SIGNS = re.compile(
    r"just a moment|attention required|access denied|are you a human|"
    r"checking your browser|cloudflare|forbidden|captcha|một chút nữa|xin chờ|"
    r"verify you are human|bot detected",
    re.IGNORECASE,
)


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else "https://gearvn.com/collections/cpu-bo-vi-xu-ly"
    print(f"URL: {url}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT, viewport={"width": 1920, "height": 1080})

        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            status = resp.status if resp else None
        except Exception as e:
            print(f"❌ goto() LỖI: {e}")
            browser.close()
            sys.exit(1)

        page.wait_for_timeout(4000)  # chờ thêm cho JS render xong (lazy content nếu có)

        title = page.title()
        html = page.content()
        blocked = bool(_BLOCK_SIGNS.search(title or "")) or bool(_BLOCK_SIGNS.search(html[:8000]))

        print(f"HTTP status : {status}")
        print(f"Page title  : {title!r}")
        print(f"Nghi bị chặn bot (title/html): {blocked}")
        print(f"Độ dài HTML : {len(html):,} ký tự\n")

        print("== Đếm phần tử theo từng selector ứng viên ==")
        for sel in CANDIDATE_SELECTORS:
            try:
                count = page.eval_on_selector_all(sel, "(els) => els.length")
            except Exception as e:
                count = f"lỗi: {e}"
            marker = "  ⭐" if isinstance(count, int) and count > 0 else ""
            print(f"  {sel:32s} -> {count}{marker}")

        # Thử cuộn xuống để kích hoạt lazy-load, rồi đếm lại .proloop-price xem có đổi không.
        for _ in range(5):
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(800)
        after_scroll = page.eval_on_selector_all(".proloop-price", "(els) => els.length")
        print(f"\n.proloop-price SAU khi cuộn: {after_scroll}")

        page.screenshot(path="gearvn_evidence.png", full_page=True)
        with open("gearvn_evidence.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("\nĐã lưu gearvn_evidence.png và gearvn_evidence.html để xem thêm nếu cần.")

        browser.close()


if __name__ == "__main__":
    main()