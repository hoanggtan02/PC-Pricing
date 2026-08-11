# `discover_fptshop.py` — Giải thích scraper FPT Shop + proxy Việt Nam

Một bài phân tích chi tiết [`scraper/scraper/discover_fptshop.py`](../scraper/scraper/discover_fptshop.py)
và lớp proxy dùng chung trong [`scraper/scraper/browser.py`](../scraper/scraper/browser.py).

Hãy đọc [`scraper-anphat.md`](scraper-anphat.md) trước — FPT hoạt động theo cùng cách, nhưng thêm
**hai điểm khác biệt**: nó bị **chặn theo vị trí địa lý** (cần proxy dân dụng tại Việt Nam) và nó có
**phân trang** bằng `&page=N`. Tài liệu này tập trung vào hai điểm khác biệt đó.

---

## Điểm khác biệt 1: FPT chặn IP nước ngoài → proxy dân dụng

FPT Shop nằm sau **Cloudflare**, dịch vụ này trả về **HTTP 403 (Forbidden)** cho bất kỳ khách truy
cập nào có IP không phải của Việt Nam. Một lập trình viên ở nước ngoài — *và* cả GitHub Actions (chạy
tại Mỹ) — đều bị chặn. Cách khắc phục là định tuyến request qua một **proxy dân dụng (residential)
tại Việt Nam** để trang web nhìn thấy một IP Việt Nam và cho phép truy cập.

### Proxy dân dụng (residential) là gì

Proxy là một server trung gian mà request của bạn đi qua; trang web nhìn thấy IP của **proxy**, chứ
không phải IP của bạn. Một proxy *dân dụng (residential)* sử dụng một IP internet gia đình thật của
Việt Nam (từ nhà mạng như VNPT), nên đối với Cloudflare nó trông giống như một người mua hàng bình
thường tại Việt Nam — chính xác là đối tượng mà nó cho phép truy cập.

```
Without proxy:  Your machine (US IP) ─────────────► FPT   ❌ 403 (foreign IP)
With proxy:     Your machine ──► VN proxy (VN IP) ──► FPT   ✅ 200 (looks local)
```

Chúng ta dùng **DataImpulse** (~1 USD/GB, dạng dân dụng). Việc nhắm mục tiêu vào Việt Nam nằm trong
username của proxy (`...__cr.vn`).

### Cách proxy được kết nối vào hệ thống — `browser.py`

Toàn bộ logic proxy nằm trong một helper dùng chung để các scraper riêng lẻ không phải lặp lại nó.
Thông tin xác thực được lấy từ biến môi trường (không bao giờ hard-code), nạp từ `scraper/.env`:

```ini
# scraper/.env  (git-ignored — never committed)
PROXY_SERVER=http://gw.dataimpulse.com:823
PROXY_USERNAME=<your-username>__cr.vn   # the "__cr.vn" forces a Vietnam exit IP
PROXY_PASSWORD=<your-password>
```

`browser.py` đọc các giá trị này và dựng cấu hình proxy của Playwright:

```python
def _proxy_config() -> dict | None:
    server = os.environ.get("PROXY_SERVER", "").strip()
    if not server:
        return None                              # no proxy configured
    return {
        "server":   server,
        "username": os.environ.get("PROXY_USERNAME", ""),
        "password": os.environ.get("PROXY_PASSWORD", ""),
    }
```

Sau đó `browser_page(use_proxy=True)` khởi chạy Chromium **thông qua** proxy đó:

```python
@contextmanager
def browser_page(use_proxy: bool = False):
    proxy = _proxy_config() if use_proxy else None
    if use_proxy and proxy is None:
        # fail LOUDLY instead of silently getting a 403
        raise RuntimeError("This site needs a VN proxy, but PROXY_SERVER isn't set in .env.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, proxy=proxy)   # ← all traffic routes via VN
        context = browser.new_context(user_agent=USER_AGENT, viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        ...
        yield page
```

Vậy nên một scraper bị chặn theo vị trí địa lý chỉ cần mở trang của nó như thế này:

```python
from .browser import browser_page

with browser_page(use_proxy=True) as page:    # FPT, Phong Vũ, TGĐĐ → True
    page.goto(PAGE_URL, ...)
```

Các site truy cập trực tiếp (An Phát, CellphoneS, HACOM, TNC) truyền `use_proxy=False` và kết nối
bình thường.

### Tiết kiệm băng thông của proxy (tính phí theo dung lượng)

Proxy dân dụng tính phí **theo từng gigabyte**, và một lần tải trang đầy đủ (hình ảnh, font, quảng
cáo) rất nặng. Vì vậy khi dùng proxy, `browser.py` sẽ **chặn các tài nguyên không cần thiết** — giá
và liên kết nằm trong HTML + JavaScript, không nằm trong hình ảnh:

