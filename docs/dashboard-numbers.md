# Ý nghĩa các con số trên Dashboard

Tài liệu này giải thích **mỗi con số trên giao diện được tính từ đâu**, để người xem hiểu đúng —
đặc biệt là vì sao "Sản phẩm" (ví dụ 478) có thể KHÁC với mẫu số ở phần "Độ phủ đối thủ" (ví dụ
1182). Chúng đến từ hai phép lọc khác nhau, nên đại diện cho hai tập sản phẩm khác nhau.

## Nền tảng: 3 khái niệm

Mọi con số bắt nguồn từ view `latest_prices` — **kết quả lần scrape GẦN NHẤT**, mỗi dòng là một
cặp (sản phẩm × cửa hàng) kèm giá và trạng thái `in_stock`.

Từ đó tách thành 2 nhánh, lọc KHÁC nhau:

| Khái niệm | View | Bộ lọc | Trả lời câu hỏi |
|---|---|---|---|
| **Ta theo dõi** | `competitor_coverage` (dòng của TA) | không lọc — đếm mọi sản phẩm | "Ta đang theo dõi bao nhiêu sản phẩm?" |
| **So sánh được** | `product_overview` | **CHỈ khi TA còn hàng** (`we_in_stock`) | "Bao nhiêu sản phẩm có thể so giá?" |
| **Đối thủ khớp** | `competitor_coverage` (dòng đối thủ) | không lọc | "Đối thủ này có giá cho bao nhiêu sản phẩm?" |

Điểm mấu chốt: **"So sánh được" chỉ tính sản phẩm TA CÒN HÀNG**, vì không thể so "giá của ta vs thị
trường" khi ta ghi "Liên hệ" (hết hàng). "Ta theo dõi" thì tính TẤT CẢ.

---

## Từng con số trên giao diện

### Trang danh mục (CategoryView)

**"Sản phẩm" (ví dụ 478)**
→ Số sản phẩm trong danh mục mà **TA đang CÒN HÀNG** (có giá thật để so sánh).
→ Nguồn: `product_overview` (đã lọc `we_in_stock`).
→ Đây KHÔNG phải tổng số sản phẩm ta theo dõi — sản phẩm ta "Liên hệ"/hết hàng bị loại khỏi số này.

**"Trung bình so với thị trường" (ví dụ −2.4%)**
→ Trung bình `pct_vs_mean` trên các sản phẩm CÓ đối thủ. Âm = ta rẻ hơn trung bình đối thủ (tốt).
→ Chỉ tính sản phẩm có ít nhất một đối thủ; sản phẩm không có đối thủ bị bỏ qua.

**"Cao hơn thị trường" (ví dụ 7)**
→ Số sản phẩm mà giá của ta cao hơn trung bình đối thủ **trên 5%** (cần chú ý về giá).

**Phần "Độ phủ của đối thủ" — ví dụ "An Phát PC: 196 / 478 (41%)"**
- **Mẫu số** = **"Sản phẩm (còn hàng)"** = `stats.count` (số sản phẩm TA còn hàng, so sánh được).
- **Tử số** = trong số sản phẩm SO SÁNH ĐƯỢC đó, có bao nhiêu cái đối thủ này CÓ giá. Tính trực
  tiếp từ `prices_by_store` của các dòng đang hiện trên trang (KHÔNG dùng `competitor_coverage`).
- **%** = tử/mẫu → "đối thủ có giá cho 41% số sản phẩm ta có thể so".

> ⚠️ Vì sao KHÔNG dùng `competitor_coverage` (đếm trên `latest_prices`)? Vì nó đếm mọi SKU đối thủ
> khớp trong catalog — KỂ CẢ sản phẩm ta đang hết hàng. Ví dụ Server: ta còn hàng 2 sản phẩm, nhưng
> `competitor_coverage` báo An Phát khớp 13 — mà 13 đó KHÔNG trùng 2 sản phẩm đang hiện (overlap=0).
> Hiện "13" bên cạnh bảng chỉ có 2 dòng gây hiểu nhầm. Nay tử số chỉ đếm phần **so sánh được thật**,
> nên Server hiện An Phát 0/2 (đúng: không đối thủ nào có 2 server ta đang còn hàng).

### Trang chủ (Dashboard)

**"Sản phẩm theo dõi"** → tổng số dòng `product_overview` (đã phân trang qua 1000-row cap của
PostgREST) trên các danh mục ĐANG BẬT. Đây là số sản phẩm **còn hàng, so sánh được** — không phải
toàn bộ catalog.

**Thẻ mỗi danh mục** → count / avg-vs-market / số cao-hơn-5% / số OOS-gap, tất cả tính trên phần
còn hàng của danh mục đó.

---

## Ba con số dễ nhầm (ví dụ danh mục Server, Dell)

| Con số | Giá trị | Nguồn | Nghĩa |
|---|---|---|---|
| Catalog | 58 | bảng `products` | Tất cả server Dell trong danh mục |
| **Ta theo dõi** (mẫu số độ phủ) | 58 | `competitor_coverage` (dòng TA) | Server ta theo dõi (cả hàng hết) |
| **Sản phẩm** (hiện trên bảng) | 2 | `product_overview` | Server **TA CÒN HÀNG** → so giá được |
| **Đối thủ khớp** (tử số) | 13 | `competitor_coverage` (dòng An Phát) | Server An Phát có giá |

→ Bảng chỉ hiện **2** vì 56 server còn lại TA ghi "Liên hệ" (không có giá để so). Đây là hàng bán
theo báo giá — bình thường với server/workstation doanh nghiệp.

---

## Tóm tắt một câu

- **"Sản phẩm" = ta còn hàng, so sánh được.**
- **Mẫu số "Độ phủ" = tổng ta theo dõi (cả hàng hết).**
- Hai số khác nhau là ĐÚNG khi ta hết hàng nhiều; % độ phủ luôn ≤100% vì tử và mẫu cùng đo trên
  tập "ta theo dõi".


New Feature, 
use the price history table in database to analize the freq of price adjustion across 8 competitors. visualize this to see which competitor most freq adjust their price and how fast are we reacting. 
