"""Adapter Thành Nhân — thu thập giá từ cửa hàng của CHÍNH chúng ta.

Về mặt cơ chế giống hệt một adapter đối thủ: tải trang sản phẩm, phân tích giá.
Cờ is_self trên source (được đặt trong DB) mới là thứ đánh dấu đây là baseline, chứ không phải
scraper — nên không có gì đặc biệt xảy ra ở đây. Cập nhật các selector cho khớp với markup của
trang web chính chúng ta.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup


def _digits_to_int(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def parse_price(html: str, url: str) -> int | None:
    """Trả về giá sản phẩm của chúng ta bằng VND, hoặc None nếu không tìm thấy."""
    soup = BeautifulSoup(html, "html.parser")

    # Chiến lược 1: dữ liệu có cấu trúc (JSON-LD), nếu trang web của chúng ta có cung cấp.
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in data if isinstance(data, list) else [data]:
            offers = node.get("offers") if isinstance(node, dict) else None
            if isinstance(offers, dict) and offers.get("price"):
                price = _digits_to_int(str(offers["price"]))
                if price:
                    return price

    # Chiến lược 2: phần tử giá hiển thị — điều chỉnh cho khớp với markup của trang web chúng ta.
    el = soup.select_one(".product-price, .price, [class*='price']")
    if el:
        price = _digits_to_int(el.get_text())
        if price:
            return price

    return None
