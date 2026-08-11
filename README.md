# PC Pricing Dashboard

Dashboard giá cạnh tranh nội bộ dành cho **Thành Nhân Computer (TNC).**

Hệ thống thu thập giá laptop từ các website đối thủ mỗi sáng và trình bày trong một nơi duy nhất, để
ban lãnh đạo có thể nhìn thấy vị thế của TNC so với thị trường chỉ trong một cái nhìn — và phát hiện
các sản phẩm đang định giá cao hơn đối thủ — mà không cần duy trì file Excel thủ công.

> **Trạng thái:** Đang hoạt động. **8 đối thủ × 7 thương hiệu** được thu thập hàng ngày vào Supabase;
> dashboard so sánh giá của TNC với thị trường (chỉ tính đối thủ), đánh dấu các sản phẩm hết hàng, và
> làm nổi bật các sản phẩm đang định giá cao hơn thị trường.
>
> **Công nghệ:** Python + Playwright (thu thập dữ liệu) · Supabase / Postgres (dữ liệu + SQL views) ·
> React + Vite + Tremor (dashboard, trên GitHub Pages) · GitHub Actions (cron hàng ngày + deploy).

---

## Chức năng

- **Thu thập tự động hàng ngày** — mỗi đối thủ được thu thập dữ liệu mỗi sáng (05:40 giờ VN) trước
  giờ làm việc, để giá luôn mới nhất trước 07:00.
- **Bảy thương hiệu** — Dell, Lenovo, HP, Apple, Asus, Acer, MSI. Chọn một thương hiệu trên dashboard
  để xem chi tiết các sản phẩm của thương hiệu đó.
- **So sánh theo từng sản phẩm** — giá hiện tại của mọi đối thủ được đặt cạnh nhau, rẻ nhất lên đầu,
  kèm cửa hàng có giá thấp nhất và % chênh lệch của TNC so với giá trung bình thị trường.
- **Đánh dấu hết hàng** — các sản phẩm của đối thủ đã hết hàng được đánh dấu và loại khỏi thống kê
  thị trường (giá OOS đã cũ không phải là giá thực).
- **"Định giá cao hơn thị trường"** — danh sách trên trang chủ liệt kê các sản phẩm mà TNC đang định
  giá cao hơn mức trung bình của đối thủ nhiều nhất, để các quyết định về giá bắt đầu từ nơi quan
  trọng nhất.

---

## Cách hoạt động

```
 Competitor listing pages ──▶ Headless scraper ──▶ Supabase ──▶ SQL views ──▶ Dashboard
   (JS-rendered)                (Playwright)         (history)    (compare)     (React)
```

1. Một **job GitHub Actions chạy hàng ngày** lặp qua từng thương hiệu được theo dõi. Với mỗi thương
   hiệu, scraper của TNC chạy trước (định nghĩa danh mục sản phẩm của chúng ta), sau đó mỗi scraper
   đối thủ tải trang danh sách thương hiệu đó của website tương ứng trong trình duyệt headless, để
   JS render xong, rồi đọc giá hiện tại của từng laptop.
2. Mỗi laptop được khớp với một **SKU chuẩn hoá (canonical SKU)**. Các scraper đối thủ chỉ **ghi
   nhận khi khớp (match-only)**: giá chỉ được lưu lại cho SKU đã có sẵn trong danh mục của TNC. Mỗi
   lần quan sát đều được thêm vào `price_history` kèm dấu thời gian, nên lịch sử giá được tích luỹ
   dần.
3. Các **view** của Postgres thực hiện toàn bộ công việc so sánh (giá mới nhất theo từng cửa hàng,
   pivot, thống kê thị trường, cửa hàng rẻ nhất, % so với thị trường, độ phủ theo từng thương hiệu,
   "cần chú ý"). Dashboard chỉ đọc các dòng dữ liệu đã hoàn chỉnh và hiển thị — không có tổng hợp dữ
   liệu phía client.

---

## Đối thủ & thương hiệu

**8 đối thủ:** An Phát PC · Thế Giới Di Động · Phong Vũ · FPT Shop · CellphoneS · Hà Nội Computer
(HACOM) · Memoryzone · GearVN. Bản thân TNC cũng được thu thập theo cách tương tự, được đánh dấu
`is_self` làm cơ sở đối chiếu.

**7 thương hiệu** cho mỗi đối thủ, mỗi thương hiệu có URL trang danh sách riêng trong map `BRANDS`
của scraper. Độ phủ khác nhau tuỳ nơi — các cửa hàng có danh mục lớn (An Phát, TGDĐ, FPT, Phong Vũ)
khớp được nhiều nhất; HACOM và các cửa hàng có danh mục mỏng khớp được ít hoặc không khớp, điều này
là bình thường.

---

## Kiến trúc

