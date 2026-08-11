"""Làm mới bảng cache latest_prices_cache sau khi scrape xong.

latest_prices giờ đọc từ BẢNG latest_prices_cache (đã tính sẵn) thay vì tính lại ~1.2s mỗi request →
dashboard đọc ~50ms. Bảng cache là ẢNH CHỤP — không tự cập nhật khi price_history đổi. File này gọi
hàm SQL refresh_latest_prices() (qua RPC) để tính lại + thay nội dung bảng sau mỗi lần scrape.

refresh_latest_prices() dùng delete+insert trong 1 transaction (nguyên tử): người dùng đọc GIỮA lúc
refresh vẫn thấy trọn snapshot CŨ, xong commit thì lần đọc sau thấy trọn snapshot MỚI.

CHẠY Ở CUỐI job CI, SAU khi mọi scraper xong (xem .github/workflows/scrape.yml).

Thất bại thì THOÁT MÃ LỖI (exit 1) → CI đỏ → có email. KHÔNG nuốt lỗi: refresh im lặng thất bại là ca
tệ nhất (price_history mới nhưng dashboard hiện dữ liệu cũ, không báo gì). Vì vậy KHÔNG dùng `|| true`
cho step này trong workflow.

Cách dùng:
    python -m scraper.refresh_views
"""

from __future__ import annotations

import sys

from .db import get_client


def main() -> int:
    client = get_client()
    print("Refreshing latest_prices_cache ...")
    try:
        # Hàm SQL refresh_latest_prices() tính lại + thay nội dung bảng (delete+insert nguyên tử).
        client.rpc("refresh_latest_prices").execute()
    except Exception as e:
        print(f"ERROR: refresh_latest_prices() thất bại — dashboard sẽ hiển thị dữ liệu CŨ: {e}",
              file=sys.stderr)
        return 1  # CI đỏ để không âm thầm phục vụ dữ liệu cũ

    # Xác nhận độ tươi: refreshed_at của bảng cache so với scraped_at mới nhất của price_history.
    try:
        cache = client.table("latest_prices_cache").select("refreshed_at").limit(1).execute()
        ph = (client.table("price_history").select("scraped_at")
              .order("scraped_at", desc=True).limit(1).execute())
        refreshed = cache.data[0]["refreshed_at"] if cache.data else "?"
        scraped = ph.data[0]["scraped_at"] if ph.data else "?"
        print(f"OK. refreshed_at={refreshed}  |  latest scraped_at={scraped}")
    except Exception as e:
        # Refresh đã chạy xong; đây chỉ là bước xác nhận, lỗi ở đây không nên làm CI đỏ.
        print(f"(refresh done; freshness check skipped: {e})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
