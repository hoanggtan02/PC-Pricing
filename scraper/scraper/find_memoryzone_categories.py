"""Dò menu điều hướng của memoryzone.com.vn để tìm URL category THẬT cho từng danh mục hệ thống
(giống cách bạn đã xác minh URL GearVN — xem ghi chú "đã xác minh 2026-09" trong sources.yaml).

VÌ SAO CẦN SCRIPT NÀY: `scraper/config/sources.yaml` hiện chỉ có đúng 1 entry
`paths.memoryzone` (cho category "software"). Mọi category khác (ram, ssd, mainboard, cpu, vga,
router, ...) chưa có URL category thật của Memoryzone — cần dò thủ công từ menu điều hướng của
site rồi điền tay vào sources.yaml (không tự đoán/bịa URL vì dễ trỏ nhầm trang).

CÁCH DÙNG (chạy TRÊN MÁY CÓ MẠNG RA NGOÀI — sandbox trò chuyện này KHÔNG có egress tới
memoryzone.com.vn nên không tự chạy được):
    cd scraper
    pip install httpx beautifulsoup4      # nếu chưa có sẵn trong requirements.txt
    python find_memoryzone_categories.py

Kết quả in ra:
  1. TOÀN BỘ link trong menu điều hướng (text hiển thị + href) — để bạn tự soát bằng mắt.
  2. Một bảng GỢI Ý khớp mỗi category hệ thống (lấy từ scraper/config/sources.yaml) với các link
     menu có vẻ liên quan nhất, dựa trên so khớp từ khóa đơn giản (không phải chắc chắn đúng —
     luôn xác nhận bằng mắt trước khi điền vào sources.yaml, đặc biệt các category dễ nhầm như
     "ram" vs "ram-laptop", "ssd" vs "o-cung-gan-ngoai").
  3. Danh sách category hệ thống KHÔNG tìm được gợi ý nào — Memoryzone có thể không bán mục đó,
     hoặc tên menu khác xa từ khóa category (cần bạn tự tìm tay).

Sau khi có URL đúng, thêm vào scraper/config/sources.yaml dạng:
    categories:
      ram:
        paths:
          memoryzone: "https://memoryzone.com.vn/<slug-thật>"
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://memoryzone.com.vn"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# Từ khóa gợi ý khớp category hệ thống -> menu Memoryzone. Không đọc từ sources.yaml (không muốn
# phụ thuộc PyYAML/import nội bộ scraper package cho một script debug độc lập) — liệt kê tay,
# đồng bộ tinh thần với name_match trong sources.yaml. Cập nhật danh sách này nếu hệ thống có
# thêm/bớt category.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "monitor": ["màn hình", "man hinh", "monitor", "lcd"],
    "cpu": ["cpu", "vi xử lý", "vi xu ly"],
    "vga": ["vga", "card màn hình", "card man hinh", "card đồ họa"],
    "mainboard": ["mainboard", "bo mạch chủ", "bo mach chu", "main"],
    "printer": ["máy in", "may in", "printer"],
    "scanner": ["máy scan", "may scan", "scanner"],
    "ups": ["ups", "lưu điện", "luu dien"],
    "projector": ["máy chiếu", "may chieu", "projector"],
    "tv": ["tivi", "tv"],
    "tablet": ["máy tính bảng", "may tinh bang", "tablet", "ipad"],
    "ram": ["ram"],
    "ssd": ["ssd"],
    "hdd": ["hdd", "ổ cứng", "o cung"],
    "keyboard": ["bàn phím", "ban phim", "keyboard"],
    "mouse": ["chuột", "chuot", "mouse"],
    "combo": ["combo"],
    "webcam": ["webcam"],
    "usb": ["usb"],
    "memcard": ["thẻ nhớ", "the nho"],
    "box": ["box", "docking", "hộp ổ cứng", "hop o cung"],
    "router": ["router", "phát wifi", "phat wifi", "bộ phát", "bo phat"],
    "switch": ["switch"],
    "accesspoint": ["access point"],
    "wlan_controller": ["controller", "wlan"],
    "pc": ["máy bộ", "may bo", "pc", "máy tính để bàn", "may tinh de ban"],
    "workstation": ["workstation", "máy trạm", "may tram"],
    "server": ["server", "máy chủ", "may chu"],
    "software": ["phần mềm", "phan mem", "bản quyền", "ban quyen"],
    "camera": ["camera"],
    "audio": ["tai nghe", "loa", "microphone", "headphone"],
}


def fetch_nav_links() -> list[tuple[str, str]]:
    """Trả về [(text, absolute_url)] từ MỌI thẻ <a> trong <header>/<nav> của trang chủ.

    Memoryzone chạy theme Bizweb/Sapo (xem ghi chú trong discover_memoryzone.py) — menu điều
    hướng thường SSR sẵn trong HTML (không cần Playwright), nhưng nếu site đổi sang render menu
    bằng JS, script này sẽ trả về danh sách rỗng/thiếu — khi đó cần đổi sang Playwright
    (browser_page() có sẵn trong scraper/scraper/browser.py) thay vì httpx.
    """
    resp = httpx.get(BASE_URL, headers=HEADERS, timeout=20, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Thử phạm vi hẹp trước (header/nav thật), rơi xuống toàn trang nếu không tìm thấy gì — một
    # số theme đặt menu ngoài thẻ <nav> chuẩn (ví dụ trong <div id="header">).
    scopes = soup.select("header, nav, #header, .header, .main-nav, .menu")
    seen: set[str] = set()
    out: list[tuple[str, str]] = []

    def _collect(container) -> None:
        for a in container.select("a[href]"):
            href = (a.get("href") or "").strip()
            text = a.get_text(strip=True)
            if not href or href.startswith("#") or href.startswith("javascript"):
                continue
            if not text:
                continue
            abs_url = urljoin(BASE_URL, href)
            key = (text.lower(), abs_url)
            if key in seen:
                continue
            seen.add(key)
            out.append((text, abs_url))

    if scopes:
        for scope in scopes:
            _collect(scope)
    if not out:
        print("⚠️  Không tìm thấy link trong header/nav — quét TOÀN TRANG thay thế "
              "(kết quả sẽ nhiễu hơn, cần lọc tay kỹ hơn).")
        _collect(soup)

    # Chỉ giữ link cùng domain (loại mạng xã hội / link ngoài).
    out = [(t, u) for t, u in out if u.startswith(BASE_URL)]
    return out


def suggest_matches(links: list[tuple[str, str]]) -> dict[str, list[tuple[str, str]]]:
    suggestions: dict[str, list[tuple[str, str]]] = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        matches = []
        for text, url in links:
            hay = f"{text} {url}".lower()
            if any(kw in hay for kw in keywords):
                matches.append((text, url))
        if matches:
            suggestions[cat] = matches
    return suggestions


def main() -> int:
    print(f"Đang tải {BASE_URL} để dò menu điều hướng...\n")
    try:
        links = fetch_nav_links()
    except Exception as e:
        print(f"❌ Lỗi tải trang: {e}")
        print("Nếu đây là lỗi mạng/bị chặn bot, thử đổi User-Agent hoặc dùng Playwright "
              "(browser_page() trong scraper/scraper/browser.py) thay cho httpx.")
        return 1

    if not links:
        print("❌ Không tìm thấy link menu nào — site có thể render menu bằng JS. "
              "Cần đổi script này sang dùng Playwright (xem debug_gearvn.py làm ví dụ).")
        return 1

    print(f"== TOÀN BỘ {len(links)} link menu tìm thấy ==")
    for text, url in links:
        print(f"  {text:35s} -> {url}")

    suggestions = suggest_matches(links)
    print(f"\n== GỢI Ý khớp category hệ thống ({len(suggestions)}/{len(CATEGORY_KEYWORDS)}) ==")
    for cat in CATEGORY_KEYWORDS:
        matches = suggestions.get(cat)
        if not matches:
            continue
        print(f"\n  [{cat}]")
        for text, url in matches:
            print(f"    - {text:30s} -> {url}")

    missing = [c for c in CATEGORY_KEYWORDS if c not in suggestions]
    if missing:
        print(f"\n== KHÔNG tìm được gợi ý nào cho {len(missing)} category (cần tự tìm tay) ==")
        for c in missing:
            print(f"  - {c}")

    print(
        "\nLƯU Ý: đây chỉ là GỢI Ý dựa trên so khớp từ khóa đơn giản, không chắc chắn đúng. "
        "Xác nhận bằng mắt (mở URL, xem có đúng card sản phẩm của category đó không — giống cách "
        "bạn đã xác minh URL GearVN) trước khi điền vào scraper/config/sources.yaml."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())