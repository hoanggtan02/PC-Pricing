"""Thiết lập trình duyệt Playwright dùng chung.

Tập trung hóa việc khởi chạy Chromium headless và (tùy chọn) một proxy. Các trang chặn IP ngoài
Việt Nam theo vị trí địa lý (FPT Shop, Phong Vũ) cần proxy Việt Nam; truyền use_proxy=True cho
các trang đó. Các trang truy cập được từ bất kỳ đâu (CellphoneS, An Phát, HACOM, TNC) gọi với
use_proxy=False và kết nối trực tiếp.

Proxy được cấu hình qua biến môi trường (xem .env): PROXY_SERVER, PROXY_USERNAME, PROXY_PASSWORD.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

load_dotenv()

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def goto_with_retry(
    page: Page,
    url: str,
    wait_selector: str,
    *,
    attempts: int = 3,
    goto_timeout: int = 60000,
    selector_timeout: int = 20000,
    label: str = "",
) -> bool:
    """Tải `url` rồi chờ `wait_selector` xuất hiện, thử lại tối đa `attempts` lần trước khi bỏ cuộc.

    Trả về True nếu selector xuất hiện (trang tải OK), False nếu đã hết số lần thử. Việc thử lại xử
    lý các lỗi tải trang tạm thời (mạng chậm, proxy chập chờn) vốn là nguyên nhân chính khiến một
    lần chạy scraper trả về 0 kết quả một cách âm thầm. In WARNING mỗi lần thất bại để phân biệt
    "trang lỗi" với "thực sự không có sản phẩm nào".
    """
    tag = f"[{label}] " if label else ""
    for attempt in range(1, attempts + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=goto_timeout)
            page.wait_for_selector(wait_selector, timeout=selector_timeout)
            return True
        except Exception as e:
            msg = str(e).splitlines()[0][:80]
            print(f"  {tag}WARNING: lần tải {attempt}/{attempts} thất bại ({msg})")
            if attempt < attempts:
                page.wait_for_timeout(2000)  # nghỉ ngắn trước khi thử lại
    print(f"  {tag}WARNING: bỏ qua sau {attempts} lần thử — có thể là lỗi tạm thời, không phải 0 thật")
    return False


class StaleSelectorError(RuntimeError):
    """Trang tải OK và có card sản phẩm, nhưng KHÔNG parse được món nào — nhiều khả năng competitor
    đã đổi cấu trúc HTML (đổi tên class, dựng lại layout). Khác với '0 thật' (trang không có card)."""


def assert_parsed(competitor: str, card_count: int, parsed_count: int) -> None:
    """Báo lỗi lớn nếu trang có card nhưng parse ra 0 sản phẩm — dấu hiệu selector bên trong đã
    lỗi thời do site được thiết kế lại. Gọi sau vòng lặp parse của mỗi scraper.

    - card_count == 0  -> trang thật sự không có sản phẩm (0 thật), không báo lỗi.
    - parsed_count > 0 -> parse bình thường, không báo lỗi.
    - card_count > 0 và parsed_count == 0 -> raise StaleSelectorError để lần chạy thất bại rõ ràng
      (exit khác 0), giúp CI/giám sát bắt được ngay thay vì âm thầm trả 0 hàng ngày.

    QUAN TRỌNG — `parsed_count` phải là số card trích được name+price HỢP LỆ, TRƯỚC khi lọc theo
    brand/loại sản phẩm. Nếu truyền vào số đã-lọc, một kết quả "0 thật" hợp lệ (ví dụ HACOM không
    bán Dell) sẽ bị báo nhầm là selector lỗi. Vì vậy hiện chỉ dùng ở các scraper lọc brand SAU khi
    parse (CellphoneS, An Phát). Các scraper lọc ngay trong JS (HACOM/GearVN/Memoryzone/Phong Vũ/
    TGDĐ/FPT) cần được sửa để JS báo thêm "số card có giá parse được" trước khi áp dụng ở đây.
    """
    if card_count > 0 and parsed_count == 0:
        raise StaleSelectorError(
            f"[{competitor}] tìm thấy {card_count} card nhưng parse được 0 sản phẩm — "
            f"selector có thể đã lỗi thời (competitor đổi cấu trúc trang?)."
        )


def _proxy_config() -> dict | None:
    server = os.environ.get("PROXY_SERVER", "").strip()
    if not server:
        return None
    cfg: dict = {"server": server}
    user = os.environ.get("PROXY_USERNAME", "").strip()
    pwd = os.environ.get("PROXY_PASSWORD", "").strip()
    if user:
        cfg["username"] = user
        cfg["password"] = pwd
    return cfg


@contextmanager
def browser_page(use_proxy: bool = False):
    """Yield một Playwright page sẵn sàng sử dụng (viewport desktop, proxy VN tùy chọn).

    Throw RuntimeError nếu use_proxy=True nhưng chưa cấu hình PROXY_SERVER, để một scraper bị
    chặn theo vị trí địa lý báo lỗi rõ ràng thay vì âm thầm nhận lỗi 403.
    """
    # ── OFF-SWITCH khi chạy trên server ĐẶT TẠI VIỆT NAM (xem docs/proxy.md) ─────────────────────
    """ 
    if os.environ.get("PROXY_DISABLED", "").strip() in ("1", "true", "yes"):
         use_proxy = False
    """

    proxy = _proxy_config() if use_proxy else None
    if use_proxy and proxy is None:
        raise RuntimeError(
            "This site geo-blocks non-Vietnam IPs and needs a proxy, but PROXY_SERVER is not set "
            "in .env. Configure a Vietnam proxy to scrape it."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, proxy=proxy)
        context = browser.new_context(user_agent=USER_AGENT, viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        # Với proxy tính theo dung lượng (METERED), chặn các tài nguyên nặng (giá/link đã nằm
        # trong HTML+JS) để giảm ~60-80% băng thông và kéo dài hạn mức GB của proxy residential.
        if use_proxy:
            blocked = {"image", "font", "media", "stylesheet"}
            page.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in blocked
                else route.continue_(),
            )

        try:
            yield page
        finally:
            browser.close()
