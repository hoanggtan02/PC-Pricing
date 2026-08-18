"""Thiết lập trình duyệt Playwright dùng chung.

Tập trung hóa việc khởi chạy Chromium headless và (tùy chọn) một proxy. Các trang chặn IP ngoài
Việt Nam theo vị trí địa lý (FPT Shop, Phong Vũ) cần proxy Việt Nam; truyền use_proxy=True cho
các trang đó. Các trang truy cập được từ bất kỳ đâu (CellphoneS, An Phát, HACOM, TNC) gọi với
use_proxy=False và kết nối trực tiếp.

Proxy được cấu hình qua PROXY_LIST (nhiều proxy, tự rotate khi 1 cái hết hạn) hoặc PROXY_SERVER
đơn lẻ (tương thích ngược) — xem proxy_pool.py.

── BUG ĐÃ SỬA (2026-08): proxy chết KHÔNG được thay giữa các lần retry ──────────────────────────
Playwright CHỈ set được proxy lúc `chromium.launch()` — không thể đổi proxy cho một browser đang
chạy. Trước đây `browser_page()` mở MỘT browser duy nhất cho cả lượt scrape (toàn bộ phân
trang/category), và `goto_with_retry()` khi phát hiện lỗi proxy chỉ gọi `pool.mark_dead(proxy)`
rồi RETRY TRÊN CHÍNH page/browser đó — tức là vẫn dùng lại đúng proxy vừa bị đánh dấu chết. Kết
quả thực tế: cả 3 lần thử của Phong Vũ/FPT Shop cùng dính một proxy `165.99.14.18:5432` đã hỏng,
"đổi proxy" chỉ có tác dụng ở LẦN CHẠY category/brand KẾ TIẾP (mở browser_page() mới) — quá muộn.

Sửa bằng ProxySession/browser_session(): bọc quanh page một object biết tự RELAUNCH cả browser
(đóng cái cũ, mở cái mới với proxy còn sống MỚI NHẤT từ pool) khi goto_with_retry phát hiện lỗi
proxy — relaunch xong thử lại NGAY trong cùng lượt retry, không cần đợi tới category kế tiếp.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Union

from playwright.sync_api import Page, sync_playwright

from .proxy_pool import get_pool, is_proxy_error

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class ProxySession:
    """Bọc quanh MỘT Playwright page, biết tự RELAUNCH browser với proxy khác khi proxy hiện tại
    chết. Dùng cho các trang cần proxy VN (Phong Vũ, FPT Shop) trong Mode A (weekend discovery),
    nơi một lượt scrape có thể chạy hàng chục phút và cần sống sót qua nhiều lần proxy hết hạn.

    Không tự quản lý retry — đó là việc của goto_with_retry(session, ...). Session chỉ cung cấp
    `.page` (page hiện tại) và `.rebuild()` (đóng browser cũ, mở browser mới với proxy còn sống
    mới nhất từ pool).
    """

    def __init__(self, playwright, use_proxy: bool):
        self._p = playwright
        self._use_proxy = use_proxy
        self._browser = None
        self._page = None
        self._build()

    def _build(self) -> None:
        proxy = None
        if self._use_proxy:
            proxy = get_pool().current()
            if proxy is None:
                raise RuntimeError(
                    "This site geo-blocks non-Vietnam IPs and needs a proxy, but no live proxy "
                    "is configured/available. Set PROXY_LIST (or PROXY_SERVER) in .env with a "
                    f"Vietnam proxy. Pool status: {get_pool().status()}."
                )
        self._browser = self._p.chromium.launch(headless=True, proxy=proxy)
        context = self._browser.new_context(
            user_agent=USER_AGENT, viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        # Gắn proxy hiện tại vào page để goto_with_retry đọc `page._current_proxy` mà không cần
        # truyền tay ở mọi call site — thuộc tính riêng, không phải API chuẩn của Playwright.
        page._current_proxy = proxy  # type: ignore[attr-defined]

        # Với proxy tính theo dung lượng (METERED), chặn tài nguyên nặng để giảm băng thông và
        # kéo dài hạn mức GB của proxy residential — giống hành vi cũ của browser_page().
        if self._use_proxy:
            blocked = {"image", "font", "media", "stylesheet"}
            page.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in blocked
                else route.continue_(),
            )

        self._page = page

    @property
    def page(self) -> Page:
        """Page hiện tại. LUÔN đọc qua property này (không cache biến `page` cục bộ) — sau
        rebuild(), page cũ đã bị đóng và mọi thao tác trên nó sẽ lỗi."""
        return self._page

    def rebuild(self) -> None:
        """Đóng browser hiện tại, launch lại với proxy còn sống MỚI NHẤT từ pool. Raise nếu pool
        đã hết proxy sống (get_pool().current() trả None) — caller (goto_with_retry) nên dừng
        retry khi gặp lỗi này, vì không còn proxy nào để thử tiếp."""
        old_browser = self._browser
        self._build()
        if old_browser is not None:
            try:
                old_browser.close()
            except Exception:
                pass

    def close(self) -> None:
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass


@contextmanager
def browser_session(use_proxy: bool = False):
    """Context manager yield một ProxySession — dùng thay cho browser_page() ở các trang cần
    proxy VN và muốn goto_with_retry() có thể relaunch browser giữa chừng khi proxy chết.

        with browser_session(use_proxy=True) as session:
            goto_with_retry(session, url, selector, label="Phong Vũ")
            page = session.page   # đọc LẠI mỗi lần dùng, phòng vừa bị rebuild
            ...
    """
    with sync_playwright() as p:
        session = ProxySession(p, use_proxy)
        try:
            yield session
        finally:
            session.close()


def goto_with_retry(
    page_or_session: Union[Page, ProxySession],
    url: str,
    wait_selector: str,
    *,
    attempts: int = 5,
    goto_timeout: int = 60000,
    selector_timeout: int = 20000,
    label: str = "",
) -> bool:
    """Tải `url` rồi chờ `wait_selector` xuất hiện, thử lại tối đa `attempts` lần trước khi bỏ cuộc.

    Trả về True nếu selector xuất hiện (trang tải OK), False nếu đã hết số lần thử. Việc thử lại xử
    lý các lỗi tải trang tạm thời (mạng chậm, proxy chập chờn) vốn là nguyên nhân chính khiến một
    lần chạy scraper trả về 0 kết quả một cách âm thầm. In WARNING mỗi lần thất bại để phân biệt
    "trang lỗi" với "thực sự không có sản phẩm nào".

    `page_or_session` chấp nhận HAI dạng (tương thích ngược, không phải sửa mọi call site):
      • một Playwright Page trần (hành vi CŨ) — dùng cho các trang không cần proxy, hoặc các
        scraper tự tạo page qua sync_playwright trực tiếp (HACOM, An Phát, CellphoneS, TNC). Khi
        lỗi là lỗi PROXY thật, hàm này vẫn mark_dead() proxy trong pool như cũ, nhưng KHÔNG relaunch
        được (Playwright không đổi proxy cho browser đang chạy) — proxy khác chỉ có hiệu lực ở lần
        browser_page()/browser_session() TIẾP THEO (category/brand kế tiếp trong cùng lượt chạy).
      • một ProxySession (browser_session()) — dùng cho các trang cần proxy VN (Phong Vũ, FPT
        Shop) trong Mode A. Khi lỗi là lỗi PROXY thật, hàm này gọi session.rebuild() để RELAUNCH
        browser với proxy còn sống mới nhất NGAY TRONG lượt retry hiện tại, rồi thử lại — không
        cần đợi tới category/brand kế tiếp mới đổi được proxy (đây là fix cho bug cùng một proxy
        chết bị dùng lại 3 lần liên tiếp).
    """
    is_session = hasattr(page_or_session, "rebuild")
    tag = f"[{label}] " if label else ""
    for attempt in range(1, attempts + 1):
        page = page_or_session.page if is_session else page_or_session
        proxy = getattr(page, "_current_proxy", None)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=goto_timeout)
            page.wait_for_selector(wait_selector, timeout=selector_timeout)
            return True
        except Exception as e:
            msg = str(e).splitlines()[0][:120]
            print(f"  {tag}WARNING: lần tải {attempt}/{attempts} thất bại ({msg})")
            proxy_dead = proxy is not None and is_proxy_error(msg)
            if proxy_dead:
                get_pool().mark_dead(proxy)
            if attempt >= attempts:
                break
            if proxy_dead and is_session:
                print(f"  {tag}🔄 Proxy chết — relaunch browser với proxy khác rồi thử lại ngay...")
                try:
                    page_or_session.rebuild()
                    continue  # thử ngay với proxy mới; không cần nghỉ 2s như nhánh dưới
                except Exception as rebuild_err:
                    print(f"  {tag}WARNING: relaunch browser thất bại ({rebuild_err}) — "
                          f"có thể đã hết proxy sống trong pool.")
                    break
            page.wait_for_timeout(2000)  # nghỉ ngắn trước khi thử lại (lỗi không phải do proxy)
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


@contextmanager
def browser_page(use_proxy: bool = False):
    """Yield một Playwright page sẵn sàng sử dụng (viewport desktop, proxy VN tùy chọn).

    LƯU Ý: context manager này KHÔNG có khả năng relaunch browser khi proxy chết giữa chừng — nếu
    proxy hỏng, goto_with_retry() chỉ mark_dead() được (xem docstring của nó), proxy khác chỉ có
    hiệu lực ở lần browser_page() TIẾP THEO. Với các trang cần proxy VN và muốn sống sót qua nhiều
    lần proxy hết hạn TRONG CÙNG một lượt scrape (một category/brand chạy lâu, nhiều trang phân
    trang), dùng browser_session() thay thế — nó cho goto_with_retry() relaunch được ngay lập tức.

    Khi use_proxy=True: lấy proxy HIỆN TẠI từ pool dùng chung (proxy_pool.get_pool()).

    Throw RuntimeError nếu use_proxy=True nhưng pool rỗng (chưa cấu hình PROXY_LIST/PROXY_SERVER)
    hoặc mọi proxy trong pool đã bị đánh dấu chết, để một scraper bị chặn theo vị trí địa lý báo
    lỗi rõ ràng thay vì âm thầm nhận lỗi 403/407.
    """
    proxy = None
    if use_proxy:
        pool = get_pool()
        proxy = pool.current()
        if proxy is None:
            raise RuntimeError(
                "This site geo-blocks non-Vietnam IPs and needs a proxy, but no live proxy is "
                "configured/available. Set PROXY_LIST (or PROXY_SERVER) in .env with a Vietnam "
                f"proxy. Pool status: {pool.status()}."
            )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, proxy=proxy)
        context = browser.new_context(user_agent=USER_AGENT, viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page._current_proxy = proxy  # type: ignore[attr-defined]

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