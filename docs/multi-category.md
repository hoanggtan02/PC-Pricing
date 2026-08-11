# Scraping đa danh mục — các quyết định thiết kế

Cách scraper mở rộng ra ngoài laptop để phủ mọi danh mục sản phẩm (màn hình, RAM, SSD, TV, …), và
những lựa chọn không hiển nhiên đằng sau nó. Tài liệu này nói về mô hình **theo danh mục
(category-driven)** mà mọi thứ ngoài laptop đều sử dụng.

**Pipeline laptop không bị thay đổi.** Hành vi của nó được giữ nguyên chính xác — phần công việc
danh mục là bổ sung thêm (additive). Ở những nơi code danh mục dùng chung một hàm với laptop
(`discover()`), logic laptop được rào lại phía sau một nhánh `category == "laptop"` chạy đúng luồng
gốc từng byte một; nhánh không phải laptop hoàn toàn tách biệt. Các lần dry-run laptop cho ra kết
quả giống hệt nhau trước và sau (đã kiểm chứng). Chúng ta không thay đổi việc so khớp laptop, URL,
danh sách thương hiệu, hay lần chạy laptop hàng ngày.

Liên quan: [`sku-matching.md`](sku-matching.md) (cách một SKU được suy ra),
[`schema-design.md`](schema-design.md).

---

## Hai vấn đề mà cách làm này giải quyết

1. **URL tràn lan.** Scraper laptop ban đầu hard-code một dict `BRANDS` cho mỗi đối thủ — 9 đối thủ
   × 7 thương hiệu ≈ 63 URL. Mở rộng cách tiếp cận theo-thương-hiệu đó sang ~12 danh mục sẽ đồng
   nghĩa với ~750 URL phải duy trì thủ công. Không khả thi.
2. **Thương hiệu không ánh xạ nhất quán giữa các danh mục.** Dell làm laptop và màn hình nhưng không
   làm tai nghe; Sony làm tai nghe và TV nhưng không làm RAM. Một vòng lặp toàn cục `(thương hiệu ×
   danh mục)` sẽ tạo ra rất nhiều ô trống (`dell tai nghe` → không có gì) và cần một danh sách
   thương hiệu riêng cho từng danh mục mà không ai muốn duy trì.

---

## Quyết định cốt lõi: theo danh mục, không theo thương hiệu

**Scrape một truy vấn cho mỗi danh mục, suy ra thương hiệu của mỗi sản phẩm từ tên gọi của nó, so
khớp theo SKU.**

Thay vì lặp qua các thương hiệu (`for brand in dell, lenovo, …: search "man hinh dell"`), một danh
mục được scrape trong **một lượt duy nhất** (`search "man hinh"` → tất cả thương hiệu cùng lúc).
Điều này:

- **Thu gọn số lượng URL** — một URL danh sách cho mỗi cặp (đối thủ, danh mục), không phải cho mỗi
  thương hiệu. Một tìm kiếm cho "màn hình" trả về Dell, Samsung, LG, ViewSonic… cùng một lúc.
- **Nhanh hơn** — ít hơn khoảng 7 lần số lượt tải trang cho mỗi danh mục.
- **Xoá bỏ vấn đề "Dell không làm tai nghe"** — thương hiệu không bao giờ bị liệt kê trước; chúng ta
  scrape danh mục và nhận bất kỳ thương hiệu nào xuất hiện.

### Vì sao mô hình theo-thương-hiệu của laptop KHÔNG được tái sử dụng cho các danh mục

Scraper laptop lặp qua một danh sách thương hiệu cố định (Dell/Lenovo/Apple/HP/Asus/Acer/MSI) vì
laptop có một tập hợp nhà sản xuất nhỏ, đã biết trước, và ổn định. Điều đó **không** áp dụng được
cho các danh mục khác, vì hai lý do:

1. **Chúng ta không biết hết các thương hiệu trong một danh mục — thị trường mới biết.** Chỉ riêng
   màn hình đã lộ ra 17 nhà sản xuất trên TNC (ViewSonic, Gigabyte, AOC, BenQ, Hikvision, Xiaomi,
   Cooler Master…), trong đó có nhiều cái chúng ta chưa bao giờ liệt kê trước, cộng thêm các tên
   ít phổ biến (E-Dra, VSP, Koorui) xuất hiện rồi biến mất. Hard-code một danh sách thương hiệu cho
   từng danh mục sẽ âm thầm bỏ sót bất cứ thứ gì chúng ta quên. Suy ra thương hiệu từ tên của mỗi
   sản phẩm thay vào đó nghĩa là chúng ta nắm bắt được **mọi** thương hiệu mà cửa hàng thực sự bán,
   kể cả những thương hiệu mới đối với chúng ta.
