"""Các hàm hỗ trợ Supabase client cho scraper."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set. Copy .env.example to .env and fill them in."
        )
    return create_client(url, key)


def fetch_catalog_skus(client: Client, category: str | None = None) -> set[str]:
    """Trả về các sku trong `products` để đối chiếu khi khớp giá đối thủ.

    Một scraper CHỈ khớp SKU cùng danh mục với thứ nó đang cào (scrape laptop → chỉ cần SKU laptop),
    nên truyền `category` để lấy đúng tập đó: vừa nhanh (một request, ~vài trăm–nghìn dòng) vừa an
    toàn (không có nguy cơ khớp chéo danh mục). Bỏ qua `category` (None) sẽ lấy toàn bộ catalog.

    Vì sao KHÔNG `.select("sku").execute()` trần: PostgREST giới hạn mặc định 1000 dòng/lần. Catalog
    nay ĐA DANH MỤC đã vượt 1000, nên select trần sẽ CẮT CỤT ở 1000 và bỏ sót phần lớn SKU → đối
    thủ khớp được rất ít. Ta lọc theo danh mục (và vẫn phân trang phòng khi một danh mục >1000 dòng).
    """
    skus: set[str] = set()
    page = 0
    size = 1000
    while True:
        q = client.table("products").select("sku")
        if category is not None:
            q = q.eq("category", category)
        rows = q.range(page * size, page * size + size - 1).execute().data or []
        skus.update(r["sku"] for r in rows)
        if len(rows) < size:  # trang cuối (ít hơn size) → hết dữ liệu
            break
        page += 1
    return skus


def fetch_existing_source_skus(client: Client, competitor: str) -> set[str]:
    """SKU nào của `competitor` ĐÃ có source trong DB (bất kể active hay không).

    Vì sao cần: Mode A (scrape.yml, chạy cuối tuần) trước đây ghi giá cho MỌI SKU khớp được, kể cả
    những SKU đã có source từ trước — tức là ĐÃ được Mode B (sync.yml, chạy hàng ngày) cào giá đều
    đặn rồi. Kết quả: mỗi cuối tuần price_history bị ghi thêm một dòng TRÙNG LẶP hoàn toàn không cần
    thiết cho toàn bộ catalog cũ, tốn cả thời gian chạy CI (check_stock/goto từng trang) lẫn dung
    lượng bảng price_history.

    Dùng tập SKU này ở Mode A để CHỈ ghi price_history cho SKU MỚI phát hiện (chưa từng có source ở
    competitor này) — sku cũ chỉ cần refresh URL (qua upsert_sources), giá của nó daily sync đã lo.

    Không phân biệt active/inactive: một source từng bị tắt (is_manual_url hoặc hàng cũ/demo) vẫn
    tính là "đã biết", để Mode A không cào giá lại cho nó chỉ vì nó đang bị tắt tạm thời.
    """
    skus: set[str] = set()
    page = 0
    size = 1000
    while True:
        rows = (
            client.table("sources")
            .select("product_sku")
            .eq("competitor", competitor)
            .range(page * size, page * size + size - 1)
            .execute()
            .data
            or []
        )
        skus.update(r["product_sku"] for r in rows)
        if len(rows) < size:
            break
        page += 1
    return skus


def fetch_active_sources(
    client: Client, competitor: str | None = None, category: str | None = None
) -> list[dict]:
    """Trả về các source đang active kèm join với sản phẩm tương ứng, để biết cần scrape gì.

    Một source được nhận diện bởi (product_sku, competitor); `products` được join vào để lấy
    tên hiển thị.

    Truyền `competitor` để chỉ lấy source của MỘT cửa hàng — dùng khi chạy job song song theo
    từng competitor (xem .github/workflows/sync.yml, mỗi job matrix chỉ lo một shop). Bỏ trống
    (None) sẽ lấy toàn bộ source active như trước (mọi competitor).

    Truyền `category` để chỉ lấy source của các SKU thuộc MỘT danh mục (vd "Monitor", "Mainboard").
    Dùng khi muốn cào lại giá cho riêng một danh mục thay vì toàn bộ catalog. Bỏ trống (None) sẽ
    lấy mọi danh mục như hành vi cũ.
    """
    # PostgREST/Supabase giới hạn một response ở 1.000 dòng. Không phân trang ở
    # đây khiến job Sync tưởng chỉ có 1.000 source dù database có hàng nghìn.
    all_sources: list[dict] = []
    page = 0
    size = 1_000

    # products!inner ép JOIN kiểu inner để PostgREST cho phép lọc theo cột category của bảng
    # products qua embed filter (.eq("products.category", ...)). Chỉ đổi sang !inner khi CÓ lọc
    # category — giữ nguyên select cũ (products, không !inner) khi không lọc, để không đổi hành
    # vi hiện tại của các lệnh gọi cũ (vd .github/workflows/sync.yml không truyền category).
    select_cols = (
        "product_sku, competitor, url, products!inner(sku, name, category)"
        if category
        else "product_sku, competitor, url, products(sku, name)"
    )

    while True:
        q = (
            client.table("sources")
            .select(select_cols)
            .eq("active", True)
        )
        if competitor:
            q = q.eq("competitor", competitor)
        if category:
            q = q.eq("products.category", category)
        rows = (
            q.order("competitor")
            .order("product_sku")
            .range(page * size, page * size + size - 1)
            .execute()
            .data
            or []
        )
        all_sources.extend(rows)
        if len(rows) < size:
            break
        page += 1

    return all_sources


def deactivate_source(client: Client, product_sku: str, competitor: str) -> None:
    """Tắt source khi URL trỏ tới hàng cũ/demo, nhưng giữ lịch sử để audit."""
    client.table("sources").update({"active": False}).match(
        {"product_sku": product_sku, "competitor": competitor}
    ).execute()


def update_source_used(client: Client, product_sku: str, competitor: str, is_used: bool = True) -> None:
    """Cập nhật trạng thái hàng cũ/demo cho source."""
    client.table("sources").update({"is_used": is_used}).match(
        {"product_sku": product_sku, "competitor": competitor}
    ).execute()


def deactivate_all_sources(client: Client, product_sku: str) -> None:
    """Tắt tất cả sources của SKU này (ví dụ khi TNC ngừng kinh doanh sản phẩm)."""
    client.table("sources").update({"active": False}).eq("product_sku", product_sku).execute()


def ensure_competitor(client: Client, name: str, is_self: bool = False) -> None:
    """Đăng ký một competitor vào registry nếu chưa tồn tại.

    Các scraper gọi hàm này một lần khi khởi động để cửa hàng xuất hiện trong `competitors`
    ngay cả khi nó không khớp với laptop nào của ta (ví dụ GearVN/Memoryzone) — nhờ đó dashboard
    có thể LEFT JOIN và luôn hiển thị đầy đủ các cửa hàng. Cũng là bước bắt buộc trước khi insert
    bất kỳ source nào (ràng buộc khóa ngoại).
    """
    client.table("competitors").upsert(
        {"name": name, "is_self": is_self}, on_conflict="name", ignore_duplicates=True
    ).execute()


def insert_price(
    client: Client, product_sku: str, competitor: str, price: int, in_stock: bool = True, is_used: bool = False
) -> None:
    """Thêm một bản ghi giá vào price_history, khóa theo (product_sku, competitor).

    in_stock: False khi competitor niêm yết giá nhưng thực tế không còn hàng model đó
    ("Hàng sắp về" / "Liên hệ" / showroom hết hàng). Dashboard sẽ đánh dấu các trường hợp này.
    """
    client.table("price_history").insert(
        {
            "product_sku": product_sku,
            "competitor": competitor,
            "price": price,
            "currency": "VND",
            "in_stock": in_stock,
            "is_used": is_used,
        }
    ).execute()


# ── Ghi theo lô (batch) ──────────────────────────────────────────────────────────────────────
# Mỗi scraper khớp hàng chục sản phẩm. Ghi từng cái một tốn N lượt round-trip HTTP tới Supabase;
# gom thành một lời gọi cho mỗi bảng nhanh hơn nhiều và tránh ghi dở dang khi mạng chập chờn.
# Các hàm dưới bỏ qua danh sách rỗng (không gọi mạng khi không có gì để ghi).


def _dedupe(rows: list[dict], key) -> list[dict]:
    """Giữ lại bản ghi CUỐI CÙNG cho mỗi khóa trùng (khớp hành vi 'upsert sau ghi đè' của vòng lặp
    cũ). Cần thiết vì một lời upsert theo lô với khóa xung đột trùng sẽ bị Postgres từ chối
    ("ON CONFLICT ... cannot affect row a second time")."""
    out: dict = {}
    for r in rows:
        out[key(r)] = r
    return list(out.values())


def upsert_products(client: Client, rows: list[dict]) -> None:
    """Upsert nhiều sản phẩm (TNC's catalog) trong một lời gọi, khóa theo sku."""
    rows = _dedupe(rows, lambda r: r["sku"])
    if rows:
        client.table("products").upsert(rows, on_conflict="sku").execute()


def upsert_sources(client: Client, rows: list[dict]) -> None:
    """Upsert nhiều source trong một lời gọi, khóa theo (product_sku, competitor).
    KHÔNG ghi đè URL nếu source đó đã được sửa tay (is_manual_url = True).
    """
    rows = _dedupe(rows, lambda r: (r["product_sku"], r["competitor"]))
    if not rows:
        return
        
    try:
        # Lấy danh sách các sources đã được cấu hình thủ công
        manual_res = client.table("sources").select("product_sku, competitor").eq("is_manual_url", True).execute()
        manual_keys = {(s["product_sku"], s["competitor"]) for s in (manual_res.data or [])}
    except Exception as e:
        print(f"Warning: Không thể kiểm tra các sources sửa thủ công: {e}. Tiến hành ghi đè bình thường.")
        manual_keys = set()
        
    # Lọc bỏ các sources đã sửa thủ công khỏi danh sách upsert để tránh ghi đè URL
    to_upsert = [r for r in rows if (r["product_sku"], r["competitor"]) not in manual_keys]
    
    if to_upsert:
        # Đảm bảo mỗi row có is_used — cột NOT NULL, default False
        for r in to_upsert:
            r.setdefault("is_used", False)
        client.table("sources").upsert(to_upsert, on_conflict="product_sku,competitor").execute()


def insert_prices(client: Client, rows: list[dict]) -> None:
    """Thêm nhiều bản ghi giá vào price_history trong một lời gọi. Mỗi row cần có
    product_sku, competitor, price, in_stock; currency mặc định 'VND' được thêm ở đây."""
    if rows:
        client.table("price_history").insert(
            [{"currency": "VND", "is_used": r.get("is_used", False), **r} for r in rows]
        ).execute()


# ── Sản phẩm đối thủ mà catalog TNC (`products`) CHƯA CÓ ────────────────────────────────────────
# Bảng `missing_products` (xem scraper/missing_products.sql) độc lập với sources/price_history —
# KHÔNG có product_sku thật để tham chiếu (đó chính là lý do bảng này tồn tại: sản phẩm chưa từng
# được TNC bán nên chưa có SKU nào cho nó). Khóa theo (competitor, url) để mỗi lần cào lại CÙNG một
# sản phẩm chỉ cập nhật last_seen_at/giá, không tạo dòng trùng.


def upsert_missing_products(client: Client, rows: list[dict]) -> None:
    """Upsert nhiều dòng vào `missing_products` — sản phẩm của một competitor mà catalog TNC chưa
    có (xem discover_anphat.py). Mỗi row cần có competitor, category, name; brand/price/url/is_used/
    reason là tùy chọn.

    CHỈ gửi các cột nên được CẬP NHẬT mỗi lần thấy lại (price/name/category/brand/is_used/reason/
    last_seen_at) — KHÔNG gửi first_seen_at/resolved/resolved_at. PostgREST upsert chỉ áp DEFAULT
    cho các cột vắng mặt lúc INSERT LẦN ĐẦU; khi gặp xung đột (đã có dòng), các cột không được gửi
    giữ nguyên giá trị cũ — nhờ vậy first_seen_at không bị ghi đè và một dòng đã resolved=true
    không bị vô tình mở lại chỉ vì item xuất hiện lại trong một lượt cào khác.
    """
    if not rows:
        return
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = []
    for r in rows:
        payload.append({
            "competitor": r["competitor"],
            "category": r["category"],
            "brand": r.get("brand") or None,
            "name": r["name"],
            "price": r.get("price"),
            "url": r.get("url") or "",
            "is_used": bool(r.get("is_used", False)),
            "reason": r.get("reason") or "",
            "last_seen_at": now_iso,
        })
    payload = _dedupe(payload, lambda r: (r["competitor"], r["url"]))
    client.table("missing_products").upsert(payload, on_conflict="competitor,url").execute()


def resolve_missing_products(client: Client, competitor: str, urls: list[str]) -> None:
    """Đánh dấu các dòng `missing_products` của `competitor` khớp `urls` là ĐÃ GIẢI QUYẾT
    (resolved=true, resolved_at=now()) — gọi khi một item TRƯỚC ĐÂY không khớp catalog TNC nay
    ĐÃ khớp (TNC vừa bổ sung đúng sản phẩm đó). KHÔNG xóa dòng — giữ lại lịch sử "đã từng thiếu".
    Chỉ update các dòng đang resolved=false (tránh ghi đè resolved_at nếu đã resolved từ trước).
    """
    urls = [u for u in urls if u]
    if not urls:
        return
    now_iso = datetime.now(timezone.utc).isoformat()
    CHUNK = 200
    for i in range(0, len(urls), CHUNK):
        chunk = urls[i : i + CHUNK]
        client.table("missing_products").update(
            {"resolved": True, "resolved_at": now_iso}
        ).eq("competitor", competitor).eq("resolved", False).in_("url", chunk).execute()


def fetch_all_sources(
    client: Client, competitor: str | None = None, category: str | None = None
) -> list[dict]:
    """Giống fetch_active_sources nhưng lấy CẢ nguồn active LẪN inactive — dùng cho
    audit_category.py: tính lại SKU, cào lại giá, xác minh ngừng kinh doanh, bất kể source đang
    bật/tắt. Trả về thêm cột `active`/`is_manual_url`/`is_used` và `products.name`/`brand` (để
    so độ khớp với TNC) trong mỗi row.
    """
    all_sources: list[dict] = []
    page = 0
    size = 1_000

    select_cols = (
        "product_sku, competitor, url, active, is_manual_url, is_used, "
        "products!inner(sku, name, brand, category)"
        if category
        else "product_sku, competitor, url, active, is_manual_url, is_used, products(sku, name, brand)"
    )

    while True:
        q = client.table("sources").select(select_cols)
        if competitor:
            q = q.eq("competitor", competitor)
        if category:
            q = q.eq("products.category", category)
        rows = (
            q.order("competitor")
            .order("product_sku")
            .range(page * size, page * size + size - 1)
            .execute()
            .data
            or []
        )
        all_sources.extend(rows)
        if len(rows) < size:
            break
        page += 1

    return all_sources


def set_source_active(client: Client, product_sku: str, competitor: str, active: bool) -> None:
    """Bật/tắt một source cụ thể. Dùng khi audit phát hiện source ĐANG TẮT nhưng thực ra vẫn còn
    bán (nên bật lại — audit_category.py gọi khi vậy), hoặc muốn tắt tay mà không đi qua
    deactivate_source (vốn chỉ tắt, không bật lại được)."""
    client.table("sources").update({"active": active}).match(
        {"product_sku": product_sku, "competitor": competitor}
    ).execute()


def fetch_latest_prices(
    client: Client, skus: list[str], competitor: str | None = None
) -> dict[tuple[str, str], dict]:
    """Giá GẦN NHẤT của mỗi (product_sku, competitor) trong một tập SKU. Dùng cho các báo cáo
    chỉ-đọc như find_anomalies.py — không mở trang cào lại, chỉ đọc dữ liệu đã có trong DB.

    Đọc từ `latest_prices_cache` trước (đã tính sẵn, nhanh) — GIẢ ĐỊNH nó có cùng hình dạng cột
    với price_history (product_sku, competitor, price, in_stock, is_used), vì đó là ảnh chụp mới
    nhất của chính bảng đó (xem refresh_views.py). NẾU schema thật khác (ví dụ tên cột khác), sửa
    lại câu select() trong _from_cache() bên dưới cho khớp — hiện tại nó tự rơi xuống price_history
    khi cache lỗi, nên vẫn chạy đúng dù chậm hơn.

    Nếu đọc cache lỗi (bảng không tồn tại / cột sai tên), tự rơi xuống quét `price_history` sắp
    theo scraped_at giảm dần và giữ bản ĐẦU TIÊN gặp cho mỗi (sku, competitor) — chậm hơn nhưng
    luôn đúng vì đọc thẳng từ nguồn.

    Trả về {(product_sku, competitor): {"price", "in_stock", "is_used", ...}}.
    """
    skus = list(skus)
    if not skus:
        return {}
    CHUNK = 200  # tránh URL quá dài với .in_() khi category có nhiều SKU

    def _from_cache() -> dict[tuple[str, str], dict]:
        res: dict[tuple[str, str], dict] = {}
        for i in range(0, len(skus), CHUNK):
            chunk = skus[i : i + CHUNK]
            q = (
                client.table("latest_prices_cache")
                .select("product_sku, competitor, price, in_stock, is_used")
                .in_("product_sku", chunk)
            )
            if competitor:
                q = q.eq("competitor", competitor)
            for r in q.execute().data or []:
                res[(r["product_sku"], r["competitor"])] = r
        return res

    try:
        return _from_cache()
    except Exception as e:
        print(
            f"  ⚠️  Không đọc được latest_prices_cache ({e}) — rơi xuống price_history "
            f"(chậm hơn, tự dedupe theo scraped_at)."
        )

    out: dict[tuple[str, str], dict] = {}
    for i in range(0, len(skus), CHUNK):
        chunk = skus[i : i + CHUNK]
        q = (
            client.table("price_history")
            .select("product_sku, competitor, price, in_stock, is_used, scraped_at")
            .in_("product_sku", chunk)
            .order("scraped_at", desc=True)
        )
        if competitor:
            q = q.eq("competitor", competitor)
        for r in q.execute().data or []:
            key = (r["product_sku"], r["competitor"])
            if key not in out:  # đã sắp giảm dần -> bản gặp đầu tiên là MỚI NHẤT
                out[key] = r
    return out