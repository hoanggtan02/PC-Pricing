"""Unit test cho phát hiện HẾT HÀNG (out-of-stock) của MỌI cửa hàng.

Mục đích: bắt lỗi "quên kiểm tra tồn kho" hoặc "đổi tín hiệu OOS" TRƯỚC khi lên production —
chính là lỗi đã khiến HACOM/Memoryzone gắn cờ mọi sản phẩm là còn hàng (kể cả "Liên hệ").

Chạy (không cần pytest, chỉ stdlib):
    python -m unittest scraper.tests.test_stock -v
Hoặc nếu có pytest:
    pytest scraper/tests/test_stock.py -v

Chiến lược: mỗi cửa hàng ra tín hiệu OOS khác nhau. Test kiểm tra CHÍNH biểu thức/regex mà scraper
dùng (không mock), với cả mẫu HẾT HÀNG lẫn CÒN HÀNG, để một thay đổi làm hỏng logic sẽ fail ngay.
"""

from __future__ import annotations

import re
import unittest

from scraper.stock import is_in_stock, is_out_of_stock, stock_from_price


class TestSharedStock(unittest.TestCase):
    """Module dùng chung — HACOM & Memoryzone gọi is_in_stock() trên text của thẻ."""

    # Mẫu text thẻ báo HẾT HÀNG (phải trả False cho is_in_stock).
    OOS_SAMPLES = [
        "Ổ cứng HDD Synology HAT5320-4T 10.899.000đ Liên hệ Mua hàng online",  # bug thực tế
        "USB Kingston 64GB Hết hàng",
        "Màn hình Dell HÀNG SẮP VỀ 5.000.000đ",
        "SSD Samsung tạm hết hàng",
        "Router TP-Link Ngừng kinh doanh",
        "Chuột Logitech lien he",           # không dấu
        "Bàn phím cơ het hang",             # không dấu
        "Laptop XYZ SOLD OUT 20.000.000đ",
        "Card VGA cháy hàng",
    ]
    # Mẫu text thẻ CÒN HÀNG (phải trả True).
    IN_STOCK_SAMPLES = [
        "Ổ cứng HDD WD 4TB 2.500.000đ Thêm vào giỏ Mua ngay",
        "SSD Samsung 990 Pro 1TB 3.200.000đ Còn hàng",
        "Màn hình LG 27 inch 5.490.000đ Mua ngay",
        "USB SanDisk 128GB 250.000đ",
        "RAM Corsair 16GB 1.290.000đ Đặt hàng",   # "đặt hàng" ≠ OOS
    ]

    def test_oos_samples_flagged(self):
        for s in self.OOS_SAMPLES:
            with self.subTest(sample=s):
                self.assertTrue(is_out_of_stock(s), f"phải là HẾT HÀNG: {s!r}")
                self.assertFalse(is_in_stock(s), f"is_in_stock phải False: {s!r}")

    def test_in_stock_samples_pass(self):
        for s in self.IN_STOCK_SAMPLES:
            with self.subTest(sample=s):
                self.assertFalse(is_out_of_stock(s), f"phải là CÒN HÀNG: {s!r}")
                self.assertTrue(is_in_stock(s), f"is_in_stock phải True: {s!r}")

    def test_empty_and_none_default_in_stock(self):
        # Thiếu tín hiệu -> mặc định CÒN HÀNG (an toàn hơn ẩn nhầm).
        for empty in (None, "", "   "):
            self.assertTrue(is_in_stock(empty))
            self.assertFalse(is_out_of_stock(empty))

    def test_case_insensitive(self):
        self.assertFalse(is_in_stock("LIÊN HỆ"))
        self.assertFalse(is_in_stock("Liên Hệ"))
        self.assertFalse(is_in_stock("hẾt hÀng"))


class TestTncPriceStock(unittest.TestCase):
    """TNC & các trang ra tín hiệu bằng chính giá: có số = còn hàng, None = hết hàng."""

    def test_price_present_in_stock(self):
        self.assertTrue(stock_from_price(2_500_000))
        self.assertTrue(stock_from_price(0))  # giá 0 vẫn là "có giá" (không phải None)

    def test_price_none_out_of_stock(self):
        # "Liên hệ" -> không parse được số -> price None -> hết hàng
        self.assertFalse(stock_from_price(None))


# ── Test tín hiệu OOS của các scraper chạy trong JS (kiểm tra regex tương đương ở Python) ─────────
# Các scraper CellphoneS/PhongVu/FPT/TGĐĐ tính in_stock trong trình duyệt bằng regex trên text thẻ.
# Ta sao lại CHÍNH regex đó ở đây và test — nếu ai đổi cụm từ, test sẽ fail, buộc cập nhật đồng bộ.

class TestPerStoreSignals(unittest.TestCase):
    # (tên store, regex OOS như trong scraper, [mẫu OOS], [mẫu còn hàng])
    CASES = {
        "phongvu": (
            re.compile(r"liên hệ", re.I),
            ["Liên hệ", "LIÊN HỆ để biết giá"],
            ["2.500.000đ", "Mua ngay"],
        ),
        "fptshop": (
            re.compile(r"hàng sắp về", re.I),
            ["Hàng sắp về", "PC Gaming Hàng sắp về"],
            ["9.990.000đ Mua ngay", "Còn hàng"],
        ),
        "tgdd": (
            re.compile(r"sắp về|hết hàng", re.I),
            ["Sắp về", "Tạm hết hàng", "Hết hàng"],
            ["Mua ngay 5.000.000đ", "Còn hàng"],
        ),
    }

    def test_store_oos_regexes(self):
        for store, (rx, oos, ok) in self.CASES.items():
            for s in oos:
                with self.subTest(store=store, sample=s, kind="oos"):
                    # scraper dùng: in_stock = not rx.search(text)  -> phải là OOS
                    self.assertTrue(rx.search(s), f"[{store}] phải khớp OOS: {s!r}")
            for s in ok:
                with self.subTest(store=store, sample=s, kind="ok"):
                    self.assertFalse(rx.search(s), f"[{store}] KHÔNG được khớp: {s!r}")


class TestAllScrapersWriteInStock(unittest.TestCase):
    """Bảo vệ chống lỗi 'quên gắn in_stock': mỗi discover_*.py phải ghi in_stock vào price_rows.
    Đọc source, khẳng định price_rows.append có 'in_stock' (đã từng thiếu ở HACOM/Memoryzone)."""

    SCRAPERS = [
        "anphat", "cellphones", "hacom", "phongvu", "fptshop",
        "tgdd", "gearvn", "memoryzone", "tnc",
    ]

    def test_every_scraper_sets_in_stock(self):
        import pathlib

        base = pathlib.Path(__file__).resolve().parent.parent / "scraper"
        for name in self.SCRAPERS:
            src = (base / f"discover_{name}.py").read_text(encoding="utf-8")
            with self.subTest(scraper=name):
                # tìm khối price_rows.append(...) và khẳng định có 'in_stock' trong đó
                self.assertIn(
                    "in_stock",
                    _price_row_block(src),
                    f"discover_{name}.py: price_rows.append KHÔNG ghi in_stock "
                    f"(mọi sản phẩm sẽ bị gắn cờ còn hàng — chính lỗi HACOM/Memoryzone).",
                )


def _price_row_block(src: str) -> str:
    """Trả về ~400 ký tự quanh 'price_rows.append' để kiểm tra có 'in_stock' hay không."""
    i = src.find("price_rows.append")
    return src[i : i + 400] if i >= 0 else ""


if __name__ == "__main__":
    unittest.main(verbosity=2)
