"""Suy luận SKU dùng chung — nơi DUY NHẤT quyết định "hai listing này có phải cùng một laptop?".

Hai listing được coi là cùng một sản phẩm khi và chỉ khi chúng cho ra cùng một SKU ở đây. Mọi
scraper đều import `derive_sku` để quy tắc này nhất quán ở mọi nơi. Xem docs/sku-matching.md để
biết thiết kế đầy đủ.
"""

from __future__ import annotations

import re

_SERIES = re.compile(r"^[a-z]{2,}\d{4,5}$")  # Series của Dell: dc15250, pb14250, pv15250
_PV_SUFFIX = re.compile(r"--s\d+.*$")  # Phong Vũ gắn thêm "--s<id>" vào slug
_EIGHT = re.compile(r"\b(\d{8})\b")  # mã Dell trần gồm 8 chữ số, ví dụ 71092479
_LINES = ("precision", "inspiron", "latitude", "vostro", "xps")  # Các dòng Dell có số 4 chữ số
_FOUR = re.compile(r"\b(\d{4})\b")

_HP_CODE = re.compile(r"^(?=.*[a-z])(?=.*\d)[a-z0-9]{6,7}$", re.I)  # Mã part của HP: BQ5B4PT, 8K0H6AV

_ACER_CODE = re.compile(r"\bN[XH][.\-][A-Z0-9]+[.\-][A-Z0-9]+\b", re.I)  # Mã NX./NH. của Acer
_SER_ALPHA = re.compile(r"^[A-Z]{1,3}\d{1,4}[A-Z]{1,4}$", re.I)  # Series Asus/MSI: P1403CVA, B14WEK
_SER_DIGIT = re.compile(r"^[A-Z]{1,4}\d{2,4}[A-Z]?$", re.I)  # Series Acer: ANV15, AG15, A515
# NHÁNH MỚI — không sửa 2 pattern trên để không ảnh hưởng các máy đã khớp đúng từ trước.
# MSI còn dùng một dạng "mã hộp" riêng: 1 chữ + 1 số + 4-7 chữ, ví dụ D2XWFKG (Crosshair 16 HX
# AI). Dạng này không lọt _SER_ALPHA (quá nhiều chữ ở đuôi, tối đa 4) lẫn _SER_DIGIT (đòi 2-4 số),
# nên trước đây model_code() không nhận ra series -> rơi xuống nhánh fallback của Dell và vô tình
# vơ nhầm số cấu hình (VD: "RTX 5060" -> SKU sai thành "5060"). Chỉ dùng làm phương án CUỐI CÙNG,
# sau khi _SER_ALPHA/_SER_DIGIT đã thử và không khớp — xem chỗ dùng trong model_code().
_MSI_BOX_CODE = re.compile(r"^[A-Z]\d[A-Z]{4,7}$", re.I)  # Mã hộp MSI: D2XWFKG, v.v.
_MODEL_SKIP = {
    "i3", "i5", "i7", "i9", "r5", "r7", "r9", "core", "ryzen", "intel", "amd",
    "ultra", "oled", "ai", "hx", "gaming", "laptop",
}
_SPEC_MARKER = re.compile(r"^(\d{1,3}|\d{2,4}[uh]|u\d+|r\d|i\d|ux\d)$", re.I)  # spec cpu/ram xen kẽ
_CFG_TERM = re.compile(r"^[A-Z]{0,4}\d{2,4}[A-Z]?(WS|W|VN)$", re.I)  # hậu tố kết thúc: Asus …W/WS, MSI …VN


def model_code(name: str | None, slug: str | None) -> str | None:
    """Mã model Asus/Acer/MSI (SERIES-CONFIG), hoặc None nếu không tìm thấy token series nào.

    Mã NX./NH. của Acer được ưu tiên khi có mặt. Nếu không, khóa theo token series + token kết
    thúc cấu hình của nó, bỏ qua các spec CPU/RAM xen kẽ. Đọc slug trước (đầy đủ nhất), sau đó
    mới đến name.
    """
    a = _ACER_CODE.search(f"{name or ''} {slug or ''}")
    if a:
        return re.sub(r"[.\-]", ".", a.group(0)).upper()
    for src in (slug or "", name or ""):
        toks = [t for t in re.split(r"[\s\-_()]+", src) if t]
        idx = next((i for i, t in enumerate(toks) if _SER_ALPHA.match(t)), None)
        if idx is None:
            idx = next(
                (i for i, t in enumerate(toks) if _SER_DIGIT.match(t) and i < len(toks) - 1),
                None,
            )
        # NHÁNH MỚI: chỉ thử khi cả _SER_ALPHA lẫn _SER_DIGIT đều không tìm ra token series nào
        # (idx vẫn None) — không đổi thứ tự hay kết quả của 2 nhánh cũ ở trên.
        if idx is None:
            idx = next(
                (i for i, t in enumerate(toks) if _MSI_BOX_CODE.match(t) and i < len(toks) - 1),
                None,
            )
        if idx is None:
            continue
        out = [toks[idx]]
        for t in toks[idx + 1 :]:
            if t.lower() in _MODEL_SKIP or _SPEC_MARKER.match(t):
                continue
            out.append(re.sub(r"WS$", "W", t, flags=re.I))
            if _CFG_TERM.match(t):  # dừng tại token kết thúc; bỏ mọi thứ phía sau nó
                break
        return "-".join(out).upper()
    return None


# ── Gigabyte / Lenovo: mã hỗn hợp chữ+số DÀI, không dấu gạch/slash ─────────────────────────────
# Cả hai hãng đôi khi in mã sản phẩm dưới dạng MỘT khối liền chữ+số dài (Gigabyte: CMHH2VN893SH,
# CTHH3VN893SH, 9LJR2VNF93SH, 9RC55MF5FJIINIVN000; Lenovo: mã MTM 21MV000PVN, 83F5008WVN) mà
# model_code() (dành cho Asus/Acer/MSI, đòi hỏi cấu trúc "letters-digits-letters" ngắn kiểu
# series) không nhận ra. TRƯỚC KHI SỬA, các laptop này (không khớp Apple/HP/Asus/Acer/MSI) rơi
# thẳng xuống nhánh Dell tổng quát ở cuối _laptop_sku() — vốn chỉ tìm số 4 CHỮ SỐ ĐẦU TIÊN xuất
# hiện trong tên (_FOUR) hoặc TOKEN CUỐI CÙNG của tên/slug làm phương án cuối cùng — nên vô tình
# "khoá" nhầm vào một con số cấu hình GPU (RTX 3050/4050/5050/5080/2050), NĂM sản xuất (2024),
# MÀU (Xám -> XAM), hay hậu tố CPU dính trong slug URL (r5/r7/u7) thay vì mã sản phẩm thật. Hai
# hàm dưới đây bắt đúng các mã đó, chèn vào _laptop_sku() TRƯỚC khi rơi xuống logic Dell.
_LONG_MIXED_CODE = re.compile(r"^(?=.*[a-z])(?=.*\d)[a-z0-9]{7,24}$", re.I)


def _long_mixed_code(name: str | None, slug: str | None) -> str | None:
    """Mã hỗn hợp chữ+số DÀI (>=7 ký tự, không dấu gạch/slash) — chọn token DÀI NHẤT khớp, dùng
    làm phương án CUỐI CÙNG cho các hãng in mã sản phẩm dưới dạng một khối liền (hiện dùng cho
    Gigabyte khi model_code() không tìm được series ngắn). Token càng dài càng đặc thù/duy nhất,
    ít khả năng trùng giữa các cấu hình khác nhau. Đọc slug trước (đầy đủ, sạch), sau đó tới name.

    Tự động loại các token spec dính "/" (vd "16GB/ Ram", "13420H/ Ram" — nguồn không tách trên
    "/" khi split giống model_code()) vì regex neo (^...$) không cho phép ký tự "/" lọt vào giữa;
    cũng tự loại các token toàn số hoặc toàn chữ (thiếu chữ HOẶC thiếu số) nhờ 2 lookahead.
    """
    for src in (slug or "", name or ""):
        toks = [t for t in re.split(r"[\s\-_()]+", src) if t]
        cands = [t for t in toks if _LONG_MIXED_CODE.match(t)]
        if cands:
            return max(cands, key=len).upper()
    return None


# Mã MTM (Machine Type Model) của Lenovo — định danh DUY NHẤT thật, in giống nhau ở mọi cửa hàng,
# dạng 2 CHỮ SỐ + 7-9 ký tự chữ/số (tổng 9-11 ký tự): 21MV000PVN, 83F5008WVN, 83GS001SVN,
# 20YA0039VN. Ràng buộc độ dài này tự nhiên loại các token NGẮN dễ gây nhầm (mã bo mạch/CPU kiểu
# "16IAX10H"/"15IAX9" chỉ 6-8 ký tự, hậu tố CPU dính trong slug "r5"/"r7"/"u7", năm "2024", hay số
# cấu hình GPU "2050"/"3050"/"4050"/"5050"/"5080" — tất cả đều NGẮN HƠN 9 ký tự nên không khớp).
_LENOVO_MTM = re.compile(r"\b\d{2}[a-z0-9]{7,9}\b", re.I)


def _lenovo_code(name: str | None, slug: str | None) -> str | None:
    """Mã MTM của Lenovo, hoặc None nếu không tìm thấy. Đọc slug trước (đầy đủ, sạch), sau đó
    tới name. Yêu cầu match có ÍT NHẤT một chữ cái (loại trừ khả năng khớp nhầm một chuỗi 9-11
    chữ số thuần, dù trong thực tế mã MTM Lenovo luôn có chữ)."""
    for src in (slug or "", name or ""):
        m = _LENOVO_MTM.search(src)
        if m and re.search(r"[a-z]", m.group(0), re.I):
            return m.group(0).upper()
    return None


# Các cụm từ rác mà cửa hàng gắn thêm sau mã model Dell — từ chỉ màu sắc/bảo hành/thương hiệu,
# không phải là một phần của mã.
_JUNK = {
    "bac", "den", "xam", "trang", "xanh", "do", "bạc", "đen",
    "2y", "1y", "3y",
    "vpro", "nk", "slu", "win", "win11", "ubuntu",
    "intel", "core", "amd", "ryzen", "ai", "plus", "essential", "pro",
}
_CPU = re.compile(r"^(\d{3,4}[a-z]|i[3579]|r[3579]|u\d|ultra|x\d.*)$")  # 1334u, i5, r7, ultra, x1p

# Định danh tổng hợp của Apple: APPLE-{AIR|PRO|NEO}-{size}-{chip}-{ram}-{storage} — MacBook không
# có mã số part-number, nên ta khóa theo các thông số kỹ thuật (không phụ thuộc thứ tự từ giữa
# các cửa hàng).
_APPLE_LINES = (("macbook air", "AIR"), ("macbook pro", "PRO"), ("macbook neo", "NEO"))
_MAC_CHIP_M = re.compile(r"\bm([1-9])\b(?:\s*(pro|max))?")          # M5, M3 Pro, M5 Max
_MAC_CHIP_A = re.compile(r"\ba(\d{2})\b(?:\s*(pro|max))?")          # A18 / A18 Pro của Neo
_MAC_SIZE = re.compile(r"(?<!\d)(13|14|15|16)(?=\s*(?:inch|\"|\b))")  # 13, 13 inch, 13inch, 13"
_MAC_CAP = re.compile(r"(\d+)\s*(gb|tb)")                            # các token dung lượng, theo thứ tự


def _apple_parse(name: str | None) -> tuple[str, str, str, str, str] | None:
    """Parse tên MacBook thành (line, size, chip, ram, storage). None nếu không phải laptop MacBook.
    Trường nào không đọc được sẽ là '?'. Dùng chung bởi apple_sku (định danh) và apple_name (hiển thị).
    """
    low = (name or "").lower()
    line = next((tag for kw, tag in _APPLE_LINES if kw in low), None)
    if not line:
        return None
    m = _MAC_CHIP_M.search(low)
    if m:
        chip = f"M{m.group(1)}" + (m.group(2).upper() if m.group(2) else "")
    else:
        a = _MAC_CHIP_A.search(low)  # chip dòng A của Neo
        chip = (f"A{a.group(1)}" + (a.group(2).upper() if a.group(2) else "")) if a else "?"
    sm = _MAC_SIZE.search(low)
    size = sm.group(1) if sm else "?"
    # Dung lượng GB/TB đầu tiên là RAM, cái cuối cùng là storage; số lõi CPU/GPU không có GB/TB
    # nên bị loại trừ.
    caps = _MAC_CAP.findall(low)
    ram, sto = "?", "?"
    if len(caps) >= 2:
        ram = caps[0][0]
        sn, su = caps[-1]
        sto = f"{sn}TB" if su == "tb" else f"{sn}GB"
    elif len(caps) == 1:
        sn, su = caps[0]
        sto = f"{sn}TB" if su == "tb" else f"{sn}GB"
    return line, size, chip, ram, sto


# Màu MacBook (in ở CẢ tên TNC lẫn đối thủ) — thêm vào khoá để phân biệt các máy trùng spec chỉ
# khác màu (M2 Silver/Midnight/Space Grey/Starlight đều 8GB/256GB → nếu không có màu sẽ gộp một).
# KHÔNG dùng mã part Apple (MLY03SA/A) làm khoá: đối thủ KHÔNG ghi mã part → sẽ mất khớp chéo.
_APPLE_COLORS = (
    ("space grey", "SPACEGREY"), ("space gray", "SPACEGREY"), ("xám", "SPACEGREY"),
    ("midnight", "MIDNIGHT"), ("starlight", "STARLIGHT"),
    ("silver", "SILVER"), ("bạc", "SILVER"),
    ("gold", "GOLD"), ("vàng", "GOLD"),
)


def _apple_color(name: str) -> str:
    low = (name or "").lower()
    for kw, tag in _APPLE_COLORS:
        if kw in low:
            return tag
    return ""


def apple_sku(name: str | None) -> str | None:
    """SKU tổng hợp cho một MacBook, hoặc None nếu `name` không phải laptop MacBook parse được.

    Khoá = APPLE-{line}-{size}-{chip}-{ram}-{storage}-{màu?}. Dùng SPEC (không phải mã part) vì đối
    thủ chỉ ghi spec — khoá theo spec mới khớp chéo được. Thêm MÀU để các máy trùng spec khác màu
    không đụng khoá (trước đây 6 máy M2 gộp thành APPLE-AIR-?-M2-?-?). '?' = thông số thiếu trong tên.
    Trả về None cho thiết bị Apple không phải laptop (Mac mini, iMac, Studio).
    """
    parsed = _apple_parse(name)
    if not parsed:
        return None
    line, size, chip, ram, sto = parsed
    sto_key = sto[:-2] if sto.endswith("GB") else sto  # GB thì bỏ hậu tố, TB thì giữ nguyên
    color = _apple_color(name)
    key = f"APPLE-{line}-{size}-{chip}-{ram}-{sto_key}"
    return f"{key}-{color}" if color else key


