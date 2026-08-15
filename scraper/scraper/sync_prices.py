"""Script cào giá đồng bộ theo link đã có trong Database (Mode B).
Cách dùng:
    python -m scraper.sync_prices                          # cào tất cả active sources, ghi vào Supabase
    python -m scraper.sync_prices --dry                     # cào và in ra, không ghi vào DB
    python -m scraper.sync_prices --competitor "GearVN"     # chỉ cào MỘT cửa hàng (job song song)
    python -m scraper.sync_prices --skip-refresh            # không refresh cache cuối (dành cho job riêng)
    python -m scraper.sync_prices --failures-file out.tsv   # ghi danh sách link cào lỗi ra file TSV
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
from .proxy_pool import get_pool, is_proxy_error

CONCURRENCY_LIMIT = 5  # Số luồng cào song song tối đa
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ── Các competitor CHẶN IP ngoài Việt Nam (Cloudflare/geo-block) — BẮT BUỘC qua proxy VN.
# Khớp đúng danh sách use_proxy=True trong browser.py / các discover_*.py tương ứng
# (discover_phongvu.py, discover_fptshop.py, discover_tgdd.py). MỌI competitor khác (An Phát,
# CellphoneS, HACOM, Thành Nhân, GearVN, Memoryzone) truy cập trực tiếp được — KHÔNG được ép qua
# proxy, nếu không proxy hỏng/hết quota sẽ làm sập lây cả những site vốn không cần proxy
# (ERR_TUNNEL_CONNECTION_FAILED hàng loạt dù URL hoàn toàn hợp lệ).
PROXY_COMPETITORS = {"Phong Vũ", "FPT Shop", "Thế Giới Di Động"}

# Selector lấy giá cho từng đối thủ (ở trang chi tiết sản phẩm)
SELECTORS = {
    "CellphoneS": [".product__price--show", ".sale-price", "[itemprop='price']"],
    "GearVN": [".product-price", ".pro-price", ".price-current"],
    "Thành Nhân": [".new-price", ".deal-price-value", ".product-price"],
    # `data-price` của .js-pro-total-price là giá khuyến mại cuối cùng, không phải giá <del>.
    "An Phát PC": [".js-pro-total-price", ".p-price", ".d-pro-price", ".price-current"],
    "Phong Vũ": [".css-1755xpx", ".product-price", ".price-current", "span[class*='price']"],
    "Hà Nội Computer": [".dpro-p-price", ".price-current", ".product-price"],
    "Memoryzone": [".product-price", ".price-current"],
    "FPT Shop": [".b1-semibold", ".fpt-price", ".price-current"],
    # LƯU Ý: TGDD (Next.js) dùng css-module class BĂM (hash) — đổi theo mỗi lần deploy, nên các
    # selector dưới đây chỉ là DỰ PHÒNG best-effort, KHÔNG đáng tin. Nguồn giá chính cho TGDD là
    # regex bám text "Giá tại <Tỉnh/Thành>" trong extract_labeled_price() bên dưới (ổn định hơn
    # nhiều vì đó là câu UI cố định, không phụ thuộc class CSS bị băm).
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
        # TGDD/ĐMX (Next.js, css-module class băm đổi theo mỗi lần deploy -> selector CSS không
        # ổn định): trang KHÔNG có nhãn "giá bán:", giá nằm ngay sau câu hiển thị khu vực định giá
        # "Giá tại <Tỉnh/Thành>" — câu này là text UI CỐ ĐỊNH, ổn định hơn nhiều so với bất kỳ class
        # CSS nào. Cho phép whitespace/newline tùy ý giữa "giá tại ..." và số tiền đầu tiên gặp được
        # (SSR nên số tiền đã nằm sẵn trong HTML thô, không cần đợi JS thêm).
        r"giá\s+tại\s+[^\n₫đ]{0,40}[\s\S]{0,20}?([\d.,]{7,})\s*(?:₫|đ|vnđ|vnd)",
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
                        # Ví dụ An Phát: <b class="js-pro-total-price" data-price="34990000">.
                        raw_price = await el.get_attribute("data-price")
                        p = clean_price(raw_price or "")
                        if p and p > 1000:
                            return p
                        txt = await el.inner_text()
                        p = clean_price(txt)
                        if p and p > 1000:
                            return p
        except Exception:
            continue

    # 4. Thử tìm regex generic trên HTML
    # Nhiều site đổi class giá nhưng vẫn giữ nhãn văn bản (HACOM/TNC/An Phát), hoặc dùng câu UI
    # cố định thay cho nhãn (TGDD/ĐMX: "Giá tại <Tỉnh/Thành>" — xem extract_labeled_price()).
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

def _price_wait_selector(competitor: str) -> str:
    """Selector CSS gộp (OR) để wait_for_selector — bất kỳ selector giá nào của competitor này
    xuất hiện là coi như khối giá đã render xong, không cần đợi mù theo thời gian cố định."""
    sels = SELECTORS.get(competitor, [".price-current", ".product-price", "[itemprop='price']"])
    return ", ".join(sels)


async def _wait_price_rendered(page: Page, competitor: str, timeout: int) -> None:
    """Chờ tới khi MỘT trong các selector giá của competitor XUẤT HIỆN TRONG DOM (state='attached'),
    thay vì chờ cố định hoặc chờ 'visible' (mặc định của wait_for_selector).

    QUAN TRỌNG: dùng state='attached', KHÔNG dùng mặc định 'visible'. 'visible' bắt Playwright tính
    xong toàn bộ layout/paint mới coi là sẵn sàng — trang An Phát có menu danh mục khổng lồ (hàng
    trăm link ẩn/hiện) nên layout rất nặng, trong khi giá đã nằm sẵn trong HTML TĨNH ngay từ đầu
    (server-rendered, không cần đợi JS). Chờ 'visible' ở đây chỉ tốn thời gian oan, không tăng độ
    chính xác — 'attached' (element tồn tại trong DOM) là đủ vì ta chỉ đọc text/data-attribute,
    không cần element hiển thị trên màn hình.

    LƯU Ý — TGDD: selector CSS trong SELECTORS chỉ là dự phòng (class bị băm, có thể không bao giờ
    khớp). Nếu selector không xuất hiện trong `timeout`, hàm này im lặng bỏ qua (không raise) —
    extract_price_generic() vẫn tìm được giá qua regex "Giá tại ..." ở strategy 4 vì giá TGDD là
    SSR (đã nằm sẵn trong HTML ngay khi tải trang, không phụ thuộc việc chờ selector này).
    """
    try:
        await page.wait_for_selector(_price_wait_selector(competitor), timeout=timeout, state="attached")
    except Exception:
        # Selector không xuất hiện trong thời gian chờ — có thể trang thật sự không có khối giá đó
        # (competitor đổi cấu trúc) hoặc JSON-LD/meta mới là nguồn giá (không cần selector CSS).
        # Không raise ở đây: để extract_price_generic tự thử các chiến lược dự phòng khác.
        pass


# Các competitor "nặng" (tracker/JS chạy lâu, hoặc dễ bị dồn tải khi nhiều worker cào song song)
# cần thêm thời gian chờ render + thêm lượt đọc lại so với mặc định. Xem ghi chú ở scrape_source().
SLOW_COMPETITORS = {"An Phát PC"}


def _record_failure(
    failures: list[dict], competitor: str, sku: str, url: str | None, reason: str
) -> None:
    """Ghi lại MỘT link cào lỗi (để tổng hợp thành báo cáo cuối lượt chạy / job CI).
    `reason` nên ngắn gọn, một dòng — sẽ bị làm sạch tab/newline trước khi ghi ra file TSV."""
    failures.append(
        {"competitor": competitor, "sku": sku, "url": url or "", "reason": reason}
    )


async def scrape_source(
    context, source: dict, dry_run: bool, client, proxy: dict | None = None,
    failures: list[dict] | None = None,
) -> bool:
    """Trả về True nếu lấy được giá. `proxy` (nếu có) là proxy hiện tại của `context`, dùng để
    biết nên mark_dead khi lỗi là lỗi PROXY (xem is_proxy_error) chứ không phải lỗi trang đích.
    `failures` (nếu có) là danh sách dùng chung để gom lại các link cào lỗi trong lượt chạy."""
    competitor = source["competitor"]
    url = source["url"]
    sku = source["product_sku"]
    
    if not url or url == "#" or "javascript" in url:
        print(f"  ! Skip {competitor} - {sku}: URL không hợp lệ ({url})")
        if failures is not None:
            _record_failure(failures, competitor, sku, url, "URL không hợp lệ")
        return False

    page = await context.new_page()
    # Chặn tài nguyên không cần thiết để tăng tốc
    await page.route("**/*", lambda route: route.abort() if route.request.resource_type in {"image", "media", "font"} else route.continue_())

    try:
        print(f"  → Đang cào {competitor} - {sku}...")
        # Navigate với timeout 30s
        await page.goto(url, wait_until="commit", timeout=30000)

        # Chờ ĐÚNG theo tín hiệu khối giá đã render (không phải chờ cố định) — xem _wait_price_rendered.
        # Site "nặng" (SLOW_COMPETITORS) được cấp thêm thời gian: khi CI chạy 5 tab song song, các
        # site có tracker nặng/dễ bị dồn tải cần lâu hơn để JS render xong giá so với chạy đơn lẻ
        # trên máy local.
        is_slow = competitor in SLOW_COMPETITORS
        await _wait_price_rendered(page, competitor, timeout=20000 if is_slow else 10000)
        
        # Một URL có thể bị shop đổi sang hàng cũ/demo sau khi đã ghép SKU.
        # Không ghi giá đó và tắt source để cache lần refresh sau loại nó.
        title = await page.title()
        if is_old_listing_name(title):
            print(f"  [OLD] {competitor} - {sku}: tắt source ({title[:80]})")
            if not dry_run:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, deactivate_source, client, sku, competitor)
            if failures is not None:
                _record_failure(failures, competitor, sku, url, f"Hàng cũ/demo, đã tắt source ({title[:60]})")
            return False

        price = await extract_price_generic(page, competitor)

        # Không tìm thấy giá ở lần đọc đầu — có thể trang tải chậm bất thường (CPU/mạng chia tải
        # giữa 5 tab song song) chứ chưa chắc trang thật sự thiếu giá. Thử lại trên CÙNG trang (KHÔNG
        # goto lại): một số site geo/tracker-heavy (An Phát) không bao giờ đạt 'load'/'networkidle'
        # ổn định — reload ở đây từng làm mỗi lần retry tốn hẳn 30s timeout thật, nghẽn cả 5 tab song
        # song và làm kết quả TỆ HƠN. Chỉ đợi thêm một nhịp ngắn rồi đọc lại là đủ trong đa số case.
        # Site "nặng" được thêm vài lượt đọc lại (thay vì chỉ 1) vì JS của nó cần nhiều thời gian
        # hơn để điền giá vào DOM khi bị dồn tải trên CI.
        extra_reads = 3 if is_slow else 1
        for _ in range(extra_reads):
            if price:
                break
            await page.wait_for_timeout(1500 if is_slow else 1200)
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
            if failures is not None:
                _record_failure(failures, competitor, sku, url, "Không tìm thấy giá trên trang")
            return False
            
    except Exception as e:
        msg = str(e).splitlines()[0][:80]
        # Phân biệt rõ lỗi HẠ TẦNG (proxy/tunnel/mạng) với lỗi PARSE (trang đổi cấu trúc) — trước
        # đây cả hai đều in chung một dòng "Lỗi cào" nên rất khó nhận ra hàng loạt lỗi chỉ vì proxy
        # sập, chứ không phải vì URL/selector có vấn đề.
        infra = any(tag in msg for tag in (
            "ERR_TUNNEL_CONNECTION_FAILED", "ERR_PROXY_CONNECTION_FAILED",
            "ERR_CONNECTION_REFUSED", "ERR_CONNECTION_RESET", "ERR_NAME_NOT_RESOLVED",
            "Timeout", "net::ERR_",
        ))
        label = "HẠ TẦNG/MẠNG" if infra else "PARSE"
        print(f"  ❌ {competitor} - {sku}: Lỗi cào [{label}] ({msg})")
        if failures is not None:
            _record_failure(failures, competitor, sku, url, f"[{label}] {msg}")
        # Lỗi PROXY thật (hết hạn/sập) -> đánh dấu chết trong pool. worker() sẽ phát hiện qua
        # pool.current() đổi khác context["proxy_obj"] hiện tại và tự REBUILD context proxy mới
        # cho các source proxy TIẾP THEO trong hàng đợi — không cần dừng cả job để đổi tay.
        if proxy is not None and is_proxy_error(msg):
            get_pool().mark_dead(proxy)
        return False
    finally:
        await page.close()

async def _build_proxy_context(browser, proxy: dict | None):
    """Tạo context mới ứng với `proxy` hiện tại (proxy=None -> context không proxy)."""
    kwargs = {"user_agent": USER_AGENT, "viewport": {"width": 1280, "height": 800}}
    if proxy:
        kwargs["proxy"] = proxy
    return await browser.new_context(**kwargs)


async def worker(queue, browser, contexts: dict, dry_run, client, results):
    """contexts = {"direct": <context>, "proxy": <context|None>, "proxy_obj": <dict|None>}.
    Mỗi source được định tuyến tới context đúng theo PROXY_COMPETITORS — KHÔNG ép mọi site qua
    cùng một context proxy.

    Trước MỖI source cần proxy, worker kiểm tra pool.current() có còn KHỚP với proxy đang gắn
    trong contexts["proxy_obj"] không. Nếu một worker khác vừa mark_dead() proxy đó (do lỗi ở
    source trước), current() trả về proxy KHÁC — worker này tự đóng context cũ, mở context mới
    với proxy còn sống, rồi mới cào tiếp. Nhờ vậy một proxy hết hạn GIỮA lượt chạy không làm chết
    toàn bộ các source Phong Vũ/FPT Shop/TGĐĐ còn lại trong hàng đợi.
    """
    pool = get_pool()
    while True:
        source = await queue.get()
        if source is None:
            queue.task_done()
            break

        competitor = source["competitor"]
        needs_proxy = competitor in PROXY_COMPETITORS

        if needs_proxy:
            live_proxy = pool.current()
            if live_proxy is None:
                print(f"  ⚠️  Skip {competitor} - {source['product_sku']}: hết proxy sống trong "
                      f"pool ({pool.status()}).")
                results["failed"] += 1
                results["by_competitor"][competitor]["failed"] += 1
                _record_failure(
                    results["failures"], competitor, source["product_sku"], source.get("url"),
                    "Hết proxy sống trong pool",
                )
                queue.task_done()
                continue
            # Proxy hiện tại của contexts đã đổi khác proxy sống mới nhất -> rebuild context.
            if contexts.get("proxy_obj") != live_proxy:
                old_ctx = contexts.get("proxy")
                async with contexts["lock"]:
                    # double-check trong lock: có thể worker khác đã rebuild rồi.
                    if contexts.get("proxy_obj") != live_proxy:
                        contexts["proxy"] = await _build_proxy_context(browser, live_proxy)
                        contexts["proxy_obj"] = live_proxy
                        print(f"  🔄 Đổi sang proxy: {live_proxy['server']} ({pool.status()})")
                        if old_ctx is not None:
                            try:
                                await old_ctx.close()
                            except Exception:
                                pass
            context = contexts["proxy"]
            proxy_for_mark = contexts["proxy_obj"]
        else:
            context = contexts["direct"]
            proxy_for_mark = None

        success = await scrape_source(
            context, source, dry_run, client, proxy=proxy_for_mark, failures=results["failures"]
        )
        results["success" if success else "failed"] += 1
        results["by_competitor"][source["competitor"]]["success" if success else "failed"] += 1
        queue.task_done()


def _interleave_by_competitor(sources: list[dict]) -> list[dict]:
    """Trộn xen kẽ (round-robin) danh sách source theo competitor.

    fetch_active_sources() (db.py) trả về sources ĐÃ SẮP XẾP theo competitor (.order("competitor")).
    Nếu đẩy thẳng thứ tự đó vào queue, CONCURRENCY_LIMIT=5 worker chạy song song sẽ thường xuyên
    CÙNG LÚC cào MỘT competitor duy nhất suốt một đoạn dài của hàng đợi (đúng như log lỗi thực tế:
    hàng loạt "Đang cào An Phát PC..." chạy chồng lên nhau). 5 request đồng thời từ CÙNG một IP
    (runner CI) dồn vào CÙNG một site nặng-tracker rất dễ khiến trang chưa kịp render JS trong cửa
    sổ chờ, hoặc bị site soi/giới hạn tốc độ theo IP — ra đúng triệu chứng "Không tìm thấy giá trên
    trang" hàng loạt dù URL hoàn toàn hợp lệ.

    Xen kẽ round-robin rải request ra nhiều competitor khác nhau, để 5 worker song song hiếm khi
    cùng nhắm vào một site cùng lúc. KHÔNG đổi tổng số source hay nội dung — chỉ đổi THỨ TỰ.

    Khi lượt chạy chỉ có MỘT competitor (job matrix theo cửa hàng, xem sync.yml), hàm này là no-op
    thực tế — không có gì để xen kẽ, nhưng vẫn an toàn khi gọi.
    """
    from collections import defaultdict, deque

    buckets: dict[str, deque] = defaultdict(deque)
    for s in sources:
        buckets[s["competitor"]].append(s)
    order = list(buckets.keys())
    out: list[dict] = []
    while order:
        for c in list(order):
            out.append(buckets[c].popleft())
            if not buckets[c]:
                order.remove(c)
    return out


def _write_failures_file(path: str, failures: list[dict]) -> None:
    """Ghi danh sách link cào lỗi ra file TSV (competitor, sku, url, reason) — dùng để CI upload
    làm artifact và job `summary` gom lại thành báo cáo cuối lượt chạy (xem sync.yml).

    Luôn ghi file (kể cả rỗng, chỉ có header) để bước upload-artifact trong CI không phải đoán
    file có tồn tại hay không."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("competitor\tsku\turl\treason\n")
            for row in failures:
                reason = (row.get("reason") or "").replace("\t", " ").replace("\n", " ")
                f.write(
                    f"{row.get('competitor', '')}\t{row.get('sku', '')}\t"
                    f"{row.get('url', '')}\t{reason}\n"
                )
        print(f"Đã ghi {len(failures)} link cào lỗi vào {path}")
    except Exception as e:
        print(f"Lỗi ghi file lỗi {path}: {e}")


