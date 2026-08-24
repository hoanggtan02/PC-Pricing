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

RETRY (thêm 2026-08): job "refresh" của sync.yml thỉnh thoảng fail với exit code 1 dù không có gì
rõ ràng ngoài dòng ERROR cuối. Nếu lỗi là do SQL/logic sai trong refresh_latest_prices() (constraint
vi phạm, kiểu dữ liệu sai...), MỌI lần chạy sẽ fail GIỐNG NHAU — nhưng nếu chỉ "thỉnh thoảng" fail,
nhiều khả năng là lỗi TẠM THỜI (mạng chập chờn giữa runner CI và Supabase, Supabase quá tải tức
thời, connection pool hết chỗ...). Thử lại vài lần với backoff tăng dần trước khi thật sự báo CI đỏ,
để không phải re-run tay job chỉ vì một lần trục trặc thoáng qua. Nếu vẫn đỏ SAU CẢ 3 lần thử, đó
là tín hiệu đáng tin hơn rằng lỗi là THẬT (SQL/logic), không phải may rủi mạng — lúc đó cần đọc dòng
"ERROR: refresh_latest_prices() thất bại..." bên dưới để biết chính xác nguyên nhân.

Cách dùng:
    python -m scraper.refresh_views
"""

from __future__ import annotations

import sys
import time

from .db import get_client

# Số lần thử RPC trước khi bỏ cuộc + CI đỏ. Xem ghi chú "RETRY" ở docstring đầu file.
MAX_ATTEMPTS = 3
# Backoff giữa các lần thử: 5s sau lần 1, 10s sau lần 2 (tăng dần — nhường thời gian cho sự cố
# tạm thời tự phục hồi thay vì dồn dập thử lại ngay).
BACKOFF_SECONDS_PER_ATTEMPT = 5


def main() -> int:
    client = get_client()
    print("Refreshing latest_prices_cache ...")

    last_err: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            # Hàm SQL refresh_latest_prices() tính lại + thay nội dung bảng (delete+insert nguyên tử).
            client.rpc("refresh_latest_prices").execute()
            last_err = None
            break
        except Exception as e:
            last_err = e
            print(f"  ⚠️  Lần thử {attempt}/{MAX_ATTEMPTS} thất bại: {e}")
            if attempt < MAX_ATTEMPTS:
                wait_s = BACKOFF_SECONDS_PER_ATTEMPT * attempt
                print(f"  ⏳ Chờ {wait_s}s rồi thử lại...")
                time.sleep(wait_s)

    if last_err is not None:
        print(
            f"ERROR: refresh_latest_prices() thất bại sau {MAX_ATTEMPTS} lần thử — dashboard sẽ "
            f"hiển thị dữ liệu CŨ: {last_err}",
            file=sys.stderr,
        )
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