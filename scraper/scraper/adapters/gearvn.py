"""Adapter GearVN — cài đặt tham chiếu.

Trích xuất giá hiện tại (VND, dạng int) từ trang sản phẩm GearVN.

LƯU Ý: Bố cục trang web có thể thay đổi. Các selector bên dưới chỉ là điểm khởi đầu; khi GearVN
thay đổi markup, hãy cập nhật `parse_price`. Ta thử vài chiến lược trước khi bỏ cuộc để một thay
đổi markup nhỏ không làm hỏng toàn bộ việc thu thập dữ liệu.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup


def _digits_to_int(text: str) -> int | None:
    """Chuyển chuỗi giá như '23.490.000₫' hoặc '23,490,000 đ' thành 23490000."""
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def parse_price(html: str, url: str) -> int | None:
    """Trả về giá sản phẩm bằng VND, hoặc None nếu không tìm thấy."""
    soup = BeautifulSoup(html, "html.parser")

    # Chiến lược 1: dữ liệu có cấu trúc (JSON-LD) — đáng tin cậy nhất khi có sẵn.
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

    # Chiến lược 2: một thẻ meta, thường gặp trên các template thương mại điện tử.
    meta = soup.find("meta", attrs={"property": "product:price:amount"})
    if meta and meta.get("content"):
        price = _digits_to_int(meta["content"])
        if price:
            return price

    # Chiến lược 3: phần tử giá hiển thị. Điều chỉnh selector cho khớp với markup hiện tại.
    el = soup.select_one(".product-price, .price, [class*='product-price']")
    if el:
        price = _digits_to_int(el.get_text())
        if price:
            return price

    return None
