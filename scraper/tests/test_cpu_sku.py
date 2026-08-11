"""Test SKU cho CPU rời (Intel/AMD).

Vì sao cần test: SKU sai kiểu "gộp nhầm" đã gây bug thật trên production (RAM TeamGroup, laptop
Apple) — hai sản phẩm KHÁC NHAU dồn về một SKU thì dashboard hiện sai tồn kho và so giá bậy. CPU dễ
dính lỗi này nhất vì hậu tố mới là thứ phân biệt: 14700 / 14700F / 14700K / 14700KF là BỐN con CPU
khác nhau, giá chênh nhau vài triệu.

Tên sản phẩm dùng trong test được lấy THẬT từ tnc.com.vn/cpu.html và gearvn.com (2026-07).

Chạy:  cd scraper && python -m unittest tests.test_cpu_sku -v
"""

from __future__ import annotations

import unittest

from scraper.sku import cpu_sku, derive_sku


class TestIntelCore(unittest.TestCase):
    def test_core_i_series(self):
        self.assertEqual(cpu_sku("CPU Intel Core i5-14400"), "INTEL-CORE-I5-14400")
        self.assertEqual(cpu_sku("CPU Intel Core i7 12700"), "INTEL-CORE-I7-12700")
        self.assertEqual(cpu_sku("CPU Intel Core i3-6100"), "INTEL-CORE-I3-6100")

    def test_hyphen_and_space_are_same_cpu(self):
        """TNC ghi cả "i5-14400" lẫn "i5 14400" — phải ra CÙNG một SKU."""
        self.assertEqual(cpu_sku("CPU Intel Core i5-14400F"), cpu_sku("Intel Core i5 14400F"))

    def test_suffix_makes_a_DIFFERENT_cpu(self):
        """Lỗi nguy hiểm nhất: gộp 14700/F/K/KF làm một. Bốn SKU phải KHÁC NHAU."""
        skus = {
            cpu_sku("Intel Core i7 14700"),
            cpu_sku("Intel Core i7-14700F"),
            cpu_sku("Intel Core i7-14700K"),
            cpu_sku("CPU Intel Core i7-14700KF"),
        }
        self.assertEqual(len(skus), 4, f"suffix bị nuốt → gộp nhầm CPU: {skus}")

    def test_generation_matters(self):
        """i5-14400 (gen 14) ≠ i5-10400 (gen 10) — cùng dòng i5 nhưng khác đời."""
        self.assertNotEqual(cpu_sku("CPU Intel Core i5-14400"), cpu_sku("CPU Intel Core i5-10400"))


class TestIntelUltra(unittest.TestCase):
    def test_ultra(self):
        self.assertEqual(cpu_sku("CPU Intel Core Ultra 7 265K"), "INTEL-ULTRA-7-265K")
        self.assertEqual(cpu_sku("CPU Intel Core Ultra 9 285K"), "INTEL-ULTRA-9-285K")

    def test_ultra_k_vs_kf(self):
        self.assertNotEqual(
            cpu_sku("Intel Core Ultra 7 265K"), cpu_sku("Intel Core Ultra 7 265KF")
        )

    def test_plus_is_a_real_variant(self):
        """"Plus" là biến thể thật của Intel (Arrow Lake Refresh) — không được bỏ."""
        self.assertEqual(cpu_sku("CPU Intel Core Ultra 7 270K Plus"), "INTEL-ULTRA-7-270K-PLUS")
        self.assertNotEqual(
            cpu_sku("CPU Intel Core Ultra 5 250K Plus"), cpu_sku("CPU Intel Core Ultra 5 250K")
        )


class TestAmd(unittest.TestCase):
    def test_ryzen(self):
        self.assertEqual(cpu_sku("CPU AMD Ryzen 9 9900X"), "AMD-RYZEN-9-9900X")
        self.assertEqual(cpu_sku("AMD Ryzen 5 5600X"), "AMD-RYZEN-5-5600X")

    def test_x3d_is_distinct(self):
        """9900X vs 9900X3D — X3D là bản cache lớn, giá khác hẳn."""
        self.assertNotEqual(cpu_sku("CPU AMD Ryzen 9 9900X"), cpu_sku("CPU AMD Ryzen 9 9900X3D"))

    def test_g_and_gt_suffix(self):
        self.assertEqual(cpu_sku("AMD Ryzen 5 5500GT"), "AMD-RYZEN-5-5500GT")
        self.assertNotEqual(cpu_sku("AMD Ryzen 5 5600GT"), cpu_sku("AMD Ryzen 5 5600X"))

    def test_threadripper(self):
        self.assertEqual(cpu_sku("CPU AMD Ryzen Threadripper 9960X"), "AMD-THREADRIPPER-9960X")
        self.assertEqual(
            cpu_sku("CPU AMD Ryzen Threadripper PRO 9955WX"), "AMD-THREADRIPPER-PRO-9955WX"
        )

    def test_threadripper_pro_vs_non_pro(self):
        self.assertNotEqual(
            cpu_sku("AMD Ryzen Threadripper 9960X"), cpu_sku("AMD Ryzen Threadripper PRO 9955WX")
        )

    def test_uppercase_and_stray_hyphen(self):
        """TNC có ghi "CPU AMD RYZEN-3 2200G" (viết hoa + gạch lạc chỗ)."""
        self.assertEqual(cpu_sku("CPU AMD RYZEN-3 2200G"), "AMD-RYZEN-3-2200G")

    def test_athlon_without_amd_token(self):
        """TNC ghi "CPU Athlon 3000G" — KHÔNG có chữ "AMD" trong tên."""
        self.assertEqual(cpu_sku("CPU Athlon 3000G"), "AMD-ATHLON-3000G")