async def run_sync(
    dry_run: bool,
    limit: int | None = None,
    competitor: str | None = None,
    skip_refresh: bool = False,
    failures_file: str | None = "sync_failures.tsv",
):
    client = get_client()
    # Chỉ lấy source của MỘT competitor khi chạy job song song theo cửa hàng (sync.yml matrix).
    # Bỏ trống competitor -> lấy toàn bộ (hành vi cũ, chạy tuần tự tất cả cửa hàng trong 1 process).
    sources = fetch_active_sources(client, competitor=competitor)
    if not sources:
        who = f" cho '{competitor}'" if competitor else ""
        print(f"Không tìm thấy source active nào{who} trong Database.")
        if failures_file:
            _write_failures_file(failures_file, [])
        return

    # Xen kẽ theo competitor TRƯỚC khi cắt --limit, để cả khi limit nhỏ vẫn thấy nhiều shop
    # (hữu ích lúc test), và để CONCURRENCY_LIMIT worker không dồn hết vào một competitor.
    sources = _interleave_by_competitor(sources)

    if limit:
        sources = sources[:limit]

    print(f"Bắt đầu đồng bộ giá cho {len(sources)} sources (Concurrency: {CONCURRENCY_LIMIT})...")
    totals = Counter(source["competitor"] for source in sources)
    print("Source active theo cửa hàng: " + ", ".join(
        f"{c}={n}" for c, n in sorted(totals.items())
    ))
    proxy_needed = sorted(c for c in totals if c in PROXY_COMPETITORS)
    pool = get_pool()
    if proxy_needed:
        print(f"Cửa hàng cần proxy VN: {', '.join(proxy_needed)} — {pool.status()}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Context KHÔNG proxy — dùng cho An Phát, CellphoneS, HACOM, Thành Nhân, GearVN, Memoryzone.
        # Đây là context MẶC ĐỊNH cho gần hết source, nên proxy hỏng sẽ KHÔNG còn ảnh hưởng tới chúng.
        context_direct = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
        )

        # Context CÓ proxy — chỉ tạo khi thực sự có site cần proxy trong lượt chạy này, và chỉ khi
        # pool có proxy sống. Nếu cần mà pool rỗng/chết hết, các source đó sẽ bị skip có cảnh báo
        # rõ ràng ở worker() thay vì đi thẳng vào context_direct và luôn 403.
        # contexts["lock"] bảo vệ việc REBUILD context proxy khi nhiều worker cùng phát hiện proxy
        # chết gần như đồng thời — chỉ một worker được rebuild, các worker khác chờ rồi dùng lại.
        contexts = {"direct": context_direct, "proxy": None, "proxy_obj": None, "lock": asyncio.Lock()}
        if proxy_needed:
            live_proxy = pool.current()
            if live_proxy:
                contexts["proxy"] = await _build_proxy_context(browser, live_proxy)
                contexts["proxy_obj"] = live_proxy
            else:
                print("  ⚠️  Có source cần proxy VN nhưng không có proxy sống trong PROXY_LIST/"
                      "PROXY_SERVER — các source đó sẽ bị bỏ qua (xem cảnh báo bên dưới).")

        queue = asyncio.Queue()
        for src in sources:
            await queue.put(src)

        results = {
            "success": 0,
            "failed": 0,
            "by_competitor": {
                competitor_name: {"success": 0, "failed": 0} for competitor_name in totals
            },
            "failures": [],  # danh sách chi tiết mọi link cào lỗi trong lượt chạy này
        }
        
        # Tạo worker tasks chạy song song
        tasks = []
        for _ in range(CONCURRENCY_LIMIT):
            task = asyncio.create_task(worker(queue, browser, contexts, dry_run, client, results))
            tasks.append(task)
            # Thêm tín hiệu dừng cho mỗi worker
            await queue.put(None)

        await queue.join()
        await asyncio.gather(*tasks)
        await browser.close()

    if proxy_needed:
        print(f"Trạng thái proxy cuối lượt chạy: {pool.status()}")
    print(f"\nHoàn tất đồng bộ giá: Thành công {results['success']}, Thất bại {results['failed']}.")
    print("Kết quả theo cửa hàng:")
    for c in sorted(results["by_competitor"]):
        stats = results["by_competitor"][c]
        print(f"  - {c}: {stats['success']}/{totals[c]} thành công, {stats['failed']} thất bại")

    # In danh sách link lỗi ngay trong log (dễ đọc khi debug tay), rồi ghi ra file để CI gom lại.
    if results["failures"]:
        print(f"\n⚠️  {len(results['failures'])} link cào lỗi trong lượt chạy này:")
        for row in results["failures"]:
            print(f"  - [{row['competitor']}] {row['sku']}: {row['reason']} ({row['url']})")
    if failures_file:
        _write_failures_file(failures_file, results["failures"])

    # skip_refresh=True khi chạy job song song theo competitor (sync.yml) — refresh được gộp lại
    # thành MỘT job riêng chạy SAU KHI mọi job competitor xong, tránh nhiều job cùng RPC refresh
    # chồng lên nhau (race) hoặc refresh sớm khi các job khác chưa ghi xong.
    if not dry_run and not skip_refresh:
        print("Đang làm mới cache Supabase...")
        try:
            client.rpc("refresh_latest_prices").execute()
            print("Làm mới cache thành công.")
        except Exception as e:
            print(f"Lỗi làm mới cache: {e}")

def main():
    parser = argparse.ArgumentParser(description="Sync prices directly from database source URLs.")
    parser.add_argument("--dry", action="store_true", help="dry run (don't write to DB)")
    parser.add_argument("--limit", type=int, default=None, help="limit the number of sources to scrape")
    parser.add_argument(
        "--competitor", default=None,
        help="chỉ đồng bộ giá cho MỘT competitor (dùng khi chạy job song song theo cửa hàng, xem sync.yml)",
    )
    parser.add_argument(
        "--skip-refresh", action="store_true",
        help="không refresh cache latest_prices sau khi chạy — dùng khi có job refresh riêng ở cuối",
    )
    parser.add_argument(
        "--failures-file", default="sync_failures.tsv",
        help="đường dẫn file TSV ghi lại các link cào lỗi (competitor/sku/url/reason); "
             "truyền rỗng ('') để tắt ghi file",
    )
    args = parser.parse_args()

    asyncio.run(
        run_sync(
            args.dry, args.limit, args.competitor, args.skip_refresh,
            failures_file=args.failures_file or None,
        )
    )

if __name__ == "__main__":
    main()