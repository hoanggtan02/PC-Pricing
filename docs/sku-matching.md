# So khớp SKU

Cách hệ thống quyết định câu hỏi **"hai listing này có phải cùng một sản phẩm không?"** — phần cốt
lõi của việc so sánh giá giữa các cửa hàng, hoạt động theo **từng danh mục** (laptop, màn hình, …).

Cùng một sản phẩm xuất hiện trên mỗi cửa hàng với một **định dạng URL/tên khác nhau**, và *hình
dạng* của một định danh dùng được lại khác nhau tuỳ thương hiệu và danh mục. Hai listing phải quy
về **một khoá (SKU)** để giá so sánh được; hai sản phẩm *khác nhau* thì **không bao giờ** được gộp
về cùng một khoá. Toàn bộ logic định danh nằm ở [`scraper/scraper/sku.py`](../scraper/scraper/sku.py)
(`derive_sku`); nhận diện thương hiệu ở [`scraper/scraper/brand.py`](../scraper/scraper/brand.py)
(`brand_of`, đọc [`config/brands.yaml`](../scraper/config/brands.yaml)).

---

## Luồng xử lý: scrape theo danh mục → suy ra SKU → so khớp → ghi batch

Mỗi lần chạy scrape hoạt động **cho một danh mục** (được truyền qua `--category`). Với mỗi đối thủ,
luồng là:

1. **Scrape theo danh mục.** Một truy vấn cho cả danh mục (`"màn hình"`), không lặp theo thương
   hiệu — một lượt fetch trả về mọi thương hiệu. URL của mỗi (đối thủ, danh mục) được phân giải từ
   [`config/sources.yaml`](../scraper/config/sources.yaml) qua `resolve_url(competitor, category)`.
   Kết quả được lọc thô bằng regex `name_match` của danh mục (và loại bằng `name_exclude`) để bỏ
   nhiễu tìm kiếm.
2. **Suy ra SKU (`derive_sku(name, url, category)`).** Phân luồng theo danh mục qua bảng
   `_CATEGORY_SKU` trong `sku.py`, dùng chiến lược **3 tầng** (xem phần dưới). Trả về `None` khi
   không trích được định danh đáng tin — **không bao giờ đoán**.
3. **So khớp theo danh mục (chỉ khớp / match-only).** SKU của đối thủ chỉ được ghi nhận **nếu nó đã
   có sẵn** trong danh mục TNC. Tập SKU được TNC lấy **một lần mỗi lần chạy** và giữ trong một
   `set` in-memory; kiểm tra thành viên là O(1), không truy vấn DB cho từng sản phẩm:
   ```python
   tracked = { sku for sku in products where category = <category> }   # một select, một lần
   sku = derive_sku(name, url, category)
   if sku is None or sku not in tracked:
       continue                              # đối thủ bán nhưng ta không theo dõi → bỏ qua
   ```
4. **Ghi theo batch (upsert).** Các sản phẩm khớp được gom lại rồi ghi trong **một lời gọi mỗi
   bảng** (`upsert_products`/`upsert_sources`/`insert_prices`) thay vì ghi từng dòng — ít round-trip
   tới Supabase. (TNC ghi `products`; đối thủ chỉ ghi `sources` + `price_history`.)

**TNC định nghĩa danh mục; đối thủ chỉ khớp.** Vì so khớp là **so sánh chuỗi SKU chính xác tuyệt
đối** (không fuzzy), một khớp sai là không thể xảy ra ở tầng này — đánh đổi có chủ đích: **thà bỏ
lỡ một khớp còn hơn tạo ra một khớp sai** (một khớp bị bỏ lỡ hiển thị "không có đối thủ" — an toàn;
một khớp sai hiển thị giá sai — sai lầm kinh doanh).

---

## Các danh mục đã định nghĩa (config)

Danh mục là **dữ liệu**, không phải code — thêm một danh mục = thêm một khối trong
[`config/sources.yaml`](../scraper/config/sources.yaml) + (nếu cần) một hàm định danh trong
`_CATEGORY_SKU`. Mỗi khối định nghĩa nơi tìm và cách lọc:

