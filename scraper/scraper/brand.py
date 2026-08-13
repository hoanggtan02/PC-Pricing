"""Nhận diện thương hiệu — ánh xạ tên sản phẩm sang thương hiệu chuẩn của nó.

Vốn từ vựng thương hiệu là một nguồn chân lý có thể chỉnh sửa bởi con người:
scraper/config/brands.yaml. Module này nạp file đó và cung cấp brand_of(). Thứ tự nhận diện:
  1. khớp từ khóa (theo ranh giới từ) với vốn từ vựng đã tuyển chọn, hoặc
  2. dự phòng theo cấu trúc — token thực đầu tiên sau tiền tố danh mục (bắt được các thương hiệu
     chưa có trong file, như một nhà sản xuất màn hình mới, mà không cần sửa file), rồi
  3. "Other".
"""

from __future__ import annotations

import functools
import re
from pathlib import Path

import yaml

_BRANDS_PATH = Path(__file__).resolve().parent.parent / "config" / "brands.yaml"


@functools.lru_cache(maxsize=1)
def _data() -> dict:
    with open(_BRANDS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@functools.lru_cache(maxsize=1)
def _brands() -> dict[str, tuple[str, ...]]:
    """Thương hiệu chuẩn -> tuple từ khóa, giữ nguyên thứ tự trong file (thứ tự phá vỡ trùng lặp)."""
    return {b: tuple(kws) for b, kws in (_data().get("brands") or {}).items()}


@functools.lru_cache(maxsize=1)
def _brand_re() -> dict[str, re.Pattern]:
    # Ranh giới từ ĐẦU (\b) để "hp" không khớp bên trong token như "15AHP11". Ở CUỐI dùng lookahead
    # (?=\d|\b) — cho phép từ khóa dính liền mã model bằng SỐ (DrayTek "Vigor3912", "Vigor2927") mà
    # vẫn nhận diện đúng thương hiệu, đồng thời không khớp khi có chữ theo sau ("archerX" ≠ archer).
    return {
        brand: re.compile(
            r"\b(?:" + "|".join(map(re.escape, kws)) + r")(?=\d|\b)", re.IGNORECASE
        )
        for brand, kws in _brands().items()
    }


@functools.lru_cache(maxsize=1)
def _prefix_re() -> re.Pattern:
    prefixes = _data().get("name_prefixes") or []
    alt = "|".join(map(re.escape, prefixes))
    return re.compile(rf"^\s*(?:{alt})\s*", re.IGNORECASE)


# Tương thích ngược: các thương hiệu ta từng lặp qua trong quy trình laptop.
TRACKED = ["dell", "lenovo", "apple", "hp", "asus", "acer", "msi", "gigabyte"]


# Từ spec/đơn vị KHÔNG BAO GIỜ là thương hiệu — dùng để bỏ qua khi trích brand theo cấu trúc,
# kể cả khi chúng nằm GIỮA chuỗi (name_prefixes chỉ bóc phần đầu).
_SPEC_WORDS = {
    "inch", "sata", "nvme", "pcie", "gen", "sata3", "iii", "ii",
    "wifi", "wi-fi", "ghz", "mhz", "poe", "gigabit", "port", "dual", "band",
    "series", "plus", "pro", "lite", "max", "ultra", "new", "chính", "hãng",
    # VGA: từ danh mục / dòng GPU KHÔNG bao giờ là thương hiệu — nếu không "VGA GeForce RTX ..."
    # (TNC bỏ tên hãng) sẽ ra brand="Vga"/"Rtx"/"Geforce". Bỏ qua để rơi xuống suy luận theo dòng card.
    "vga", "card", "geforce", "radeon", "rtx", "gtx", "arc", "ada", "blackwell",
    "gddr5", "gddr6", "gddr7", "ecc", "sff", "oc", "edition",
}

# Suy luận THƯƠNG HIỆU từ DÒNG card khi tên KHÔNG có tên hãng (TNC hay bỏ: "VGA GeForce RTX 5060 Ti
# VENTUS ..."). Mỗi dòng card thuộc đúng một hãng board-partner nên map được chắc chắn.
_VGA_LINE_BRAND = {
    "ventus": "MSI", "shadow": "MSI", "gaming trio": "MSI", "suprim": "MSI", "vanguard": "MSI",
    "windforce": "Gigabyte", "eagle": "Gigabyte", "aorus": "Gigabyte", "gaming oc": "Gigabyte",
    "tuf": "Asus", "prime": "Asus", "dual": "Asus", "proart": "Asus", "strix": "Asus",
    "pulse": "Sapphire", "nitro": "Sapphire",
    "ichill": "Inno3D", "twin x2": "Inno3D",
    "hellhound": "PowerColor", "fighter": "PowerColor", "red devil": "PowerColor",
    "gamerock": "Palit", "jetstream": "Palit",
}


def _structural_brand(name: str) -> str | None:
    """Thương hiệu best-effort = token thực đầu tiên sau (các) tiền tố danh mục. Bắt được các
    thương hiệu chưa có trong vốn từ vựng (ví dụ một nhà sản xuất màn hình mới), để không có gì
    âm thầm biến thành 'Other'."""
    s = name.lower()
    prev = None
    while s != prev:  # bóc các tiền tố xếp chồng ("màn hình gaming ...")
        prev = s
        s = _prefix_re().sub("", s)
    toks = [t for t in re.split(r"[\s]+", s) if t]
    # Thương hiệu = token ĐẦU TIÊN bắt đầu bằng CHỮ và KHÔNG phải từ spec/đơn vị. Bỏ qua:
    #  • token dẫn đầu bằng SỐ (spec: "3.2", "2.4ghz", "128gb", "gen3x4" bắt đầu bằng "gen"→ok nên
    #    liệt kê riêng bên dưới) — brand không bao giờ bắt đầu bằng số.
    #  • từ spec/đơn vị GIỮA chuỗi mà name_prefixes (chỉ bóc ĐẦU) không với tới ("inch", "sata",
    #    "nvme", "m.2", "gen3x4", "tb", "gb"…). Nhờ vậy "... 3.5 inch Synology ..." không ra "Inch".
    for t in toks:
        if not re.match(r"[a-zà-ỹ]", t):
            continue
        if t in _SPEC_WORDS or re.fullmatch(r"gen\d[x×]?\d*|m\.?2|\d*tb|\d*gb|\d*mb", t):
            continue
        return t.title()
    return None


def brand_of(name: str | None) -> str:
    """Trả về thương hiệu chuẩn cho một tên sản phẩm. Khớp từ khóa đã tuyển chọn trước, rồi trích
    xuất theo cấu trúc, rồi 'Other'.

    Khi NHIỀU thương hiệu cùng khớp, ưu tiên cái xuất hiện SỚM NHẤT trong tên: "UPS Sorotec HP317E"
    khớp cả "Sorotec" (vị trí 4) lẫn "hp" (bên trong mã "HP317E", vị trí 11) → chọn Sorotec. Đồng
    vị trí thì thứ tự khai báo trong file phá vỡ trùng (giữ hành vi cũ, vd Lenovo trước HP)."""
    text = name or ""
    best_brand, best_pos = None, len(text) + 1
    for order, (brand, rx) in enumerate(_brand_re().items()):
        m = rx.search(text)
        if m and m.start() < best_pos:
            best_brand, best_pos = brand, m.start()
    if best_brand is not None:
        return best_brand
    # VGA không có tên hãng: suy luận theo DÒNG card (VENTUS->MSI, WINDFORCE->Gigabyte…) trước khi
    # rơi xuống trích cấu trúc (vốn có thể vớ nhầm "VGA"/"RTX" làm brand).
    low = text.lower()
    for line, brand in _VGA_LINE_BRAND.items():
        if re.search(rf"\b{re.escape(line)}\b", low):
            return brand
    # Card NVIDIA/AMD bán TRẦN không có board-partner (RTX A1000, RTX PRO 4000, Radeon Pro …): tên có
    # GPU nhưng không có hãng/dòng → gán theo hãng GPU thay vì vớ nhầm mã model ("A1000") làm brand.
    if re.search(r"\b(rtx|gtx|geforce)\b", low):
        return "NVIDIA"
    if re.search(r"\bradeon\b", low):
        return "AMD"
    return _structural_brand(text) or "Other"


def name_match_term(brand: str) -> str:
    """Chuỗi regex alternation khớp một thương hiệu trong tên sản phẩm, dùng cho các bộ lọc danh
    sách chạy trong JS. Apple cần thêm "macbook" — vì listing của hãng ghi "MacBook ...", không
    phải "Apple ...".
    """
    by_lower = {b.lower(): b for b in _brands()}
    canonical = by_lower.get(brand.lower(), brand)
    return "|".join(_brands().get(canonical, (brand.lower(),)))