_APPLE_LINE_LABEL = {"AIR": "Air", "PRO": "Pro", "NEO": "Neo"}


def apple_name(name: str | None) -> str | None:
    """Một tên hiển thị tổng hợp gọn gàng cho MacBook, hoặc None nếu không phải MacBook.

    Được xây dựng từ các thông số đã parse để dashboard hiển thị tiêu đề nhất quán, không lỗi
    chính tả, bất kể cửa hàng viết listing thế nào, ví dụ 'MacBook Pro 16" M5 Pro 48GB 1TB'. Các
    trường không parse được sẽ bị bỏ qua (không hiển thị dưới dạng '?').
    """
    parsed = _apple_parse(name)
    if not parsed:
        return None
    line, size, chip, ram, sto = parsed
    vm = re.match(r"^([A-Z]\d+)(PRO|MAX)?$", chip)  # "M5PRO" -> "M5 Pro"
    chip_disp = f"{vm.group(1)} {vm.group(2).title()}" if vm and vm.group(2) else chip
    parts = [f"MacBook {_APPLE_LINE_LABEL.get(line, line)}"]
    if size != "?":
        parts.append(f'{size}"')
    if chip_disp != "?":
        parts.append(chip_disp)
    if ram != "?":
        parts.append(f"{ram}GB")
    if sto != "?":
        parts.append(sto)
    return " ".join(parts)


def apple_incomplete(sku: str | None) -> bool:
    """True nếu SKU tổng hợp của Apple thiếu một thông số (có ký tự '?'). Nơi gọi hàm khi đó có
    thể fetch trang sản phẩm và suy luận lại từ tiêu đề đầy đủ hơn của nó (ví dụ
    "... (M5/ Ram 16GB/ SSD 1TB)")."""
    return bool(sku) and sku.startswith("APPLE-") and "?" in sku


_WARRANTY = re.compile(r"^[123]y$")  # gói bảo hành: 2y = 2 năm — LÀ một phần định danh sản phẩm


def _model_code(after: list[str]) -> str:
    """Chọn mã model Dell (dc4c5375w1 / cph99 / …) từ các token đứng sau series:
    token chữ-số dài nhất mà không phải từ rác hay spec CPU.

    Hậu tố bảo hành (-2Y/-1Y/-3Y) được GHÉP vào mã model, KHÔNG bỏ đi: TNC bán cùng một máy dưới 2
    mã khác nhau — vd "...C7U161W11BLU" và "...C7U161W11BLU-2Y" là 2 sản phẩm khác nhau (gói bảo hành
    khác, giá khác). Nếu bỏ "-2Y" thì hai máy gộp vào một SKU → ghi đè nhau, so giá nhầm."""
    cands = [
        t for t in after
        if re.search(r"[a-z]", t) and re.search(r"\d", t) and t not in _JUNK and not _CPU.match(t)
    ]
    if cands:
        code = max(cands, key=len)
        # Nếu ngay sau mã model có token bảo hành (2y/1y/3y), ghép lại thành "<code>-2Y".
        i = after.index(code)
        if i + 1 < len(after) and _WARRANTY.match(after[i + 1]):
            return f"{code}-{after[i + 1]}"
        return code
    rest = [t for t in after if t not in _JUNK and not re.fullmatch(r"\d{1,2}", t)]
    return rest[-1] if rest else (after[-1] if after else "")


def _slug_tail(url: str | None) -> str:
    if not url:
        return ""
    tail = url.rstrip("/").split("/")[-1]
    tail = tail.split("?")[0]
    tail = tail.removesuffix(".html")
    tail = _PV_SUFFIX.sub("", tail)  # bỏ hậu tố --s<id> của Phong Vũ
    return tail.lower()


# ── Monitors (Tier A) ────────────────────────────────────────────────────────────────────────
# Names read "<Màn hình LCD> <brand> <model> <size> inch <res> <panel>". The model code sits right
# after the brand; key on brand + that code, e.g. "DELL-SE2426H", "SAMSUNG-LS24F320GAEXXV".
_MON_PREFIX = re.compile(r"^\s*m[àa]n h[ìi]nh( lcd| led)?\s*", re.I)
_MON_SERIES_WORD = {
    "pro", "thinkvision", "gaming", "ultragear", "odyssey", "nano", "tuf", "rog",
    "ultrasharp", "plus", "curved", "cong",
}
_MON_SPEC_WORD = re.compile(r"^(inch|fhd|qhd|uhd|hd|2k|4k|5k|ips|tn|va|oled|led|curved|cong)$", re.I)
_MON_SIZE = re.compile(r'^\d{2}(\.\d+)?"?$')  # 24, 21.45, 27
_MON_YEAR = re.compile(r"^20\d\d$")

# A spec/measure token that LOOKS alphanumeric but is NOT a model code: 360hz, 0.03ms, 250cd,
# 4k, hdr10, 1920x1080, gsync, 23.8inch (kích thước dính liền "inch") … Không được nhầm là model.
_MON_SPEC_TOKEN = re.compile(
    r"^(fhd|qhd|uhd|hd|[245]k|5k|ips|va|tn|oled|led"
    r"|\d+(\.\d+)?(inch|\")"          # 23.8inch, 24inch, 27"
    r"|\d+hz|\d+(\.\d+)?ms|\d+(\.\d+)?(cd|nits?)|hdr\d*|g?[- ]?sync|\d+x\d+|\d+bit)$",
    re.I,
)


def _mon_model_code(toks: list[str]) -> str | None:
    """The monitor model code = the longest token that mixes letters AND digits and isn't a spec
    measure (360hz, 0.03ms, 4k, …). ASUS ROG puts the code AFTER a panel word ("ROG Strix OLED
    XG27AQDMES"), so we scan the whole name for the code rather than stopping at the first spec.
    """
    cands = [
        t
        for t in toks
        if re.search(r"[a-z]", t)
        and re.search(r"\d", t)
        and len(t) >= 4
        and not _MON_SPEC_TOKEN.match(t)
        and not _MON_SIZE.match(t)
        and not _MON_YEAR.match(t)
    ]
    return max(cands, key=len) if cands else None


# MSI DÙNG LẠI cùng một mã model cho hai màn KHÁC ĐỘ PHÂN GIẢI (274QPF: X30MV=FHD vs X32=WQHD) → nếu
# chỉ key theo mã model chúng gộp làm một, so giá sai. Mã "đời" X##/E## KHÔNG dùng để tách được vì cửa
# hàng ghi tuỳ tiện (An Phát list cùng một màn dưới E20 và X32; 275QF khi E20 khi E21) → tách theo đời
# sẽ vỡ 1 sản phẩm thành nhiều SKU. Thay vào đó, với MÀN HÌNH MSI ta gắn ĐỘ PHÂN GIẢI CHUẨN HOÁ vào
# SKU: độ phân giải xuất hiện ở MỌI listing và LÀ thứ thật sự khác nhau + quyết định giá. Nhờ vậy
# 274QPF tách FHD/WQHD (đúng), còn 274QRFW/275QF/MP251… (cùng độ phân giải) vẫn gộp (đúng), KHÔNG cần
# allowlist thủ công. Gộp bí danh: 2K == QHD == WQHD (2560×1440); 4K == UHD.
_MON_RES_PATTERNS = [
    ("UWQHD", r"uwqhd|3440\s*x\s*1440"),
    ("DQHD",  r"dqhd|5120\s*x\s*1440"),
    ("5K",    r"\b5k\b|5120\s*x\s*2880"),
    ("UHD",   r"\b4k\b|\buhd\b|3840\s*x\s*2160"),
    ("WQHD",  r"\bwqhd\b|\bqhd\b|\b2k\b|2560\s*x\s*1440"),  # 2K/QHD/WQHD là một
    ("FHD",   r"\bfhd\b|full\s*hd|1920\s*x\s*1080"),
]


def _mon_resolution(name: str) -> str | None:
    """Bucket độ phân giải chuẩn hoá từ tên màn hình, hoặc None nếu không nêu. Kiểm tra từ CAO xuống
    THẤP để '2K' không nuốt trước 'UWQHD'. 2K/QHD/WQHD -> WQHD; 4K/UHD -> UHD (gộp bí danh)."""
    n = (name or "").lower()
    for bucket, pat in _MON_RES_PATTERNS:
        if re.search(pat, n):
            return bucket
    return None


def monitor_sku(name: str | None) -> str | None:
    """BRAND-MODEL cho một màn hình LCD, hoặc None nếu không parse được, ví dụ "DELL-SE2426H".

    - Thương hiệu lấy từ `brand_of(name)` — cùng một nguồn chân lý (config/brands.yaml) và các quy
      tắc mà phần còn lại của hệ thống dùng, nên các thương hiệu nhiều từ ("Cooler Master") và các
      từ mô tả dẫn đầu ("cảm ứng", "gaming") được xử lý đúng, không bị cắt cụt.
    - Mã model là token trộn chữ+số dài nhất, bỏ qua các token spec (360hz, 0.03ms, 4k, …), nên nó
      hoạt động kể cả khi hãng đặt mã SAU từ panel ("ASUS ROG Strix OLED XG27AQDMES").
    """
    from .brand import brand_of  # lazy import để tránh phụ thuộc vòng ở thời điểm nạp module
    from .config import name_exclude_re

    # Bỏ phụ kiện lọt lưới name_match: giá đỡ / tay treo màn hình (tên có "màn hình" nhưng không
    # phải màn hình) → None để scraper skip, không tạo SKU rác kiểu "GIÁ-43INCH".
    ex = name_exclude_re("monitor")
    if ex and name and ex.search(name):
        return None

    # Tách trên khoảng trắng, ngoặc, và các dấu phân tách spec / , (nhưng KHÔNG tách trên "-", vì mã
    # model dùng gạch nối: VX2758-2KP-MHD, 27GP750-B). Nhờ vậy khối spec kiểu "(27 inch/FHD/120Hz)"
    # của HACOM tách thành từng token spec riêng, không dính lại thành một "mã" giả dài.
    cleaned = _MON_PREFIX.sub("", (name or "").lower())
    toks = [t for t in re.split(r"[\s()/,]+", cleaned) if t]
    if not toks:
        return None
    brand = brand_of(name).upper()  # "ViewSonic" -> "VIEWSONIC", "Cooler Master" -> "COOLER MASTER"

    # HP puts a marketing name FIRST ("Series 7", "E45c", "S3") and the real part code LAST,
    # before the size — e.g. "HP Series 7 Pro 724pn 8X534AA 24 inch". Key on that trailing code
    # (mirrors the laptop HP rule), not the first digit token which is just the product line.
    if brand == "HP":
        before_size = []
        for t in toks:
            if _MON_SIZE.match(t) or _MON_YEAR.match(t) or _MON_SPEC_WORD.match(t):
                break
            before_size.append(t)
        hp_codes = [t for t in before_size if _HP_CODE.match(t)]
        if hp_codes:
            return f"HP-{hp_codes[-1]}".upper()
        # no part code found — fall through to the generic first-code rule

    # Ưu tiên: mã model là token trộn chữ+số dài nhất (bỏ qua các token spec như 360hz/0.03ms/4k).
    # Bắt được cả trường hợp ASUS ROG đặt mã SAU từ panel ("ROG Strix OLED XG27AQDMES").
    code = _mon_model_code(toks)
    if code:
        if brand == "MSI":  # MSI dùng lại mã model cho các độ phân giải khác nhau -> gắn độ phân giải
            res = _mon_resolution(name)
            if res:
                code = f"{code}-{res}"
        return f"{brand}-{code}".upper().replace(" ", "-")

    # Dự phòng (mã thuần chữ số như LG "27GP750"): đi tới token có-chữ-số đầu tiên, bỏ qua từ mô
    # tả / series / token của chính thương hiệu, dừng ở size/spec.
    brand_toks = set(brand.lower().split())
    model = []
    started = False
    for t in toks:
        if _MON_SIZE.match(t) or _MON_YEAR.match(t) or _MON_SPEC_WORD.match(t):
            if started:
                break
            continue
        if t in _MON_SERIES_WORD or t in brand_toks:  # bỏ từ series / token thương hiệu
            continue
        model.append(t)
        started = True
        if re.search(r"\d", t):  # mã model lõi — dừng trước các mã spec đuôi
            break
    if not model:
        return None
    if brand == "MSI":  # cùng quy tắc: gắn độ phân giải chuẩn hoá vào SKU màn hình MSI
        res = _mon_resolution(name)
        if res:
            model.append(res)
    return f"{brand}-{'-'.join(model)}".upper().replace(" ", "-")


# ── PC / Máy bộ (Tier A) ─────────────────────────────────────────────────────────────────────
# Tên đọc "Máy bộ <BRAND> <dòng> <(mã cấu hình)> <spec>". Ưu tiên mã 8 chữ số trần (định danh duy
# nhất, như Dell laptop); nếu không, khoá theo dòng + mã cấu hình trong ngoặc (nhiều máy cùng dòng
# "ECT1250" chỉ khác nhau ở mã trong ngoặc TFPC81/TFPC812). Máy build không mã (chỉ có spec) -> None.
_PC_PREFIX = re.compile(r"^\s*m[áa]y b[ộo]\s*", re.I)
_PC_SPEC = re.compile(
    r"^(tower|slim|mini|pro|essential|gen\d|g\d+|pci|nuc|văn|phòng|van|phong|\d+y|"
    r"\d+gb?|\d+tb|\d{2,4}g|ram|ssd|hdd|ryzen|core|ultra|u\d|r\d|win\d*|ddr\d|"
    r"i[3579](-\S+)?|\d{4,5}[a-z]{1,2}|\d+w|aio|inch|"
    r"\d{2,4}[uhpt]|\d{3,4}[a-z]?|"     # hậu tố CPU: 100U, 13420H, 1315U, 1235U, 12M
    r"\d+x\d+(\.\d+)?|a\d{3,4}|rtx|xeon|silver|gold|platinum)$",  # 6x2.5 (khay ổ), A400/RTX GPU, Xeon
    re.I,
)