| Trường | Ý nghĩa |
| --- | --- |
| `tier` | Mức độ dễ so khớp: **A** = mã model sạch (khớp trực tiếp), **B** = brand+model có "trang trí", **C** = không có mã (chỉ ingest TNC / bảng alias). |
| `search_term` | Truy vấn cho các site có ô tìm kiếm (điền vào `{query}`). |
| `name_match` | Regex tên sản phẩm phải khớp để tính vào danh mục (loại nhiễu tìm kiếm). |
| `name_exclude` | Regex loại BỎ (phụ kiện lọt lưới, ví dụ "giá đỡ màn hình"). |
| `tnc` | URL trang danh mục của TNC (nguồn dẫn dắt danh mục). |
| `paths` | URL riêng cho 3 site không có ô tìm kiếm (Phong Vũ, TGĐĐ, FPT). |

Hiện đã cấu hình:

| Danh mục | Tier | Hàm định danh |
| --- | --- | --- |
| **laptop** | — | `_laptop_sku` (đường dẫn mặc định — 7 thương hiệu, xem dưới) |
| **monitor** (màn hình) | A | `monitor_sku` (`BRAND-MODEL`) |

Các site được chia hai kiểu trong `competitors:`: **site có ô tìm kiếm** (HACOM, CellphoneS, An
Phát, Memoryzone, GearVN — một `search_url` template, dùng lại cho mọi danh mục) và **site có đường
dẫn theo danh mục** (Phong Vũ, TGĐĐ, FPT — cần URL riêng trong `paths`).

---

## So khớp 3 tầng

`derive_sku` trích **định danh** của sản phẩm bằng ba tầng, từ tổng quát đến ngoại lệ. Đa số sản
phẩm được xử lý ở Tầng 1; chỉ số ít cần code riêng theo thương hiệu.

- **Tầng 1 — bộ trích tổng quát (làm phần lớn công việc).** Thương hiệu (`brand_of`) + **token mã
  model** = token trộn chữ+số dài nhất mà KHÔNG phải spec. Không phụ thuộc thứ tự từ (chỉ chọn một
  token, không so sánh cả chuỗi), nên `"Dell SE2426H 24 inch"` và `"gaming Dell 27\" SE2426H"` đều
  ra `DELL-SE2426H`. Hầu hết thương hiệu ở mọi danh mục đi qua tầng này mà không cần code riêng
  (màn hình: 16/17 thương hiệu).
- **Tầng 2 — cấu hình theo danh mục (dữ liệu, không phải code).** Mỗi danh mục khác nhau chỉ ở
  **hình dạng của "spec nhiễu"**: màn hình (`Hz/inch/2K/IPS`), RAM (`DDR5/MHz/CL16`), SSD
  (`TB/NVMe/PCIe`). Đó là một danh sách mẫu nhiễu cho mỗi danh mục, dùng để bóc trước khi chọn mã.
- **Tầng 3 — ngoại lệ theo thương hiệu (chỉ vài trường hợp).** Chỉ dành cho thương hiệu **phá vỡ**
  quy tắc tổng quát: **Apple** (không in mã → khoá tổng hợp thông số), **HP** (mã đứng CUỐI, không
  phải token số đầu tiên), **Asus/Acer/MSI** (mã model nhiều mảnh cần luật riêng). Các chi tiết
  theo từng thương hiệu ở phần "[Quy tắc chi tiết theo từng thương hiệu](#quy-tắc-chi-tiết-theo-từng-thương-hiệu)".
- **Không trích được → `None`.** Sản phẩm không có mã dùng được (một sợi cáp không tên, hoặc cùng
  sản phẩm nhưng hai cửa hàng không dùng chung định danh nào — ví dụ "Office Home 2024" vs mã
  `EP2-06811`) trả về `None` và **không bao giờ được so khớp mờ**. Đây là giới hạn *thông tin*, không
  phải lỗi code: nếu token phân biệt không có trong tên thì không thuật toán nào suy ra được. Các
  trường hợp này cần một bảng **alias do người duyệt** (chưa triển khai) — máy gợi ý, người xác nhận.

---

## Đường dẫn laptop — chi tiết Tầng 3 cho 7 thương hiệu

Laptop là danh mục mặc định (`_laptop_sku`) và cũng là ví dụ đầy đủ nhất về **Tầng 3** (ngoại lệ
theo thương hiệu): mỗi thương hiệu in định danh theo một hình dạng khác nhau. `derive_sku` nhìn
vào **tên** để chọn quy tắc của thương hiệu nào, rồi trích xuất. Thứ tự kiểm tra như sau (quy tắc
riêng chạy trước, vì một quy tắc chung chạy sau có thể lấy nhầm token):