2. **Thương hiệu × danh mục sẽ quá chậm.** Lặp qua từng thương hiệu như một tìm kiếm riêng biệt —
   cho mỗi đối thủ, cho mỗi danh mục — sẽ nhân số lượt tải trang lên rất nhiều (một danh sách
   thương hiệu × ~12 danh mục × 9 site). Mỗi tìm kiếm là một lượt tải trang đầy đủ bằng trình duyệt
   headless kèm cuộn/tải-thêm; lần chạy hàng ngày hiện đã mất ~1 giờ chỉ riêng cho laptop. Một tìm
   kiếm cho mỗi danh mục ("màn hình") trả về tất cả thương hiệu chỉ trong một lượt fetch, giữ cho
   thời gian chạy vẫn khả thi khi số danh mục tăng lên.

Vì vậy với các danh mục, chúng ta scrape **danh mục đó một lần** và để `brand_of` phân chia kết quả
theo thương hiệu dựa trên tên gọi — không bao giờ lặp theo thương hiệu.

### Vì sao thương hiệu là *được suy ra*, không phải một đầu vào

Đối với việc **so khớp**, thương hiệu là dư thừa so với SKU — hai listing khớp nhau khi và chỉ khi
`derive_sku` cho ra cùng một khoá, đây là phép so sánh chuỗi thuần tuý. Thương hiệu không bao giờ
được tham chiếu trong việc so khớp. Vì vậy thương hiệu:

- **Không phải là tham số scrape** — chúng ta không tìm kiếm theo từng thương hiệu.
- **Được suy ra từ tên sản phẩm** tại thời điểm ghi nhận thông qua `brand_of(name)` (xem bên dưới).
- **Được gắn vào SKU** như một tiền tố chống trùng lặp (collision-guard) ở những nơi hữu ích
  (`DELL-P2425H` so với một `P2425H` trần trụi có thể trùng với mã model của một nhà sản xuất khác).
  Nhưng thương hiệu đó đến từ tên gọi bên trong `derive_sku`, không phải từ một cờ (flag).
- **Được giữ lại như một cột `products.brand`** chỉ nhằm phục vụ dashboard (lọc/độ phủ theo từng
  thương hiệu).

Vậy nên: **SKU là định danh để so sánh; thương hiệu là một nhãn được suy ra cho giao diện người
dùng.**

---

## Nhận diện thương hiệu là một nguồn chân lý có thể chỉnh sửa bởi con người

`brand_of(name)` phân giải một tên sản phẩm thành một thương hiệu chuẩn hoá qua ba tầng
([`scraper/scraper/brand.py`](../scraper/scraper/brand.py)):

1. **So khớp từ khoá đã tuyển chọn** với
   [`scraper/config/brands.yaml`](../scraper/config/brands.yaml) — một file có thể chỉnh sửa bởi
   con người, ánh xạ mỗi thương hiệu chuẩn hoá với (các) từ khoá xuất hiện trong tên gọi
   (`Samsung: [samsung, odyssey, viewfinity]`, `Apple: [apple, macbook, imac]`). Thứ tự trong file
   phá vỡ các trường hợp trùng lặp (Lenovo trước HP, để `15AHP11` không bị đọc nhầm thành HP).
2. **Phương án dự phòng theo cấu trúc** — nếu không từ khoá nào khớp, lấy token thực sự đầu tiên
   sau tiền tố danh mục (`Màn hình <BRAND> <model>` → token ngay sau "màn hình"). Cách này bắt được
   các thương hiệu **chưa có trong file** (một nhà sản xuất màn hình mới như Koorui) để không có gì
   âm thầm biến thành "Other".
3. `"Other"` chỉ khi thực sự không có gì.

**Vì sao dùng file, không phải code:** vốn từ vựng thương hiệu tăng theo từng danh mục (thương hiệu
màn hình, thương hiệu âm thanh, …). Một người không biết code có thể chỉnh sửa nó trong YAML, và
phương án dự phòng theo cấu trúc nghĩa là file chỉ cần chứa các *trường hợp ngoại lệ* (thương hiệu
nhiều từ, các bí danh thương hiệu con như `Odyssey`→Samsung), không cần mọi thương hiệu.

---

## Cấu hình: `sources.yaml` (URL) + `brands.yaml` (từ vựng)

Toàn bộ kiến thức về từng site, từng danh mục nằm trong hai file dữ liệu, không phải trong Python.

**[`scraper/config/sources.yaml`](../scraper/config/sources.yaml)** — nơi tìm mỗi danh mục:

- `competitors:` — mỗi **site có ô tìm kiếm (search-box)** có DUY NHẤT một mẫu `search_url`
  (`?q={query}`), được điền bằng `search_term` của danh mục. Một dòng cho mỗi site, chỉ một lần
  duy nhất; không có URL riêng cho từng danh mục.
- `categories.<cat>:`
  - `search_term` — truy vấn dành cho các site có ô tìm kiếm (ví dụ `man hinh`).
  - `name_match` — một regex mà tên sản phẩm phải khớp để được tính vào danh mục này (loại bỏ nhiễu
    từ tìm kiếm — một tìm kiếm "màn hình" có thể trả về cả giá treo màn hình/dây cáp).
  - `tnc` — URL trang danh sách theo danh mục của TNC (nguồn dẫn dắt danh mục sản phẩm).
  - `paths` — các URL rõ ràng cho 3 **site có đường dẫn theo danh mục (category-path)** (Phong Vũ,
    TGDĐ, FPT) không có ô tìm kiếm rõ ràng.