def pc_sku(name: str | None) -> str | None:
    """BRAND-CODE cho một máy bộ (PC), hoặc None nếu không có mã dùng được (máy build theo spec)."""
    from .brand import brand_of  # lazy import để tránh phụ thuộc vòng ở thời điểm nạp module

    if not name:
        return None
    brand = brand_of(name)
    if brand.lower() in ("other", "máy", "may"):   # brand không nhận diện được -> không đoán
        return None
    # 1. mã 8 chữ số trần — định danh duy nhất, ưu tiên trước.
    m = _EIGHT.search(name)
    if m:
        return f"{brand}-{m.group(1)}".upper()
    # 2. dòng + (các) mã cấu hình chữ+số, bỏ spec / brand lặp; giữ tối đa 2 mã đầu (dòng + config).
    body = _PC_PREFIX.sub("", name)
    toks = [t for t in re.split(r"[\s()/]+", body) if t]
    codes: list[str] = []
    for t in toks:
        if not (re.search(r"[a-z]", t, re.I) and re.search(r"\d", t)):
            continue
        if len(t) < 4 or _PC_SPEC.match(t) or t.upper() == brand.upper():
            continue
        if t.upper() not in codes:
            codes.append(t.upper())
    if codes:
        return f"{brand}-{'-'.join(codes[:2])}".upper()
    return None


# ── RAM (Tier A) ─────────────────────────────────────────────────────────────────────────────
# Tên đọc "Ram Desktop <BRAND> <capacity> <DDRx> Bus <speed> <MÃ PART>". Định danh là MÃ PART của
# nhà sản xuất (KVR56U46BS8-16WP, CMH64GX5M2D6000C40, F4-3200C16S-16GIS) — in giống nhau ở mọi cửa
# hàng. KHÔNG tách trên "/" (mã Kingston KF432C16BB/8WP dùng "/"; "/8WP" phân biệt dung lượng).
# RAM chỉ có spec (không mã) -> khoá tổng hợp BRAND-CAP-SPEED để cùng spec vẫn khớp, thay vì bắt
# nhầm "3200mhz" làm mã.
_RAM_SPEC = re.compile(
    r"^(ram|desktop|laptop|sodimm|udimm|dimm|bus|ddr\d|\d+gb|\d+mb|\d+mhz|\d+mt/?s|"
    r"cl\d+|\d+\.\d+v|rgb|kit|pc\d*|vengeance|fury|trident|ripjaws|xpg|dominator|"
    r"\d+[x*]\d+gb?|\d+[x*]\d+|lpx|beast|lancer|elite|heat|spreader|oc|aura\d*|nox)$",
    re.I,
)
_RAM_CAP = re.compile(r"(\d+)\s*gb", re.I)          # dung lượng
_RAM_SPEED = re.compile(r"(\d{4,5})\s*(mhz|mt/?s)", re.I)   # bus/speed

# Dòng sản phẩm RAM (in giống nhau ở mọi cửa hàng) — dùng để phân biệt các RAM cùng cap+speed.
_RAM_LINES = (
    "xtreem", "vulcan", "delta", "elite", "t-create", "tcreate", "vengeance", "dominator",
    "fury", "beast", "renegade", "trident", "ripjaws", "flare", "aegis", "lancer",
    "gammix", "spectrix", "predator", "viper", "ballistix", "nitro",
)
_RAM_COLORS = ("black", "white", "red", "silver", "đen", "trắng", "bạc", "xám", "grey", "gray")


def _ram_line(name: str) -> str:
    """Ghép DÒNG + MÀU của thanh RAM (ví dụ 'XTREEM-BLACK') để tránh đụng khoá khi cùng cap/speed.
    Trả về '' nếu tên không có token nào — khi đó khoá tổng hợp lùi về brand+cap+speed như cũ."""
    low = name.lower()
    line = next((w for w in _RAM_LINES if w in low), "")
    color = next((c for c in _RAM_COLORS if re.search(rf"\b{re.escape(c)}\b", low)), "")
    # chuẩn hoá màu tiếng Việt -> tiếng Anh để cùng sản phẩm ở các cửa hàng ra cùng khoá
    color = {"đen": "black", "trắng": "white", "bạc": "silver", "xám": "grey", "gray": "grey"}.get(
        color, color
    )
    return "-".join(p for p in (line, color) if p)


def ram_sku(name: str | None) -> str | None:
    """BRAND-PARTCODE cho RAM; nếu không có mã, khoá tổng hợp BRAND-<cap>GB-<speed>. None nếu trống."""
    from .brand import brand_of

    if not name:
        return None
    brand = brand_of(name)
    if brand.lower() in ("other",):
        return None
    # Tách trên khoảng trắng (GIỮ "/" trong token — thuộc mã part).
    toks = [t for t in re.split(r"[\s()]+", name) if t]
    codes = [
        t for t in toks
        if re.search(r"[a-z]", t, re.I) and re.search(r"\d", t)
        and len(t) >= 6 and not _RAM_SPEC.match(t)
    ]
    if codes:
        code = max(codes, key=len)
        # Bỏ hậu tố CHƯƠNG TRÌNH BẢO HÀNH đứng ở CUỐI mã Kingston: "...D8/16WP" vs "...D8/16" là CÙNG
        # thanh RAM (WP = warranty program, TNC bỏ đi). Chỉ cắt "WP" ĐỨNG SAU một chữ số ở cuối mã —
        # không đụng phần lõi. KHÔNG cắt "W"/"K" đơn lẻ (Corsair C40W vs C40K là màu khác nhau).
        code = re.sub(r"(?<=\d)WP$", "", code, flags=re.I)
        return f"{brand}-{code}".upper().replace(" ", "-")
    # Không có mã part → khoá tổng hợp. PHẢI kèm DÒNG sản phẩm + MÀU, không chỉ cap+speed: nhiều
    # RAM khác nhau trùng dung lượng/tốc độ (Vulcan vs Delta vs Xtreem; Black vs White) sẽ đụng cùng
    # một SKU → ghi đè nhau trong catalog, trộn tình trạng còn/hết hàng, và so giá NHẦM sản phẩm.
    # Dòng & màu được in nhất quán ở mọi cửa hàng nên vẫn khớp chéo được.
    cap = _RAM_CAP.search(name)
    spd = _RAM_SPEED.search(name)
    if cap and spd:
        line = _ram_line(name)
        parts = [brand]
        if line:
            parts.append(line)
        parts += [f"{cap.group(1)}GB", spd.group(1)]
        return "-".join(parts).upper().replace(" ", "-")
    return None


# ── SSD / HDD (Tier A) ───────────────────────────────────────────────────────────────────────
# Tên đọc "Ổ cứng SSD <cap> <BRAND> <dòng> <MÃ PART>". Định danh là mã part (MZ-V9P1T0BW,
# WDS100T3B0A, SA400S37/240G) — in giống nhau ở mọi cửa hàng. Không tách "/" (mã Kingston có
# "/240G"). Ổ chỉ có spec (không mã) -> khoá tổng hợp BRAND-<cap>-<giao tiếp>.
_SSD_SPEC = re.compile(
    r"^(ổ|o|cứng|cung|ssd|hdd|gắn|gan|trong|inch|sata|nvme|pcie|m\.?2|2280|2\.5|3\.5|"
    r"gen\d|\d+gb|\d+tb|\d+mb/s|x\d|iii|ii|internal|external|portable|"
    r"western|digital|black|blue|green|red|evo|pro|plus)$",
    re.I,
)
_SSD_CAP = re.compile(r"(\d+)\s*(gb|tb)", re.I)
_SSD_IFACE = re.compile(r"\b(nvme|sata|pcie)\b", re.I)


def ssd_sku(name: str | None) -> str | None:
    """BRAND-PARTCODE cho SSD/HDD; nếu không mã, khoá tổng hợp BRAND-<cap>-<giao tiếp>."""
    from .brand import brand_of

    if not name:
        return None
    brand = brand_of(name)
    if brand.lower() in ("other",):
        return None
    toks = [t for t in re.split(r"[\s()]+", name) if t]
    codes = [
        t for t in toks
        if re.search(r"[a-z]", t, re.I) and re.search(r"\d", t)
        and len(t) >= 6 and not _SSD_SPEC.match(t)
    ]
    if codes:
        return f"{brand}-{max(codes, key=len)}".upper().replace(" ", "-")
    cap = _SSD_CAP.search(name)
    iface = _SSD_IFACE.search(name)
    if cap:
        parts = [brand, f"{cap.group(1)}{cap.group(2)}"]
        if iface:
            parts.append(iface.group(1))
        return "-".join(parts).upper().replace(" ", "-")
    return None


# ── Bàn phím / Chuột / Combo (Tier A) ────────────────────────────────────────────────────────
# Tên đọc "<loại> <mô tả> <BRAND> <MODEL> (<màu>)", ví dụ "Chuột Gaming có dây Logitech G102 màu
# đen", "Bàn phím DELL KB216". Định danh = mã model ngắn (G102, KB216, MK240, DX-110) in giống
# nhau ở mọi cửa hàng. HP giấu mã part thật trong ngoặc — "(266C9AA)" — nên ưu tiên mã đó (giống
# quy tắc HP laptop/màn hình). Model chỉ có màu/không mã -> None (không tạo SKU rác).
_PERIPH_SPEC = re.compile(
    r"^(bàn|ban|phím|phim|chuột|chuot|combo|mouse|keyboard|kb|gaming|văn|van|phòng|phong|"
    r"có|co|không|khong|dây|day|dai|wireless|wired|bluetooth|cơ|co|số|so|silent|slim|"
    r"mode|mini|led|rgb|switch|blue|red|brown|black|white|đen|den|trắng|trang|xám|xam|"
    r"xanh|hồng|hong|đỏ|do|graphite|rose|gen|ii|iii|màu|mau|pro|plus|new|2\.4g|usb)$",
    re.I,
)
_PERIPH_COLOR_TAIL = re.compile(r"\s*\((?![^)]*[A-Z]{2,}\d)[^)]*\)\s*$")  # bỏ đuôi "(màu đen)" nhưng GIỮ "(266C9AA)"


def peripheral_sku(name: str | None) -> str | None:
    """BRAND-MODEL cho bàn phím / chuột / combo, ví dụ "LOGITECH-G102", "HP-266C9AA"."""
    from .brand import brand_of

    if not name:
        return None
    brand = brand_of(name)
    if brand.lower() == "other":
        return None
    BRAND = brand.upper()

    # HP để mã part thật trong ngoặc: "Chuột ... HP 105 (822M9AA)" — ưu tiên mã đó (giống HP laptop).
    parens = re.findall(r"\(([^)]*)\)", name)
    for p in parens:
        for t in re.split(r"[\s/,]+", p):
            if _HP_CODE.match(t):
                return f"{BRAND}-{t}".upper().replace(" ", "-")

    # Bỏ đuôi màu trong ngoặc rồi tách token. Mã model = token trộn chữ+số dài nhất KHÔNG phải spec.
    cleaned = _PERIPH_COLOR_TAIL.sub("", name)
    toks = [t for t in re.split(r"[\s()]+", cleaned) if t]
    brand_toks = set(brand.lower().split())
    cands = [
        t for t in toks
        if re.search(r"[a-z]", t, re.I) and re.search(r"\d", t)
        and len(t) >= 3 and not _PERIPH_SPEC.match(t)
        and t.lower() not in brand_toks
    ]
    if cands:
        return f"{BRAND}-{max(cands, key=len)}".upper().replace(" ", "-")
    return None


# ── USB / Thẻ nhớ (Tier A) ───────────────────────────────────────────────────────────────────
# Tên đọc "USB <cap> <BRAND> <dòng> <MÃ>", ví dụ "USB 64GB Sandisk CZ430", "USB Kingston
# DataTraveler Exodia S 64GB DTXS/64GB". Mã (CZ430, CZ73, DTXS/64GB) in giống nhau mọi nơi NHƯNG
# cùng một mã bán nhiều dung lượng (CZ50 có 16/32/64GB) -> PHẢI kèm dung lượng để khỏi đụng SKU.
_USB_SPEC = re.compile(
    r"^(usb|thẻ|the|nhớ|nho|card|memory|flash|drive|ổ|o|cứng|cung|di|động|dong|"
    r"\d+gb|\d+tb|\d+mb|2\.0|3\.0|3\.1|3\.2|type-?c|otg|class\d+|u\d|v\d+|a\d+|"
    r"sandisk|kingston|ultra|luxe|flair|blade|cruzer|datatraveler|exodia)$",
    re.I,
)
_USB_CAP = re.compile(r"(\d+)\s*(gb|tb)", re.I)


def usb_sku(name: str | None) -> str | None:
    """BRAND-MODEL-CAP cho USB / thẻ nhớ (dung lượng bắt buộc — cùng mã bán nhiều cỡ)."""
    from .brand import brand_of

    if not name:
        return None
    brand = brand_of(name)
    if brand.lower() == "other":
        return None
    BRAND = brand.upper()
    cap = _USB_CAP.search(name)
    cap_s = f"{cap.group(1)}{cap.group(2).upper()}" if cap else None

    # Mã part: token trộn chữ+số (GIỮ "/" — mã Kingston "DTXS/64GB"), bỏ token spec/dung lượng.
    toks = [t for t in re.split(r"[\s()]+", name) if t]
    cands = [
        t for t in toks
        if re.search(r"[a-z]", t, re.I) and re.search(r"\d", t)
        and len(t) >= 3 and not _USB_SPEC.match(t)
    ]
    if cands:
        code = max(cands, key=len)
        # Nếu mã đã chứa dung lượng (DTXS/64GB) thì đủ định danh; nếu không, gắn thêm cap.
        base = f"{BRAND}-{code}"
        if cap_s and not re.search(r"\d+\s*(gb|tb)", code, re.I):
            base = f"{base}-{cap_s}"
        return base.upper().replace(" ", "-")
    return None


# ── HDD/SSD Box & Docking (Tier A) ───────────────────────────────────────────────────────────
# Tên đọc "<Box/Dock> <mô tả giao tiếp> <BRAND> <MÃ>", ví dụ "... ORICO-6218US3-BK", "HDD BOX
# Ugreen 30847". Mã Orico có chữ+số; mã Ugreen thuần số (30847) nên PHẢI có tiền tố BRAND để phân
# biệt. Định danh = BRAND-MÃ.
_BOX_SPEC = re.compile(
    r"^(box|dock|docking|hộp|hop|đựng|dung|đế|de|ổ|o|cứng|cung|ssd|hdd|khay|inch|"
    r"sata|usb|nvme|m\.?2|m2|type-?c|gen\d?|2\.5|3\.5|3\.0|3\.1|3\.2|2\.0|"
    r"đen|den|trắng|trang|xám|xam|bk|gy|cr|1|2)$",
    re.I,
)