| # | Thương hiệu | Định danh sử dụng | Ví dụ khoá |
| --- | --- | --- | --- |
| 0 | **Apple** | Khoá tổng hợp thông số kỹ thuật (không có mã sản phẩm) | `APPLE-PRO-14-M5-16-1TB` |
| 0.5 | **HP** | Mã bộ phận HP (`6–7 ký tự chữ+số`, xen kẽ chữ cái và số) | `AM9H1PT` |
| 0.6 | **Asus / Acer / MSI** | Mã model (series + cấu hình) | `X1504VA-BQ185W`, `NH.QZ9SV.004`, `B14WEK-027VN` |
| 1 | **Dell** (+ bất kỳ) | Mã 8 chữ số trần trụi nếu có | `71092479` |
| 2 | **Dell** | Series + mã model | `DC15250-CPH99` |
| 3 | **Dell** dòng khác | Dòng + số 4 chữ số | `PRECISION-3590` |
| 4 | bất kỳ | Phương án dự phòng token cuối cùng | `J9XFD` |

Các quy tắc theo thương hiệu được **chốt theo từ khoá thương hiệu xuất hiện trong tên** (`\bhp\b`,
`\b(asus|acer|msi)\b`, `macbook`), nên chúng chỉ kích hoạt cho đúng thương hiệu của mình — listing
Dell/Lenovo đi thẳng xuống các quy tắc chung (2–4) và không bị ảnh hưởng.

