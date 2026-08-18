"""Script cào giá đồng bộ theo link đã có trong Database (Mode B).
Cách dùng:
    python -m scraper.sync_prices                          # cào tất cả active sources, ghi vào Supabase
    python -m scraper.sync_prices --dry                     # cào và in ra, không ghi vào DB
    python -m scraper.sync_prices --competitor "GearVN"     # chỉ cào MỘT cửa hàng (job song song)
    python -m scraper.sync_prices --skip-refresh             # không refresh cache cuối (dành cho job riêng)
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
from .stock import is_out_of_stock

CONCURRENCY_LIMIT = 5  # Số luồng cào song song tối đa (mặc định cho mọi cửa hàng)

# Override RIÊNG cho từng competitor — dùng khi 1 site cụ thể có dấu hiệu bị chặn/rate-limit
# khi nhận nhiều request đồng thời từ cùng 1 IP runner CI (vd CellphoneS: gần như 100% SKU fail
# "Không tìm thấy giá" trên CI dù trang thật vẫn có JSON-LD đầy đủ khi load tay/local). Nguyên
# nhân chính đã xác định là IP (xem PROXY_COMPETITORS bên dưới), nhưng vẫn giữ giảm concurrency
# này như một lớp phòng hờ bổ sung — không gây hại gì cho các cửa hàng khác.
# Các cửa hàng KHÔNG có trong dict này vẫn dùng CONCURRENCY_LIMIT mặc định như cũ.
#
# "Thành Nhân": 15 -> 6 (2026-08, điều tra chuỗi fail "Không tìm thấy giá trên trang" hàng loạt
# cho các SKU Lexar thẻ nhớ/RAM/SSD dài đuôi). Đã xác nhận các trang này CÓ offers.price hợp lệ
# trong JSON-LD (không phải thiếu giá thật) — nên nguyên nhân nhiều khả năng là TIMING/TẢI TRANG,
# không phải parse: 15 tab Chromium song song trên cùng 1 runner CI tranh CPU dữ dội, cộng với
# trang sản phẩm TNC rất nặng (mega-menu + hàng trăm "Sản phẩm Hot Deal" ở cuối trang) khiến JSON-LD
# có thể CHƯA kịp render/attach vào DOM lúc page.content() được gọi, đặc biệt với các SKU dài đuôi
# ít được cache. 15 vốn là mức concurrency CAO NHẤT trong toàn hệ thống (cao hơn cả mặc định 5) —
# hạ xuống 6 để giảm áp lực CPU/mạng đồng thời mà vẫn nhanh hơn đáng kể so với chạy tuần tự.
# Nếu sau khi hạ vẫn còn fail hàng loạt, cân nhắc hạ tiếp hoặc điều tra thêm theo hướng khác.
#
# "An Phát PC": thêm cùng đợt (2026-08) — người dùng xác nhận An Phát cũng gặp CHUỖI FAIL "Không
# tìm thấy giá trên trang" tương tự Thành Nhân. An Phát vốn đã được coi là site "nặng" (xem
# SLOW_COMPETITORS bên dưới, và ghi chú trong discover_anphat.py: "An Phát giữ các kết nối mạng
# luôn mở (do tracker)", "trang An Phát có menu danh mục khổng lồ" khiến layout rất nặng), nhưng
# TRƯỚC ĐÂY chưa từng bị giảm concurrency riêng — vẫn chạy ở mức mặc định 5 dù chạy standalone
# trong job riêng (sync.yml matrix, mỗi competitor 1 job). 5 tab song song trên cùng runner CI vẫn
# có thể đủ để trang tracker-nặng này chưa kịp render xong giá lúc page.content() được gọi. Hạ
# xuống 3 để giảm áp lực, tương tự hướng đã áp dụng cho Thành Nhân.
PER_COMPETITOR_CONCURRENCY = {
    "CellphoneS": 4,
    "Thành Nhân": 6,
    "An Phát PC": 3,
}

# Ngưỡng GIÁ TỐI THIỂU hợp lệ. Không sản phẩm nào trong catalog (laptop, linh kiện, phụ kiện...)
# có giá THẬT dưới mức này — VND rẻ nhất trong catalog vẫn là hàng trăm nghìn trở lên. Một giá
# < 500đ hầu như chắc chắn là DỮ LIỆU RÁC: placeholder giá "0đ"/"1đ" site trả về khi hết hàng/lỗi
# render, phần còn sót của một class giá bị parse nhầm ("giảm 5%" đọc thành "5"), v.v. — KHÔNG
# PHẢI giá thật của bất kỳ sản phẩm nào. Coi tín hiệu này là HẾT HÀNG (đồng bộ với quy ước
# price=0 -> in_stock=False đã dùng xuyên suốt hệ thống — xem stock.stock_from_price()), thay vì
# ghi nhầm một mức giá vô nghĩa vào price_history khiến dashboard hiện "rẻ nhất thị trường: 5đ".
MIN_VALID_PRICE = 500


def _concurrency_for(competitor: str | None) -> int:
    """Số worker song song cho lượt chạy này. Khi lượt chạy CHỈ lo MỘT competitor (job matrix
    theo cửa hàng, xem sync.yml) và competitor đó có override riêng, dùng giá trị thấp hơn.
    Mọi trường hợp khác (nhiều competitor trong hàng đợi, hoặc competitor không có override)
    giữ nguyên CONCURRENCY_LIMIT — không đổi hành vi của các cửa hàng khác."""
    if competitor and competitor in PER_COMPETITOR_CONCURRENCY:
        return PER_COMPETITOR_CONCURRENCY[competitor]
    return CONCURRENCY_LIMIT


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ── Các competitor CHẶN IP ngoài Việt Nam (Cloudflare/geo-block/anti-bot) — BẮT BUỘC qua proxy VN.
# Khớp đúng danh sách use_proxy=True trong browser.py / các discover_*.py tương ứng
# (discover_phongvu.py, discover_fptshop.py, discover_tgdd.py).
#
# CellphoneS được THÊM VÀO ĐÂY (trước đây không có): test thực tế cho thấy cùng code, cùng
# concurrency, chạy LOCAL (IP nhà mạng VN) thì 10/10 thành công, nhưng chạy trên GitHub Actions
# (IP datacenter nước ngoài) thì gần như 100% SKU fail "Không tìm thấy giá trên trang" — dù trang
# thật (kiểm tra tay) vẫn có JSON-LD đầy đủ giá. Đây là dấu hiệu IP-block/anti-bot theo dải IP
# datacenter, chứ không phải do concurrency hay selector lỗi thời — cùng lớp vấn đề với FPT
# Shop/Phong Vũ/TGĐĐ nên xử lý bằng proxy VN là hợp lý.
#
# MỌI competitor khác (An Phát, HACOM, Thành Nhân, GearVN, Memoryzone) truy cập trực tiếp được —
# KHÔNG được ép qua proxy, nếu không proxy hỏng/hết quota sẽ làm sập lây cả những site vốn không
# cần proxy (ERR_TUNNEL_CONNECTION_FAILED hàng loạt dù URL hoàn toàn hợp lệ).
PROXY_COMPETITORS = {"Phong Vũ", "FPT Shop"}

# PROXY_COMPETITORS: set[str] = set()

# Timeout cho page.goto(). Site cần proxy VN được cấp timeout NGẮN HƠN (15s thay vì 30s mặc định):
# khi một proxy đã chết/treo (không bao giờ trả lời), mỗi request qua nó chắc chắn ăn đủ timeout
# rồi mới fail — với hàng trăm source dùng chung 1 proxy chết trước khi kịp rotate (xem
# proxy_pool.is_proxy_error, đã sửa để nhận diện đúng "ERR_TIMED_OUT"), 30s/request nhân lên rất
# chậm. 15s vẫn đủ cho trang thật load qua proxy VN bình thường (proxy VN tuy chậm hơn direct
# nhưng hiếm khi cần tới 15s để commit response đầu tiên), trong khi cắt gọn ~50% thời gian chờ
# vô ích của các request dính đúng lúc proxy vừa chết giữa lượt chạy.
GOTO_TIMEOUT_MS = {
    "default": 30000,
    "proxy": 15000,
}

# Selector lấy giá cho từng đối thủ (ở trang chi tiết sản phẩm)
#
# LƯU Ý — FPT Shop: các selector dưới đây (".b1-semibold" ...) chỉ còn là DỰ PHÒNG cuối cùng, GẦN
# NHƯ KHÔNG BAO GIỜ khớp trên markup hiện tại của trang (2026-08, xác nhận từ HTML thật): class
# "b1-semibold" trên site LUÔN dính tiền tố responsive Tailwind thành "pc:b1-semibold" — không có
# phần tử nào mang class trần "b1-semibold". Nguồn giá THẬT cho FPT Shop giờ là
# _fptshop_price_and_stock() (được gọi RIÊNG, ưu tiên trước mọi selector ở đây — xem
# extract_price_generic()), không phải danh sách này.
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

# ── Tồn kho từ JSON-LD (offers.availability) ────────────────────────────────────────────────
# Một số cửa hàng (xác nhận thật: CellphoneS) vẫn niêm yết GIÁ bình thường trong offers.price ngay
# cả khi sản phẩm đang hết hàng — tín hiệu hết hàng THẬT nằm ở field RIÊNG offers.availability
# trong CÙNG khối JSON-LD (ví dụ thực tế lấy từ trang sản phẩm CellphoneS 2026-08:
# {"price":"26990000", ..., "availability":"https://schema.org/OutOfStock"} — sản phẩm này hiển thị
# badge "TẠM HẾT HÀNG" ở khối #boxRegisterProduct trên trang, HOÀN TOÀN TÁCH BIỆT khỏi ô giá).
#
# Trước đây extract_price_generic() chỉ đọc offers.price rồi trả về NGAY (JSON-LD được tin tuyệt
# đối — xem comment trong hàm), bỏ qua hẳn offers.availability nằm cùng object đó -> sản phẩm hết
# hàng thật bị ghi in_stock=True sai. Sửa: đọc availability CÙNG LÚC với price (không tốn thêm
# request/DOM query nào — dữ liệu đã có sẵn trong JSON đang parse), map sang bool qua
# _availability_to_in_stock(), và ƯU TIÊN nó hơn suy luận "price > 0" cũ khi có giá trị rõ ràng.
#
# Đây là dữ liệu CÓ CẤU TRÚC theo chuẩn schema.org (không phải CSS class dễ đổi theo redesign) nên
# áp dụng được cho MỌI competitor có JSON-LD chuẩn, không chỉ CellphoneS — competitor nào không
# khai availability (hoặc giá trị lạ) sẽ nhận None và rơi về hành vi suy-từ-giá như cũ, không đổi.
_AVAILABILITY_OUT = {"outofstock", "soldout", "discontinued"}
_AVAILABILITY_IN = {
    "instock", "limitedavailability", "onlineonly", "presale", "preorder", "backorder",
}


def _availability_to_in_stock(availability_raw) -> bool | None:
    """Map giá trị offers.availability (URL schema.org như "https://schema.org/OutOfStock", hoặc
    chuỗi trần "OutOfStock") sang in_stock. Trả None nếu thiếu/không nhận diện được — caller khi
    đó suy in_stock từ giá như quy ước cũ (KHÔNG coi None là hết hàng, tránh gắn cờ sai khi site
    dùng giá trị availability lạ hoặc không khai báo field này)."""
    if not availability_raw:
        return None
    val = str(availability_raw).rstrip("/").rsplit("/", 1)[-1].strip().lower()
    if val in _AVAILABILITY_OUT:
        return False
    if val in _AVAILABILITY_IN:
        return True
    return None


def clean_price(text: str) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _price_value_to_int(price_raw) -> int | None:
    """Chuyển một giá trị SỐ CHUẨN (JSON-LD offers.price, hoặc content của thẻ meta) thành int VND.

    BUG THẬT (TGDD, phát hiện 2026-08 — "giá cào bị x10"): trước đây strategy 1/2 dùng
    `clean_price(str(price_raw))`. clean_price() strip mọi ký tự không phải chữ số, coi "." là
    dấu PHÂN CÁCH NGHÌN kiểu hiển thị VN ("20.990.000" -> "20990000") — đúng cho text hiển thị
    trên trang. Nhưng offers.price của JSON-LD (và content của <meta>) là một SỐ THEO CHUẨN
    schema.org/Open Graph: dấu "." ở đó LÀ dấu THẬP PHÂN, không phải phân cách nghìn. TGDD trả về
    price dạng FLOAT TRÒN (vd 20990000.0); str(20990000.0) = "20990000.0" rồi bị clean_price()
    nuốt luôn dấu chấm thập phân vào thành chuỗi số → "209900000" — GIÁ BỊ NHÂN 10 cho MỌI sản
    phẩm TGDD (giá VND luôn là số tròn nên luôn dính ".0"), đúng triệu chứng báo cáo.

    Parse ĐÚNG kiểu số (float) rồi ROUND về int — không strip ký tự. Dự phòng: nếu parse float
    thất bại (giá trị dính ký hiệu tiền tệ/chuỗi lạ), rơi về clean_price() như cũ thay vì mất giá.
    """
    if price_raw is None:
        return None
    try:
        return int(round(float(price_raw)))
    except (TypeError, ValueError):
        return clean_price(str(price_raw))


# ── FPT Shop: chiến lược riêng (2026-08) ─────────────────────────────────────────────────────
# Trang sản phẩm FPT Shop (Next.js) KHÔNG có JSON-LD, KHÔNG có meta og:price/product:price:amount,
# và SELECTORS["FPT Shop"] (".b1-semibold") không còn khớp gì (xác nhận từ HTML thật: class này
# trên site LUÔN dính tiền tố responsive Tailwind "pc:b1-semibold" — không tồn tại class trần
# "b1-semibold"). Hệ quả: MỌI sản phẩm FPT Shop (kể cả CÒN hàng) đang fail "Không tìm thấy giá
# trên trang" ở Mode B — không phải vấn đề riêng của hàng hết hàng.
#
# Giá THẬT nằm trong <p>/<span class="text-textOnWhitePrimary ...">1.199.000đ</span> — đúng class
# discover_fptshop.py (Mode A) đã dùng qua JS eval. Class này dùng CHUNG cho nhiều đoạn text khác
# trên trang (không riêng giá) nên phải lọc đúng ĐỊNH DẠNG giá (không chỉ "có chữ số"), tránh vớ
# nhầm số điện thoại/ngày tháng/mã giảm giá. Bỏ qua phần tử "line-through" (giá cũ gạch ngang).
#
# QUAN TRỌNG — hết hàng ("Hàng sắp về"): trang VẪN hiển thị giá bình thường khi hết hàng (giống
# CellphoneS ở khối availability phía trên), nên phải ĐỌC RIÊNG banner "Hàng sắp về" để suy ra
# in_stock, KHÔNG được suy in_stock từ việc "có tìm thấy giá hay không" — nếu không sẽ luôn ghi
# in_stock=True cho cả hàng hết, hoặc tệ hơn là bỏ qua sản phẩm hoàn toàn (không ghi được gì).
_FPTSHOP_PRICE_RE = re.compile(r"^[0-9]{1,3}(?:\.[0-9]{3}){1,3}\s*đ?$")


async def _fptshop_price_and_stock(page: Page) -> tuple[int | None, bool | None]:
    """Đọc giá + tín hiệu hết hàng riêng cho FPT Shop. LUÔN cố lấy giá kể cả khi hết hàng — trang
    không ẩn giá khi hết hàng, chỉ thêm banner "Hàng sắp về". Trả về (price, in_stock):
      - price: giá VND tìm được (kể cả khi hết hàng), hoặc None nếu không tìm thấy phần tử nào
        khớp định dạng giá (trang đổi cấu trúc / lỗi tải).
      - in_stock: False nếu phát hiện banner/tín hiệu hết hàng trên trang; None nếu không có tín
        hiệu rõ ràng (caller tự suy in_stock từ price > 0 như quy ước chung của hệ thống).
    """
    price: int | None = None
    try:
        loc = page.locator('[class*="text-textOnWhitePrimary"]')
        for i in range(await loc.count()):
            el = loc.nth(i)
            cls = await el.get_attribute("class") or ""
            if "line-through" in cls:   # giá cũ gạch ngang — bỏ qua, không phải giá hiện tại
                continue
            txt = (await el.inner_text()).strip()
            if _FPTSHOP_PRICE_RE.match(txt):
                p = clean_price(txt)
                if p:
                    price = p
                    break
    except Exception:
        pass

    in_stock: bool | None = None
    try:
        body_text = await page.locator("body").inner_text()
        # is_out_of_stock() đã có sẵn pattern "hàng sắp về" (dùng chung mọi cửa hàng — stock.py).
        if is_out_of_stock(body_text):
            in_stock = False
    except Exception:
        pass

    return price, in_stock


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


async def extract_price_generic(page: Page, competitor: str) -> tuple[int | None, bool | None]:
    """Sử dụng nhiều chiến lược để trích xuất giá (và, khi có, tín hiệu tồn kho) từ trang sản phẩm.

    Trả về (price, in_stock_from_availability):
      - price: giá VND tìm được, hoặc None nếu không tìm thấy ở bất kỳ chiến lược nào.
      - in_stock_from_availability: bool nếu có tín hiệu tồn kho RÕ RÀNG (JSON-LD
        offers.availability — xem _availability_to_in_stock/_AVAILABILITY_OUT/_AVAILABILITY_IN ở
        đầu file; hoặc banner trang riêng của FPT Shop — xem _fptshop_price_and_stock()), ngược
        lại None (chưa biết — caller tự suy in_stock từ price > 0 như quy ước cũ).

    QUAN TRỌNG — FPT Shop: chạy TRƯỚC MỌI chiến lược khác (xem _fptshop_price_and_stock() ở trên).
    Trang FPT Shop không có JSON-LD/meta giá và selector CSS cũ đã lỗi thời, nên các chiến lược
    generic bên dưới gần như không dùng được cho competitor này; nếu vì lý do nào đó
    _fptshop_price_and_stock() cũng không tìm được giá (trang đổi cấu trúc tiếp), code RƠI XUỐNG
    các chiến lược chung bên dưới như lưới an toàn thay vì bỏ cuộc ngay.

    QUAN TRỌNG — "Liên hệ"/hết hàng: nếu Ô GIÁ CHÍNH của sản phẩm (selector đặc thù của
    competitor, strategy 3) chứa văn bản kiểu "Liên hệ"/"Hết hàng" thay vì một con số, đó là TÍN
    HIỆU THẬT (sản phẩm hết hàng/báo giá riêng), KHÔNG PHẢI "chưa tìm thấy giá". Ta trả về 0 NGAY
    LẬP TỨC (kèm in_stock=False dứt khoát) và KHÔNG rơi xuống strategy 4 (regex quét toàn bộ HTML
    trang).
    Lý do: trang chi tiết TNC luôn có thêm khối "Sản phẩm liên quan/tương tự", và những khối đó
    dùng CHUNG class giá (.new-price/.product-price) hoặc có số tiền trong text ở đâu đó trên
    trang. Nếu tiếp tục quét toàn trang sau khi đã biết sản phẩm CHÍNH là "Liên hệ", ta rất dễ
    vớ nhầm giá của MỘT SẢN PHẨM KHÁC hiển thị cùng trang rồi ghi sai vào price_history — đúng bug
    đã gặp trên production. Dừng ngay ở đây loại bỏ khả năng đó.

    QUAN TRỌNG — giá vẫn niêm yết nhưng THỰC TẾ hết hàng (CellphoneS): một số trang giữ nguyên
    offers.price bình thường trong JSON-LD dù sản phẩm đang tạm hết hàng; tín hiệu hết hàng thật
    nằm ở offers.availability (CÙNG object với price, đọc được miễn phí — không cần thêm DOM
    query/selector riêng). Xem khối comment ở đầu file. Ta đọc field này ngay trong strategy 1 và
    trả kèm theo price, để caller (scrape_source) ưu tiên nó hơn suy luận "price > 0".
    """
    # 0. FPT Shop: chiến lược riêng, chạy TRƯỚC — xem docstring + comment ở _fptshop_price_and_stock().
    if competitor == "FPT Shop":
        price, in_stock = await _fptshop_price_and_stock(page)
        if price is not None:
            return price, in_stock
        # Không tìm được giá qua chiến lược riêng (trang đổi cấu trúc?) — rơi xuống các chiến
        # lược chung bên dưới như lưới an toàn, KHÔNG return ở đây.

    html = await page.content()
    availability_stock: bool | None = None

    # 1. JSON-LD schema — NGUỒN TIN TUYỆT ĐỐI cho GIÁ. Trang tự khai báo giá này để phục vụ Google/
    # SEO (Google Shopping, rich snippet...), nên đây được coi là giá CHÍNH XÁC NHẤT — kể cả khi
    # giá đó là 0 (sản phẩm hết hàng/liên hệ). Một khi đã parse được offers.price, DỪNG NGAY và
    # trả thẳng — KHÔNG rơi xuống meta/CSS selector/regex bên dưới (những chiến lược đó chỉ nên
    # chạy khi trang KHÔNG có JSON-LD hoặc JSON-LD không parse được).
    #
    # LƯU Ý quan trọng: dùng `offers.get("price") is not None` (KHÔNG dùng `if offers.get("price")`)
    # — giá trị 0 là falsy trong Python nên check cũ đã VÔ TÌNH bỏ qua giá 0 hợp lệ và rơi xuống các
    # chiến lược dự phòng, khiến trang có flash-sale/giá-liên-hệ bị đọc nhầm sang CSS selector giá
    # thường. Cũng bỏ luôn ngưỡng `p > 1000`: ngưỡng đó chỉ hợp lý để lọc NHIỄU cho các chiến lược
    # heuristic (CSS/regex), không áp dụng cho dữ liệu có cấu trúc mà ta đã quyết định tin tuyệt đối.
    # LƯU Ý: chính vì JSON-LD được tin tuyệt đối và KHÔNG lọc theo ngưỡng giá tối thiểu ở đây, một
    # giá trị rác/nhỏ bất thường (vd site trả "1"/"100" do lỗi render) vẫn có thể lọt qua tới đây —
    # ngưỡng MIN_VALID_PRICE được áp dụng SAU CÙNG ở scrape_source(), sau khi mọi chiến lược (kể
    # cả chiến lược "tin tuyệt đối" này) đã chạy xong, để bắt được cả trường hợp này.
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
                        price_raw = None
                        offer_obj = None
                        if isinstance(offers, dict) and offers.get("price") is not None:
                            price_raw, offer_obj = offers["price"], offers
                        elif isinstance(offers, list) and len(offers) > 0:
                            price_raw, offer_obj = offers[0].get("price"), offers[0]
                        # Đọc availability CÙNG LÚC với price — cùng object, không tốn thêm truy
                        # vấn nào. Ghi lại NGAY CẢ KHI price_raw rỗng, phòng trường hợp node có
                        # availability nhưng lại thiếu price hợp lệ (hiếm, nhưng an toàn hơn).
                        if offer_obj is not None:
                            mapped = _availability_to_in_stock(offer_obj.get("availability"))
                            if mapped is not None:
                                availability_stock = mapped
                        if price_raw is not None:
                            p = _price_value_to_int(price_raw)
                            if p is not None:  # tin tuyệt đối — kể cả 0
                                return p, availability_stock
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
                # _price_value_to_int (không phải clean_price trần): content chuẩn Open Graph là
                # SỐ THẬP PHÂN ("20990000.00" nghĩa là 20990000, KHÔNG PHẢI 2099000000) — cùng lớp
                # bug "x10" đã sửa ở strategy 1 JSON-LD, xem _price_value_to_int().
                p = _price_value_to_int(content)
                if p and p > 1000:
                    return p, availability_stock
    except Exception:
        pass

    # 3. Lấy theo CSS Selector đặc thù của competitor (ô giá chính của TRANG SẢN PHẨM ĐANG XEM).
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
                            return p, availability_stock
                        txt = await el.inner_text()
                        p = clean_price(txt)
                        if p and p > 1000:
                            return p, availability_stock
                        # "Liên hệ"/hết hàng NGAY TRONG ô giá chính — tín hiệu THẬT, không phải
                        # "chưa tìm thấy". DỪNG NGAY, trả 0 kèm in_stock=False DỨT KHOÁT (quy ước
                        # price=0 -> in_stock=False dùng xuyên suốt hệ thống, xem stock_from_price()).
                        # KHÔNG rơi xuống strategy 4 (regex quét toàn trang) — nếu không sẽ vớ nhầm
                        # giá của SẢN PHẨM KHÁC hiển thị trên cùng trang (sản phẩm liên quan/tương
                        # tự/combo kèm theo).
                        if txt and is_out_of_stock(txt):
                            return 0, False
        except Exception:
            continue

    # 4. Thử tìm regex generic trên HTML — CHỈ còn chạy tới đây khi ô giá chính (strategy 3)
    # KHÔNG hề khớp/không đọc được gì (không phải trường hợp "Liên hệ" đã bắt ở trên). Nhiều site
    # đổi class giá nhưng vẫn giữ nhãn văn bản (HACOM/TNC/An Phát), hoặc dùng câu UI cố định thay
    # cho nhãn (TGDD/ĐMX: "Giá tại <Tỉnh/Thành>" — xem extract_labeled_price()).
    # Thử body đã render trước, rồi đến HTML thô từ SSR.
    try:
        price = extract_labeled_price(await page.locator("body").inner_text())
        if price:
            return price, availability_stock
    except Exception:
        pass

    price = extract_labeled_price(html)
    if price:
        return price, availability_stock

    match = re.search(r'property="product:price:amount"\s+content="(\d+)"', html)
    if match:
        return int(match.group(1)), availability_stock

    return None, availability_stock


def _price_wait_selector(competitor: str) -> str:
    """Selector CSS gộp (OR) để wait_for_selector — bất kỳ selector giá nào của competitor này
    xuất hiện là coi như khối giá đã render xong, không cần đợi mù theo thời gian cố định.

    FPT Shop: giữ nguyên selector cũ trong SELECTORS chỉ cho MỤC ĐÍCH CHỜ (khối giá gần như chắc
    chắn không khớp — xem ghi chú ở SELECTORS/_fptshop_price_and_stock()); do đó ta CHỜ THÊM class
    "text-textOnWhitePrimary" thật sự dùng để đọc giá, để không đợi timeout vô ích rồi mới đọc."""
    if competitor == "FPT Shop":
        return ", ".join(SELECTORS[competitor] + ['[class*="text-textOnWhitePrimary"]'])
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
#
# "Thành Nhân" ĐƯỢC THÊM VÀO ĐÂY (2026-08, cùng đợt sửa với PER_COMPETITOR_CONCURRENCY ở trên):
# đã xác nhận các trang bị fail "Không tìm thấy giá trên trang" hàng loạt (SKU Lexar dài đuôi) VẪN
# CÓ offers.price hợp lệ trong JSON-LD — tức đây không phải lỗi thiếu giá thật, mà nhiều khả năng
# là JSON-LD/DOM chưa kịp render xong lúc page.content() được gọi. Trang sản phẩm TNC rất nặng
# (mega-menu khổng lồ + hàng trăm sản phẩm "Hot Deal" chèn cuối trang) nên cần nhiều thời gian hơn
# mức mặc định (10s + 1 lần đọc lại) để chắc chắn JSON-LD đã attach vào DOM, đặc biệt khi bị dồn
# tải bởi nhiều tab chạy song song trên cùng runner CI.
SLOW_COMPETITORS = {"An Phát PC", "Thành Nhân"}


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
        # Navigate với timeout riêng cho site cần proxy VN — 15s thay vì 30s mặc định. Khi một
        # proxy đã chết/treo (không commit được response), mỗi request qua nó chắc chắn ăn đủ
        # timeout rồi mới fail; rút ngắn timeout không đổi kết quả (vẫn fail) nhưng giảm ~50% thời
        # gian lãng phí trước khi worker rảnh ra để dùng proxy khác (xem GOTO_TIMEOUT_MS ở đầu file).
        goto_timeout = GOTO_TIMEOUT_MS["proxy"] if proxy is not None else GOTO_TIMEOUT_MS["default"]
        await page.goto(url, wait_until="commit", timeout=goto_timeout)

        # Chờ ĐÚNG theo tín hiệu khối giá đã render (không phải chờ cố định) — xem _wait_price_rendered.
        # Site "nặng" (SLOW_COMPETITORS) được cấp thêm thời gian: khi CI chạy nhiều tab song song, các
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

        price, availability_stock = await extract_price_generic(page, competitor)

        # Không tìm thấy giá ở lần đọc đầu — có thể trang tải chậm bất thường (CPU/mạng chia tải
        # giữa nhiều tab song song) chứ chưa chắc trang thật sự thiếu giá. Thử lại trên CÙNG trang
        # (KHÔNG goto lại): một số site geo/tracker-heavy (An Phát) không bao giờ đạt
        # 'load'/'networkidle' ổn định — reload ở đây từng làm mỗi lần retry tốn hẳn 30s timeout
        # thật, nghẽn cả các tab song song và làm kết quả TỆ HƠN. Chỉ đợi thêm một nhịp ngắn rồi
        # đọc lại là đủ trong đa số case. Site "nặng" được thêm vài lượt đọc lại (thay vì chỉ 1)
        # vì JS/JSON-LD của nó cần nhiều thời gian hơn để attach vào DOM khi bị dồn tải trên CI.
        #
        # QUAN TRỌNG: dùng `price is not None` để kiểm tra, KHÔNG dùng `if price:`. Từ khi JSON-LD
        # được tin tuyệt đối (strategy 1 ở extract_price_generic) VÀ "Liên hệ" ở ô giá chính cũng
        # được nhận diện và trả 0 ngay (strategy 3), `price` có thể hợp lệ là 0 (hết hàng/liên hệ
        # THẬT) — 0 là falsy trong Python nên check cũ sẽ coi đó là "chưa tìm thấy" và retry vô ích,
        # rồi vẫn quay lại đúng 0 đó (hoặc tệ hơn, có nguy cơ rơi vào chiến lược khác cho ra giá SAI
        # nếu logic dừng sớm ở strategy 3 từng bị bỏ qua).
        extra_reads = 3 if is_slow else 1
        for _ in range(extra_reads):
            if price is not None:
                break
            await page.wait_for_timeout(1500 if is_slow else 1200)
            price, availability_stock = await extract_price_generic(page, competitor)

        if price is not None:
            # Giá RÁC dưới ngưỡng hợp lệ (MIN_VALID_PRICE): không sản phẩm nào trong catalog có
            # giá thật thấp đến vậy — đây gần như chắc chắn là placeholder/lỗi parse, KHÔNG PHẢI
            # giá thật. Coi là HẾT HÀNG giống tín hiệu "Liên hệ"/0 (đồng bộ quy ước price=0 ->
            # in_stock=False), thay vì ghi một mức giá vô nghĩa vào price_history. Không áp dụng
            # cho price == 0 (đã là "hết hàng" sẵn từ JSON-LD/"Liên hệ" ở trên) — chỉ bắt các giá
            # RÁC KHÁC 0 nhưng vẫn quá nhỏ để là thật (vd 1, 100, 499).
            if 0 < price < MIN_VALID_PRICE:
                print(
                    f"  ⚠️  {competitor} - {sku}: giá {price:,} VND < {MIN_VALID_PRICE}đ "
                    f"— coi là dữ liệu rác, ghi nhận HẾT HÀNG thay vì giá này"
                )
                price = 0
                availability_stock = False

            # in_stock: ƯU TIÊN tín hiệu availability đọc từ JSON-LD hoặc từ chiến lược riêng của
            # competitor (offers.availability — xem khối comment ở đầu file; hoặc banner "Hàng sắp
            # về" của FPT Shop — xem _fptshop_price_and_stock()) khi có — đây là dữ liệu THẬT do
            # chính trang tự khai/hiển thị, và có thể là False dù price > 0 (site vẫn niêm yết giá
            # trong khi sản phẩm đang tạm hết hàng — xác nhận thật trên CellphoneS: price=26990000
            # nhưng availability=OutOfStock; và trên FPT Shop: giá vẫn hiện bình thường kèm banner
            # "Hàng sắp về" tách biệt khỏi ô giá). Không có tín hiệu rõ ràng (availability_stock is
            # None) -> suy in_stock từ giá như quy ước cũ.
            in_stock = availability_stock if availability_stock is not None else price > 0
            flag = "" if in_stock else "  [Liên hệ/hết hàng — không ghi nhầm giá SP khác]"
            print(f"  ✅ {competitor} - {sku}: {price:,} VND{flag}")
            if not dry_run:
                # Ghi giá vào DB
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, insert_price, client, sku, competitor, price, in_stock)
            return True
        else:
            # Log thêm độ dài HTML lúc fail để phân biệt "trang thật sự không có giá" với "trang
            # tải dở dang/timing" (vd chuỗi fail hàng loạt của TNC/Lexar dù đã xác nhận có
            # offers.price hợp lệ trong JSON-LD khi tải tay — nghi ngờ JSON-LD chưa kịp attach vào
            # DOM lúc page.content() được gọi). Một html_len bất thường nhỏ (so với các lần cào
            # thành công khác của cùng competitor) là dấu hiệu trang bị cắt cụt do tải dở dang;
            # html_len bình thường mà vẫn không tìm thấy giá thì nghiêng về "trang thật sự không
            # có giá hiển thị" (hàng ngừng bán/chưa mở bán). Không raise/đổi hành vi, chỉ thêm dữ
            # liệu chẩn đoán vào log + vào lý do fail trong file TSV.
            try:
                html_len = len(await page.content())
            except Exception:
                html_len = -1
            print(
                f"  ❌ {competitor} - {sku}: Không tìm thấy giá trên trang "
                f"(html={html_len} ký tự) ({url})"
            )
            if failures is not None:
                _record_failure(
                    failures, competitor, sku, url,
                    f"Không tìm thấy giá trên trang (html={html_len} ký tự)",
                )
            return False
            
    except Exception as e:
        msg = str(e).splitlines()[0][:80]
        # Phân biệt rõ lỗi HẠ TẦNG (proxy/tunnel/mạng) với lỗi PARSE (trang đổi cấu trúc) — trước
        # đây cả hai đều in chung một dòng "Lỗi cào" nên rất khó nhận ra hàng loạt lỗi chỉ vì proxy
        # sập, chứ không phải vì URL/selector có vấn đề.
        infra = any(tag in msg for tag in (
            "ERR_TUNNEL_CONNECTION_FAILED", "ERR_PROXY_CONNECTION_FAILED",
            "ERR_CONNECTION_REFUSED", "ERR_CONNECTION_RESET", "ERR_NAME_NOT_RESOLVED",
            "ERR_TIMED_OUT", "Timeout", "net::ERR_",
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
    toàn bộ các source Phong Vũ/FPT Shop/TGĐĐ/CellphoneS còn lại trong hàng đợi.
    """
    while True:
        source = await queue.get()
        if source is None:
            queue.task_done()
            break

        competitor = source["competitor"]
        needs_proxy = competitor in PROXY_COMPETITORS

        if needs_proxy:
            # get_pool() TỰ ĐỘNG TẢI danh sách proxy free từ ProxyScrape ngay khi được gọi lần đầu
            # (không lazy — xem proxy_pool.get_pool()/_load_proxies()). Gọi vô điều kiện ở đầu hàm
            # (như trước đây) khiến MỌI lượt sync — kể cả lượt CHỈ cào site không cần proxy như
            # TGDD/An Phát/HACOM/GearVN/Memoryzone/Thành Nhân — đều tải về 20-30 proxy hoàn toàn vô
            # ích (tốn thời gian + một request mạng thừa ra ProxyScrape). Chỉ gọi khi source NÀY
            # thật sự cần proxy; lru_cache của get_pool() đảm bảo các worker/source cần proxy khác
            # trong CÙNG lượt chạy vẫn dùng chung một pool đã tải, không tải lại nhiều lần.
            pool = get_pool()
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

    # Concurrency cho lượt chạy này — mặc định CONCURRENCY_LIMIT, TRỪ các competitor có override
    # riêng trong PER_COMPETITOR_CONCURRENCY (hiện có CellphoneS, Thành Nhân) khi job chỉ lo riêng
    # cửa hàng đó.
    effective_concurrency = _concurrency_for(competitor)

    print(f"Bắt đầu đồng bộ giá cho {len(sources)} sources (Concurrency: {effective_concurrency})...")
    totals = Counter(source["competitor"] for source in sources)
    print("Source active theo cửa hàng: " + ", ".join(
        f"{c}={n}" for c, n in sorted(totals.items())
    ))
    proxy_needed = sorted(c for c in totals if c in PROXY_COMPETITORS)
    # get_pool() TỰ ĐỘNG TẢI danh sách proxy free từ ProxyScrape ngay khi được gọi (không lazy) —
    # gọi vô điều kiện ở đây (như trước đây) từng khiến MỌI lượt sync, kể cả lượt chỉ cào site
    # không cần proxy (TGDD/An Phát/HACOM/GearVN/Memoryzone/Thành Nhân...), đều tải về proxy vô
    # ích. Chỉ gọi khi lượt chạy này THẬT SỰ có competitor cần proxy VN.
    pool = get_pool() if proxy_needed else None
    if proxy_needed:
        print(f"Cửa hàng cần proxy VN: {', '.join(proxy_needed)} — {pool.status()}")
    if effective_concurrency != CONCURRENCY_LIMIT:
        print(f"  ⚠️  Giảm concurrency xuống {effective_concurrency} cho '{competitor}' "
              f"(nghi bị chặn/rate-limit khi nhận nhiều request đồng thời).")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Context KHÔNG proxy — dùng cho An Phát, HACOM, Thành Nhân, GearVN, Memoryzone.
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
        for _ in range(effective_concurrency):
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