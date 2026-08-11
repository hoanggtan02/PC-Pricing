"""Adapter CellphoneS — https://cellphones.com.vn

Đã xác minh trên các trang sản phẩm thực tế. CellphoneS nhúng một khối JSON-LD Product theo
schema.org với offers.price được đặt bằng giá HIỆN TẠI (giá sale) — nguồn sạch và đáng tin cậy
nhất. Ta dự phòng bằng phần tử .sale-price hiển thị (KHÔNG phải .base-price, vốn là giá gốc bị
gạch ngang).
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup


def _digits_to_int(text: str) -> int | None:
    """Chuyển '20.990.000đ' hoặc '20990000' thành 20990000."""
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def parse_price(html: str, url: str) -> int | None:
    """Trả về giá hiện tại bằng VND, hoặc None nếu không tìm thấy."""
    soup = BeautifulSoup(html, "html.parser")

    # Chiến lược 1: JSON-LD Product theo schema.org → offers.price (giá hiện tại/giá sale).
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in data if isinstance(data, list) else [data]:
            if not isinstance(node, dict) or node.get("@type") != "Product":
                continue
            offers = node.get("offers")
            if isinstance(offers, dict) and offers.get("price"):
                price = _digits_to_int(str(offers["price"]))
                if price:
                    return price

    # Chiến lược 2: giá sale hiển thị. Quan trọng là .sale-price, không phải .base-price (gạch ngang).
    el = soup.select_one(".sale-price")
    if el:
        price = _digits_to_int(el.get_text())
        if price:
            return price

    return None