| Thành phần | Nhiệm vụ | Công nghệ |
| --- | --- | --- |
| **Scrapers** | Khám phá & phân tích giá; một `discover_*.py` cho mỗi đối thủ + TNC | Python + Playwright (Chromium headless) |
| **Kho dữ liệu** | Sản phẩm (khoá theo SKU), danh bạ đối thủ, lịch sử giá chỉ-thêm (append-only), các view so sánh | Supabase / Postgres |
| **Dashboard** | Thông tin tổng quan trang chủ + xem chi tiết theo thương hiệu | React + Vite + Tremor, trên GitHub Pages |
| **Bộ lập lịch** | Thu thập dữ liệu hàng ngày + deploy dashboard | GitHub Actions (`scrape.yml`, `deploy.yml`) |

**Vì sao chọn bộ công nghệ này**

- **Supabase / Postgres** — SQL tính toán thống kê giá và lịch sử theo chuỗi thời gian một cách tự
  nhiên, đồng thời cung cấp sẵn API đọc + RLS để dashboard công khai có thể đọc dữ liệu an toàn.
- **Python + Playwright** — mọi đối thủ đều render giá bằng JavaScript; HTML thô không chứa giá. Cần
  một trình duyệt headless, và Python là lựa chọn tự nhiên cho bộ thu thập dữ liệu.
- **React + Tremor trên GitHub Pages** — một công cụ nội bộ, ưu tiên desktop, dạng bảng và biểu đồ.
  Một web app tĩnh có thể chia sẻ ngay lập tức qua URL, và Tremor được thiết kế chuyên biệt cho
  dashboard.

---

## So khớp SKU — phần cốt lõi

Việc so sánh giữa các cửa hàng chỉ hoạt động đúng nếu *cùng một* laptop cho ra *cùng một* khoá ở mọi
nơi, và các laptop *khác nhau* không bao giờ trùng khoá. Toàn bộ logic nằm trong
[`scraper/scraper/sku.py`](scraper/scraper/sku.py); `derive_sku(name, url)` phân luồng theo thương
hiệu:

| Thương hiệu | Định danh | Ví dụ |
| --- | --- | --- |
| Dell | mã 8 chữ số → series+mã → dòng+số | `DC15250-CPH99` |
| Lenovo | mã sản phẩm gốc (đi qua nguyên vẹn) | `21NS010HVN` |
| Apple | khoá tổng hợp thông số kỹ thuật (không có mã sản phẩm) | `APPLE-PRO-14-M5-16-1TB` |
| HP | mã bộ phận (part code, không phải số dòng model dùng chung) | `AM9H1PT` |
| Asus / Acer / MSI | mã model: series + phần kết thúc cấu hình | `X1504VA-BQ185W`, `NH.QZ9SV.004` |

Toàn bộ lý do chi tiết theo từng thương hiệu và các trường hợp đặc biệt nằm trong
[`docs/sku-matching.md`](docs/sku-matching.md).

---

## Các quyết định thiết kế

Những lựa chọn không hiển nhiên, được ghi lại ở đây để không phải tranh luận lại.

### Thu thập dữ liệu (Scraping)

- **Trình duyệt headless, không phải HTTP thuần.** Mọi đối thủ đều render kết quả bằng JavaScript —
  HTML thô chỉ có *khung mẫu* giá, không có giá thật. Chúng ta điều khiển Chromium headless và đọc
  DOM đã render.
- **Khám phá qua trang danh sách, không lưu sẵn URL theo từng model.** Mỗi scraper tải một URL danh
  sách theo thương hiệu và tự khám phá lại từng laptop mỗi lần chạy — không có danh sách URL thủ
  công nào bị lỗi thời khi slug thay đổi. Bảng `sources` vẫn ghi lại URL đã khám phá được để tham
  chiếu.
- **So khớp theo SKU, không bao giờ theo tên.** Tên gọi ("Dell 15") bao gồm nhiều cấu hình có giá
  chênh lệch nhau hàng triệu đồng. SKU được suy ra chính là định danh.
- **Giá hiện tại, không phải giá gạch ngang.** Các adapter nhắm vào phần tử giá hiện tại, tránh giá
  gốc bị gạch ngang.
- **Các đặc thù riêng của từng site là điều bình thường** — một module cho mỗi đối thủ. Ví dụ: HACOM
  cần viewport desktop đầy đủ + cuộn để tải thêm; An Phát không bao giờ đạt trạng thái network-idle;
  TGDĐ/CellphoneS/An Phát ẩn phần lớn sản phẩm sau nút "Xem thêm" (load-more).
- **Một số site chặn IP ngoài Việt Nam theo vị trí địa lý.** FPT Shop, Phong Vũ, và TGDĐ trả về lỗi
  403 cho IP không phải Việt Nam (bao gồm cả CI đặt tại Mỹ), nên các scraper đó định tuyến qua một
  **proxy dân dụng (residential) tại Việt Nam** ([`browser.py`](scraper/scraper/browser.py),
  `use_proxy=True`, cấu hình qua `PROXY_*` trong `.env`). Với proxy tính phí theo dung lượng, chúng
  ta chặn hình ảnh/font/CSS để tiết kiệm băng thông.

