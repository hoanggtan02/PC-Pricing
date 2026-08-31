"""Audit toàn diện MỘT danh mục — của một cửa hàng hoặc TẤT CẢ cửa hàng.

Khác với sync_prices.py (Mode B, chỉ cào các source ĐANG active) và discover_*.py (Mode A, chỉ
khám phá sản phẩm mới), script này CÀO LẠI TOÀN BỘ source của một category — BẤT KỂ đang active
hay inactive — và làm 4 việc trên mỗi source:

  1. TÍNH LẠI SKU từ tên sản phẩm đọc được TRÊN TRANG NGAY LÚC NÀY (không phải tên lưu trong DB
     lúc khám phá), so với `product_sku` đang gắn cho source đó. Lệch nhau = nghi ngờ mapping sai
     (đối thủ đổi tên sản phẩm khiến derive_sku ra khoá khác) — CHỈ BÁO CÁO, không tự sửa product_sku
     (đổi khoá chính ảnh hưởng price_history/sources, rủi ro nếu tự động).

  2. CÀO LẠI GIÁ bất kể source đang active hay inactive — dùng LẠI đúng logic trích giá của
     sync_prices.py (extract_price_generic) để không lệch hành vi giữa hai script.

  3. XÁC MINH NGỪNG KINH DOANH THẬT — cùng regex "ngừng/ngưng kinh doanh" như sync_prices.py,
     nhưng áp dụng cho CẢ source đang tắt: một source đã bị tắt trước đây (do lỗi tạm thời, đổi
     URL, hay bug) có thể THỰC RA vẫn còn bán — nếu giờ đọc được giá + còn hàng + không phải hàng
     cũ/demo, tự động BẬT LẠI. Ngược lại, nếu phát hiện dấu hiệu ngừng kinh doanh, tắt như cũ.

  4. ĐỘ KHỚP VỚI TNC — lớp kiểm tra ĐỘC LẬP với derive_sku(): hai sản phẩm KHÁC NHAU vẫn có thể vô
     tình ra CÙNG một SKU (bug trong logic suy luận SKU — xem sku.py, các vụ RAM/CPU/laptop trùng
     SKU trong lịch sử). SKU trùng KHÔNG PHẢI bằng chứng hai bên là cùng sản phẩm. Ở đây ta so
     sánh trực tiếp TÊN listing hiện tại của đối thủ với TÊN sản phẩm TNC (products.name) đang
     được gắn SKU đó — bằng difflib (không phụ thuộc logic derive_sku) + so brand — và gắn cờ
     "NGHI SAI KHỚP" khi độ giống thấp hoặc khác hãng, để người xem lại tay.

AN TOÀN: script CHỈ tự động ghi giá (price_history) và bật/tắt source (sources.active) — hai thao
tác vốn đã được sync_prices.py tự động hoá sẵn theo đúng quy tắc cũ. Nó KHÔNG tự sửa product_sku
hay xoá dữ liệu — nghi ngờ sai khớp/lệch SKU chỉ được BÁO CÁO ra file TSV để xem lại tay, vì sửa
khoá chính sai có thể làm hỏng lịch sử giá của một sản phẩm khác.

Cách dùng:
    python -m scraper.audit_category --category Mainboard
    python -m scraper.audit_category --category Mainboard --competitor "GearVN"
    python -m scraper.audit_category --category Mainboard --dry
    python -m scraper.audit_category --category Mainboard --min-similarity 0.35 --report out.tsv
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import re
import sys

from playwright.async_api import async_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .brand import brand_of
from .config import is_old_listing_name
from .db import (
    deactivate_all_sources,
    deactivate_source,
    fetch_all_sources,
    get_client,
    insert_price,
    set_source_active,
    update_source_used,
)
from .proxy_pool import get_pool, is_proxy_error
from .sku import derive_sku
from .sync_prices import (
    CHROMIUM_STEALTH_ARGS,
    GOTO_TIMEOUT_MS,
    PROXY_COMPETITORS,
    SLOW_COMPETITORS,
    _build_proxy_context,
    _looks_blocked,
    _wait_price_rendered,
    extract_price_generic,
)

TNC_NAME = "Thành Nhân"

# Cùng regex "ngừng kinh doanh" như sync_prices.py (giữ đồng bộ hai nơi — nếu sửa, sửa cả hai chỗ
# hoặc tách ra module dùng chung).
_DISCONTINUED_RE = re.compile(r"\b(?:ngừng|ngưng|ngung)\s+kinh\s+doanh\b", re.IGNORECASE)

# Ngưỡng độ giống tên (0.0-1.0, difflib.SequenceMatcher.ratio trên chuỗi đã chuẩn hoá) — dưới
# ngưỡng này bị gắn cờ NGHI SAI KHỚP. Đây là NGƯỠNG HEURISTIC chưa được calibrate bằng dữ liệu
# thật — bắt đầu THẤP (dễ bỏ sót còn hơn báo động giả tràn lan làm report vô dụng); tăng dần theo
# --min-similarity nếu review thực tế thấy ngưỡng này quá lỏng.
DEFAULT_MIN_SIMILARITY = 0.30

DEFAULT_CONCURRENCY = 4


def _normalize_for_similarity(text: str) -> str:
    """Chuẩn hoá tên để so khớp: lowercase, bỏ dấu câu, gộp khoảng trắng. KHÔNG bỏ dấu tiếng Việt
    (accent) — cả TNC lẫn đối thủ đều ghi tiếng Việt có dấu, bỏ dấu làm GIẢM khả năng phân biệt
    (vd "bạc" vs "bác" thành cùng "bac") chứ không tăng độ chính xác so khớp ở đây."""
    t = (text or "").lower()
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def name_similarity(a: str, b: str) -> float:
    """Độ giống 0.0-1.0 giữa hai tên sản phẩm — ĐỘC LẬP với derive_sku(). Đây chính là lớp kiểm
    tra bổ sung: derive_sku có thể (do bug) cho hai sản phẩm khác nhau ra cùng SKU; so tên trực
    tiếp bắt được trường hợp đó mà logic suy luận SKU không tự phát hiện được."""
    na, nb = _normalize_for_similarity(a), _normalize_for_similarity(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _clean_fresh_name(title: str, h1: str) -> str:
    """Tên 'tươi' đọc lại từ trang NGAY LÚC AUDIT, dùng để tính lại SKU + so độ giống. Ưu tiên h1
    (thường là tên sản phẩm đầy đủ/sạch — <title> hay bị site nối thêm hậu tố " | Tên shop").
    Nếu h1 rỗng, dùng <title> và cắt phần sau dấu "|" (hậu tố tên shop thường đứng sau đó)."""
    h1 = (h1 or "").strip()
    if h1:
        return h1
    t = (title or "").strip()
    return re.split(r"\s*\|\s*", t)[0].strip()


def _is_discontinued(title: str, h1: str, body_text: str) -> bool:
    hay = f"{title} {h1} {body_text}"
    return bool(_DISCONTINUED_RE.search(hay))


async def _read_title_h1_body(page) -> tuple[str, str, str]:
    title = await page.title()
    h1_text = ""
    try:
        h1_el = page.locator("h1").first
        if await h1_el.count() > 0:
            h1_text = (await h1_el.inner_text(timeout=2000)).strip()
    except Exception:
        pass
    body_text = ""
    try:
        body_text = await page.locator("body").inner_text()
    except Exception:
        pass
    return title, h1_text, body_text


async def audit_one(
    context,
    source: dict,
    category: str,
    client,
    dry_run: bool,
    proxy: dict | None,
    min_similarity: float,
    report: list[dict],
) -> None:
    """Audit MỘT source (bất kể active/inactive). Kết quả được append vào `report` (list dùng
    chung, an toàn vì mỗi source chỉ append đúng một lần và asyncio là single-threaded)."""
    competitor = source["competitor"]
    sku = source["product_sku"]
    url = source.get("url")
    was_active = bool(source.get("active"))
    product = source.get("products") or {}
    tnc_name = product.get("name") or ""

    row: dict = {
        "competitor": competitor,
        "sku": sku,
        "was_active": was_active,
        "tnc_name": tnc_name,
        "scraped_name": "",
        "recomputed_sku": "",
        "sku_match": "",
        "similarity": "",
        "price": "",
        "in_stock": "",
        "discontinued": False,
        "action": "",
        "url": url or "",
    }

    if not url or url == "#" or "javascript" in url:
        row["action"] = "SKIP (URL không hợp lệ)"
        report.append(row)
        return

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

        title, h1_text, body_text = await _read_title_h1_body(page)

        # Trang có thể chưa tải xong / bị chặn bot (xem _looks_blocked trong sync_prices.py) —
        # cho thêm MỘT cơ hội với chờ lâu hơn trước khi kết luận, y hệt sync_prices.py.
        try:
            stale_html = await page.content()
        except Exception:
            stale_html = ""
        if _looks_blocked(stale_html):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            except Exception:
                pass
            await page.wait_for_timeout(3000)
            title, h1_text, body_text = await _read_title_h1_body(page)

        fresh_name = _clean_fresh_name(title, h1_text)
        row["scraped_name"] = fresh_name[:160]

        # ── 1) NGỪNG KINH DOANH — xác minh lại thay vì tin mù theo cờ active hiện tại ──────────
        if _is_discontinued(title, h1_text, body_text):
            row["discontinued"] = True
            if competitor == TNC_NAME:
                row["action"] = "NGỪNG KINH DOANH (TNC) — tắt toàn bộ sources của SKU này"
                if not dry_run:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, deactivate_all_sources, client, sku)
            else:
                row["action"] = "NGỪNG KINH DOANH (đối thủ) — tắt source + ghi nhận hết hàng"
                if not dry_run:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, deactivate_source, client, sku, competitor)
                    await loop.run_in_executor(
                        None, insert_price, client, sku, competitor, 0, False, False
                    )
            report.append(row)
            return

        # ── 2) TÍNH LẠI SKU từ tên hiện tại — phát hiện khả năng lệch mapping ───────────────────
        recomputed = derive_sku(fresh_name, url, category) if fresh_name else None
        row["recomputed_sku"] = recomputed or ""
        sku_match = (recomputed == sku) if recomputed else None  # None = không tính lại được
        row["sku_match"] = sku_match if sku_match is not None else "?"

        # ── 3) ĐỘ KHỚP VỚI SẢN PHẨM TNC ĐANG SO SÁNH — độc lập với derive_sku (xem docstring đầu
        # file) ───────────────────────────────────────────────────────────────────────────────
        sim = name_similarity(fresh_name, tnc_name) if (fresh_name and tnc_name) else None
        row["similarity"] = f"{sim:.2f}" if sim is not None else ""
        low_similarity = sim is not None and sim < min_similarity
        brand_mismatch = (
            bool(fresh_name) and bool(tnc_name) and brand_of(fresh_name) != brand_of(tnc_name)
        )

        flags = []
        if sku_match is False:
            flags.append("SKU LỆCH")
        if low_similarity:
            flags.append(f"TÊN KHÁC XA (sim={sim:.2f})")
        if brand_mismatch:
            flags.append(f"KHÁC HÃNG ({brand_of(fresh_name)} ≠ {brand_of(tnc_name)})")
        row["action"] = ("NGHI SAI KHỚP: " + "; ".join(flags)) if flags else "OK"

        # ── 4) GIÁ — cào lại BẤT KỂ source đang active hay không ───────────────────────────────
        is_used = is_old_listing_name(title) or is_old_listing_name(h1_text)
        if not dry_run:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, update_source_used, client, sku, competitor, is_used)

        price, availability_stock = await extract_price_generic(page, competitor)
        extra_reads = 3 if is_slow else 1
        for _ in range(extra_reads):
            if price is not None:
                break
            await page.wait_for_timeout(1500 if is_slow else 1200)
            price, availability_stock = await extract_price_generic(page, competitor)

        if price is not None:
            in_stock = availability_stock if availability_stock is not None else price > 0
            row["price"] = price
            row["in_stock"] = in_stock
            if not dry_run:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, insert_price, client, sku, competitor, price, in_stock, is_used
                )
            # Source ĐANG TẮT nhưng giờ đọc được giá thật + còn hàng + không phải hàng cũ/demo ->
            # rất có thể bị tắt NHẦM (hoặc đã về hàng lại) -> tự bật lại. KHÔNG bật lại nếu is_used
            # (hàng cũ/demo vẫn nên đứng ngoài so giá dù còn hiển thị giá).
            if not was_active and in_stock and not is_used:
                row["action"] += " | ĐANG TẮT nhưng vẫn còn hàng thật -> BẬT LẠI"
                if not dry_run:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, set_source_active, client, sku, competitor, True)
        else:
            row["action"] += " | KHÔNG lấy được giá (selector lỗi thời hoặc trang chặn bot)"

    except Exception as e:
        msg = str(e).splitlines()[0][:150]
        row["action"] = f"LỖI CÀO: {msg}"
        if proxy is not None and is_proxy_error(msg):
            get_pool().mark_dead(proxy)
    finally:
        await page.close()
        report.append(row)


async def run_audit(
    category: str,
    competitor: str | None,
    dry_run: bool,
    min_similarity: float,
    concurrency: int,
    report_path: str | None,
) -> list[dict]:
    client = get_client()
    sources = fetch_all_sources(client, competitor=competitor, category=category)
    if not sources:
        who = f" cho '{competitor}'" if competitor else " (tất cả cửa hàng)"
        print(f"Không tìm thấy source nào{who} trong danh mục '{category}'.")
        return []

    n_active = sum(1 for s in sources if s.get("active"))
    print(
        f"Audit {len(sources)} source(s) trong danh mục '{category}'"
        f"{f' — {competitor}' if competitor else ' — tất cả cửa hàng'}"
        f" ({n_active} active, {len(sources) - n_active} inactive)"
        f"{' [DRY RUN]' if dry_run else ''}...\n"
    )

    proxy_needed = any(s["competitor"] in PROXY_COMPETITORS for s in sources)
    pool = get_pool() if proxy_needed else None
    if proxy_needed:
        print(f"Cửa hàng cần proxy VN có trong lượt audit này — {pool.status()}")

    report: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=CHROMIUM_STEALTH_ARGS)
        context_direct = await _build_proxy_context(browser, None)
        contexts = {
            "direct": context_direct,
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
        for s in sources:
            await queue.put(s)

        async def worker() -> None:
            while True:
                source = await queue.get()
                if source is None:
                    queue.task_done()
                    break

                needs_proxy = source["competitor"] in PROXY_COMPETITORS
                if needs_proxy:
                    live_proxy = pool.current() if pool else None
                    if live_proxy is None:
                        report.append(
                            {
                                "competitor": source["competitor"],
                                "sku": source["product_sku"],
                                "url": source.get("url", ""),
                                "was_active": bool(source.get("active")),
                                "action": "SKIP (hết proxy sống trong pool)",
                            }
                        )
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
                    ctx = contexts["proxy"]
                    proxy_for_mark = contexts["proxy_obj"]
                else:
                    ctx = contexts["direct"]
                    proxy_for_mark = None

                state = "active" if source.get("active") else "INACTIVE"
                print(f"  → {source['competitor']} · {source['product_sku']} ({state})")
                await audit_one(
                    ctx, source, category, client, dry_run, proxy_for_mark, min_similarity, report
                )
                queue.task_done()

        tasks = [asyncio.create_task(worker()) for _ in range(concurrency)]
        for _ in tasks:
            await queue.put(None)
        await queue.join()
        await asyncio.gather(*tasks)
        await browser.close()

    _print_summary(report)
    if report_path:
        _write_report(report_path, report)
    return report


def _print_summary(report: list[dict]) -> None:
    total = len(report)
    priced = sum(1 for r in report if r.get("price") not in ("", None))
    discontinued = sum(1 for r in report if r.get("discontinued") is True)
    reactivated = sum(1 for r in report if "BẬT LẠI" in str(r.get("action", "")))
    mismatched = [r for r in report if "NGHI SAI KHỚP" in str(r.get("action", ""))]
    errors = sum(1 for r in report if str(r.get("action", "")).startswith("LỖI CÀO"))

    print("\n=== TỔNG KẾT AUDIT ===")
    print(f"Tổng số source đã kiểm tra : {total}")
    print(f"Lấy được giá               : {priced}")
    print(f"Ngừng kinh doanh (phát hiện): {discontinued}")
    print(f"Bật lại (trước đó bị tắt)  : {reactivated}")
    print(f"Nghi SAI KHỚP (cần xem tay): {len(mismatched)}")
    print(f"Lỗi cào                    : {errors}")

    if mismatched:
        print(f"\n⚠️  {len(mismatched)} source nghi sai khớp — xem lại tay (chi tiết trong report):")
        for r in mismatched[:30]:
            print(f"  - [{r['competitor']}] {r['sku']}: {r['action']}")
            print(f"      TNC : {str(r.get('tnc_name', ''))[:70]}")
            print(f"      Shop: {str(r.get('scraped_name', ''))[:70]}")
        if len(mismatched) > 30:
            print(f"  ... và {len(mismatched) - 30} dòng khác, xem file report.")


_REPORT_COLUMNS = [
    "competitor",
    "sku",
    "was_active",
    "tnc_name",
    "scraped_name",
    "recomputed_sku",
    "sku_match",
    "similarity",
    "price",
    "in_stock",
    "discontinued",
    "action",
    "url",
]


def _write_report(path: str, report: list[dict]) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\t".join(_REPORT_COLUMNS) + "\n")
            for r in report:
                f.write(
                    "\t".join(
                        str(r.get(c, "")).replace("\t", " ").replace("\n", " ")
                        for c in _REPORT_COLUMNS
                    )
                    + "\n"
                )
        print(f"\nĐã ghi report vào {path}")
    except Exception as e:
        print(f"Lỗi ghi report {path}: {e}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Audit toàn diện MỘT danh mục: tính lại SKU, cào lại giá (bất kể active/inactive), "
            "xác minh ngừng kinh doanh, và kiểm tra độ khớp với sản phẩm TNC đang so sánh."
        )
    )
    ap.add_argument(
        "--category", required=True, help="Danh mục cần audit (vd: Mainboard, Cpu, Laptop, Monitor)"
    )
    ap.add_argument(
        "--competitor", default=None, help="Chỉ audit MỘT cửa hàng (bỏ trống = tất cả cửa hàng)"
    )
    ap.add_argument("--dry", action="store_true", help="Chỉ in ra / ghi report, không ghi vào DB")
    ap.add_argument(
        "--min-similarity",
        type=float,
        default=DEFAULT_MIN_SIMILARITY,
        help=f"Ngưỡng độ giống tên 0-1 để gắn cờ nghi sai khớp (mặc định {DEFAULT_MIN_SIMILARITY})",
    )
    ap.add_argument(
        "--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="Số tab chạy song song"
    )
    ap.add_argument("--report", default="audit_report.tsv", help="Đường dẫn file TSV ghi report")
    args = ap.parse_args()

    asyncio.run(
        run_audit(
            category=args.category.capitalize(),
            competitor=args.competitor,
            dry_run=args.dry,
            min_similarity=args.min_similarity,
            concurrency=args.concurrency,
            report_path=args.report,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())