class TestBudgetIntel(unittest.TestCase):
    def test_celeron_pentium(self):
        self.assertEqual(cpu_sku("CPU Intel Celeron G4900"), "INTEL-CELERON-G4900")
        self.assertEqual(cpu_sku("CPU Intel Pentium Gold G6400"), "INTEL-PENTIUM-G6400")

    def test_celeron_models_distinct(self):
        self.assertNotEqual(cpu_sku("CPU Intel Celeron G5900"), cpu_sku("CPU Intel Celeron G5905"))


class TestCrossStoreMatching(unittest.TestCase):
    """Điều kiện SỐNG CÒN: TNC và đối thủ phải ra CÙNG SKU thì mới so giá được.

    Tên ở GearVN có đuôi spec dài (" / Turbo up to 4.7GHz / 10 Nhân 16 Luồng / 20MB / LGA 1700");
    phải cắt sạch phần đó, chỉ giữ định danh.
    """

    CASES = [
        ("CPU Intel Core i5 14400F",
         "Bộ vi xử lý Intel Core i5 14400F / Turbo up to 4.7GHz / 10 Nhân 16 Luồng / 20MB / LGA 1700"),
        ("Intel Core i7 14700",
         "Bộ vi xử lý Intel Core i7 14700 / Turbo up to 5.4GHz / 20 Nhân 28 Luồng / 33MB / LGA 1700"),
        ("CPU Intel Core Ultra 9 285K",
         "Bộ vi xử lý Intel Core Ultra 9 285K / Turbo up to 5.7GHz / 24 Nhân 24 Luồng / 36MB / LGA 1851"),
        ("AMD Ryzen 5 5600X",
         "Bộ vi xử lý AMD Ryzen 5 5600X / 3.7GHz Boost 4.6GHz / 6 nhân 12 luồng / 32MB / AM4"),
        ("AMD Ryzen 5 5500GT",
         "Bộ vi xử lý AMD Ryzen 5 5500GT / 3.6GHz Boost 4.4GHz / 6 nhân 12 luồng / 19MB / AM4"),
    ]

    def test_tnc_and_gearvn_agree(self):
        for tnc_name, gearvn_name in self.CASES:
            with self.subTest(tnc=tnc_name):
                a, b = cpu_sku(tnc_name), cpu_sku(gearvn_name)
                self.assertIsNotNone(a, f"TNC không ra SKU: {tnc_name}")
                self.assertEqual(a, b, f"không khớp chéo cửa hàng:\n  TNC={a}\n  GearVN={b}")

    def test_tray_suffix_does_not_split(self):
        """GearVN gắn "(Tray)" ở cuối — không được tạo SKU riêng."""
        self.assertEqual(
            cpu_sku("Bộ vi xử lý AMD Ryzen 7 9800X3D / 4.7GHz / 8 nhân 16 luồng / 104MB / AM5"),
            cpu_sku("Bộ vi xử lý AMD Ryzen 7 9800X3D / 4.7GHz / 8 nhân 16 luồng / 104MB / AM5 (Tray)"),
        )


class TestRejectsNonCpu(unittest.TestCase):
    """Trang cpu.html của TNC có lẫn hàng KHÔNG phải CPU — phải trả None để không ghi vào catalog."""

    def test_mainboard_rejected(self):
        self.assertIsNone(cpu_sku("Mainboard Gigabyte X870E AORUS PRO X3D ICE"))

    def test_empty_and_junk(self):
        self.assertIsNone(cpu_sku(None))
        self.assertIsNone(cpu_sku(""))
        self.assertIsNone(cpu_sku("Tản nhiệt nước Deepcool LE500"))


class TestDispatch(unittest.TestCase):
    def test_derive_sku_routes_cpu_category(self):
        """derive_sku(..., "Cpu") phải gọi cpu_sku (category lưu trong DB là .capitalize())."""
        self.assertEqual(derive_sku("CPU Intel Core i5-14400", None, "Cpu"), "INTEL-CORE-I5-14400")

    def test_no_collisions_on_real_catalog_sample(self):
        """Mẫu tên THẬT từ TNC: mỗi CPU khác nhau phải ra SKU khác nhau."""
        names = [
            "CPU Intel Core i5-14400", "CPU Intel Core i5-10400", "CPU Intel Core i5 14400F",
            "AMD Ryzen 3 3200G", "Intel Core i7 14700", "CPU AMD Ryzen 9 9900X",
            "Intel Core i5 12400F", "Intel Core i7-14700F", "CPU Intel Core i5 12500",
            "CPU Intel Core i7 12700", "CPU Intel Core i7-14700KF", "CPU Intel Core Ultra 7 265K",
            "CPU AMD Ryzen 7 5700G", "AMD Ryzen 5 5500GT", "Intel Core i7-14700K",
            "AMD Ryzen 5 5600X", "CPU Intel Core Ultra 9 285K", "CPU AMD Ryzen 5 5600GT",
            "CPU Intel Core i5 12600K", "CPU AMD Ryzen 7 9850X3D", "CPU AMD Ryzen 9 9900X3D",
            "CPU AMD Ryzen 9 9950X3D", "CPU AMD Ryzen Threadripper 9960X",
        ]
        skus = [cpu_sku(n) for n in names]
        self.assertNotIn(None, skus, "có tên không ra SKU")
        dupes = {s for s in skus if skus.count(s) > 1}
        self.assertFalse(dupes, f"SKU bị trùng giữa các CPU khác nhau: {dupes}")


if __name__ == "__main__":
    unittest.main()