### Mô hình dữ liệu

- **Danh mục của TNC quyết định những gì chúng ta theo dõi.** Các scraper đối thủ chỉ ghi nhận khi
  khớp (match-only) — chúng ta chỉ quan tâm thị trường định giá các laptop *chúng ta* đang bán như
  thế nào.
- **TNC cũng chỉ là một nguồn được scrape, được đánh dấu `is_self`.** Thống kê thị trường loại trừ
  `is_self`; dashboard so sánh giá của chúng ta với thị trường đó (chỉ gồm đối thủ).
- **Hàng hết hàng bị loại khỏi thống kê thị trường.** Một giá của đối thủ đang hết hàng thường đã cũ
  (các cửa hàng thường ngừng cập nhật những gì họ không bán được), nên `price_stats` chỉ tính các giá
  `in_stock` của đối thủ.
- **`latest_prices` chọn một giá hiện tại cho mỗi cặp (model, cửa hàng)** thông qua `DISTINCT ON`
  trên `price_history` dạng chỉ-thêm (append-only), nên mọi view phía sau đều so sánh các giá mới
  nhất, tương ứng nhau.
- **SQL đảm nhận phần việc nặng; dashboard chỉ hiển thị.** Pivot, thống kê, cửa hàng rẻ nhất, % so
  với thị trường, độ phủ theo thương hiệu, và danh sách "cần chú ý" đều là các view của Postgres.

> **Giới hạn đã biết — trùng lặp một phần.** So khớp SKU nghiêm ngặt chỉ so sánh các laptop mà cả
> TNC và một đối thủ cùng có hàng. Các nhà bán lẻ đặt hàng các cấu hình khác nhau, nên độ trùng lặp
> chính xác vốn dĩ bị giới hạn. So khớp theo dòng sản phẩm/thông số kỹ thuật sẽ mở rộng phạm vi này
> nhưng lại so sánh các máy hơi khác nhau — việc này cố tình không được thực hiện.

---

## Cấu trúc dự án

```
PC-Pricing-Dashboard/
├── scraper/            # Python collector — brand.py, sku.py, browser.py, discover_*.py per site
├── dashboard/          # React + Vite + Tremor app (landing + /brand/:name routes)
├── supabase/           # SQL schema + views (products, sources, price_history, comparison views)
├── docs/sku-matching.md
└── .github/workflows/  # scrape.yml (daily cron), deploy.yml (Pages)
```

## Bắt đầu

```bash
git clone <repo-url>
cd PC-Pricing-Dashboard

# Scraper (Python)
cd scraper
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
# Set SUPABASE_URL, SUPABASE_KEY (service_role), and PROXY_* in scraper/.env, then:
python -m scraper.discover_tnc --brand dell          # scrape one brand from our catalog
python -m scraper.discover_anphat --brand dell --dry # dry-run a competitor (no DB write)

# Dashboard (React)
cd ../dashboard
npm install
# Set VITE_SUPABASE_URL + VITE_SUPABASE_ANON_KEY (anon, NOT service_role) in dashboard/.env
npm run dev
```

Mỗi scraper nhận tham số `--brand {dell,lenovo,apple,hp,asus,acer,msi}` (mặc định `dell`) và
`--dry`. Workflow chạy hàng ngày sẽ lặp qua tất cả các thương hiệu được theo dõi.

**Bí mật (Secrets):** `.env` bị git bỏ qua (git-ignored) và không bao giờ được commit. Scraper sử
dụng khoá **service_role** của Supabase (bỏ qua RLS, dùng để ghi) + thông tin xác thực proxy;
dashboard chỉ sử dụng khoá **anon/publishable** (chỉ đọc, tuân theo RLS). Không bao giờ đặt khoá
service_role trong dashboard.

## Triển khai (Deployment)

- **Thu thập dữ liệu:** `.github/workflows/scrape.yml` chạy hàng ngày lúc 05:40 giờ VN (22:40 UTC),
  lệch khỏi đầu giờ để tránh độ trễ lập lịch của GitHub. Các secret (`SUPABASE_*`, `PROXY_*`) nằm
  trong Actions.
- **Dashboard:** `.github/workflows/deploy.yml` build và publish lên GitHub Pages.

## Lộ trình (Roadmap)

- [x] Schema Supabase: sản phẩm khoá theo SKU, lịch sử chỉ-thêm (append-only), các view so sánh + RLS
- [x] Scraper Playwright cho toàn bộ 8 đối thủ + danh mục TNC
- [x] Đa thương hiệu: Dell, Lenovo, HP, Apple, Asus, Acer, MSI với so khớp SKU theo từng thương hiệu
- [x] Đánh dấu hết hàng (loại khỏi thống kê thị trường)
- [x] Thu thập dữ liệu theo lịch hàng ngày (GitHub Actions)
- [x] Dashboard: thông tin tổng quan trang chủ, xem chi tiết theo thương hiệu, "định giá cao hơn thị trường"
- [x] Deploy dashboard lên GitHub Pages


</content>
