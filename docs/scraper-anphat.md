# `discover_anphat.py` — Giải thích scraper An Phát

Một bài phân tích chi tiết [`scraper/scraper/discover_anphat.py`](../scraper/scraper/discover_anphat.py).
Đây là **scraper đối thủ đơn giản nhất** — An Phát có thể truy cập trực tiếp (không chặn theo vị trí
địa lý, không cần proxy), nên đây là scraper tốt nhất để học mẫu hình chung. Mọi scraper khác đều là
một biến thể của scraper này.

---

## Bức tranh tổng thể

Một scraper gồm hai nửa:

1. **`discover()`** — mở trang tìm kiếm "laptop dell" của đối thủ trong trình duyệt headless, tải
   toàn bộ sản phẩm, và trả về một danh sách phẳng gồm `{name, price, url}`.
2. **`main()`** — với mỗi laptop được khám phá, suy ra SKU của nó và, **nếu SKU đó nằm trong danh
   mục TNC đang bán**, ghi giá của nó vào cơ sở dữ liệu.

```
search page → discover() → [{name, price, url}, ...] → match SKUs → write to Supabase
```

---

## Vì sao dùng trình duyệt headless (không phải HTTP GET đơn giản)?

Trang của An Phát được **render bằng JavaScript**. Nếu bạn chỉ tải HTML thô, giá vẫn chưa xuất hiện
— HTML gửi về chỉ chứa các *khung mẫu (template)* như `${priceFormat}` mà JavaScript của trang sẽ
điền vào *sau khi* nó tải xong. Vì vậy chúng ta dùng **Playwright** để điều khiển một Chromium thực
sự (ở chế độ headless): nó chạy JS của trang, và *sau đó* chúng ta đọc trang đã hoàn chỉnh.

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)   # invisible browser
    page = browser.new_page(user_agent=...)        # pretend to be a normal Chrome
    page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=45000)
```

**Vì sao dùng `wait_until="domcontentloaded"` chứ không phải `"networkidle"`?** "networkidle" chờ
cho đến khi mạng ngừng hoạt động — nhưng An Phát luôn giữ các kết nối mở cho trình theo dõi
(trackers), nên nó *không bao giờ* ngừng hoạt động và sẽ bị timeout. Thay vào đó chúng ta tải DOM,
rồi chủ động **chờ phần tử giá** xuất hiện:

```python
page.wait_for_selector(PRICE_SELECTOR, timeout=20000)   # ".p-price"
```

Đó là tín hiệu đáng tin cậy cho thấy lưới sản phẩm đã thực sự được render.

---

## Các selector (cách chúng ta tìm dữ liệu trên trang)

Những selector này được tìm ra bằng cách kiểm tra trang đã render trong DevTools của trình duyệt:

```python
CARD_SELECTOR  = ".p-text"      # the container for one product card
NAME_SELECTOR  = "a.p-name"     # the product link: href = URL, text = name
PRICE_SELECTOR = ".p-price"     # the CURRENT price (NOT .p-old-price, the crossed-out one)
```

Chi tiết `.p-old-price` rất quan trọng: các cửa hàng hiển thị giá khuyến mãi bên cạnh giá gốc bị
gạch ngang. Chúng ta phải nhắm vào giá **hiện tại** (`.p-price`), nếu không phép so sánh sẽ dùng
nhầm con số.

---

## Vấn đề nút "Xem thêm" (view more)

An Phát chỉ hiển thị ~30 laptop lúc đầu; phần còn lại nằm sau nút **"Xem thêm" (View more)** để tải
thêm qua JavaScript. Nếu chúng ta không bấm vào nút này, chúng ta sẽ bỏ lỡ một nửa danh mục.

```python
stale = 0
for _ in range(40):
    btn = page.query_selector(".btn-view-more")
    if not btn or not btn.is_visible():
        break                                  # button gone = everything loaded
    before = len(page.query_selector_all(CARD_SELECTOR))
    page.click(".btn-view-more", timeout=5000)
    page.wait_for_timeout(2000)                # wait for the new batch to render
    after = len(page.query_selector_all(CARD_SELECTOR))
    stale = stale + 1 if after == before else 0
    if stale >= 3:                             # 3 clicks with no new cards = done
        break
```

Bộ đếm `stale` là mấu chốt của thủ thuật này: một lần bấm "không có sản phẩm mới" có thể chỉ là do
một đợt tải mạng chậm, nên chúng ta chỉ dừng lại sau **3 lần bấm liên tiếp** không tăng thêm sản
phẩm. Điều này đã giúp An Phát tăng từ ~17 lên ~33 sản phẩm khớp.

---

## Trích xuất dữ liệu

Khi mọi thứ đã tải xong, lặp qua từng thẻ sản phẩm (card) và lấy tên + giá + url:

```python
seen = set()
for card in page.query_selector_all(CARD_SELECTOR):
    name  = card.query_selector(NAME_SELECTOR).inner_text().strip()
    price = _digits_to_int(card.query_selector(PRICE_SELECTOR).inner_text())
    href  = card.query_selector(NAME_SELECTOR).get_attribute("href")
    url   = BASE_URL + href if href.startswith("/") else href

    # keep only laptops (search returns accessories too), and de-dupe by URL
    if name.lower().startswith("laptop") and url not in seen:
        seen.add(url)
        results.append({"name": name, "price": price, "url": url})
```

`_digits_to_int` loại bỏ mọi ký tự không phải chữ số: `"22.490.000 ₫"` → `22490000`.

Tập hợp `seen` giúp loại bỏ trùng lặp — một số trang render mỗi thẻ sản phẩm hai lần (biến thể
desktop + mobile).

---

## `main()` — so khớp và ghi dữ liệu

Phần này giống hệt nhau ở mọi scraper đối thủ:

```python
client = get_client()
ensure_competitor(client, COMPETITOR)               # register "An Phát PC" in the registry

# load every SKU TNC stocks — ONE query, kept in memory
tracked = { row["sku"] for row in client.table("products").select("sku").execute().data }

for item in discover():
    sku = derive_sku(item["name"], item["url"])     # canonical key (see sku-matching.md)
    if sku not in tracked:
        continue                                     # we don't sell it → skip, no DB write

    # matched! record it:
    client.table("sources").upsert(                  # one listing per (product, competitor)
        {"product_sku": sku, "competitor": COMPETITOR, "url": item["url"]},
        on_conflict="product_sku,competitor",
    ).execute()
    insert_price(client, sku, COMPETITOR, item["price"])   # append a price observation
```

Các điểm chính:
- **So khớp trước, ghi dữ liệu sau.** Chúng ta không bao giờ ghi giá cho một laptop mà TNC không
  bán.
- **`sources` được upsert** (một dòng cho mỗi cặp sản phẩm×đối thủ, được cập nhật mỗi lần chạy).
- **`price_history` được thêm vào (append)** (một dòng mới mỗi lần chạy → tích luỹ lịch sử giá theo
  thời gian).
- Xem [`sku-matching.md`](sku-matching.md) để biết cách `derive_sku` quyết định "có phải cùng một
  laptop?".

---

## Chạy scraper

```bash
python -m scraper.discover_anphat --dry   # print what it finds, write nothing
python -m scraper.discover_anphat          # write prices to Supabase
```

> An Phát **không cần proxy** — có thể truy cập từ bất kỳ đâu. So sánh với
> [`scraper-fptshop.md`](scraper-fptshop.md), tài liệu nói về một site **bị chặn theo vị trí địa
> lý** và *cần* proxy dân dụng (residential) tại Việt Nam.
</content>
