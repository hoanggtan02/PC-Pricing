"""Test SKU cho laptop — tập trung vào hậu tố bảo hành Dell (-2Y/-1Y/-3Y).

Vì sao cần test: TNC bán CÙNG một máy dưới 2 mã — có "-2Y" (bảo hành 2 năm) và không — với GIÁ KHÁC
nhau. Trước khi sửa, "-2Y" bị coi là rác và bị bỏ → hai sản phẩm khác nhau gộp vào một SKU, ghi đè
nhau trong catalog và so giá nhầm (cùng lỗi lớp với vụ trùng SKU RAM/CPU).

Tên/slug dùng trong test lấy THẬT từ tnc.com.vn (2026-07, keyword C7U161W11BLU).

Chạy:  cd scraper && python -m unittest tests.test_laptop_sku -v
"""

from __future__ import annotations

import unittest

from scraper.sku import derive_sku


def sku(name: str, slug: str) -> str | None:
    return derive_sku(name, slug, "Laptop")


class TestDellWarrantySuffix(unittest.TestCase):
    # Hai listing THẬT trên TNC cho keyword C7U161W11BLU — cùng model, KHÁC gói bảo hành.
    NAME_2Y = "Laptop Dell 16 DC16250 DC16250-C7U161W11BLU-2Y (Core 7 150U)"
    SLUG_2Y = "/laptop-dell-16-dc16250-dc16250-c7u161w11blu-2y.html"
    NAME_STD = "Laptop Dell 16 DC16250 DC16250-C7U161W11BLU (Core 7 150U)"
    SLUG_STD = "/laptop-dell-16-dc16250-core-7-dc16250-c7u161w11blu.html"

    def test_2y_and_standard_are_distinct(self):
        """Lỗi gốc: cả hai ra DC16250-C7U161W11BLU. Giờ phải KHÁC nhau."""
        s_2y = sku(self.NAME_2Y, self.SLUG_2Y)
        s_std = sku(self.NAME_STD, self.SLUG_STD)
        self.assertNotEqual(s_2y, s_std, "2Y và bản thường bị gộp cùng SKU")

    def test_2y_suffix_kept_on_code(self):
        self.assertEqual(sku(self.NAME_2Y, self.SLUG_2Y), "DC16250-C7U161W11BLU-2Y")

    def test_standard_has_no_suffix(self):
        self.assertEqual(sku(self.NAME_STD, self.SLUG_STD), "DC16250-C7U161W11BLU")

    def test_other_warranty_tiers(self):
        """1Y / 3Y cũng phải được giữ, và tách khỏi nhau + khỏi bản không hậu tố."""
        base = "Laptop Dell 15 DC15250 DC15250-C3U085W11SLU"
        s0 = sku(base, "/laptop-dell-15-dc15250-dc15250-c3u085w11slu.html")
        s1 = sku(base + "-1Y", "/laptop-dell-15-dc15250-dc15250-c3u085w11slu-1y.html")
        s3 = sku(base + "-3Y", "/laptop-dell-15-dc15250-dc15250-c3u085w11slu-3y.html")
        self.assertEqual(len({s0, s1, s3}), 3, f"các gói bảo hành bị gộp: {s0} {s1} {s3}")


class TestDellNoRegression(unittest.TestCase):
    """Laptop Dell KHÔNG có hậu tố bảo hành phải giữ nguyên SKU như trước khi sửa."""

    CASES = [
        ("Laptop Dell 14 DC14255 Ryzen AI 5 330 DC4A5330W1",
         "/laptop-dell-14-dc14255-dc4a5330w1.html", "DC14255-DC4A5330W1"),
        ("Laptop Dell 15 DC15255 DC5R5973W1",
         "/laptop-dell-15-dc15255-dc5r5973w1.html", "DC15255-DC5R5973W1"),
        ("Laptop Dell Latitude 3540 42LT354001 XCTO",
         "/laptop-dell-latitude-3540-42lt354001-xcto.html", "42LT354001"),
    ]

    def test_non_warranty_dells_unchanged(self):
        for name, slug, _ in self.CASES:
            with self.subTest(name=name):
                # chỉ khẳng định hậu tố -2Y/-1Y/-3Y KHÔNG bị thêm nhầm vào máy không có bảo hành.
                s = sku(name, slug)
                self.assertIsNotNone(s)
                self.assertFalseSuffix(s)

    def assertFalseSuffix(self, s: str):
        for w in ("-1Y", "-2Y", "-3Y"):
            self.assertFalse(s.upper().endswith(w), f"{s} bị gắn nhầm hậu tố bảo hành")


if __name__ == "__main__":
    unittest.main()
