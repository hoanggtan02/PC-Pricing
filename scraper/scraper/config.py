"""Đọc scraper/config/sources.yaml và phân giải URL danh sách sản phẩm theo từng (competitor, category).

Hướng theo category: mỗi category chỉ scrape một lần (không lặp theo từng brand). Có hai kiểu URL
đối thủ:
  * site có ô tìm kiếm -> điền search_term của category vào template search_url
  * site có đường dẫn theo category -> dùng URL `path` riêng cho từng category
TNC dùng URL `tnc` của category.
"""

from __future__ import annotations

import functools
import re
from pathlib import Path
from urllib.parse import quote_plus

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "sources.yaml"


@functools.lru_cache(maxsize=1)
def _config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def categories(include_disabled: bool = False) -> list[str]:
    """Các category key ĐANG BẬT (mặc định). Một category có `enabled: false` trong sources.yaml
    sẽ bị bỏ qua ở scraper (workflow + CLI choices) — dùng để tạm tắt danh mục mà không xóa cấu
    hình. Truyền include_disabled=True để lấy cả danh mục đã tắt."""
    cats = (_config().get("categories") or {})
    if include_disabled:
        return list(cats.keys())
    return [k for k, meta in cats.items() if (meta or {}).get("enabled", True)]


def category_meta(category: str) -> dict:
    """Khối cấu hình gốc của một category (tier, search_term, name_match, tnc, paths)."""
    return (_config().get("categories") or {}).get(category, {})


def tier(category: str) -> str:
    return category_meta(category).get("tier", "A")


def name_match_re(category: str) -> re.Pattern | None:
    """Regex mà tên sản phẩm phải khớp để được tính vào category này (loại bỏ nhiễu tìm kiếm)."""
    pat = category_meta(category).get("name_match")
    return re.compile(pat, re.IGNORECASE) if pat else None


def name_exclude_re(category: str) -> re.Pattern | None:
    """Regex loại BỎ — sản phẩm khớp mẫu này bị loại dù đã khớp name_match (ví dụ giá đỡ/tay treo
    màn hình: tên chứa 'màn hình' nhưng không phải màn hình). None nếu category không cấu hình."""
    pat = category_meta(category).get("name_exclude")
    return re.compile(pat, re.IGNORECASE) if pat else None


def tnc_urls(category: str) -> list[str]:
    """(Các) URL catalog TNC của một category. `tnc:` có thể là MỘT chuỗi hoặc DANH SÁCH chuỗi —
    dùng danh sách khi một category gộp nhiều trang TNC (ví dụ router = wireless + router doanh
    nghiệp). Trả về list rỗng nếu chưa cấu hình."""
    val = category_meta(category).get("tnc")
    if not val:
        return []
    return [val] if isinstance(val, str) else list(val)


def resolve_url(competitor: str, category: str) -> str | None:
    """URL danh sách sản phẩm cho một cặp (competitor, category), hoặc None nếu chưa cấu hình.

    `competitor` là key cấu hình ngắn gọn (ví dụ: 'hacom', 'tnc'). Các site có ô tìm kiếm sẽ được
    điền template bằng search_term của category; TNC và các site có đường dẫn theo category sẽ
    dùng URL tường minh của chúng.
    """
    cfg = _config()
    cat = category_meta(category)

    if competitor == "tnc":
        return cat.get("tnc")

    # site có đường dẫn theo category với URL tường minh?
    path = (cat.get("paths") or {}).get(competitor)
    if path:
        return path

    # site có ô tìm kiếm: điền search term của category vào template
    search_url = (cfg.get("competitors") or {}).get(competitor, {}).get("search_url")
    if search_url:
        term = cat.get("search_term", "").strip()
        return search_url.replace("{query}", quote_plus(term))

    return None