def box_sku(name: str | None) -> str | None:
    """BRAND-MODEL cho box/docking ổ cứng, ví dụ "ORICO-6218US3-BK", "UGREEN-30847"."""
    from .brand import brand_of

    if not name:
        return None
    brand = brand_of(name)
    if brand.lower() == "other":
        return None
    BRAND = brand.upper()

    # Tách trên khoảng trắng + ngoặc + "," + "/" (GIỮ "-": mã Orico "6218US3-BK", "AXM2-G2-GY-BP").
    # Tách "/" để "3.5 inch/2.5 inch" rã ra token spec, không dính thành "inch/2.5" giả làm mã.
    toks = [t for t in re.split(r"[\s(),/]+", name) if t]
    # Mã Orico đôi khi dính brand: "ORICO-6218US3-BK" -> tách brand ra khỏi đầu token.
    norm = []
    for t in toks:
        low = t.lower()
        if low.startswith("orico-"):
            t = t[len("orico-"):]
        norm.append(t)
    brand_toks = set(brand.lower().split())
    # Mã có chữ+số (Orico 6218US3-BK, AXM2-G2-GY-BP): chọn token dài nhất không phải spec.
    codes = [
        t for t in norm
        if re.search(r"[a-z]", t, re.I) and re.search(r"\d", t)
        and len(t) >= 4 and not _BOX_SPEC.match(t) and t.lower() not in brand_toks
    ]
    if codes:
        return f"{BRAND}-{max(codes, key=len)}".upper().replace(" ", "-")
    # Ugreen: mã thuần số (30847). Chọn token số dài nhất (>=4 chữ số) không phải spec kích thước.
    nums = [t for t in norm if re.fullmatch(r"\d{4,}", t) and not _BOX_SPEC.match(t)]
    if nums:
        return f"{BRAND}-{max(nums, key=len)}".upper().replace(" ", "-")
    return None


# ── Thiết bị mạng: Router / Switch / Access Point / Controller (Tier A) ────────────────────────
# Tên đọc "<loại> <mô tả> <BRAND> <dòng> <MODEL> (<specs>)", ví dụ "Router Wifi TP-Link Archer
# AX12 (1500Mbps/Wifi 6)", "Switch D-link DGS-105GL (5 port)", "Access Point TP-Link Omada
# EAP670". Định danh = mã model (token trộn chữ+số DÀI NHẤT, giữ "-": TL-SG108, DGS-105GL,
# RG-RAP6260), bỏ token spec mạng (1500mbps, wifi, ax5400, 2.4/5ghz, poe, gigabit, port…).
#
# BUG ĐÃ SỬA (2026-08) — "N-pack" bị lấy nhầm làm mã model: TP-Link Deco bán theo bộ ("Deco X10
# (2-pack)", "Deco X50 (1-pack)", "Deco E4 (3-Pack)"). Token "2-pack"/"3-pack" CÓ CẢ chữ lẫn số và
# DÀI HƠN mã model thật (X10/X50/E4 chỉ 3 ký tự) — vì is_code() chọn token dài nhất (max(...,
# key=len)), "2-pack" thắng "X10" và trở thành "mã" giả. Kết quả: SKU ra TP-LINK-2-PACK /
# TP-LINK-1-PACK / TP-LINK-3-PACK — gộp/tách nhầm theo SỐ LƯỢNG PACK thay vì theo DÒNG MÁY, trong
# khi "Deco" (mã dòng thật) không hề chứa chữ số nên chưa từng được coi là candidate.
# Sửa: (1) thêm "N-pack"/"N pack" vào _NET_SPEC để nó KHÔNG được chọn làm mã model; (2) số lượng
# pack VẪN LÀ một phần định danh thật (Deco X50 1-pack ≠ 3-pack, giá khác hẳn) nên tách riêng
# thành hậu tố qua with_pack(), y hệt cách with_tier() đang ghép "Pro/Lite/Plus/Max".
_NET_SPEC = re.compile(
    r"^(router|switch|hub|access|point|ap|bộ|bo|phát|phat|wifi|wi-fi|wlan|controller|gateway|"
    r"mesh|poe|gigabit|unmanaged|managed|smart|omada|unifi|eagle|pro|ai|nano|lite|vigor|"
    r"\d+mbps|\d+gbps|\d+g|wifi\d|n\d{3,}|"
    r"(ax|ac|be|n)\d{3,4}mbps|"                            # AX5400MBPS/AC1200MBPS/AC750MBPS: chuẩn wifi
                                                          # DÍNH "mbps" -> là SPEC, KHÔNG phải mã model
    r"802\.11[a-z]*|"                                      # 802.11ax/ac: chuẩn wifi, không phải model
    r"\d+(\.\d+)?ghz|\d(\.\d)?/\d(\.\d)?ghz|ghz|"          # 5ghz, 2.4ghz, 2.4/5ghz
    r"\d+port|port|dual|band|indoor|outdoor|sfp|xgs|"
    r"\d+-?\s*pack)$",                                     # "2-pack"/"3-pack"/"1 pack" — SỐ LƯỢNG,
                                                          # không phải mã model (xem ghi chú BUG ở trên)
    re.I,
)

# Số lượng bộ (pack) — TÁCH RIÊNG thành hậu tố vì nó LÀ một phần định danh thật (Deco X50 1-pack
# và 3-pack là hai gói khác nhau, giá chênh lệch rõ), không phải filler để bỏ đi hoàn toàn như các
# token spec khác trong _NET_SPEC.
_NET_PACK = re.compile(r"(\d+)\s*-?\s*pack", re.I)


def network_sku(name: str | None) -> str | None:
    """BRAND-MODEL cho router/switch/AP/controller, ví dụ "TP-LINK-ARCHER-AX12" → "TP-LINK-AX12".

    Mã model = token chữ+số dài nhất KHÔNG phải spec mạng. Giữ "-" (mã có gạch: TL-SG108,
    DGS-105GL). Bỏ dòng sản phẩm thuần chữ (Archer/Omada) và spec (wifi6/ax5400/mbps/port).
    Số lượng "N-pack" (nếu có) được tách riêng và ghép làm hậu tố — xem with_pack().
    """
    from .brand import brand_of

    if not name:
        return None
    brand = brand_of(name)
    if brand.lower() == "other":
        return None
    BRAND = brand.upper()

    # Tách trên khoảng trắng + ngoặc + "," + "/" (GIỮ "-": mã "TL-SG108", "DGS-105GL"). Tách "/"
    # để "1500Mbps/Wifi 6" và "10/100/1000Mbps" rã thành token spec riêng, không dính thành mã giả.
    toks = [t for t in re.split(r"[\s(),/]+", name) if t]
    brand_toks = set(brand.lower().replace("-", " ").split())
    # Chuẩn wifi: AX/AC/BE/N + 3-4 chữ số (AX5400, AC1200, BE5000, N300). PHÂN BIỆT với mã model
    # ngắn cùng tiền tố (Archer "AX12", "AX72" — chỉ 1-2 chữ số) nên KHÔNG loại nhầm mã model.
    wifi_class = re.compile(r"^(ax|ac|be|n)\d{3,4}$", re.I)

    def is_code(t: str) -> bool:
        if t.lower() in brand_toks or not re.search(r"\d", t):
            return False
        if not re.search(r"[a-z]", t, re.I):
            return False
        # Chấp nhận mã ngắn dạng <chữ><số> (Archer "C54"/"C64", D-Link "R15") ≥3 ký tự; các token
        # khác cần ≥4 để tránh nhiễu. "2-pack"/"8t" bị loại vì bắt đầu bằng SỐ.
        if re.fullmatch(r"[a-z]{1,2}\d{2,3}[a-z]?", t, re.I):
            return len(t) >= 3
        return len(t) >= 4

    def with_tier(code: str) -> str:
        """Ghép HẠNG sản phẩm (Pro/Lite/Plus/Max) nếu nó đứng NGAY SAU mã model. "Pro" trên router là
        BIẾN THỂ THẬT (AX55 vs AX55 Pro — giá khác), không phải spec — bỏ đi thì hai máy gộp một SKU.
        Chỉ ghép khi hạng ĐỨNG SAU đúng token mã (tránh gắn "Pro" của phần khác trong tên)."""
        try:
            i = toks.index(code)
        except ValueError:
            return code
        if i + 1 < len(toks) and toks[i + 1].lower() in ("pro", "lite", "plus", "max"):
            return f"{code}-{toks[i + 1]}"
        return code

    def with_pack(code: str) -> str:
        """Ghép SỐ LƯỢNG BỘ (N-pack) nếu tên có nêu — Deco X50 1-pack và Deco X50 3-pack là hai
        gói khác nhau, giá khác nhau thật, gộp chung sẽ ghi đè nhau trong catalog (xem ghi chú BUG
        ở đầu khối network). Quét trên toàn bộ tên gốc (không chỉ toks) vì "(2-pack)" có thể đã bị
        _NET_SPEC loại khỏi danh sách candidate code trước khi tới đây."""
        m = _NET_PACK.search(name)
        return f"{code}-{m.group(1)}PACK" if m else code

    cands = [
        t for t in toks
        if is_code(t) and not _NET_SPEC.match(t) and not wifi_class.match(t)
    ]
    if cands:
        return f"{BRAND}-{with_pack(with_tier(max(cands, key=len)))}".upper().replace(" ", "-")
    # Dự phòng: model ngắn trùng hình dạng chuẩn wifi (Archer "C54"/"AX12" khi mọi token khác đều
    # là spec). Lấy token chữ+số dài nhất còn lại (kể cả wifi-class) — thà có SKU còn hơn None.
    fallback = [t for t in toks if is_code(t) and not _NET_SPEC.match(t)]
    if fallback:
        return f"{BRAND}-{with_pack(with_tier(max(fallback, key=len)))}".upper().replace(" ", "-")
    return None


# CPU: mã model LÀ danh tính. "Intel Core i5" KHÔNG đủ — i5-14400, i5-12400F, i5-12600K là các sản
# phẩm khác nhau, giá khác nhau. Hậu tố cũng có nghĩa: 14700 / 14700F / 14700K / 14700KF là 4 CPU
# khác nhau (F = không có iGPU, K = mở hệ số nhân). Vì vậy SKU = BRAND-LINE-MODEL, giữ nguyên hậu tố.
#   "CPU Intel Core i5-14400F"                  → INTEL-CORE-I5-14400F
#   "Bộ vi xử lý Intel Core i5 14400F / 4.7GHz" → INTEL-CORE-I5-14400F   (khớp chéo cửa hàng)
#   "CPU Intel Core Ultra 7 265K"               → INTEL-ULTRA-7-265K
#   "CPU AMD Ryzen 9 9950X3D"                   → AMD-RYZEN-9-9950X3D
#   "CPU AMD Ryzen Threadripper PRO 9955WX"     → AMD-THREADRIPPER-PRO-9955WX
_CPU_MODEL = re.compile(r"^\d{3,5}[a-z0-9]*$", re.I)   # 14400, 14400F, 9950X3D, 265K, 5500GT


def cpu_sku(name: str | None) -> str | None:
    """BRAND-LINE-MODEL cho CPU rời (Intel/AMD).

    Tên ở các cửa hàng khác nhau chỉ giống nhau ở phần ĐẦU (thương hiệu + dòng + mã); phần đuôi là
    spec tự do (" / 3.6GHz Boost / 6 nhân 12 luồng / 16MB / AM4"). Vì vậy chỉ lấy phần định danh và
    BỎ toàn bộ spec — nhờ đó TNC và GearVN cùng ra một SKU.
    """
    if not name:
        return None
    n = name.lower()
    # Cắt phần spec sau dấu "/" hoặc "(" — GearVN/TNC nhét thông số vào đó.
    n = re.split(r"[/(]", n)[0]
    # Bỏ tiền tố mô tả ("cpu", "bộ vi xử lý", "bo vi xu ly", "processor").
    n = re.sub(r"^\s*(cpu|bộ vi xử lý|bo vi xu ly|processor)\s*", " ", n)
    # Chuẩn hoá "i5-14400" và "i5 14400" về cùng một dạng (dấu gạch ↔ khoảng trắng).
    n = n.replace("-", " ")
    toks = [t for t in re.split(r"[\s,]+", n) if t]
    if not toks:
        return None

    if "intel" in toks:
        # Intel Core Ultra 7 265K  |  Intel Core i5 14400F  |  Intel Xeon E-2314
        if "ultra" in toks:
            i = toks.index("ultra")
            tier = toks[i + 1] if i + 1 < len(toks) else ""          # 5 / 7 / 9
            model = next((t for t in toks[i + 2:] if _CPU_MODEL.match(t)), "")
            # "Plus" là BIẾN THỂ THẬT của Intel (Arrow Lake Refresh) — giữ lại để
            # sau này Intel ra bản không-Plus cùng số thì hai SKU vẫn tách nhau.
            plus = "-PLUS" if "plus" in toks[i:] else ""
            return f"INTEL-ULTRA-{tier}-{model}{plus}".upper().rstrip("-") if model else None
        if "xeon" in toks:
            i = toks.index("xeon")
            rest = [t for t in toks[i + 1:] if re.search(r"\d", t)]
            return f"INTEL-XEON-{'-'.join(rest[:2])}".upper() if rest else None
        # Core i3/i5/i7/i9 — mã đứng ngay sau token "iN"
        for i, t in enumerate(toks):
            if re.fullmatch(r"i[3579]", t):
                model = next((x for x in toks[i + 1:] if _CPU_MODEL.match(x)), "")
                return f"INTEL-CORE-{t}-{model}".upper().rstrip("-") if model else None
        # Dòng phổ thông: Celeron G4900, Pentium Gold G6400 (mã bắt đầu bằng "G" + số).
        for line in ("celeron", "pentium"):
            if line in toks:
                i = toks.index(line)
                model = next((x for x in toks[i + 1:] if re.fullmatch(r"g\d{3,4}", x, re.I)), "")
                return f"INTEL-{line}-{model}".upper().rstrip("-") if model else None
        return None

    # Athlon: TNC ghi "CPU Athlon 3000G" — KHÔNG có token "amd", nên phải bắt riêng ở đây.
    if "athlon" in toks:
        i = toks.index("athlon")
        model = next((t for t in toks[i + 1:] if _CPU_MODEL.match(t)), "")
        return f"AMD-ATHLON-{model}".upper().rstrip("-") if model else None

    if "amd" in toks or "ryzen" in toks:
        # Threadripper (PRO) 9955WX — dòng riêng, không có bậc số
        if "threadripper" in toks:
            i = toks.index("threadripper")
            pro = "-PRO" if "pro" in toks[i:] else ""
            model = next((t for t in toks[i + 1:] if _CPU_MODEL.match(t)), "")
            return f"AMD-THREADRIPPER{pro}-{model}".upper().rstrip("-") if model else None
        if "ryzen" in toks:
            i = toks.index("ryzen")
            tier = toks[i + 1] if i + 1 < len(toks) and re.fullmatch(r"[3579]", toks[i + 1]) else ""
            model = next((t for t in toks[i + 1:] if _CPU_MODEL.match(t)), "")
            if not model:
                return None
            return f"AMD-RYZEN-{tier}-{model}".upper().replace("--", "-").rstrip("-")
        return None

    return None