```python
if use_proxy:
    blocked = {"image", "font", "media", "stylesheet"}
    page.route("**/*", lambda route:
        route.abort() if route.request.resource_type in blocked else route.continue_())
```

Điều này giảm băng thông proxy khoảng ~60–80%, giúp một gói dung lượng GB nhỏ chạy được nhiều lần
mỗi ngày.

---

## Điểm khác biệt 2: FPT phân trang bằng `&page=N`

An Phát dùng nút "xem thêm". FPT thay vào đó phục vụ kết quả theo **các trang 24 sản phẩm** thông
qua tham số URL. Tìm kiếm thông thường của nó bị giới hạn ở 24, nhưng chế độ xem "khám phá"
(explore) có phân trang — mỗi trang là 24 laptop Dell *khác nhau*:

```python
PAGE_URL = (
    "https://fptshop.com.vn/tim-kiem?tab=kham-pha&s=laptop+dell"
    "&sort=noi-bat&categories=may-tinh-xach-tay&page={page}"
)
MAX_PAGES = 15
```

Vì vậy `discover()` lặp qua từng trang, dừng lại khi một trang không thêm được sản phẩm mới nào:

```python
with browser_page(use_proxy=True) as page:        # one browser, reused across pages
    for n in range(1, MAX_PAGES + 1):
        try:
            page.goto(PAGE_URL.format(page=n), wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector(".cardInfo", timeout=15000)
        except Exception:
            break                                  # a slow/missing page → stop, keep what we have

        new_on_page = 0
        for card in <cards on this page>:
            ... extract name/price/url ...
            if url not in seen_urls:               # de-dupe across pages
                seen_urls.add(url)
                new_on_page += 1
                results.append({...})

        if new_on_page == 0:                        # this page was all duplicates → last page
            break
```

Điều kiện kiểm tra `new_on_page == 0` là cách chúng ta biết đã đến trang cuối cùng — trang đầu tiên
không trả về sản phẩm *mới* nào nghĩa là không còn trang nào nữa. Điều này đã giúp FPT tăng từ 24 →
~150 laptop được khám phá.

### Chọn giá hiện tại (định dạng markup của FPT)

FPT hiển thị một giá cũ bị gạch ngang bên cạnh giá hiện tại. Giá hiện tại là một thẻ `<p>` mà
**nội dung văn bản của chính nó chỉ chứa đúng một giá** (ví dụ `"20.990.000đ"`) và **không** có
kiểu `line-through`:

```js
const PRICE = /^[0-9]{1,3}\.[0-9]{3}\.[0-9]{3}\s*đ?$/;
for (const el of card.querySelectorAll('p')) {
  if (!el.className.includes('text-textOnWhitePrimary')) continue;  // the current-price style
  if (PRICE.test(el.textContent.trim())) { price = el.textContent.trim(); break; }
}
```

Chúng ta bỏ qua nhãn giảm giá `-13%`, dòng tiết kiệm `Giảm …`, và giá gốc bị gạch ngang.

---

## `main()` — giống hệt mọi scraper khác

Sau khi `discover()` trả về danh sách laptop, việc so khớp + ghi dữ liệu theo cùng luồng match-only
như An Phát (xem [`scraper-anphat.md`](scraper-anphat.md)): nạp danh mục TNC một lần, và với mỗi
laptop có `derive_sku` nằm trong danh mục, upsert nguồn (source) của nó và thêm giá của nó. Khác
biệt duy nhất mang tính hình thức là dòng log ghi thêm *"(via VN proxy)"*.

---

## Chạy scraper

```bash
python -m scraper.discover_fptshop --dry   # needs the proxy creds in .env, or it errors clearly
python -m scraper.discover_fptshop
```

Nếu `PROXY_SERVER` chưa được thiết lập, nó sẽ báo lỗi rõ ràng thay vì âm thầm trả về một trang lỗi
403 — để bạn luôn biết *vì sao* nó thất bại.

---

## So sánh nhanh: An Phát vs FPT

| | An Phát | FPT Shop |
| --- | --- | --- |
| Bị chặn theo vị trí địa lý? | Không | **Có** → cần proxy dân dụng tại Việt Nam |
| `use_proxy` | `False` | `True` |
| Tải thêm bằng | nút "Xem thêm" | phân trang `&page=N` |
| Chặn băng thông | tắt | **bật** (proxy tính phí theo dung lượng) |
| Mọi thứ khác | — | giống hệt nhau (trừ các selector) |

Proxy + phân trang là những khác biệt thực sự *duy nhất*. Logic match-only, cách suy ra SKU, và việc
ghi vào cơ sở dữ liệu đều dùng chung cho cả 9 scraper.
</content>
