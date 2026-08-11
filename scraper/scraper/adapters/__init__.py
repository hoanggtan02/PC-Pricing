"""Adapter cho các đối thủ cạnh tranh.

Mỗi adapter biết cách trích xuất giá (bằng VND) từ trang sản phẩm của một đối thủ.
Để thêm một đối thủ mới, tạo một module mới ở đây với hàm `parse_price(html, url) -> int | None`
và đăng ký tên của nó trong `ADAPTERS` bên dưới.
"""

from .cellphones import parse_price as cellphones_parse_price
from .gearvn import parse_price as gearvn_parse_price
from .thanhnhan import parse_price as thanhnhan_parse_price

# Ánh xạ giá trị `competitor` lưu trong bảng `sources` tới parser tương ứng.
# Cửa hàng của chính chúng ta ("Thành Nhân") chỉ là một entry khác — chính cờ is_self trong DB,
# chứ không phải map này, mới là thứ đánh dấu nó là baseline.
ADAPTERS = {
    "CellphoneS": cellphones_parse_price,
    "GearVN": gearvn_parse_price,
    "Thành Nhân": thanhnhan_parse_price,
}