# ── Máy in / scan / UPS / máy chiếu / TV ──────────────────────────────────────────────────────
# Tất cả đều dạng "<mô tả> <BRAND> <mã model>": Epson L3250, Canon LBP121dn, HP Laser 108w (4ZB80A),
# Santak TG 750 PRO, Panasonic PT-VW360, Samsung UA55U8500F. Định danh = BRAND + mã model (token trộn
# chữ+số dài nhất, không phải spec). Cùng máy in ở mọi cửa hàng đều in cùng mã nên khớp chéo được.
_AV_SPEC = re.compile(
    r"^(máy|may|in|scan|ups|bộ|bo|lưu|luu|điện|dien|máy chiếu|chiếu|chieu|tivi|smart|google|"
    r"qled|oled|uhd|led|lcd|4k|8k|full|hd|1080p|2025|2024|inch|"
    r"laser|wifi|đơn|don|đa|da|năng|nang|trắng|trang|đen|den|màu|mau|"
    r"\d+va|\d+w|\d+va/\d+w|va|online|offline|line|interactive|pro|lumens|ansi|3lcd|"
    r"a4|a3|adf|usb|đảo|dao|mặt|mat)$",
    re.I,
)


def av_sku(name: str | None) -> str | None:
    """BRAND-MODEL cho máy in / scan / UPS / máy chiếu / TV.

    Mã model = token trộn chữ+số DÀI NHẤT không phải spec. Giữ "-" (mã có gạch: PT-VW360, DS-UPS1000,
    LV-HD420). HP để mã part thật trong ngoặc (vd "HP Laser 108w (4ZB80A)") — ưu tiên mã đó.
    """
    from .brand import brand_of

    if not name:
        return None
    brand = brand_of(name)
    if brand.lower() == "other":
        return None
    BRAND = brand.upper()

    # HP/Canon/Epson hay để mã part thật trong ngoặc — ưu tiên mã đó (giống HP laptop/peripheral).
    # NHƯNG chỉ khi ngoặc là MÃ PART, không phải spec: UPS ghi "(Line Interactive/1200VA/650W)" và
    # "1200VA" cũng khớp _HP_CODE → phải loại token spec (chứa VA/W) trước khi nhận là mã part.
    for p in re.findall(r"\(([^)]*)\)", name):
        if re.search(r"\d+\s*(va|kva|w)\b|/", p, re.I):
            continue  # ngoặc chứa spec công suất / dấu "/" → bỏ, không phải mã part
        for t in re.split(r"[\s/,]+", p):
            if _HP_CODE.match(t):
                return f"{BRAND}-{t}".upper().replace(" ", "-")

    # KHÔNG tách trên "/" ở đây: mã part có thể chứa "/" hiếm, nhưng spec "1200VA/650W" cũng vậy —
    # ta lọc spec riêng bên dưới. Tách trên khoảng trắng + ngoặc + ",".
    raw = [t for t in re.split(r"[\s(),]+", name) if t]
    # "121dn" đứng sau "LBP" (mã bị tách rời) → ghép lại thành "LBP121dn". Ghép token toàn-CHỮ ngắn
    # (2-4 ký tự, vd LBP/DCP) với token số-chữ ngay sau nó.
    toks: list[str] = []
    i = 0
    while i < len(raw):
        t = raw[i]
        nxt = raw[i + 1] if i + 1 < len(raw) else ""
        _MERGE_SKIP = {"máy", "may", "pro", "led", "lcd", "hd", "uhd", "4k", "8k",
                       "inch", "in", "qled", "oled", "ai", "smart", "full", "mini"}
        if (re.fullmatch(r"[a-z]{2,4}", t, re.I) and t.lower() not in _MERGE_SKIP
                and re.match(r"^\d", nxt) and re.search(r"[a-z]", nxt, re.I) and "/" not in nxt):
            toks.append(t + nxt)
            i += 2
            continue
        toks.append(t)
        i += 1
    brand_toks = set(brand.lower().replace("-", " ").split())

    def is_spec_code(t: str) -> bool:
        # Token có "/" thường là chuỗi spec ghép (Offline/1000VA, Interactive/1200VA/650W).
        if "/" in t:
            return True
        # Spec công suất VA/kVA: an toàn để bỏ vì KHÔNG mã model nào kết thúc bằng "VA".
        if re.search(r"\d+\s*(va|kva)\b", t, re.I):
            return True
        # Spec Watt "650W", "1200W": chỉ bỏ khi token là W THUẦN TÚY (số + W), KHÔNG bỏ mã model kết
        # thúc bằng W (LBP6030W, P2505W, T420W, DCP-T430W đều là mã máy in hợp lệ).
        return bool(re.fullmatch(r"\d+w", t, re.I))

    def is_code(t: str) -> bool:
        tl = t.lower()
        if tl in brand_toks or _AV_SPEC.match(t) or is_spec_code(t):
            return False
        return bool(re.search(r"\d", t)) and len(t) >= 3

    cands = [t for t in toks if is_code(t)]
    if not cands:
        return None
    # Ưu tiên mã CÓ CẢ chữ lẫn số (mã model thật: BVG1200I-MSN, UA55U8500F) hơn mã chỉ toàn số (750,
    # 400 — thường là công suất/đời). Trong mỗi nhóm lấy token dài nhất.
    mixed = [t for t in cands if re.search(r"[a-z]", t, re.I)]
    pick = max(mixed, key=len) if mixed else max(cands, key=len)
    return f"{BRAND}-{pick}".upper().replace(" ", "-")


# ── Máy tính bảng / tablet ─────────────────────────────────────────────────────────────────────
# Lenovo/Samsung/Xiaomi có mã part (ZAEF0103VN, SM-X710) → dùng luôn.
#
# iPAD — khoá theo THÔNG SỐ, KHÔNG theo MPN. Lý do (bài học từ vụ laptop Apple): MPN (MXN63ZA/A) chỉ
# CÓ ở TNC/Phong Vũ; FPT & TGĐĐ ghi tên marketing "iPad Air M4 128GB" KHÔNG kèm MPN → khoá theo MPN
# thì hai bên KHÔNG BAO GIỜ khớp. Thông số (dòng + chip + size + dung lượng) in ở MỌI cửa hàng nên
# khoá theo nó mới khớp chéo được.
#   BỎ MÀU: iPad Air M4 256GB dù Purple/Blue/Starlight đều CÙNG GIÁ — với công cụ SO GIÁ thì màu là
#   cosmetic, gộp màu là ĐÚNG (khác vụ RAM/laptop nơi token bị gộp làm đổi cả spec lẫn giá). FPT/TGĐĐ
#   cũng không ghi màu, nên khoá không-màu là tập chung khớp được.
_IPAD_MPN = re.compile(r"^[A-Z0-9]{5,6}(ZA|LL|VN|ZP)/A$", re.I)   # MXN63ZA/A — chỉ dùng làm DỰ PHÒNG
_TABLET_CODE = re.compile(r"^(?=.*[a-z])(?=.*\d)[a-z0-9]{6,}$", re.I)  # ZAEF0103VN, SM-X710


def _ipad_spec_sku(name: str) -> str | None:
    """APPLE-{line}-{chip?}-{size?}-{cap}{-CELL?} — thông số in giống ở mọi cửa hàng, không màu."""
    chip = re.search(r"\b(m[1-9]|a1[0-9])\b", name, re.I)
    line = next((w.upper() for w in ("air", "pro", "mini") if re.search(rf"\b{w}\b", name, re.I)), None)
    if line is None:
        # iPad base (không Air/Pro/Mini). Chip (A16…) là token định danh CHUNG ở mọi cửa hàng; "Gen 11"
        # chỉ TNC ghi. Nếu CÓ chip → dùng "GEN" trơn (chip đã phân biệt đời); nếu KHÔNG có chip mới
        # đính số Gen để khỏi mất định danh.
        gen = re.search(r"\bgen\s*(\d{1,2})\b", name, re.I)
        line = "GEN" if chip else (f"GEN{gen.group(1)}" if gen else "GEN")
    size = re.search(r"\b(1[0-9](?:\.\d)?)\s*inch\b", name, re.I)
    cap = re.search(r"\b(\d+)\s*(gb|tb)\b", name, re.I)
    cell = re.search(r"cellular|4g|5g", name, re.I)
    parts = ["APPLE", line]
    if chip:
        parts.append(chip.group(1).upper())
    if size:
        parts.append(size.group(1))
    if cap:
        parts.append(f"{cap.group(1)}{cap.group(2).upper()}")
    if cell:
        parts.append("CELL")
    # Cần ÍT NHẤT dung lượng HOẶC (chip+size) để định danh có nghĩa; nếu không, rơi về MPN/None.
    if cap or (chip and size):
        return "-".join(parts)
    return None


def tablet_sku(name: str | None) -> str | None:
    """SKU cho máy tính bảng. iPad → APPLE-<thông số> (khớp chéo được); hãng khác → BRAND-<mã part>."""
    from .brand import brand_of

    if not name:
        return None

    # iPad: ưu tiên khoá theo THÔNG SỐ (khớp mọi cửa hàng). MPN chỉ là dự phòng khi không rút được spec.
    if re.search(r"\bipad\b", name, re.I):
        spec = _ipad_spec_sku(name)
        if spec:
            return spec
        toks = re.split(r"[\s(),]+", name)
        mpn = next((t for t in toks if _IPAD_MPN.match(t)), None)
        return f"APPLE-{mpn}".upper() if mpn else None

    brand = brand_of(name)
    if brand.lower() == "other":
        return None
    BRAND = brand.upper()
    brand_toks = set(brand.lower().replace("-", " ").split())
    toks = re.split(r"[\s(),]+", name)
    codes = [t for t in toks if _TABLET_CODE.match(t) and t.lower() not in brand_toks]
    if codes:
        return f"{BRAND}-{max(codes, key=len)}".upper()
    return None


# ── VGA / Card màn hình (Tier A) ─────────────────────────────────────────────────────────────
# Tên đọc "Card Màn Hình <BRAND> GeForce <GPU> <DÒNG> <MEM> (<MPN>)". Định danh khoá theo FULL
# MODEL, BỎ mã MPN trong ngoặc (GV-N5060WF2OC-8GD) vì cửa hàng in MPN không nhất quán → đối thủ
# ghi cùng card mà KHÔNG kèm MPN sẽ mất khớp. SKU = BRAND-GPU-DÒNG-MEM, ví dụ GIGABYTE-RTX5060-WF-8G.
#   GPU = rtx/gtx/rx/gt/arc + số + hậu tố tuỳ chọn (ti/xt/xtx/super). Dính liền ("RTX5060") hay
#     tách rời ("RTX 5060", "RX 6500 XT") đều chuẩn hoá về một dạng.
#   DÒNG = từ chỉ dòng card (windforce->WF, eagle, aorus, tuf, prime, dual, ventus, phoenix, pulse,
#     nitro, ...) — phân biệt TUF vs PRIME (không đụng khoá). Không có dòng thì bỏ qua (GT1030 2G).
#   MEM = dung lượng NG (8G/12G/16G). GPU không tìm thấy -> None.
_VGA_GPU = re.compile(
    # Bắt cả:
    #  • dòng thường "RTX 5060", "RX 6500 XT", "Arc A750" (mã có thể có tiền tố chữ: A400/A2000).
    #  • dòng WORKSTATION/PRO có chữ "PRO"/"AI PRO" xen giữa: "RTX PRO 4000", "Arc PRO B70",
    #    "Radeon AI PRO R9700" — nếu không, các card này ra None.
    r"\b(rtx|gtx|rx|gt|arc|radeon)\s*(?:ai\s+)?(?:pro\s+)?[- ]?\s*([a-z]?\d{2,4})\s*(ti|xtx|xt|super)?\b",
    re.I,
)
_VGA_MEM = re.compile(r"\b(\d{1,2})\s*g(?:b|d\d?)?\b", re.I)  # 8GB, 12G, 6GB (không bắt "GDDR5")
# Dòng card (in nhất quán mọi cửa hàng). windforce có bí danh WF; các dòng khác giữ nguyên chữ.
# Duyệt theo THỨ TỰ: dòng cụ thể trước, "gaming" (chung, hay đi kèm dòng khác như "TUF Gaming")
# gần CUỐI — để "ASUS TUF Gaming ..." ra TUF chứ không phải GAMING.
_VGA_LINES = (
    ("windforce", "WF"), ("wf", "WF"),
    ("aorus", "AORUS"), ("eagle", "EAGLE"), ("tuf", "TUF"),
    ("prime", "PRIME"), ("dual", "DUAL"), ("ventus", "VENTUS"), ("phoenix", "PHOENIX"),
    ("pulse", "PULSE"), ("nitro", "NITRO"), ("ichill", "ICHILL"), ("twin", "TWIN"),
    ("mech", "MECH"), ("shadow", "SHADOW"), ("hellhound", "HELLHOUND"), ("fighter", "FIGHTER"),
    ("challenger", "CHALLENGER"), ("suprim", "SUPRIM"), ("trio", "TRIO"),
    ("gamerock", "GAMEROCK"), ("jetstream", "JETSTREAM"), ("solid", "SOLID"), ("amp", "AMP"),
    ("aero", "AERO"), ("expedition", "EXPEDITION"), ("elite", "ELITE"),
    ("gaming", "GAMING"),  # chung — chỉ dùng khi không có dòng cụ thể nào khớp
)


def vga_sku(name: str | None) -> str | None:
    """BRAND-GPU-DÒNG-MEM cho card màn hình (VGA), ví dụ "GIGABYTE-RTX5060-WF-8G". None nếu không có GPU.

    Khoá theo FULL MODEL, BỎ mã MPN trong ngoặc (GV-N5060WF2OC-8GD) — cửa hàng in MPN không nhất quán,
    đối thủ ghi cùng card mà không kèm MPN vẫn phải ra CÙNG SKU.
    """
    from .brand import brand_of

    if not name:
        return None
    brand = brand_of(name)
    if brand.lower() == "other":
        return None
    BRAND = brand.upper()

    # Bỏ phần trong ngoặc (MPN) trước khi parse — mã MPN không dùng làm định danh.
    body = re.sub(r"\([^)]*\)", " ", name)

    g = _VGA_GPU.search(body)
    if not g:
        return None
    gpu = f"{g.group(1)}{g.group(2)}{g.group(3) or ''}".upper()

    low = body.lower()
    line = next((tag for kw, tag in _VGA_LINES if re.search(rf"\b{kw}\b", low)), None)

    # HẬU TỐ định danh sau DÒNG: số quạt (2X/3X) và hạng (PLUS). MSI dùng lại "VENTUS" cho nhiều card
    # KHÁC nhau: "VENTUS 2X OC PLUS" ≠ "VENTUS 3X OC" (giá chênh HƠN 2 lần). Nếu bỏ 2X/3X/PLUS chúng
    # gộp một SKU → so giá nhầm hai card. Bắt "2x"/"3x" (số quạt) và "plus" đứng bất kỳ đâu trong tên.
    fans = re.search(r"\b([23])x\b", low)
    plus = re.search(r"\bplus\b", low)
    mem = None
    for m in _VGA_MEM.finditer(body):
        mem = f"{m.group(1)}G"  # lấy dung lượng cuối cùng (bỏ qua "GT 1030" không có 'g' đứng riêng)
    parts = [BRAND, gpu]
    if line:
        parts.append(line)
    if fans:
        parts.append(f"{fans.group(1)}X")
    if plus:
        parts.append("PLUS")
    if mem:
        parts.append(mem)
    return "-".join(parts).upper().replace(" ", "-")


