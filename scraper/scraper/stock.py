"""Phát hiện HẾT HÀNG (out-of-stock) dùng chung cho các scraper.

Vì sao tách ra: mỗi cửa hàng ra tín hiệu hết hàng theo cách khác nhau, và LỖI phổ biến nhất là
scraper QUÊN kiểm tra tồn kho → mọi sản phẩm bị gắn cờ "còn hàng" (kể cả hàng "Liên hệ"). Gom
logic vào một HÀM THUẦN (chỉ nhận text, trả bool) để:
  1. mọi scraper gọi cùng một chỗ (không ai quên),
  2. viết unit test dễ dàng (đưa text mẫu vào, assert kết quả) — bắt lỗi trước khi lên production.

Quy ước: `is_in_stock(text)` trả về False nếu text chứa BẤT KỲ cụm từ báo hết hàng nào. Mặc định
CÒN HÀNG (True) khi không có tín hiệu — an toàn hơn là ẩn nhầm sản phẩm còn bán.
"""

from __future__ import annotations

import re

# Các cụm từ báo HẾT HÀNG mà những cửa hàng VN dùng (không phân biệt hoa/thường, có/không dấu).
# "Liên hệ" = báo giá theo yêu cầu (không bán trực tiếp) → coi như hết hàng để không hiện là rẻ nhất.
_OOS_PATTERNS = (
    r"liên hệ",
    r"lien he",
    r"hết hàng",
    r"het hang",
    r"hàng sắp về",
    r"hang sap ve",
    r"sắp về hàng",
    r"tạm hết",
    r"tam het",
    r"ngừng kinh doanh",
    r"ngung kinh doanh",
    r"sold out",
    r"cháy hàng",
    r"đăng ký mua",       # HACOM: nút "ĐĂNG KÝ MUA / Nhận thông báo khi có hàng" = hết hàng
    r"dang ky mua",
    r"thông báo khi có hàng",
    r"nhận thông báo",
)
_OOS_RE = re.compile("|".join(_OOS_PATTERNS), re.IGNORECASE)


def is_out_of_stock(text: str | None) -> bool:
    """True nếu `text` (nội dung thẻ sản phẩm hoặc trang) chứa tín hiệu hết hàng."""
    return bool(text) and bool(_OOS_RE.search(text))


def is_in_stock(text: str | None) -> bool:
    """True nếu KHÔNG thấy tín hiệu hết hàng (mặc định còn hàng khi thiếu tín hiệu)."""
    return not is_out_of_stock(text)


def stock_from_price(price: int | None) -> bool:
    """Với cửa hàng ra tín hiệu bằng CHÍNH giá: có giá (số) = còn hàng; không có (None/"Liên hệ") =
    hết hàng. Dùng cho TNC và các trang chỉ hiện "Liên hệ" thay cho giá."""
    return price is not None
