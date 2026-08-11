"""Các hàm hỗ trợ Supabase client cho scraper."""

from __future__ import annotations

import os

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


def fetch_active_sources(client: Client) -> list[dict]:
    """Trả về các source đang active kèm join với sản phẩm tương ứng, để biết cần scrape gì.

    Một source được nhận diện bởi (product_sku, competitor); `products` được join vào để lấy
    tên hiển thị.
    """
    resp = (
        client.table("sources")
        .select("product_sku, competitor, url, products(sku, name)")
        .eq("active", True)
        .execute()
    )
    return resp.data or []


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
    client: Client, product_sku: str, competitor: str, price: int, in_stock: bool = True
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
    """Upsert nhiều source trong một lời gọi, khóa theo (product_sku, competitor)."""
    rows = _dedupe(rows, lambda r: (r["product_sku"], r["competitor"]))
    if rows:
        client.table("sources").upsert(rows, on_conflict="product_sku,competitor").execute()


def insert_prices(client: Client, rows: list[dict]) -> None:
    """Thêm nhiều bản ghi giá vào price_history trong một lời gọi. Mỗi row cần có
    product_sku, competitor, price, in_stock; currency mặc định 'VND' được thêm ở đây."""
    if rows:
        client.table("price_history").insert(
            [{"currency": "VND", **r} for r in rows]
        ).execute()