_MB_CHIPSET = re.compile(r"\b([a-z]\d{2,4}[a-z]{0,2})\b", re.I)  # B760M, Z890, A520M, X670E, H610,
                                                                   # B650EM, H81 (chipset Intel đời
                                                                   # 8/9-series chỉ 2 chữ số: H81,
                                                                   # H97, B85, Q87, Z87…)
# HEDT/workstation AMD: 3 CHỮ trước số (không phải 1 chữ như B760M) — TRX40/TRX50/WRX80/WRX90
# KHÔNG khớp _MB_CHIPSET. Thử pattern này TRƯỚC.
_MB_HEDT_CHIPSET = re.compile(r"\b((?:trx|wrx)\d{2}[a-z]?)\b", re.I)

# Một số listing dính TÊN DÒNG ngay sau mã chipset, KHÔNG qua khoảng trắng/gạch nối nào cả (vd
# "B450AORUS-PRO" thay vì "B450 AORUS-PRO") — không có ranh giới \b giữa số và chữ kế tiếp nên
# .search() cũng không tách được. Chèn khoảng trắng trước các từ dòng ĐÃ BIẾT khi đứng NGAY SAU
# một dãy số. Danh sách có thể mở rộng khi gặp case mới.
_MB_GLUED_LINE = re.compile(r"(?<=\d)(aorus|eagle|elite|vision)", re.I)

# Tiền tố dòng THẬT (phân biệt sản phẩm, khác GA-/PRIME-/TUF- trong _MB_LEAD_FILLER vốn là chữ đệm
# thuần): "EX-" (dòng doanh nghiệp Asus) và "WS-" (dòng Workstation) đứng trước CÙNG một chipset
# vẫn là board KHÁC — giữ lại làm một phần định danh, đứng ngay trước chipset trong SKU.
_MB_KEEP_PREFIX = {"ex", "ws"}

_MB_LEAD_FILLER = {"mainboard", "bo", "mạch", "chủ", "main", "prime", "tuf"}
_MB_NOISE = {
    "wifi", "wifi6", "wifi6e", "wifi7", "csm", "ax", "ai", "top", "bluetooth", "th", "rgb",
    "d4", "d5", "ddr4", "ddr5", "gen5", "gen4", "gen", "m.2",
    "r2.0", "v2", "v3", "r2", "rev", "atx", "matx", "m-atx", "itx",
    "lga1700", "lga1851", "lga1200", "lga1151", "am4", "am5", "socket", "edition", "limited",
}
_MB_MEMGEN = (
    ("GEN5", r"\bgen5\b"),
    ("D5", r"\bddr5\b|\bd5\b"),
    ("D4", r"\bddr4\b|\bd4\b"),
)
_MB_WIFI = (
    ("WIFI7", r"\bwifi\s*7\b"),
    ("WIFI6E", r"\bwifi\s*6e\b"),
    ("WIFI6", r"\bwifi\s*6\b"),
    ("WIFI", r"\bwifi\b"),
)


def _mb_wifi_tag(body: str) -> str | None:
    """Hậu tố đời WiFi tích hợp (WIFI7/WIFI6E/WIFI6/WIFI), hoặc None nếu tên không nhắc đến WiFi."""
    for tag, pat in _MB_WIFI:
        if re.search(pat, body, re.I):
            return tag
    return None


# Board KHÔNG có mã chipset dạng số — ASUS ROG dòng flagship đặt tên THUẦN MARKETING (Maximus/
# Rampage/Crosshair/Strix/Zenith + số La Mã đời + biến thể Hero/Extreme/Formula/Code/Encore),
# không hề có token chữ+số như B760M/X670E.
_MB_ROG_LINE = {"maximus", "rampage", "crosshair", "strix", "zenith"}


def _mb_fallback(name: str, body: str, toks: list[str], brand: str, BRAND: str) -> str | None:
    """Dự phòng khi KHÔNG tìm được mã chipset nào (cả _MB_HEDT_CHIPSET lẫn _MB_CHIPSET đều trượt)
    — hai lớp board không theo quy ước chipset tiêu dùng:

    1. ASUS ROG dòng flagship — khoá theo DÒNG + mọi token còn lại (số La Mã đời + biến thể), in
       NHẤT QUÁN ở mọi cửa hàng nên vẫn khớp chéo được dù không có mã ngắn. WiFi (thường ghi trong
       ngoặc "(WI-FI)" mà `body` đã bóc mất) được dò lại từ `name` GỐC để không mất biến thể
       có/không WiFi.
    2. Board máy chủ/doanh nghiệp mã dạng khối (Z11PA-U12, MW51-HP0, DBS1200SPSR, P10S-X…) — GIỮ
       NGUYÊN VẸN từng token chữ+số (KHÔNG tách gạch nối) làm một khối định danh, rồi nối tối đa 2
       khối dài nhất. Giữ nguyên token (không .split("-")) để không mất hậu tố ngắn phân biệt thật
       — nếu tách "P11C-M" thành "P11C"+"M" rồi lọc theo độ dài, "P11C-M" và "P11C-X" (hai board
       KHÁC NHAU thật) đều rơi về chỉ "P11C" và gộp làm một.
    """
    low = body.lower()
    skip = {"mainboard", "bo", "mạch", "chủ", "main"} | set(brand.lower().split())

    if any(re.search(rf"\b{w}\b", low) for w in _MB_ROG_LINE):
        kept = [t.upper() for t in toks if t.lower() not in (skip | {"rog"})]
        if not kept:
            return None
        wifi = "-WIFI" if re.search(r"wi-?fi", name, re.I) else ""
        return f"{BRAND}-{'-'.join(kept)}{wifi}"

    skip |= {"server", "workstation"}
    cands: list[str] = []
    for t in toks:
        if t.lower() in skip:
            continue
        core = re.sub(r"[-/]", "", t)
        if re.search(r"[a-z]", core, re.I) and re.search(r"\d", core) and len(core) >= 3:
            up = t.upper()
            if up not in cands:
                cands.append(up)
    return f"{BRAND}-{'-'.join(cands[:2])}" if cands else None


def mainboard_sku(name: str | None) -> str | None:
    """BRAND-<[EX|WS]?>-<CHIPSET>-<MODEL>-<WIFI?>-<MEMGEN> cho bo mạch chủ, ví dụ
    "GIGABYTE-B760M-DS3H-D4" hoặc "ASUS-EX-B860M-V5".

    BUG ĐÃ SỬA (2026-08, phát hiện từ log thật `discover_tnc --category mainboard`: ~60/672 sản
    phẩm bị "SKIP (no SKU)"), gộp từ NHIỀU lỗi trong logic cũ:

    1. `_MB_CHIPSET.match(t)` chỉ khớp khi chipset ở ĐẦU token — tiền tố dòng board dính liền qua
       gạch nối (GA-B450M, EX-B860M-V5, WS-C246, PRIME-H510M-E, TUF-B365M-PLUS-GAMING) đẩy chipset
       ra giữa token, không bao giờ tìm thấy. Đổi sang `.search()`.
    2. Chipset HEDT của AMD (TRX40/TRX50/WRX80/WRX90) có 3 CHỮ trước số — thêm `_MB_HEDT_CHIPSET`
       thử trước.
    3. Một số chipset dính liền form-factor ngay sau số, KHÔNG qua gạch nối (B650EM, A620AM,
       H310CM) — nới hậu tố chữ tùy chọn từ 1 lên tối đa 2 ký tự.
    4. Chipset Intel đời cũ (8/9-series: H81, H97, B85, Q87, Z87…) chỉ có 2 CHỮ SỐ — nới `\d{3}`
       thành `\d{2,4}`.
    5. Gigabyte đôi khi dính TÊN DÒNG ngay sau số, không qua gạch/khoảng trắng nào cả
       (B450AORUS-PRO) — chèn khoảng trắng cho các từ dòng ĐÃ BIẾT trước khi tokenize.
    6. ASUS ROG dòng flagship không có mã chipset digit nào — thêm nhánh dự phòng trong
       `_mb_fallback`.
    7. Board máy chủ/doanh nghiệp (Z11PA-U12, MW51-HP0, DBS1200SPSR…) không theo quy ước chipset
       tiêu dùng — thêm nhánh "mã khối" trong `_mb_fallback`.
    8. Hậu tố hạng SAU chipset ("AORUS-PRO", "AORUS-ELITE") trước đây chỉ lấy ĐOẠN ĐẦU trước dấu
       gạch khi gom model — "AORUS-PRO" và "AORUS-ELITE" (hai board GA-X570 THẬT KHÁC NHAU) sẽ gộp
       cùng "AORUS" nếu không sửa; giờ tách hết mọi đoạn, không chỉ đoạn đầu.
    9. Cụm quảng cáo cuối tên kiểu " - Chính hãng giá rẻ" (TNC) từng bị nuốt làm "model" — cắt bỏ
       mọi thứ sau " - " (gạch nối CÓ khoảng trắng — mã model thật không bao giờ viết vậy).
    """
    from .brand import brand_of

    if not name:
        return None
    brand = brand_of(name)
    if brand.lower() == "other":
        return None
    BRAND = brand.upper()

    body = re.sub(r"\([^)]*\)", " ", name)
    body = re.split(r"\s-\s", body, maxsplit=1)[0]  # cắt cụm quảng cáo " - Chính hãng giá rẻ"
    body = _MB_GLUED_LINE.sub(r" \1", body)
    toks = [t for t in re.split(r"[\s,/]+", body) if t]
    if not toks:
        return None

    ci = None
    chipset = None
    match_obj = None
    for i, t in enumerate(toks):
        m = _MB_HEDT_CHIPSET.search(t) or _MB_CHIPSET.search(t)
        if m:
            ci, chipset, match_obj = i, m.group(1).upper(), m
            break

    if chipset is None:
        return _mb_fallback(name, body, toks, brand, BRAND)

    memgen = next((tag for tag, pat in _MB_MEMGEN if re.search(pat, body, re.I)), None)
    wifi_tag = _mb_wifi_tag(body)

    # Tiền tố dòng THẬT (EX-/WS-) đứng trước chipset — quét mọi đoạn (tách trên "-") của các token
    # ĐỨNG TRƯỚC ci, CỘNG phần đứng trước điểm khớp NGAY TRONG chính token chứa chipset.
    prefix_markers: list[str] = []
    for seg in [s for tk in toks[:ci] for s in re.split(r"[-/]", tk)] + re.split(
        r"[-/]", toks[ci][: match_obj.start()]
    ):
        if seg and seg.lower() in _MB_KEEP_PREFIX:
            prefix_markers.append(seg.upper())

    # MODEL = mọi đoạn định danh SAU chipset — cả phần còn lại của CHÍNH token chứa chipset (vd
    # "-V5" trong "EX-B860M-V5") LẪN các token đứng sau, tách TIẾP trên "-"/"/" (vd "AORUS-PRO"
    # -> "AORUS","PRO" — nếu chỉ lấy đoạn đầu thì "AORUS-PRO" và "AORUS-ELITE" gộp một SKU).
    raw_after = [s for s in re.split(r"[-/]", toks[ci][match_obj.end() :]) if s]
    for t in toks[ci + 1 :]:
        raw_after.extend(s for s in re.split(r"[-/]", t) if s)

    model_parts: list[str] = []
    for seg in raw_after:
        sl = seg.lower()
        if sl in _MB_NOISE:
            continue
        if not model_parts and sl in _MB_LEAD_FILLER:
            continue
        if re.fullmatch(r"\d+", seg):
            continue
        if any(re.search(pat, seg, re.I) for _, pat in _MB_MEMGEN):
            continue
        model_parts.append(seg.upper())
        if len(model_parts) >= 3:
            break

    parts = [BRAND, *prefix_markers, chipset, *model_parts]
    if wifi_tag:
        parts.append(wifi_tag)
    if memgen:
        parts.append(memgen)
    return "-".join(parts).upper().replace(" ", "-")

# ── Phần mềm bản quyền (Windows/Office, diệt virus, đồ họa...) ──────────────────────────────
_SW_SPEC = re.compile(
    r"^(phần|phan|mềm|mem|bản|ban|quyền|quyen|key|license|cho|digital|download|new|"
    r"chính|chinh|hãng|hang|vĩnh|vinh|viễn|vien|trọn|tron|đời|doi|"
    r"kích|kich|hoạt|hoat|active|code|activation|"
    r"điện|dien|tử|tu|online|dwnld|dl|all|lng|lang|language|pk|pack|package|lic|"
    r"64bit|32bit|64-bit|32-bit|x64|x86|bit|apac|em|nr|"
    # MỚI: mô tả CHUNG của category "software" — không phân biệt sản phẩm nào với sản phẩm nào,
    # nên phải loại khỏi phần định danh (xem BUG #1 ở trên).
    r"diệt|diet|virus|và|va|and)$",
    re.IGNORECASE,
)

# Số LƯỢNG (PC/user/device/máy/server) — TÁCH RIÊNG khỏi thân tên vì nó là một phần định danh
# (khác gói = khác giá), không phải filler để bỏ đi. Khớp CẢ dạng SỐ NHIỀU ("pcs", "users",
# "devices", "servers"/"svr") — trước đây \bpc\b không khớp "5PCS" vì chữ "S" liền sau phá ranh
# giới từ \b (xem BUG #2). "?" sau "s" chấp nhận cả số ít lẫn số nhiều.
_SW_QTY = re.compile(
    r"\b(\d{1,3})\s*(pcs?|thiết\s*bị|thiet\s*bi|users?|devices?|máy|may|servers?|svr)\b",
    re.IGNORECASE,
)
# Thời hạn: "1 năm", "12 tháng", "2 year" — cũng là một phần định danh, tách riêng như trên.
_SW_DURATION = re.compile(r"\b(\d{1,2})\s*(năm|nam|years?|tháng|thang|months?)\b", re.IGNORECASE)
# Mã sản phẩm phần mềm (ví dụ KW9-00664, FQC-10572, EP2-06604) — loại bỏ để khớp chéo dễ hơn.
_SW_PART = re.compile(r"\b[A-Z0-9]{3,4}-[A-Z0-9]{5}\b", re.IGNORECASE)


