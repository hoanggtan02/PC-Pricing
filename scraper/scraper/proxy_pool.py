"""Pool nhiều proxy VN với tự động chuyển proxy khác khi proxy hiện tại hết hạn/lỗi.

Vì sao cần: PROXY_SERVER cũ chỉ khai báo MỘT proxy — hết hạn là mọi scraper cần proxy VN
(FPT Shop, Phong Vũ, TGĐĐ) chết theo cả lượt chạy. Module này đọc một DANH SÁCH proxy từ
PROXY_LIST, và khi một proxy bị lỗi kết nối (hết hạn/sập), tự đánh dấu "dead" trong lượt chạy
này rồi chuyển sang proxy kế tiếp còn sống — không cần sửa code scraper, không cần chờ người
canh log rồi đổi tay.

Format PROXY_LIST (.env / GitHub Secret), mỗi proxy cách nhau ";" (cũng chấp nhận "," hoặc xuống
dòng — tiện khi dán một danh sách IP:PORT thô từ nhà cung cấp):

    # Không cần username/password (proxy IP trần, mỗi IP tự có port riêng — dạng phổ biến nhất):
    PROXY_LIST=116.96.32.160:8080;113.160.132.26:3128;14.241.231.13:1080

    # Có username/password (thêm "|user|pass" sau mỗi host:port):
    PROXY_LIST=http://host1:port|user1|pass1;http://host2:port|user2|pass2

Không cần ghi tiền tố "http://" — nếu thiếu, module tự thêm vào (Playwright bắt buộc phải có
scheme trong proxy.server).

Tương thích ngược: nếu PROXY_LIST trống, dùng PROXY_SERVER/PROXY_USERNAME/PROXY_PASSWORD cũ
làm danh sách 1 proxy.

Cách dùng:
    from .proxy_pool import get_pool
    pool = get_pool()
    proxy = pool.current()          # {"server":..., "username":..., "password":...} | None
    ...
    pool.mark_dead(proxy)           # gọi khi request qua proxy này bị lỗi kết nối
    proxy = pool.current()          # lần đọc kế tiếp tự trả về proxy khác (nếu còn)
"""

from __future__ import annotations

import functools
import os
import re
import threading

from dotenv import load_dotenv

load_dotenv()

# Các chuỗi lỗi cho thấy PROXY chết (hết hạn/quota/sập) chứ không phải trang đích lỗi. Dùng để
# quyết định có nên mark_dead + rotate hay không (lỗi trang đích thì đổi proxy cũng vô ích).
PROXY_ERROR_MARKERS = (
    "ERR_TUNNEL_CONNECTION_FAILED",
    "ERR_PROXY_CONNECTION_FAILED",
    "ERR_NO_SUPPORTED_PROXIES",
    "ERR_SOCKS_CONNECTION_FAILED",
    "ERR_CONNECTION_RESET",
    "407",  # Proxy Authentication Required — thường là hết hạn/sai quota
)


def is_proxy_error(exc_msg: str) -> bool:
    """True nếu thông báo lỗi cho thấy PROXY chết (nên rotate), không phải lỗi trang đích."""
    return any(marker in exc_msg for marker in PROXY_ERROR_MARKERS)


class ProxyPool:
    """Danh sách proxy với con trỏ "proxy hiện tại" và khả năng loại proxy chết khỏi vòng quay.

    Thread-safe ở mức tối thiểu (Lock) vì sync_prices.py chạy nhiều worker asyncio có thể cùng
    gọi mark_dead() gần như đồng thời khi proxy vừa hết hạn giữa lượt chạy.
    """

    def __init__(self, proxies: list[dict]):
        self._all = proxies
        self._dead: set[int] = set()  # index trong self._all đã bị đánh dấu chết
        self._idx = 0
        self._lock = threading.Lock()

    def current(self) -> dict | None:
        """Proxy đang dùng, hoặc None nếu không còn proxy nào sống (hoặc danh sách rỗng)."""
        with self._lock:
            if not self._all:
                return None
            n = len(self._all)
            for step in range(n):
                i = (self._idx + step) % n
                if i not in self._dead:
                    self._idx = i
                    return self._all[i]
            return None  # mọi proxy đều đã chết

    def mark_dead(self, proxy: dict | None) -> None:
        """Đánh dấu một proxy là chết (hết hạn/lỗi kết nối) — vòng quay sẽ bỏ qua nó."""
        if proxy is None:
            return
        with self._lock:
            for i, p in enumerate(self._all):
                if p == proxy:
                    if i not in self._dead:
                        self._dead.add(i)
                        print(f"  ⚠️  PROXY hết hạn/lỗi, loại khỏi vòng quay: {p['server']} "
                              f"({len(self._dead)}/{len(self._all)} proxy đã chết)")
                    self._idx = (i + 1) % len(self._all)  # lần sau bắt đầu từ proxy kế tiếp
                    break

    def has_live_proxy(self) -> bool:
        with self._lock:
            return len(self._dead) < len(self._all)

    def status(self) -> str:
        with self._lock:
            return f"{len(self._all) - len(self._dead)}/{len(self._all)} proxy còn sống"


_SPLIT_RE = re.compile(r"[;,\n\r]+")  # chấp nhận ";", ",", hoặc xuống dòng giữa các proxy


def _normalize_server(server: str) -> str:
    """Thêm scheme "http://" nếu thiếu — Playwright BẮT BUỘC proxy.server phải có scheme
    (vd "http://1.2.3.4:8080"); một IP:PORT trần dán thẳng từ nhà cung cấp sẽ bị Playwright từ
    chối nếu không có bước chuẩn hoá này."""
    return server if "://" in server else f"http://{server}"


def _parse_proxy_list(raw: str) -> list[dict]:
    proxies = []
    for entry in _SPLIT_RE.split(raw):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split("|")
        server = _normalize_server(parts[0].strip())
        if not server or server in ("http://", "https://"):
            continue
        cfg = {"server": server}
        if len(parts) > 1 and parts[1].strip():
            cfg["username"] = parts[1].strip()
        if len(parts) > 2 and parts[2].strip():
            cfg["password"] = parts[2].strip()
        proxies.append(cfg)
    return proxies


def _load_proxies() -> list[dict]:
    raw_list = os.environ.get("PROXY_LIST", "").strip()
    if raw_list:
        return _parse_proxy_list(raw_list)

    # Tương thích ngược: PROXY_SERVER đơn lẻ -> danh sách 1 proxy.
    server = os.environ.get("PROXY_SERVER", "").strip()
    if not server:
        return []
    cfg = {"server": _normalize_server(server)}
    user = os.environ.get("PROXY_USERNAME", "").strip()
    pwd = os.environ.get("PROXY_PASSWORD", "").strip()
    if user:
        cfg["username"] = user
        cfg["password"] = pwd
    return [cfg]


@functools.lru_cache(maxsize=1)
def get_pool() -> ProxyPool:
    """Pool dùng chung cho cả lượt chạy (một process). lru_cache đảm bảo mọi scraper/worker
    trong cùng process CHIA SẺ cùng một trạng thái "proxy nào đã chết" — proxy hết hạn ở
    discover_fptshop sẽ không bị dùng lại ở discover_phongvu trong cùng lượt chạy."""
    return ProxyPool(_load_proxies())