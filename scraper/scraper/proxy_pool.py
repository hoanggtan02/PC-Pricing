"""Pool nhiều proxy VN với tự động chuyển proxy khác khi proxy hiện tại hết hạn/lỗi.

Vì sao cần: PROXY_SERVER cũ chỉ khai báo MỘT proxy — hết hạn là mọi scraper cần proxy VN
(FPT Shop, Phong Vũ, TGĐĐ) chết theo cả lượt chạy. Module này đọc một DANH SÁCH proxy, và khi một
proxy bị lỗi kết nối (hết hạn/sập), tự đánh dấu "dead" trong lượt chạy này rồi chuyển sang proxy kế
tiếp còn sống — không cần sửa code scraper, không cần chờ người canh log rồi đổi tay.

NGUỒN proxy, theo thứ tự ưu tiên (xem _load_proxies()):
  1. TỰ ĐỘNG TẢI VÀ GỘP proxy VN MIỄN PHÍ từ CÁC nguồn độc lập (BẬT SẴN, không cần cấu hình gì thêm):
       a. ProxyScrape VN: text thuần "ip:port" mỗi dòng.
       b. Proxifly VN: danh sách proxy VN cập nhật liên tục hàng giờ trên GitHub (hàng trăm proxy).
       c. Geonode VN: API proxy VN với nhiều protocol (HTTP, HTTPS, SOCKS5).
       d. FineProxy / Databay VN (dự phòng).
     Gộp (union, dedupe theo "ip:port") và tự động HEALTH CHECK trực tiếp với FPT Shop / Thế Giới Di Động,
     chỉ giữ lại các proxy sống, phản hồi nhanh (<4.0s) để đưa vào pool cào.
  2. PROXY_SERVER đơn lẻ (tương thích ngược) — dự phòng khi tất cả nguồn tự tải đều lỗi/rỗng hoặc bị tắt.

  (Đã bỏ PROXY_LIST tĩnh — không dùng, luôn để trống trong thực tế. Nếu sau này cần dán tay một
  danh sách proxy trả phí, dùng lại _parse_proxy_list()/PROXY_SCRAPE_URL trỏ tới một endpoint tự
  host trả về đúng format text "ip:port" mỗi dòng, thay vì thêm lại biến môi trường riêng.)

Vì get_pool() cache theo process (lru_cache), việc "tự động tải mỗi lần cào" tự nhiên xảy ra:
mỗi lượt chạy scraper (mỗi job CI, mỗi lần chạy `python -m scraper...`) là MỘT process mới nên sẽ
tự gọi lại cả ba nguồn để lấy danh sách MỚI, không cần cache thủ công giữa các lượt chạy.

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
import json
import os
from pathlib import Path
import re
import threading
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

# Các chuỗi lỗi cho thấy PROXY chết (hết hạn/quota/sập/TREO) chứ không phải trang đích lỗi. Dùng để
# quyết định có nên mark_dead + rotate hay không (lỗi trang đích thì đổi proxy cũng vô ích).
#
# "Timeout" ĐƯỢC THÊM Ở ĐÂY (trước đây thiếu — bug thật): page.goto(..., wait_until="commit") chỉ
# cần nhận header đầu tiên của response, nên nếu nó timeout sau 30s thì gần như chắc chắn là PROXY
# bị treo/quá tải/hết quota (kết nối không bao giờ commit được), KHÔNG PHẢI trang đích chậm thật.
# Trước khi thêm "Timeout" vào đây: log ở sync_prices.py vẫn IN ra đúng là "[HẠ TẦNG/MẠNG]" (nhãn đó
# có check "Timeout" riêng), nhưng is_proxy_error() (dùng để quyết định mark_dead) lại KHÔNG nhận
# diện "Timeout" — nên proxy treo không bao giờ bị loại khỏi vòng quay, và MỌI source proxy tiếp
# theo trong lượt chạy (TGDD/FPT Shop/Phong Vũ) tiếp tục dùng lại đúng proxy đã treo đó, timeout lặp
# lại hàng loạt, mỗi cái tốn nguyên 30s chờ vô ích thay vì rotate ngay sang proxy sống.
#
# "ERR_TIMED_OUT" ĐƯỢC THÊM Ở ĐÂY (bug thật thứ 2, phát hiện 2026-08 từ log TGDD 100% fail): lỗi
# thực tế Chromium/Playwright ném ra khi proxy KHÔNG BAO GIỜ trả lời là "net::ERR_TIMED_OUT" —
# chuỗi này KHÔNG chứa chuỗi con "Timeout" (khác cách viết: "TIMED_OUT" viết hoa toàn bộ và tách
# chữ khác với "Timeout"). Vì is_proxy_error() dùng khớp CHUỖI CON đơn giản (không phân biệt hoa
# thường), "ERR_TIMED_OUT" lọt qua mọi marker cũ → is_proxy_error() luôn trả False cho lỗi này →
# mark_dead() KHÔNG BAO GIỜ được gọi → proxy chết bị dùng lại cho MỌI source còn lại trong hàng đợi,
# mỗi source ăn đủ 30s timeout rồi fail — đúng triệu chứng "100% fail liên tục, không thấy dòng
# 🔄 Đổi sang proxy nào" trong log thực tế của TGDD.
PROXY_ERROR_MARKERS = (
    "ERR_TUNNEL_CONNECTION_FAILED",
    "ERR_PROXY_CONNECTION_FAILED",
    "ERR_NO_SUPPORTED_PROXIES",
    "ERR_SOCKS_CONNECTION_FAILED",
    "ERR_CONNECTION_RESET",
    "ERR_CONNECTION_REFUSED",
    "ERR_CONNECTION_CLOSED",
    "ERR_TIMED_OUT",          # net::ERR_TIMED_OUT — proxy không bao giờ trả lời (bug đã sửa)
    "ERR_EMPTY_RESPONSE",
    "407",  # Proxy Authentication Required — thường là hết hạn/sai quota
    "Timeout",  # page.goto/wait_for_selector treo — proxy không commit được kết nối
)


def is_proxy_error(exc_msg: str) -> bool:
    """True nếu thông báo lỗi cho thấy PROXY chết (nên rotate), không phải lỗi trang đích.

    So khớp KHÔNG phân biệt hoa/thường — tránh lặp lại đúng bug đã gặp (marker "Timeout" không
    khớp "ERR_TIMED_OUT" vì khác cách viết hoa/thường + khác chữ). Dùng .upper() cho cả 2 vế để
    marker nào thêm sau này cũng an toàn dù ai đó gõ hoa/thường khác nhau.
    """
    msg_upper = exc_msg.upper()
    return any(marker.upper() in msg_upper for marker in PROXY_ERROR_MARKERS)


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

    def next_proxy(self) -> dict | None:
        """Lấy proxy theo vòng tròn (Round-Robin) và nhảy con trỏ sang proxy kế tiếp.
        Dùng để phân phối đều danh sách proxy cho nhiều request/page khác nhau, tránh
        dồn tất cả request vào cùng 1 proxy làm nó bị quá tải hoặc Cloudflare chặn.
        """
        with self._lock:
            if not self._all:
                return None
            n = len(self._all)
            for step in range(n):
                i = (self._idx + step) % n
                if i not in self._dead:
                    self._idx = (i + 1) % n  # Tịnh tiến tới vị trí tiếp theo
                    return self._all[i]
            return None

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



DEFAULT_PROXYSCRAPE_URL = (
    "https://api.proxyscrape.com/v4/free-proxy-list/get"
    "?request=display_proxies&proxy_format=ipport&format=text&country=vn"
)

DEFAULT_GEONODE_URL = (
    "https://proxylist.geonode.com/api/proxy-list"
    "?country=VN&limit=100&page=1&sort_by=lastChecked&sort_type=desc"
)

DEFAULT_PROXIFLY_URL = (
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/VN/data.txt"
)

DEFAULT_FINEPROXY_URL = "https://fineproxy.org/vi/wp-json/fineproxy/v1/free-proxies/vn"

DEFAULT_DATABAY_URL = "https://databay.com/api/v1/proxy-list?country=VN"


def _fetch_remote_proxy_list(url: str, timeout: float = 10.0) -> str:
    """Tải danh sách proxy thô (text) từ một API công khai. KHÔNG raise khi lỗi (mạng chập chờn /
    API rate-limit / timeout) — trả về chuỗi rỗng để caller lặng lẽ rơi xuống nguồn khác thay vì
    làm sập cả lượt chạy CI chỉ vì một API bên thứ ba tạm thời không phản hồi.
    """
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"  ⚠️  Không tải được danh sách proxy tự động ({url}): {e}")
        return ""


def _parse_geonode_response(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []

    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []

    proxies = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        ip, port = r.get("ip"), r.get("port")
        if not ip or not port:
            continue
        protocols = [p.lower() for p in (r.get("protocols") or [])]
        # Ưu tiên socks5 > https > http (Playwright hỗ trợ tốt socks5 & http/https)
        if "socks5" in protocols:
            scheme = "socks5"
        elif "https" in protocols:
            scheme = "https"
        elif "http" in protocols:
            scheme = "http"
        else:
            continue
        proxies.append({"server": f"{scheme}://{ip}:{port}"})
    return proxies


def _fetch_geonode_proxies(url: str, timeout: float = 10.0) -> list[dict]:
    raw = _fetch_remote_proxy_list(url, timeout=timeout)
    return _parse_geonode_response(raw) if raw else []


def _parse_proxifly_response(raw: str) -> list[dict]:
    proxies = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Format trong file proxifly là socks5://ip:port hoặc http://ip:port
        server = _normalize_server(line)
        proxies.append({"server": server})
    return proxies


def _fetch_proxifly_proxies(url: str, timeout: float = 10.0) -> list[dict]:
    raw = _fetch_remote_proxy_list(url, timeout=timeout)
    return _parse_proxifly_response(raw) if raw else []


def _parse_fineproxy_response(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []

    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []

    scored: list[tuple[float, dict]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        ip, port = r.get("ip"), r.get("port")
        protos = r.get("protos") or []
        if not ip or not port or "HTTP" not in protos:
            continue
        scored.append((r.get("score") or 0, {"server": _normalize_server(f"{ip}:{port}")}))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [cfg for _, cfg in scored]


def _fetch_fineproxy_proxies(url: str, timeout: float = 10.0) -> list[dict]:
    """Tải + parse danh sách proxy VN từ FineProxy. Không raise — trả về [] khi lỗi (xem
    _fetch_remote_proxy_list / _parse_fineproxy_response)."""
    raw = _fetch_remote_proxy_list(url, timeout=timeout)
    return _parse_fineproxy_response(raw) if raw else []


def _databay_server(entry: dict) -> str | None:
    """Ghép server URI đúng scheme cho một proxy Databay. Playwright chỉ chấp nhận scheme
    http/https/socks5 cho proxy.server, và Databay không trả sẵn scheme — chỉ "protocol"
    ("Http"/"Socks5") + "ssl" (bool, chỉ áp dụng khi protocol là Http):
      - protocol "Socks5"                -> "socks5://ip:port"
      - protocol "Http" với ssl=true     -> "https://ip:port"  (proxy front-end có TLS)
      - protocol "Http" với ssl=false    -> "http://ip:port"
    Trả None nếu thiếu ip/port hoặc protocol lạ (không đoán bừa scheme — một scheme sai khiến
    Playwright launch lỗi ngay, hoặc tệ hơn là kết nối "thành công" qua sai giao thức)."""
    ip, port = entry.get("ip"), entry.get("port")
    if not ip or not port:
        return None
    protocol = str(entry.get("protocol") or "").strip().lower()
    if protocol == "socks5":
        scheme = "socks5"
    elif protocol == "http":
        scheme = "https" if entry.get("ssl") else "http"
    else:
        return None  # protocol chưa biết (vd "Socks4") — bỏ qua thay vì đoán
    return f"{scheme}://{ip}:{port}"


def _parse_databay_response(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []

    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []

    scored: list[tuple[float, dict]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        # Phòng hờ dù URL đã lọc country=VN — không tin tưởng mù quáng field lọc phía server.
        if str(r.get("iso") or "").upper() != "VN":
            continue
        server = _databay_server(r)
        if not server:
            continue
        # uptime (%) làm điểm xếp hạng, giống "score" của FineProxy — uptime cao hơn có xu hướng
        # sống lâu hơn trong một lượt chạy, nên ưu tiên đứng trước trong danh sách đã gộp.
        scored.append((r.get("uptime") or 0, {"server": server}))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [cfg for _, cfg in scored]


def _fetch_databay_proxies(url: str, timeout: float = 10.0) -> list[dict]:
    """Tải + parse danh sách proxy VN từ Databay. Không raise — trả về [] khi lỗi (xem
    _fetch_remote_proxy_list / _parse_databay_response)."""
    raw = _fetch_remote_proxy_list(url, timeout=timeout)
    return _parse_databay_response(raw) if raw else []


def _truthy_env(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() not in ("0", "false", "no", "")


def _health_check_proxies(proxies: list[dict], timeout: float = 4.0, max_workers: int = 20) -> list[dict]:
    """Kiểm tra song song tốc độ phản hồi của danh sách proxy qua HTTP trong max 4s.
    Dùng URL thật của site VN (fptshop) thay vì httpbin để lọc đúng proxy hoạt động với target."""
    if not proxies:
        return []

    import concurrent.futures

    # Test URL thật sát với site cần proxy nhất — nếu proxy trả về response HTTP bất kỳ là OK
    TEST_URLS = [
        "https://fptshop.com.vn/",
        "https://www.thegioididong.com/",
    ]

    def check_one(p: dict) -> dict | None:
        for test_url in TEST_URLS:
            try:
                with httpx.Client(
                    proxy=p["server"] if "username" not in p else None,
                    mounts={"https://": httpx.HTTPTransport(proxy=httpx.Proxy(
                        url=p["server"],
                        auth=(p.get("username"), p.get("password")) if p.get("username") else None
                    ))} if p.get("username") else None,
                    timeout=timeout,
                    follow_redirects=True,
                ) as client:
                    resp = client.get(test_url, headers={"User-Agent": "Mozilla/5.0"})
                    # Chấp nhận bất kỳ response HTTP có status code — kể cả 403/429
                    # (403 từ Cloudflare vẫn nghĩa là proxy HOẠT ĐỘNG, chỉ site chặn bot)
                    if resp.status_code > 0:
                        return p
            except Exception:
                continue
        return None

    live = []
    print(f"  🔍 Đang kiểm tra sức khỏe {len(proxies)} proxy (test thực tế FPT Shop / TGDĐ)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(check_one, p) for p in proxies]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                live.append(res)

    if live:
        print(f"  ⚡ Đã lọc {len(live)}/{len(proxies)} proxy phản hồi tốt (<{timeout}s).")
        return live
    print(f"  ⚠️ Tất cả proxy test đều không phản hồi <{timeout}s, sử dụng danh sách gốc dự phòng.")
    return proxies


CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
CACHE_FILE = CACHE_DIR / "live_proxies.json"
CACHE_TTL_SECONDS = 45 * 60  # Cache sống trong 45 phút


def _read_cached_proxies() -> list[dict] | None:
    """Đọc danh sách proxy đã kiểm tra sống từ file cache nếu còn trong hạn (45 phút).
    Giúp các danh mục cào liên tiếp (hoặc các process python chạy kế tiếp) KHÔNG phải
    tải lại 400+ proxy và health-check lại từ đầu, tiết kiệm 5-15s mỗi lần chạy.
    """
    try:
        if not CACHE_FILE.exists():
            return None
        mtime = CACHE_FILE.stat().st_mtime
        age = time.time() - mtime
        if age > CACHE_TTL_SECONDS:
            return None  # Cache đã quá hạn

        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        proxies = data.get("proxies") if isinstance(data, dict) else None
        if isinstance(proxies, list) and len(proxies) >= 3:
            minutes_left = int((CACHE_TTL_SECONDS - age) / 60)
            print(f"  ⚡ Dùng lại {len(proxies)} proxy VN từ cache ({int(age / 60)} phút trước, còn hạn {minutes_left}p) — KHÔNG cần quét lại!")
            return proxies
    except Exception as e:
        print(f"  ⚠️  Lỗi đọc cache proxy: {e}")
    return None


def _save_cached_proxies(proxies: list[dict]) -> None:
    """Lưu danh sách proxy còn sống vào file cache để các danh mục/tiến trình sau dùng ngay."""
    if not proxies or len(proxies) < 3:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": time.time(),
            "count": len(proxies),
            "proxies": proxies,
        }
        CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  💾 Đã lưu {len(proxies)} proxy VN còn sống vào cache ({CACHE_FILE.name}) cho các danh mục tiếp theo.")
    except Exception as e:
        print(f"  ⚠️  Không lưu được cache proxy: {e}")


def _load_proxies() -> list[dict]:
    """Xem thứ tự ưu tiên nguồn proxy ở docstring đầu file:
    1. Kiểm tra File Cache (nếu còn hạn 45 phút -> DÙNG NGAY trong 0.01s).
    2. Nếu cache rỗng/hết hạn -> Gộp tự động ProxyScrape + Proxifly + Geonode -> Test song song -> Lưu cache.
    3. Dự phòng PROXY_SERVER đơn lẻ từ .env.
    """
    # Bước 1: Thử dùng cache nếu có
    if _truthy_env("PROXY_CACHE_ENABLED"):
        cached = _read_cached_proxies()
        if cached:
            return cached

    # Bước 2: Tự động tải từ các nguồn và kiểm tra
    if _truthy_env("PROXY_AUTO_FETCH"):
        merged: list[dict] = []
        seen_servers: set[str] = set()

        def _add_all(proxies: list[dict]) -> int:
            added = 0
            for p in proxies:
                if p["server"] not in seen_servers:
                    seen_servers.add(p["server"])
                    merged.append(p)
                    added += 1
            return added

        # Nguồn 1: ProxyScrape — text thuần "ip:port" mỗi dòng.
        ps_url = os.environ.get("PROXY_SCRAPE_URL", "").strip() or DEFAULT_PROXYSCRAPE_URL
        raw_ps = _fetch_remote_proxy_list(ps_url)
        n_ps = _add_all(_parse_proxy_list(raw_ps) if raw_ps else [])
        print(f"  ℹ️  ProxyScrape: {n_ps} proxy VN.")

        # Nguồn 2: Proxifly VN — danh sách proxy VN cập nhật liên tục hàng giờ trên GitHub (hàng trăm proxy VN)
        if _truthy_env("PROXY_PROXIFLY_FETCH"):
            pf_url = os.environ.get("PROXY_PROXIFLY_URL", "").strip() or DEFAULT_PROXIFLY_URL
            n_pf = _add_all(_fetch_proxifly_proxies(pf_url))
            print(f"  ℹ️  Proxifly VN: {n_pf} proxy VN mới (không trùng ProxyScrape).")

        # Nguồn 3: Geonode VN — API proxy theo quốc gia VN kèm thông tin protocol
        if _truthy_env("PROXY_GEONODE_FETCH"):
            gn_url = os.environ.get("PROXY_GEONODE_URL", "").strip() or DEFAULT_GEONODE_URL
            n_gn = _add_all(_fetch_geonode_proxies(gn_url))
            print(f"  ℹ️  Geonode VN: {n_gn} proxy VN mới.")

        # Nguồn 4: FineProxy VN — JSON {"rows":[{"ip","port","protos",...}]}
        if _truthy_env("PROXY_FINEPROXY_FETCH"):
            fp_url = os.environ.get("PROXY_FINEPROXY_URL", "").strip() or DEFAULT_FINEPROXY_URL
            n_fp = _add_all(_fetch_fineproxy_proxies(fp_url))
            print(f"  ℹ️  FineProxy: {n_fp} proxy VN mới.")

        # Nguồn 5: Databay VN — JSON {"data":[{"ip","port","protocol","ssl","iso",...}]}
        if _truthy_env("PROXY_DATABAY_FETCH"):
            db_url = os.environ.get("PROXY_DATABAY_URL", "").strip() or DEFAULT_DATABAY_URL
            n_db = _add_all(_fetch_databay_proxies(db_url))
            print(f"  ℹ️  Databay: {n_db} proxy VN mới.")

        if merged:
            print(f"  ℹ️  Đã tải tổng {len(merged)} proxy (miễn phí, tự động, gộp các nguồn).")
            live_proxies = _health_check_proxies(merged)
            if live_proxies:
                _save_cached_proxies(live_proxies)
            return live_proxies
        print("  ⚠️  Danh sách proxy tự động rỗng/lỗi (tất cả các nguồn) — thử PROXY_SERVER (nếu có cấu hình).")

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
    discover_fptshop sẽ không bị dùng lại ở discover_phongvu trong cùng lượt chạy.

    Vì cache theo PROCESS (không phải theo ngày/theo file), việc tự động tải proxy mới xảy ra
    tự nhiên mỗi khi có một process Python mới chạy (mỗi job CI, mỗi lần gọi
    `python -m scraper.sync_prices` / `python -m scraper.discover_*`)."""
    return ProxyPool(_load_proxies())