def _sw_qty_tag(unit: str) -> str:
    """Chuẩn hoá đơn vị số lượng về một hậu tố ngắn: server -> SRV, user -> USER, còn lại
    (pc/pcs/thiết bị/device/máy) -> PC."""
    u = unit.lower().replace(" ", "")
    if u.startswith(("server", "svr")):
        return "SRV"
    if u.startswith("user"):
        return "USER"
    return "PC"


def software_sku(name: str | None) -> str | None:
    """BRAND-<TÊN SẢN PHẨM>-<SỐ LƯỢNG?>-<THỜI HẠN?> cho phần mềm bản quyền/diệt virus.

    Không có mã part như phần cứng nên khoá theo brand + các token định danh còn lại của tên (bỏ
    filler THẬT SỰ chung chung: "phần mềm", "bản quyền", "key", "diệt virus"...). Số lượng
    (PC/User/Server) và thời hạn được TÁCH RIÊNG thành hậu tố vì chúng LÀ một phần định danh — bỏ
    đi sẽ gộp nhầm các gói khác giá vào một SKU. Hình thức đóng gói (FPP/OEM/ESD...) được GIỮ LẠI
    làm token định danh vì nó ảnh hưởng giá thật, không phải filler.
    """
    from .brand import brand_of

    if not name:
        return None
    brand = brand_of(name)
    if brand.lower() == "other":
        return None
    BRAND = brand.upper()

    # Phân biệt bản Microsoft ESD (Key điện tử) và FPP (Hộp vật lý) tránh trùng lặp SKU gây sót sản phẩm
    is_esd = False
    if BRAND == "MICROSOFT":
        low_name = name.lower()
        if any(kw in low_name for kw in ["esd", "điện tử", "dien tu", "online", "dwnld", "key điện tử", "download"]):
            is_esd = True

    # Bắt TẤT CẢ cụm số lượng trong tên (không chỉ cụm ĐẦU TIÊN) — "1Server + 5PCS" có 2 cụm, cả
    # hai đều là định danh thật của gói combo server+client (xem BUG #1/#2 ở docstring khối).
    qty_matches = list(_SW_QTY.finditer(name))
    duration = _SW_DURATION.search(name)

    # Bỏ ngoặc, mã part-number + mọi cụm số-lượng/thời-hạn khỏi thân tên trước khi tách token, để
    # không lẫn vào phần định danh dưới dạng số trần vô nghĩa.
    body = re.sub(r"\([^)]*\)", " ", name)
    body = _SW_PART.sub(" ", body)
    for m in qty_matches:
        body = body.replace(m.group(0), " ")
    if duration:
        body = body.replace(duration.group(0), " ")

    # Thêm "+" vào ký tự tách — các gói combo dùng "+" nối "1Server + 5PCS".
    toks = [t for t in re.split(r"[\s,/+]+", body) if t]
    brand_toks = set(brand.lower().replace("-", " ").split())
    core: list[str] = []
    for t in toks:
        low = t.lower().strip(".,-")
        if not low or low in brand_toks or _SW_SPEC.match(low):
            continue
        cleaned = re.sub(r"[^\w]", "", t).upper()
        if cleaned:
            core.append(cleaned)
    if not core:
        return None

    # Trần nâng từ 4 lên 6 (xem BUG #1/(d)) — đủ giữ token định danh thật (năm phát hành, ENG,
    # FPP/OEM...) mà không làm SKU quá dài.
    parts = [BRAND, *core[:6]]

    # Ghép TẤT CẢ cụm số lượng tìm được, theo đúng thứ tự xuất hiện trong tên gốc — gói combo
    # "1Server + 5PCS" ra hậu tố "-1SRV-5PC", phân biệt rõ với "1Server + 10PCS" ("-1SRV-10PC").
    for m in qty_matches:
        num, unit = m.group(1), m.group(2)
        parts.append(f"{num}{_sw_qty_tag(unit)}")

    if duration:
        unit = "Y" if re.search(r"năm|nam|year", duration.group(2), re.IGNORECASE) else "M"
        parts.append(f"{duration.group(1)}{unit}")

    sku = "-".join(parts).upper().replace(" ", "-")
    if is_esd:
        sku = f"{sku}-ESD"
    return sku


# ── Thiết bị âm thanh: tai nghe / loa / micro ──────────────────────────────────────────────────
# Tên đọc "<loại> <BRAND> <MODEL> (<màu/mã>)", ví dụ "Tai nghe Logitech Zone 305 (981-001459)",
# "Loa Creative Pebble Pro 2.0 (White)". Định danh = BRAND + MODEL. Audio products thường không có
# mã part kiểu phần cứng — model là một hoặc nhiều token chữ (Zone, Pebble, Evolve) đôi khi kèm số
# (305, 30, 2.0). Fallback: nếu không có token chữ+số, dùng token chữ dài nhất (Pebble, Evolve).
_AUDIO_COLORS = {
    "black", "white", "red", "blue", "green", "pink", "purple", "gray", "grey", "silver",
    "gold", "graphite", "quartz", "midnight", "starlight", "sapphire", "pearl", "matte",
    "piano", "cream", "lavender", "teal", "aqua", "ice", "ocean", "titan",
    # tiếng Việt
    "đen", "trắng", "đỏ", "xanh", "hồng", "tím", "xám", "bạc", "vàng",
    # tổ hợp màu 2 từ tiếng Việt (biển "xanh dương"/"xanh lá"/"xanh biển"/"xanh ngọc" hay gặp trên
    # TNC/EDIFIER) — token thứ hai của cụm cũng phải bị loại, nếu không nó lọt vào model_toks và
    # (hiếm khi) làm sai lệch phần fallback không-có-digit ở cuối audio_sku().
    "dương", "duong", "lá", "la", "biển", "bien", "ngọc", "ngoc", "nhạt", "nhat", "đậm", "dam",
}
# CHỈ loại từ KHÔNG bao giờ là một phần model: mô tả kết nối/đặc tính chung.
# ĐÃ XÓA: "pro", "plus", "max", "mini", "ultra", "ii", "iii", "se" — các từ này
# LÀ tên model thật (Logitech G Pro, Cloud II, WH-1000XM5 SE...) nên không được coi là filler.
_AUDIO_FILLERS = {
    "bluetooth", "wireless", "wired", "usb", "cable", "stereo", "mono",
    "true", "tws", "sport", "light",
    "noise", "cancelling", "cancellation", "open", "ear", "in-ear", "over-ear",
    "on-ear", "headband", "neckband", "earbuds", "hands-free", "handsfree",
    "kids", "uc", "ms",
    "di", "động", "dong", "máy", "may", "hội", "nghị", "nghi", "trợ",
    "giảng", "không", "dây", "day", "choàng", "nhét", "tai",
    "2.1", "2.0", "1.0",
    # Mô tả loại sản phẩm (lọc thêm sau khi prefix strip)
    "loa", "speaker", "speakers", "headphone", "headphones", "headset", "headsets",
    "earphone", "earphones", "micro", "microphone", "microphones", "gaming",
}
# Loại phụ kiện âm thanh — THỨ TỰ QUAN TRỌNG: pattern DÀI hơn phải đứng TRƯỚC pattern ngắn
# hơn để regex alternation ưu tiên match đúng (vd "loa bluetooth di dong" phải match trước "loa bluetooth").
# GHI CHÚ: các biến thể có dấu ("kéo", "trợ giảng", "hội nghị"...) được thêm SONG SONG với bản
# không dấu — bản gốc chỉ có "keo"/"tro giang"/"hoi nghi" (không dấu) nên KHÔNG khớp được với tên
# sản phẩm thật (TNC luôn ghi CÓ dấu, ví dụ "Loa kéo mini ..."). Thiếu các biến thể có dấu khiến
# toàn bộ nhánh "loa\s*(?:...)" không bao giờ khớp, rơi xuống "loa" trơn — hậu quả: mô tả loại vẫn
# CHỈ bị cắt một phần ("Loa " thay vì "Loa kéo "), để lại rác ("kéo", "trợ giảng"...) lẫn trong
# phần thân dùng để suy ra model. Điều này không tự nó gây None (không loại bỏ được model thật),
# nhưng làm SKU kém sạch hơn cần thiết — sửa cho nhất quán với brand.py (vốn đã chấp nhận cả hai
# dạng có dấu/không dấu ở name_prefixes).
_AUDIO_PREFIX = re.compile(
    r"^\s*(?:"
    r"tai\s*nghe\s*(?:khong\s*day|không\s*dây|bluetooth|wireless|gaming|choang\s*dau|choàng\s*đầu|"
    r"nhet\s*tai|nhét\s*tai)?|"
    r"tainghe|headphone|headset|earphone|"
    r"loa\s*(?:tro\s*giang\s*di\s*dong|trợ\s*giảng\s*di\s*động|bluetooth\s*di\s*dong|"
    r"hoi\s*nghi|hội\s*nghị|may\s*tinh|máy\s*tính|"
    r"di\s*dong|di\s*động|keo|kéo|bluetooth|tro\s*giang|trợ\s*giảng)|"
    r"loa|speaker|micro(?:phone)?|"
    r"form\s*tai\s*nghe|form"
    r")\s*",
    re.I,
)

# ── MỚI (2026-08) — hãng dùng SỐ TRẦN làm mã dòng sản phẩm ──────────────────────────────────
# Một số hãng đặt tên dòng sản phẩm chỉ bằng SỐ, không kèm chữ — ví dụ Jabra: "Biz 1100",
# "Biz 1500", "Biz 2400", "Evolve2 65", "Speak 750". Với ĐA SỐ brand khác, một token số trần
# đứng một mình gần như luôn là rác (năm sản xuất, giá, watt…) nên bị loại ở bước lọc bên dưới —
# nhưng với các hãng trong set này, số đó CHÍNH LÀ định danh phân biệt hai sản phẩm khác giá.
#
# BUG ĐÃ SỬA: trước khi có set này, "Jabra Biz 1100 Duo USB" và "Jabra Biz 1500 Duo USB" (hai tai
# nghe khác nhau, giá khác nhau thật) đều bị rút gọn về chung một SKU "JABRA-BIZ-DUO" vì "1100"/
# "1500" bị quy tắc lọc số trần loại bỏ, chỉ còn "Biz"+"Duo" sống sót. Một nguồn (An Phát PC) ghi
# nhận giá của bản 1100 nhưng lại bị gắn vào đúng dòng catalog của bản 1500 do hai bản trùng SKU.
#
# Mở rộng set này khi gặp thêm hãng có kiểu đặt tên số-trần-là-mã-dòng tương tự.
_AUDIO_NUMERIC_MODEL_BRANDS = {"jabra"}
# Chỉ giữ số trần dài 2-5 chữ số (65, 750, 1100, 2400, 8300…) — tránh vô tình giữ lại một chữ số
# lẻ lạc vào tên do tách token sai (ví dụ phần còn sót của "2.0"/"5.1" nếu lọt qua bước trước).
_AUDIO_MODEL_NUMBER = re.compile(r"^\d{2,5}$")


def audio_sku(name: str | None) -> str | None:
    """BRAND-MODEL cho thiết bị âm thanh (tai nghe / loa / micro), ví dụ "LOGITECH-G-PRO",
    "EDIFIER-W820NB". Dùng chiến lược KHÔNG PHỤ THUỘC VỊ TRÍ: thu thập tất cả token không phải
    brand/filler/màu, rồi ưu tiên token chứa chữ số làm mã model — khắc phục lỗi cũ (brand_idx=None
    cho brand dạng gạch nối như E-Dra, và filler "Pro/Gen/II" chặn token model nằm sau).

    Với các hãng trong `_AUDIO_NUMERIC_MODEL_BRANDS` (vd Jabra), số trần đứng một mình KHÔNG bị
    loại — nó chính là mã dòng sản phẩm (xem ghi chú BUG ở khối hằng số phía trên).
    """
    from .brand import brand_of

    if not name:
        return None
    brand = brand_of(name)
    if brand.lower() == "other":
        return None
    BRAND = brand.upper()

    # Tập token nhận diện brand — bao gồm cả dạng có gạch nối, không gạch nối, và từng từ riêng lẻ.
    # "E-Dra" → {"e-dra", "e", "dra", "edra"}; "TP-Link" → {"tp-link", "tp", "link", "tplink"}
    brand_toks: set[str] = {
        brand.lower(),
        *brand.lower().replace("-", " ").split(),
        brand.lower().replace("-", ""),
    }

    # Bỏ tiền tố loại sản phẩm ("Tai nghe", "Loa", "Micro…") rồi tách token.
    body = _AUDIO_PREFIX.sub("", name)
    # Bỏ phần trong ngoặc — mã trong ngoặc (981-001459, 4P5K4AA) là product ID nội bộ,
    # thường KHÔNG phải model hiển thị (bất nhất giữa cửa hàng → gây sai SKU khi dùng làm khoá).
    body = re.sub(r"\([^)]*\)", " ", body)
    toks = [t for t in re.split(r"[\s,/]+", body) if t]

    # MỚI: hãng nào dùng số trần làm mã dòng (Jabra) — không loại bỏ số trần cho hãng đó.
    keep_bare_numbers = brand.lower() in _AUDIO_NUMERIC_MODEL_BRANDS

    # Thu thập model tokens theo chiến lược KHÔNG PHỤ THUỘC VỊ TRÍ:
    # Duyệt TOÀN BỘ token, bỏ qua brand/filler/màu — không cần tìm brand_idx.
    # Ưu điểm: bắt được "EH496W" trong "E-Dra EH496W Black" (brand = "E-Dra" không match token
    # nào nếu dùng brand_idx cũ vì tên "E-Dra" bị tách thành 2 token sau split trên khoảng trắng).
    model_toks: list[str] = []
    for t in toks:
        tl = t.lower().strip("-")
        # Bỏ brand token (khớp mọi biến thể gạch nối/không gạch nối/từng từ)
        if tl in brand_toks:
            continue
        # Bỏ màu sắc
        if tl in _AUDIO_COLORS:
            continue
        # Bỏ filler mô tả
        if tl in _AUDIO_FILLERS:
            continue
        # Bỏ số trần (năm, giá, watt…) — mã model LUÔN có chữ lẫn số hoặc toàn chữ có nghĩa.
        # NGOẠI LỆ: với brand ở _AUDIO_NUMERIC_MODEL_BRANDS, số trần 2-5 chữ số CHÍNH LÀ mã dòng
        # (Jabra "Biz 1100" vs "Biz 1500") — giữ lại thay vì loại bỏ (xem ghi chú BUG phía trên).
        if re.fullmatch(r"\d+(\.\d+)?[wghz]?", t, re.I):
            if keep_bare_numbers and _AUDIO_MODEL_NUMBER.match(t):
                model_toks.append(t)
            continue
        model_toks.append(t)

    if not model_toks:
        return None

    # Ưu tiên token chữ+số dài nhất (EH496W, WI-C310, A710, HS-HP21SV, 4P5K4AA).
    mixed = [t for t in model_toks if re.search(r"\d", t) and re.search(r"[a-z]", t, re.I)]
    if mixed:
        code = max(mixed, key=len)
        return f"{BRAND}-{code}".upper().replace(" ", "-")

    # Fallback: dùng tất cả token model (giữ thứ tự vị trí, không sort length)
    # để "Sound Blaster", "G Pro" không bị đảo hay mất token.
    parts = model_toks[:4]
    return f"{BRAND}-{'-'.join(parts)}".upper().replace(" ", "-")