> **Lenovo không có quy tắc riêng của mình.** Mã sản phẩm Lenovo (`83K80016VN`, `21NS010HVN`) là các
> mã sạch, xen kẽ chữ và số, sống sót nguyên vẹn qua **phương án dự phòng token cuối cùng (#4)** —
> các quy tắc Dell (8 chữ số, series, dòng 4 chữ số) đều bị chặn theo hình dạng và định dạng của
> Lenovo không kích hoạt bất kỳ quy tắc nào trong số đó. Vì vậy Lenovo "tự động hoạt động đúng" mà
> không cần bất kỳ đoạn code riêng nào cho thương hiệu.

---

## Quy tắc chi tiết theo từng thương hiệu

### Dell — 8 chữ số → series+mã → dòng+số

Dell giữ nguyên chiến lược ba tầng ban đầu:

1. **Mã 8 chữ số trần trụi** (`71092479`) xuất hiện ở bất kỳ đâu trong slug/tên — duy nhất trên
   toàn hệ thống, có mặt trên hầu hết listing. Được dùng đầu tiên.
   ```
   /laptop-dell-15-dc15250-71092479                        → 71092479
   /laptop-dell-pro-14-...-pv14250-71084489-ltdl0666        → 71084489   (HACOM's internal code ignored)
   ```
2. **Series + mã model** — token series của Dell (`2+ chữ cái, 4–5 chữ số`: `dc15250`, `pb14250`)
   ghép với mã model (token chữ+số dài nhất sau series, bỏ qua các nhiễu CPU/màu sắc/bảo hành).
   ```
   …dc15250-cph99            → DC15250-CPH99
   …dc15250-i5-1334u-cph99   → DC15250-CPH99   (CPU "i5-1334u" skipped — matches the line above)
   …dc15255-x9ym41--s250809  → DC15255-X9YM41  (Phong Vũ "--s<id>" stripped)
   ```
3. **Các dòng không có mã** (Precision / XPS / Inspiron / Latitude / Vostro) không có mã riêng —
   chỉ có một số model 4 chữ số. Được khoá theo `<dòng>-<số>`.
   ```
   …precision-3590   → PRECISION-3590   (matches "Mobile Precision 3590" ↔ "Precision 3590 Workstation")
   ```

### Lenovo — không cần gì cả (phương án dự phòng tự lo)

`83K80016VN`, `21NS010HVN` → phương án dự phòng token cuối cùng trả về chúng nguyên vẹn. Quy tắc 8
chữ số của Dell đòi hỏi *8 chữ số liên tiếp* (mã Lenovo xen kẽ chữ cái, nên không khớp), và quy tắc
dòng 4 chữ số đòi hỏi một chuỗi 4 chữ số có ranh giới rõ ràng (không có ở đây). Đi qua nguyên vẹn.

### Apple — khoá tổng hợp thông số kỹ thuật

MacBook **không có mã sản phẩm** nào được các cửa hàng in ra một cách nhất quán. Thay vào đó chúng
ta xây dựng một định danh tổng hợp từ các thông số kỹ thuật xác định một chiếc Mac có thể mua được:

```
APPLE-{AIR|PRO|NEO}-{size}-{chip}-{ram}-{storage}
```

Được phân tích **không phụ thuộc vị trí** bằng regex, nên sự khác biệt về thứ tự từ không thành vấn
đề:

```
TNC:        "MacBook Pro M5 14 inch 24GB/ 1TB"          ┐
CellphoneS: "MacBook Pro 14 M5 10CPU 10GPU 24GB 1TB"    ┴→ both  APPLE-PRO-14-M5-24-1TB
```

- **Dòng**: Air / Pro / **Neo** (Neo dùng chip dòng `A18`, không phải dòng `M`).
- **Chip**: `M5`, `M5 Pro`, `M5 Max`, `A18 Pro` → `M5` / `M5PRO` / `M5MAX` / `A18PRO`.
- **RAM / dung lượng lưu trữ**: hai token dung lượng `<n>GB`/`<n>TB` (đầu tiên = RAM, cuối cùng =
  dung lượng lưu trữ). Số nhân CPU/GPU (`10CPU 10GPU`) không mang GB/TB, nên tự nhiên bị bỏ qua.
- **Không nằm trong khoá**: màu sắc và năm sản xuất — cố tình bỏ qua, để "cùng cấu hình, khác màu"
  gộp về một sản phẩm được theo dõi.

**Bổ sung thông số còn thiếu.** Một số listing của TNC bỏ sót RAM/dung lượng lưu trữ trong tên
(`MacBook Pro M5 Pro 16 inch 2026 Silver`). Hàm `enrich_apple()` của scraper TNC ghé thăm những
trang sản phẩm đó và phân tích lại tiêu đề H1 đầy đủ hơn (`… (M5 Pro/ Ram 48GB/ SSD 1TB)`); bất kỳ
sản phẩm nào vẫn còn thiếu thông tin (`APPLE-…-?-?`) sẽ bị **bỏ qua**, không bao giờ được lưu, để
các thông số còn thiếu không thể gộp nhầm các cấu hình khác nhau vào một dòng.

**Tên hiển thị gọn gàng.** Đối với Apple, TNC lưu một `apple_name()` tổng hợp (`MacBook Pro 16" M5
Pro 48GB 1TB`) thay vì chuỗi listing gốc, vốn thường bị gõ sai (`18GPU/ 20GPU`) hoặc nhiễu.

### HP — mã bộ phận

Mỗi laptop HP có một mã bộ phận duy nhất: **6–7 ký tự chữ+số xen kẽ giữa chữ cái và số**
(`BQ5B4PT`, `8K0H6AV`, `AM9H1PT`). Chúng ta khoá theo mã đó.

Quy tắc này được kiểm tra **trước** quy tắc 4 chữ số của Dell, vì tên gọi của HP chứa một số dòng
model dùng chung mà KHÔNG được dùng làm khoá:

```
"EliteBook X360 1040 G11 AM9H1PT"   → AM9H1PT   (NOT "1040" — the model line, shared by many configs)
"ZBook Power 16 ... RTX 2000 ... 9A673AV" → 9A673AV   (NOT "2000" — the GPU)
"Elite Dragonfly G3 6Z980PA (Xanh)" → 6Z980PA   (NOT "XANH" — the color)
```

Nếu có nhiều token đủ điều kiện, token **cuối cùng** sẽ được lấy (mã bộ phận nằm ở cuối; số dòng
model xuất hiện sớm hơn trong tên gọi).

### Asus / Acer / MSI — mã model

Listing của các thương hiệu này lộn xộn nhất: chúng bị cắt ngắn thành các mảnh dễ vỡ và xen kẽ các
thông số kỹ thuật. `model_code()` xây dựng `SERIES-CONFIG`:

- **Acer** có một mã bộ phận chuẩn `NX.xxxxx.xxx` / `NH.xxxxx.xxx` — được ưu tiên bất cứ khi nào có
  mặt.
  ```
  "Acer Nitro V ... ANV15-52-72BM (NH.QZ9SV.004)"  → NH.QZ9SV.004
  ```
- **Nếu không**: tìm **token series** rồi đi tới **phần kết thúc cấu hình (config terminator)**,
  giữ lại các mã cấu hình có cấu trúc nhưng bỏ đi các dấu hiệu CPU/RAM mà các cửa hàng xen kẽ vào,
  rồi dừng lại ở phần kết thúc đó (và bỏ đi mọi thứ sau nó).
  - Series kết thúc bằng chữ cái (model thật của Asus/MSI): `P1403CVA`, `X1504VA`, `B14WEK`, `D3MG`.
  - Series kết thúc bằng chữ số (dòng Acer có cấu hình theo sau): `ANV15`, `AG15`, `A515`.
  - Phần kết thúc cấu hình: `…W` / `…WS` (Asus) hoặc `…VN` (MSI), ví dụ `BQ185W`, `LY849W`,
    `432VN`. `WS` được chuẩn hoá thành `W`.

```
TNC:  "Asus Vivobook 15 X1504VA-BQ185W"                    ┐
TGDĐ: "Asus Vivobook 15 X1504VA - Core 5 - BQ185WS"        ┴→ both  X1504VA-BQ185W
FPT:  "Asus Vivobook 14 M1407KA-LY849W R5 330/AI"          → M1407KA-LY849W   (trailing "-330" dropped)
FPT:  "MSI ... F1MG-432VN-5-120U"                          → F1MG-432VN       (trailing CPU dropped)
Acer: "Aspire Go 15 AG15-52P-52WT"                         → AG15-52P-52WT    (no W/VN terminator → tail kept)
```

**Cấu hình có cấu trúc so với dấu hiệu thông số kỹ thuật.** Phần khó nhất: một token như `C5H08`
*phân biệt* các cấu hình ExpertBook và phải được giữ lại, trong khi `5` / `120U` / `U7` là nhiễu
CPU/RAM cần bỏ qua. Quy tắc giữ lại các mã cấu hình có cấu trúc và bỏ qua các hình dạng "dấu hiệu
thông số kỹ thuật" hẹp (1–3 chữ số trần trụi, `120U`, `u9`, `r5`, `i7`, `ux9`):

```
"ExpertBook P1 P1403CVA-C5H08-50W"   → P1403CVA-C5H08-50W   ┐  distinct — C5H08 vs C3U08
"ExpertBook P1 P1403CVA-C3U08-50W"   → P1403CVA-C3U08-50W   ┘  (RAM/CPU config kept)
```

---

## Màn hình — Tier A (`BRAND-MODEL`)

Màn hình là **danh mục đầu tiên ngoài laptop**, và cũng là loại dễ so khớp nhất: gần như mọi cửa
hàng đều in **mã model của nhà sản xuất** ngay trong tên sản phẩm (`SE2426H`, `LS27FG502EEXXV`,
`VX2758-2KP-MHD`). Khác với laptop (mỗi thương hiệu một chiến lược), toàn bộ màn hình dùng **một**
quy tắc: khoá theo `BRAND-MODEL`. Logic nằm ở `monitor_sku()` trong
[`scraper/scraper/sku.py`](../scraper/scraper/sku.py), được `derive_sku(..., category="Monitor")`
gọi thông qua bảng phân luồng `_CATEGORY_SKU`.

Tên màn hình có dạng: **`Màn hình [LCD/LED] <(các) từ mô tả> <BRAND> <MODEL> <size> inch <res>
<panel>`**. Mã model nằm ngay sau thương hiệu; mọi thứ từ kích thước trở đi là thông số kỹ thuật cần
bỏ. `monitor_sku` đi qua các bước sau:

**1. Bóc tiền tố danh mục.** `_MON_PREFIX` xoá phần `"màn hình"` / `"màn hình lcd"` / `"màn hình
led"` ở đầu.

**2. Bỏ các từ mô tả đứng trước thương hiệu.** Đây là bước then chốt để khoá **độc lập với cửa
hàng**: một cửa hàng viết `"Màn hình gaming ViewSonic VX2758"`, cửa hàng khác viết `"Màn hình
ViewSonic VX2758"`. Nếu cứ lấy token đầu tiên làm thương hiệu, ta sẽ nhận nhầm `"gaming"`. Vòng lặp
bỏ mọi từ mô tả dẫn đầu (`gaming`, `cong`, `curved`, `oled`, … — cùng tập `_MON_SERIES_WORD` và các
từ spec) cho tới khi token đầu tiên là **thương hiệu thật**.

```
"Màn hình gaming ViewSonic VX2758-2KP-MHD 27 inch 2K"   → VIEWSONIC-VX2758-2KP-MHD
"Màn hình cong Samsung Odyssey LS27DG502EEXXV 27"        → SAMSUNG-LS27DG502EEXXV
```

**3. Thương hiệu = token đầu tiên còn lại.** (Ví dụ `viewsonic`, `samsung`, `dell`.)

**4. Model = token có-chữ-số đầu tiên sau thương hiệu**, vừa đi vừa bỏ qua:
- **từ series** (`Odyssey`, `UltraGear`, `ThinkVision`, `Pro`, `TUF`, … — `_MON_SERIES_WORD`), và
- **thương hiệu lặp lại** (`"Dell Dell SE2426H"`),

rồi **dừng ngay khi gặp token đầu tiên có chứa chữ số** (đó chính là mã model), và dừng trước
kích thước / năm / từ spec (`24`, `2026`, `inch`, `fhd`, `ips`, …).

```
TNC:        "Màn hình LCD Dell SE2426H 24 inch FHD IPS"   ┐
đối thủ:    "Màn hình Dell SE2426H 23.8\" 100Hz"          ┴→ cả hai  DELL-SE2426H
"Màn hình LG UltraGear 27GP750 27 inch"                   → LG-27GP750   ("UltraGear" bỏ qua)
"Màn hình AOC Q27G4S 27 inch QHD IPS"                     → AOC-Q27G4S
```

### HP là ngoại lệ — mã đứng CUỐI, không phải đầu

Y như laptop, HP đặt tên khác mọi hãng: một **tên marketing đứng trước** (`Series 7`, `E45c`, `S3`)
và **mã bộ phận thật đứng cuối**, ngay trước kích thước. Quy tắc "token có-chữ-số đầu tiên" sẽ lấy
nhầm tên marketing (`Series 7` → `HP-SERIES-7`), vốn dùng chung cho nhiều cấu hình. Vì vậy `HP` có
một nhánh riêng: lấy **mã `_HP_CODE` cuối cùng** trước kích thước (6–7 ký tự xen kẽ chữ và số — tái
dùng đúng quy tắc HP của laptop).

```
"Màn hình LCD HP Series 7 Pro 724pn 8X534AA 24 inch"  → HP-8X534AA   (NOT HP-SERIES-7)
"Màn hình LCD HP S3 Pro 324ph B0BU9UT 23.8 inch"      → HP-B0BU9UT   (NOT HP-S3)
"Màn hình LCD HP E45c G5 6N4C1AA 44.5 inch DQHD"      → HP-6N4C1AA
```

Nếu không tìm thấy mã bộ phận nào, HP rơi xuống quy tắc chung (token có-chữ-số đầu tiên).

### Những trường hợp đặc biệt mà quy tắc màn hình ngăn chặn

- **`GAMING-...` / `CONG-...` giả làm thương hiệu** — nếu không bỏ các từ mô tả dẫn đầu, cùng một
  chiếc ViewSonic sẽ có khoá khác nhau giữa hai cửa hàng (`GAMING-VIEWSONIC-...` vs `VIEWSONIC-...`)
  và **không bao giờ khớp**. Đây là lỗi thật đã gặp trong lần dry-run đầu tiên.
- **`HP-SERIES-7` trùng lặp** — `Series 7`/`Series 3`/`Series 5` là *dòng* marketing, không phải mã.
  Nhiều màn hình HP khác cấu hình dùng chung một dòng, nên khoá theo dòng sẽ gộp nhầm. Khoá theo mã
  bộ phận cuối (`8X534AA`) giữ chúng tách biệt.
- **Đuôi spec bị cắt** — dừng ở token có-chữ-số đầu tiên đảm bảo `27 inch`, `144Hz`, `IPS`, `2K` …
  không bao giờ lọt vào khoá, nên `"...VX2758 27 inch"` và `"...VX2758 (27\"/2K/165Hz)"` khớp nhau.

> **Điều kiện để khớp giữa các cửa hàng vẫn là: cửa hàng kia cũng phải in mã model.** Đa số có
> (Dell/Samsung/ViewSonic/LG/AOC/…), nên tỉ lệ khớp cao. HP là hãng yếu nhất — nếu một cửa hàng chỉ
> ghi `"Màn hình HP Series 7 24 inch"` (không có mã bộ phận), nó sẽ ra `HP-SERIES-7` và không khớp
> với `HP-8X534AA` của TNC. Đây là giới hạn đã biết, không phải lỗi.

---

## Vì sao những trường hợp đặc biệt này lại quan trọng (các lỗi mà mỗi quy tắc ngăn chặn)

- **Trùng lặp `16512W` của Dell** — `16512W` là một mã *thông số kỹ thuật* (16 GB / 512 GB /
  Windows). Một quy tắc "token cuối cùng" đã gộp nhầm Pro 13 (`PB13250`) và Pro 14 (`PB14250`).
  Khoá theo series giữ chúng tách biệt.
- **Hậu tố `-5` / màu sắc / bảo hành của Dell** — các cửa hàng thêm vào `…-bac` (Bạc = màu bạc),
  `…-2y` (bảo hành), `…-5`. Bỏ qua các nhiễu này + token CPU và lấy đúng mã model thật đã khắc phục
  vấn đề.
- **Trùng lặp dòng model của HP** — `1040` (dòng EliteBook), `2000` (một GPU RTX), `XANH`/`BAC`
  (màu sắc) đều từng bị lấy nhầm thay vì mã bộ phận, gây gộp nhầm các cấu hình khác nhau. Khoá theo
  mã bộ phận (`AM9H1PT`, `9A673AV`) đã khắc phục vấn đề.
- **Trùng lặp do bị cắt ngắn của Asus/MSI** — `P1403CVA-C3U08-50W` và `P1503CVA-C5H16-50W` đều từng
  bị gộp thành `50W`. Khoá theo mã model đầy đủ khiến chúng tách biệt.
- **Sai lệch giữa các cửa hàng của Asus/MSI** — TGDĐ xen CPU vào giữa (`X1504VA-5-BQ185WS`), FPT
  thêm nhiễu vào cuối (`…-LY849W-R5-330`), phần kết thúc của MSI là chữ số trần trụi (`432VN`).
  Việc đi từ series đến phần kết thúc kèm bỏ qua dấu hiệu thông số kỹ thuật + chuẩn hoá `WS→W` giúp
  mọi cửa hàng đồng nhất. *(Quy tắc này đã mất ba lần lặp lại trên dữ liệu thực tế — dấu hiệu của sự
  sai lệch là một sản phẩm có ít đối thủ hơn dự kiến.)*
- **Apple không có mã** — một khoá tổng hợp thông số kỹ thuật là định danh ổn định duy nhất; việc
  phân tích không phụ thuộc thứ tự từ giúp các cửa hàng đồng nhất, và việc bổ sung thông tin từ
  trang sản phẩm lấp đầy khoảng trống thay vì gộp nhầm vào `?`.

---

## Giới hạn (nói một cách đơn giản)

Mỗi cửa hàng đặt tên và liệt kê sản phẩm hơi khác nhau, nên việc so khớp không bao giờ hoàn hảo:

- **Không phải sản phẩm nào cũng có đối thủ.** Thường một đối thủ đơn giản là không bán đúng sản
  phẩm đó — đây là thật, không phải lỗi.
- **Đôi khi cùng một sản phẩm bị bỏ sót.** Hai cửa hàng mô tả khác nhau đến mức hệ thống không nhận
  ra chúng khớp. Dấu hiệu: một sản phẩm có ít đối thủ hơn dự kiến → thường là **quy tắc trích mã
  cần chỉnh** (sửa một lần, sửa cho tất cả), không phải sản phẩm thật sự không có đối thủ.
- **Một số dòng không thể so khớp chính xác.** Dòng Precision/XPS/Inspiron của Dell khoá theo
  dòng + số, không phải một mã duy nhất — hai phiên bản hơi khác nhau có thể bị coi là một.
- **Apple/composite so khớp theo cấu hình, không theo màu/năm.** Cùng cấu hình khác màu được cố ý
  coi là một sản phẩm.
- **Một số danh mục không có mã dùng chung** (phần mềm theo tên vs SKU, cáp không tên). `derive_sku`
  trả về `None` và không so khớp mờ — cần bảng alias do người duyệt (xem [So khớp 3
  tầng](#so-khớp-3-tầng)). Đây là giới hạn *thông tin*, không phải lỗi code.

Tóm lại: hệ thống được xây dựng để **an toàn hơn là tham lam** — thà hiển thị "không khớp" còn hơn
so sánh sai hai sản phẩm khác nhau. Hãy coi các so sánh này là một hướng dẫn mạnh, không phải một
bức tranh hoàn chỉnh 100%.


