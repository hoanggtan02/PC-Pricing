"""Test SKU cho máy in / scan / UPS / máy chiếu / TV (av_sku) và máy tính bảng (tablet_sku).

Tên lấy THẬT từ tnc.com.vn (2026-07). Trọng tâm: mã model phải là ĐỊNH DANH thật (in giống ở mọi
cửa hàng), KHÔNG được lấy nhầm spec (VA/W, inch, 4K) — nếu không hai sản phẩm khác nhau gộp một SKU.

Chạy:  cd scraper && python -m unittest tests.test_av_tablet_sku -v
"""

from __future__ import annotations

import unittest

from scraper.sku import derive_sku


class TestPrinterScanner(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(derive_sku("Máy in Epson L3250", None, "Printer"), "EPSON-L3250")
        self.assertEqual(derive_sku("Máy in Pantum P2516", None, "Printer"), "PANTUM-P2516")

    def test_split_prefix_rejoined(self):
        """"LBP" + "121dn" bị tách rời phải ghép lại — LBP121 vs LBP221 là 2 máy khác nhau."""
        self.assertEqual(derive_sku("MÁY IN CANON LBP 121dn", None, "Printer"), "CANON-LBP121DN")

    def test_hp_partcode_in_parens(self):
        self.assertEqual(
            derive_sku("Máy in HP Laser 108w (4ZB80A)", None, "Printer"), "HP-4ZB80A"
        )
        self.assertEqual(
            derive_sku("Máy Scan HP ScanJet Pro 2000 s2 (6FW06A)", None, "Scanner"), "HP-6FW06A"
        )

    def test_model_with_hyphen_kept(self):
        self.assertEqual(
            derive_sku("Máy in Laser Brother DCP-B7640DW", None, "Printer"), "BROTHER-DCP-B7640DW"
        )


class TestUps(unittest.TestCase):
    def test_partcode_not_spec(self):
        """LỖI dễ gặp: lấy "1200VA" (spec) thay vì mã "BVG1200I-MSN". Phải lấy mã part."""
        self.assertEqual(
            derive_sku("Bộ lưu điện UPS APC BVG1200I-MSN (Line Interactive/1200VA/650W)", None, "Ups"),
            "APC-BVG1200I-MSN",
        )

    def test_paren_spec_ignored(self):
        self.assertEqual(
            derive_sku("Bộ lưu điện UPS Hikvision DS-UPS1000 (Offline/1000VA/600W)", None, "Ups"),
            "HIKVISION-DS-UPS1000",
        )

    def test_simple_models(self):
        self.assertEqual(
            derive_sku("Bộ lưu điện UPS Cyber Power BU650E (650VA/360W)", None, "Ups"),
            "CYBERPOWER-BU650E",
        )
        self.assertEqual(derive_sku("UPS ARES AR630", None, "Ups"), "ARES-AR630")

    def test_different_models_distinct(self):
        a = derive_sku("UPS ARES AR630", None, "Ups")
        b = derive_sku("UPS ARES AR620", None, "Ups")
        self.assertNotEqual(a, b)


class TestProjectorTv(unittest.TestCase):
    def test_projector(self):
        self.assertEqual(derive_sku("Máy chiếu PANASONIC PT-VW360", None, "Projector"), "PANASONIC-PT-VW360")
        self.assertEqual(derive_sku("Máy chiếu CANON LV-HD420", None, "Projector"), "CANON-LV-HD420")

    def test_tv_model_not_size(self):
        """Mã TV là định danh, KHÔNG phải "55 inch"/"4K"."""
        self.assertEqual(
            derive_sku("Smart Tivi Samsung 4K 55 Inch UA55U8500F", None, "Tv"), "SAMSUNG-UA55U8500F"
        )
        self.assertEqual(
            derive_sku("Smart Tivi LG UHD 4K 65 inch 2025 (65UA7350PSB)", None, "Tv"), "LG-65UA7350PSB"
        )

    def test_tcl_not_google(self):
        """"Google Tivi TCL …" — hãng là TCL, không phải Google."""
        self.assertEqual(
            derive_sku("Google Tivi TCL UHD 4K 75 inch 2025 75P6K", None, "Tv"), "TCL-75P6K"
        )


class TestTablet(unittest.TestCase):
    def test_ipad_by_spec_not_mpn(self):
        """iPad khoá theo THÔNG SỐ (không MPN): MPN chỉ có ở TNC/Phong Vũ, FPT/TGĐĐ không ghi."""
        self.assertEqual(
            derive_sku("iPad Air M4 11 inch Wifi 512GB Starlight MH3D4ZA/A", None, "Tablet"),
            "APPLE-AIR-M4-11-512GB",
        )

    def test_ipad_cross_store_match(self):
        """CÙNG iPad, cách đặt tên KHÁC ở mỗi cửa hàng, phải ra CÙNG SKU (điều kiện so giá được)."""
        tnc = derive_sku("iPad Air M4 11 inch Wifi 128GB Purple MH344ZA/A", None, "Tablet")  # có màu+MPN
        tgdd = derive_sku("iPad Air M4 11 inch WiFi 128GB", None, "Tablet")                    # trơn
        self.assertEqual(tnc, tgdd)
        # iPad base: TNC ghi "Gen 11 A16", FPT ghi "A16" — chip A16 là token chung.
        tnc_gen = derive_sku("Máy tính bảng Apple IPad Gen 11 A16 Wifi 128GB MD3Y4ZA/A", None, "Tablet")
        fpt_gen = derive_sku("iPad A16 WiFi 128GB", None, "Tablet")
        self.assertEqual(tnc_gen, fpt_gen)

    def test_ipad_colors_collapse(self):
        """Khác MÀU nhưng CÙNG spec = CÙNG SKU: màu không ảnh hưởng giá, gộp là đúng cho so-giá.
        (Khác vụ RAM/laptop nơi token bị gộp làm đổi cả spec lẫn giá.)"""
        star = derive_sku("iPad Air M4 11 inch Wifi 512GB Starlight MH3D4ZA/A", None, "Tablet")
        blue = derive_sku("iPad Air M4 11 inch Wifi 512GB Blue MH3C4ZA/A", None, "Tablet")
        self.assertEqual(star, blue)

    def test_ipad_storage_distinct(self):
        """Khác DUNG LƯỢNG = khác SKU (giá khác thật)."""
        g128 = derive_sku("iPad Air M4 11 inch WiFi 128GB", None, "Tablet")
        g512 = derive_sku("iPad Air M4 11 inch WiFi 512GB", None, "Tablet")
        self.assertNotEqual(g128, g512)

    def test_lenovo_partcode(self):
        self.assertEqual(
            derive_sku("Lenovo Legion Tab Snap 8 ZAEF0103VN", None, "Tablet"), "LENOVO-ZAEF0103VN"
        )

    def test_lenovo_configs_distinct(self):
        a = derive_sku("Lenovo Idea Tab Wifi 8GB 256GB ZAFR0402VN", None, "Tablet")
        b = derive_sku("Lenovo Idea Tab Wifi 8GB 128GB ZAFR0366VN", None, "Tablet")
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