# ── Camera an ninh ──────────────────────────────────────────────────────────────────────────────
# Tên đọc "<loại> <mô tả> <BRAND> <MODEL> (<spec>)", ví dụ "Camera IP WiFi EZVIZ H6C 3K 5MP",
# "Camera Tenda CP6". Định danh = BRAND + MODEL.
#
# BUG ĐÃ SỬA (2026-08, phát hiện từ log thật `discover_tnc --category camera`: hàng loạt SKIP,
# gần như 100% các listing TP-Link Tapo/VIGI, Dahua, Imou):
#
# 1. `brand_toks = set(brand.lower().replace("-", " ").split())` KHÔNG chứa dạng CÓ GẠCH NỐI của
#    brand — với "TP-Link" nó chỉ tạo {"tp", "link"}, KHÔNG có "tp-link". Token thật trong tên vẫn
#    là "TP-Link" (một khối, vì tách trên khoảng trắng/dấu phẩy không tách "-"), nên
#    `t.lower() in brand_toks` không bao giờ True cho brand có gạch nối → brand_idx luôn None →
#    hàm trả về None cho MỌI camera TP-Link/D-Link/E-Dra... dù brand_of() đã nhận diện đúng brand.
#    Đây là nguyên nhân của tuyệt đại đa số SKIP quan sát được (TP-Link chiếm phần lớn danh mục
#    camera). Sửa bằng bộ 3 dạng brand_toks giống audio_sku() (có gạch/không gạch/từng từ).
# 2. Vòng lặp thu thập model_toks dùng `break` ngay khi gặp token spec/màu/filler ĐẦU TIÊN sau
#    brand — nhưng spec (vd "4MP", "Wifi") thường đứng XEN GIỮA brand và mã model thật trong tên
#    gốc tiếng Việt (ví dụ "Dahua 4MP DH-IPC-HDBW1439E1-A-IL": "4MP" đứng ngay sau brand, TRƯỚC mã
#    model) — `break` dừng vòng lặp ngay tại "4MP", không bao giờ chạm tới mã model phía sau, nên
#    model_toks rỗng → trả None dù mã model có mặt trong tên. Sửa: dùng `continue` (bỏ qua token
#    spec) thay vì `break`, để quét hết toàn bộ phần còn lại của tên, giống audio_sku().
# 3. Brand có thể lặp lại NHIỀU LẦN trong tên (vd "Camera Imou Wifi 4G IMOU 2MP S21FTP" — "Imou"
#    xuất hiện cả ở đầu và giữa tên, kiểu ghi trùng lặp của một số nguồn dữ liệu). Token brand lặp
#    lại đó trước đây bị coi là một phần "model" nếu nó đứng sau brand_idx — nay được lọc ở MỌI vị
#    trí (không chỉcủa brand_idx) nhờ kiểm tra brand_toks trong chính vòng lặp model_toks.
_CAMERA_PREFIX = re.compile(
    r"^\s*(?:camera"
    r"(?:\s+ip)?"
    r"(?:\s+wi[\- ]?fi(?:\s+(?:trong\s+nh(?:a|à)|ngo(?:ai|ài)\s+tr(?:oi|ời)))?)?"
    r"(?:\s+quay\s*qu(?:e|ê)t(?:\s+th(?:o|ô)ng\s*minh)?)?"
    r"|quan\s*s[aá]t"
    r")\s*",
    re.I,
)
_CAMERA_SPEC = re.compile(
    r"^(ip|wifi|wi-fi|wlan|ngoai|ngoài|trong|nha|nhà|troi|trời|quan|sat|sát|quay|quet|quét|quẹt|"
    r"thông|minh|thong|ai|360|độ|do|"
    r"[1-9]k|\d{1,2}mp|mp|led|ir|night|color|full|full-color|pan|tilt|zoom|sd|poe|onvif|cloud|"
    r"storage|an|ninh|dùng|dung|pin|giám|giam|trẻ|tre|em|tích|tich|hợp|hop|đèn|den|pha|"
    r"1080p|hd|ống|ong|kính|kinh|"
    r"inden|outdoor|indoor|floodlight|spotlight|doorbell|chime|ngo)$",
    re.I,
)


def camera_sku(name: str | None) -> str | None:
    """BRAND-MODEL cho camera an ninh, ví dụ "TP-LINK-C232", "DAHUA-DH-IPC-HDBW1439E1-A-IL",
    "EZVIZ-H6C". Xem ghi chú "BUG ĐÃ SỬA" ở trên cho lý do các thay đổi so với bản trước.
    """
    from .brand import brand_of

    if not name:
        return None
    # Strip prefix + location + parenthetical code TRƯỚC khi detect brand — nếu không,
    # "Camera" / "ngoai troi" bị nhận nhầm là brand.
    body = _CAMERA_PREFIX.sub("", name)
    body = re.sub(r"\([^)]*\)", " ", body)
    body = re.sub(r"\b(?:ngoai\s*troi|ngoài\s*trời|trong\s*nh(?:a|à))\b", " ", body, flags=re.I)

    brand = brand_of(body)
    if brand.lower() == "other":
        return None
    BRAND = brand.upper()
    # Bộ 3 dạng brand_toks (có gạch/không gạch/từng từ) — cùng kỹ thuật với audio_sku(), sửa lỗi
    # #1 ở trên (brand có gạch nối như "TP-Link" trước đây không bao giờ khớp).
    brand_toks: set[str] = {
        brand.lower(),
        *brand.lower().replace("-", " ").split(),
        brand.lower().replace("-", ""),
    }
    toks = [t for t in re.split(r"[\s,]+", body) if t]

    brand_idx = None
    for i, t in enumerate(toks):
        if t.lower().strip("-") in brand_toks:
            brand_idx = i
            break
    if brand_idx is None:
        return None

    # Quét TOÀN BỘ phần còn lại sau brand (không dừng sớm) — sửa lỗi #2/#3 ở trên: bỏ qua
    # (continue) token spec/màu/filler/brand-lặp-lại thay vì break ngay khi gặp token đầu tiên.
    model_toks: list[str] = []
    for t in toks[brand_idx + 1:]:
        tl = t.lower().strip("-")
        if tl in brand_toks:
            continue
        if tl in _AUDIO_COLORS or tl in _AUDIO_FILLERS or _CAMERA_SPEC.match(t):
            continue
        if re.fullmatch(r"\d+", t):
            continue
        model_toks.append(t)

    if not model_toks:
        return None

    mixed = [t for t in model_toks if re.search(r"\d", t)]
    if mixed:
        return f"{BRAND}-{max(mixed, key=len)}".upper().replace(" ", "-")

    if model_toks:
        return f"{BRAND}-{'-'.join(model_toks[:3])}".upper().replace(" ", "-")

    return None


# Per-category identity dispatch. Add a category = add its function here.
_CATEGORY_SKU = {
    "printer": av_sku,
    "scanner": av_sku,
    "ups": av_sku,
    "projector": av_sku,
    "tv": av_sku,
    "tablet": tablet_sku,
    "cpu": cpu_sku,
    "vga": vga_sku,
    "mainboard": mainboard_sku,
    "monitor": monitor_sku,
    "pc": pc_sku,
    "workstation": pc_sku,   # máy trạm — cùng cấu trúc "BRAND <dòng> <mã>" như PC
    "server": pc_sku,        # máy chủ — cùng logic (branded, có mã model)
    "ram": ram_sku,
    "ssd": ssd_sku,
    "hdd": ssd_sku,   # HDD dùng chung logic (mã part + spec), chỉ khác trang scrape
    "keyboard": peripheral_sku,
    "mouse": peripheral_sku,
    "combo": peripheral_sku,
    "webcam": peripheral_sku,   # webcam cũng "BRAND MODEL" (Logitech C920) — dùng chung
    "usb": usb_sku,
    "memcard": usb_sku,         # thẻ nhớ dùng chung logic USB (BRAND-MODEL-CAP)
    "box": box_sku,
    # thiết bị mạng — tất cả dùng chung network_sku (BRAND-MODEL)
    "router": network_sku,   # gộp cả router doanh nghiệp
    "switch": network_sku,
    "accesspoint": network_sku,
    "wlan_controller": network_sku,
    # phần mềm bản quyền — không có mã part, khoá theo tên + số lượng + thời hạn
    "software": software_sku,
    # camera an ninh — model ngắn, dùng camera_sku riêng
    "camera": camera_sku,
    # thiết bị âm thanh — model ngắn/alpha, dùng audio_sku riêng
    "audio": audio_sku,
}


_USED_RE = re.compile(
    r"(?i)\b(tray|trầy|demo|trưng\s+bày|trung\s+bay|cũ|cu|like|likenew|nhập\s+khẩu|nhap\s+khau|xách\s+tay|xach\s+tay|usa|xước|xuoc|cấn|can|trôi\s+bảo\s+hành|troi\s+bao\s+hanh|active|đã\s+kích\s+hoạt|da\s+kich\s+hoat|không\s+hộp|khong\s+hop|đổi\s+trả|doi\s+tra|no\s+box|qsd|qua\s+sử\s+dụng|qua\s+su\s+dung)\b"
)


def derive_sku(name: str | None, url: str | None, category: str = "Laptop") -> str | None:
    """Canonical SKU for a discovered product — the same product yields the same key across stores.

    Dispatches on `category`: laptops (default) use the multi-brand laptop rules; other categories
    use their own identity scheme (e.g. monitors -> BRAND-MODEL). A non-laptop category returns None
    when it can't extract an identity, so the caller ingests it TNC-only / skips the match.
    See docs/sku-matching.md.
    """
    if category != "Laptop":

        fn = _CATEGORY_SKU.get(category.lower())
        return fn(name) if fn else None
    return _laptop_sku(name, url)


def _laptop_sku(name: str | None, url: str | None) -> str:
    """Trả về SKU chuẩn cho một laptop được phát hiện — cùng một laptop sẽ cho ra cùng một khóa
    ở mọi cửa hàng. Ưu tiên các quy tắc riêng theo thương hiệu (chỉ áp dụng khi có từ khóa thương
    hiệu), sau đó mới đến các chiến lược Dell tổng quát. Xem docs/sku-matching.md để biết lý do
    đầy đủ cho từng thương hiệu.
    """
    slug = _slug_tail(url)

    # Apple: khóa theo spec tổng hợp. Xử lý trước, vì tên Mac có các số trần dễ khiến rule 3
    # nhận nhầm.
    mac = apple_sku(name)
    if mac:
        return mac

    # HP: mã part (token hợp lệ cuối cùng), không phải số dòng model dùng chung.
    if re.search(r"\bhp\b", (name or ""), re.I):
        name_toks = re.split(r"[\s()/\-_]+", name or "")
        slug_toks = re.split(r"[-_]+", slug)
        hp_codes = [t for t in name_toks + slug_toks if _HP_CODE.match(t)]
        if hp_codes:
            return hp_codes[-1].upper()

    # Asus / Acer / MSI: mã model đầy đủ.
    if re.search(r"\b(asus|acer|msi)\b", (name or ""), re.I):
        mc = model_code(name, slug)
        if mc:
            return mc

    # Gigabyte: dùng chung model_code() (bắt series ngắn kiểu "EG64H"/"AM6J" + hậu tố "4WH"/"6XJ",
    # ra "EG64H-4WH"/"AM6J-6XJ"); khi KHÔNG tìm được series ngắn (mã đóng thành MỘT khối dài như
    # "CMHH2VN893SH", "CTHH3VN893SH", "9LJR2VNF93SH", "9RC55MF5FJIINIVN000"), dùng mã hỗn hợp dài
    # làm phương án cuối — xem ghi chú ở _long_mixed_code(). TRƯỚC KHI SỬA, Gigabyte không có
    # nhánh riêng nào cả nên rơi thẳng xuống logic Dell bên dưới, vô tình khoá nhầm vào số cấu
    # hình GPU/năm tìm thấy đầu tiên trong tên (RTX 3050/4050/5050/5080, năm 2024).
    if re.search(r"\bgigabyte\b", (name or ""), re.I):
        mc = model_code(name, slug)
        if mc:
            return mc
        lc = _long_mixed_code(name, slug)
        if lc:
            return lc

    # Lenovo: mã MTM (Machine Type Model) — định danh DUY NHẤT thật, in giống nhau ở mọi cửa
    # hàng, dạng 2 chữ số + 7-9 ký tự chữ/số (21MV000PVN, 83F5008WVN, 83GS001SVN, 20YA0039VN) —
    # xem _lenovo_code(). TRƯỚC KHI SỬA, Lenovo cũng rơi xuống logic Dell bên dưới, vô tình khoá
    # nhầm vào màu ("Xám"->XAM) hay hậu tố CPU dính trong slug URL (r5/r7/u7).
    if re.search(r"\blenovo\b", (name or ""), re.I):
        lc = _lenovo_code(name, slug)
        if lc:
            return lc

    # Dell 1: mã trần 8 chữ số.
    m = _EIGHT.search(slug) or _EIGHT.search((name or "").lower())
    if m:
        return m.group(1)

    tokens = [t for t in re.split(r"[-_]+", slug) if t]
    series_idx = next((i for i, t in enumerate(tokens) if _SERIES.match(t)), None)

    # Dell 2: series + mã model.
    if series_idx is not None and tokens:
        series = tokens[series_idx]
        after = tokens[series_idx + 1 :]
        if not after:
            return series.upper()
        model = _model_code(after)
        return f"{series}-{model}".upper() if model else series.upper()

    # Dell 3: các dòng không có mã (Precision/XPS/…) — <line>-<4chữsố>.
    haystack = f"{name or ''} {slug}".lower()
    line = next((w for w in _LINES if w in haystack), None)
    four = _FOUR.search(haystack)
    if line and four:
        return f"{line}-{four.group(1)}".upper()
    if four:
        return four.group(1)

    # Phương án dự phòng: token cuối của slug, nếu không có thì token cuối của name.
    if tokens:
        return tokens[-1].upper()
    return (name or "").split()[-1].upper() if name else "UNKNOWN"