`config.resolve_url(competitor, category)` trả về đúng URL cho bất kỳ site nào: `tnc` của TNC, mục
`paths` của một site category-path, hoặc mẫu đã điền của một site có ô tìm kiếm.

> **Từ khoá tìm kiếm: dấu thanh (diacritics) không quan trọng.** Các công cụ tìm kiếm thương mại
> điện tử Việt Nam chuẩn hoá dấu ("man hinh" == "màn hình" — đã kiểm chứng số lượng kết quả giống
> hệt nhau trên CellphoneS/HACOM/An Phát). ASCII thuần là lựa chọn mặc định an toàn hơn (không có
> trường hợp lỗi mã hoá URL), nhưng cả hai đều hoạt động được.

---

## Các tầng danh mục theo khả năng so khớp

Hầu như mọi sản phẩm đều mang một token thương hiệu+model, nên gần như không có tầng nào là không
thể so khớp — chỉ có hai lược đồ định danh (xem [`sku-matching.md`](sku-matching.md) để biết quy
tắc trích xuất):

- **Tầng A** — một mã bộ phận / mã model là định danh rõ ràng (màn hình, RAM, SSD, GPU, switch):
  khoá theo `BRAND-MODEL` (`DELL-P2425H`, `SAMSUNG-LS24F320GAEXXV`). Về cấu trúc giống hệt cách
  laptop Dell khoá theo mã của chúng.
- **Tầng B** — thương hiệu + model trong một tên gọi được "trang trí" thêm (TV, máy in, router, âm
  thanh): khoá theo `BRAND-NORMALIZEDMODEL` sau khi loại bỏ các từ ngữ marketing thừa.
- Chỉ những mặt hàng thực sự không có token nào (một sợi cáp không tên) mới rơi về **chỉ nằm trong
  danh mục TNC** (ingest để giá của chúng ta vẫn hiển thị, `num_sources = 0`), không bao giờ so
  khớp mờ (fuzzy match) (kết quả dương tính giả sẽ phá vỡ mô hình SKU chính xác).

---

## Cách một scraper vẫn tương thích với laptop

Mỗi `discover(brand, category="laptop")` phân nhánh một lần:

- `category == "laptop"` → luồng cũ (legacy): URL `BRANDS` theo-thương-hiệu có sẵn + bộ lọc so khớp
  thương hiệu. **Không thay đổi**, để laptop không bị hồi quy (regress).
- ngược lại → theo danh mục: `resolve_url(site, category)` để lấy URL, và regex `name_match` của
  danh mục làm bộ lọc giữ lại (thay cho bộ lọc thương hiệu). Toàn bộ phần phân tích DOM riêng của
  site (selector, phân trang, cuộn/tải-thêm, phát hiện hết hàng) được tái sử dụng nguyên trạng.

`main()` sau đó suy ra thương hiệu cho mỗi sản phẩm (`brand_of`) và SKU (`derive_sku(name, url,
category)`), rồi áp dụng cùng quy tắc **match-only** (giá của đối thủ chỉ được ghi nhận cho các SKU
đã có sẵn trong danh mục TNC).

> **Lưu ý riêng theo từng site.** Một số đối thủ gắn cứng các giả định về laptop vào phần phân tích
> của họ — HACOM lọc liên kết sản phẩm theo `href^="/laptop"`; FPT/TGDĐ/GearVN/Memoryzone có bộ lọc
> tên `^laptop|macbook` *loại bỏ* màn hình. Việc kết nối một site cho một danh mục mới nghĩa là nới
> lỏng bộ lọc đó, không chỉ đơn thuần thay URL. Đây là bước "kiểm tra selector theo từng danh mục" —
> hãy dự trù một chỉnh sửa nhỏ cho mỗi site, không phải là không cần chỉnh sửa gì.

---

## Công thức kiểm chứng (cho mỗi danh mục)

1. **Unit:** đưa các tên đã biết qua `derive_sku(name, url, "<Category>")`; khẳng định rằng một tên
   của TNC và một tên của đối thủ cho *cùng* một sản phẩm sẽ cho ra cùng một khoá.
2. **Dry-run TNC:** `python -m scraper.discover_tnc --category monitor --dry` — một lượt trả về tất
   cả thương hiệu; SKU trông giống mã model, thương hiệu phân giải đúng (không phải "Other").
3. **Dry-run đối thủ so với danh mục** (sau khi TNC đã nạp dữ liệu): số lượng "matched N SKU(s)"
   khác 0.
4. **Hồi quy (Regression):** `--category laptop --brand dell --dry` cho ra các SKU giống hệt như
   trước.

Đã được chứng minh với màn hình: một lượt scrape TNC → 240 màn hình trên 17 thương hiệu, 99% SKU
sạch; CellphoneS khớp được giữa các cửa hàng trên các model chung.
</content>
