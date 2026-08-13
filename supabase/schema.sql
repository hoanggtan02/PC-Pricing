-- Schema của PC Pricing Dashboard. Lý do thiết kế: docs/schema-design.md
-- Sử dụng natural key xuyên suốt; bảng price_history chỉ ghi thêm (append-only), là nguồn dữ liệu
-- cho một chuỗi các view so sánh chỉ đọc (read-only).

create table if not exists products (
    sku         text primary key,
    name        text not null,
    brand       text not null default 'Dell',
    category    text not null default 'Laptop',
    created_at  timestamptz not null default now()
);

create table if not exists competitors (
    name        text primary key,
    is_self     boolean not null default false,  -- true nếu là cửa hàng CỦA CHÍNH TA (Thành Nhân)
    created_at  timestamptz not null default now()
);

create table if not exists sources (
    product_sku  text not null
        references products (sku) on update cascade on delete cascade,
    competitor   text not null
        references competitors (name) on update cascade on delete cascade,
    url          text not null,
    active       boolean not null default true,
    created_at   timestamptz not null default now(),
    primary key (product_sku, competitor)
);

-- Append-only: mỗi lần scrape sẽ chèn thêm một dòng mới; không bao giờ cập nhật lại.
create table if not exists price_history (
    id           bigint generated always as identity primary key,
    product_sku  text not null,
    competitor   text not null,
    price        numeric(14, 2) not null,
    currency     text not null default 'VND',
    in_stock     boolean not null default true,  -- đối thủ có thể niêm yết giá dù đã hết hàng (OOS)
    is_flash_sale boolean not null default false, -- true nếu `price` là giá flash sale (chỉ TNC phát hiện)
    scraped_at   timestamptz not null default now(),
    foreign key (product_sku, competitor)
        references sources (product_sku, competitor)
        on update cascade on delete cascade
);

create index if not exists idx_price_history_source_time
    on price_history (product_sku, competitor, scraped_at desc);
-- Giúp CTE cat_cutoff của latest_prices (max scraped_at theo danh mục) và các lọc theo thời gian.
create index if not exists idx_price_history_scraped_at
    on price_history (scraped_at desc);

-- latest_prices: CHỈ hiển thị kết quả của lần scrape GẦN NHẤT, không phải "giá mới nhất từng biết".
-- Mỗi lần chạy scrape ghi dữ liệu trong ~40 phút (các scraper chạy tuần tự), và các lần chạy cách
-- nhau ~6 giờ. Ta lấy scraped_at mới nhất rồi chỉ giữ các dòng trong 2 giờ trước đó — cửa sổ này
-- gọn gàng bao trọn đúng MỘT lần chạy và không lấn sang lần chạy trước.
-- Đánh đổi (được chấp nhận): nếu lần chạy gần nhất scrape được ít sản phẩm hơn (một competitor lỗi/
-- timeout), dashboard sẽ hiển thị ít sản phẩm hơn — nhưng bù lại, MỌI giá hiển thị đều là giá mới
-- nhất thực sự, nên quyết định kinh doanh dựa trên đó luôn chính xác. Không "trộn" giá cũ từ lần
-- chạy trước vào.
-- Cửa sổ THEO TỪNG DANH MỤC (không phải toàn cục). Mỗi danh mục được scrape vào thời điểm khác
-- nhau; nếu neo theo max(scraped_at) toàn cục, ghi một danh mục MỚI (ví dụ RAM lúc 01:00) sẽ đẩy
-- cửa sổ qua khỏi các dòng laptop cũ (23:00) và làm chúng biến mất. Neo theo max của CÙNG danh mục.
-- Hiệu năng: tính ngưỡng (cutoff) của MỖI danh mục MỘT LẦN trong CTE `cat_cutoff` rồi JOIN — thay
-- vì subquery tương quan chạy lại cho từng dòng (O(N×M) → timeout khi price_history lớn).
-- HIỆU NĂNG: latest_prices đọc từ BẢNG cache latest_prices_cache (đã tính sẵn) thay vì tính lại
-- ~1.2s mỗi request → dashboard đọc ~50ms. Phần tính nặng (quét toàn bộ price_history lấy giá mới
-- nhất mỗi cặp sku×cửa hàng) chạy 1 lần vào bảng cache, do hàm refresh_latest_prices() thực hiện SAU
-- mỗi lần scrape (scraper/refresh_views.py gọi ở cuối CI). latest_prices thành view MỎNG select-only.
-- Dùng BẢNG THẬT (không phải materialized view) theo gợi ý review: dễ refresh/monitor/rollback/thêm
-- cột sau này. refreshed_at = mốc refresh gần nhất → dashboard hiện "cập nhật lúc" + health-check.
-- (Migration: supabase/migrations/20260727_materialize_latest_prices.sql)
create table if not exists latest_prices_cache (
    sku          text not null,
    product_name text,
    brand        text,
    category     text,
    competitor   text not null,
    is_self      boolean,
    price        numeric(14, 2),
    currency     text,
    in_stock     boolean,
    is_flash_sale boolean,
    scraped_at   timestamptz,
    url          text,
    refreshed_at timestamptz not null default now(),
    primary key (sku, competitor)
);
create index if not exists latest_prices_cache_category   on latest_prices_cache (category);
create index if not exists latest_prices_cache_competitor on latest_prices_cache (competitor);

-- RLS: dashboard đọc bảng này bằng anon key → bật RLS + policy chỉ-đọc (giống các bảng gốc bên dưới).
alter table latest_prices_cache enable row level security;
create policy "public read latest_prices_cache"
    on latest_prices_cache for select to anon, authenticated using (true);

-- Hàm refresh: tính lại giá mới nhất mỗi (sku × cửa hàng) rồi thay TOÀN BỘ bảng. delete+insert nằm
-- trong 1 transaction (thân function nguyên tử) → người đọc giữa lúc refresh thấy trọn snapshot cũ,
-- xong commit thì lần đọc sau thấy trọn snapshot mới. Logic dedup y hệt view latest_prices cũ.
create or replace function refresh_latest_prices() returns void
language plpgsql security definer as $$
begin
    delete from latest_prices_cache where true;  -- `where true` để qua chốt an toàn "DELETE requires WHERE" của Supabase
    insert into latest_prices_cache
        (sku, product_name, brand, category, competitor, is_self,
         price, currency, in_stock, is_flash_sale, scraped_at, url, refreshed_at)
    with cat_cutoff as (
        select p2.category, max(ph2.scraped_at) - interval '12 hours' as cutoff
        from price_history ph2
        join products p2 on p2.sku = ph2.product_sku
        group by p2.category
    )
    select distinct on (ph.product_sku, ph.competitor)
        p.sku, p.name, p.brand, p.category, ph.competitor, co.is_self,
        ph.price, ph.currency, ph.in_stock, ph.is_flash_sale, ph.scraped_at, s.url, now()
    from price_history ph
    join products    p  on p.sku = ph.product_sku
    join competitors co on co.name = ph.competitor
    join cat_cutoff  cc on cc.category = p.category
    -- Nguồn đã tắt không được đưa vào snapshot/dashboard. Dùng inner join vì price_history
    -- có foreign key tới sources; `active` vì thế là công tắc hiển thị lẫn scrape hiệu lực.
    join sources s on s.product_sku = ph.product_sku
                  and s.competitor = ph.competitor
                  and s.active
    where ph.scraped_at > cc.cutoff
    order by ph.product_sku, ph.competitor, ph.scraped_at desc;
end;
$$;

-- View mỏng: mọi view phụ thuộc đọc latest_prices THEO TÊN → không cần sửa gì.
create or replace view latest_prices as select * from latest_prices_cache;

-- price_stats: thị trường chỉ tính đối thủ theo từng sản phẩm (loại trừ ta; chỉ tính hàng còn trong kho).
create or replace view price_stats as
select
    sku,
    product_name,
    brand,
    category,
    count(*)                                            as num_sources,
    round(avg(price))                                   as mean_price,
    percentile_cont(0.5) within group (order by price)  as median_price,
    min(price)                                          as lowest_price,
    max(price)                                          as highest_price
from latest_prices
where not is_self and in_stock
group by sku, product_name, brand, category;

-- price_comparison: giá của ta so với thị trường. delta/pct dương nghĩa là ta đang cao hơn giá trung bình thị trường.
create or replace view price_comparison as
select
    st.sku,
    st.product_name,
    st.brand,
    st.category,
    self.price                                          as our_price,
    st.num_sources,
    st.mean_price,
    st.median_price,
    st.lowest_price,
    st.highest_price,
    (self.price - st.mean_price)                        as delta_vs_mean,
    round((self.price - st.mean_price) / st.mean_price * 100, 1) as pct_vs_mean
from price_stats st
-- Chỉ lấy giá của TA khi CÒN HÀNG (in_stock). Hàng hết được lưu price=0; nếu không lọc, chúng sẽ
-- khiến ta trông như "rẻ hơn 100%" thay vì hết hàng.
left join latest_prices self
    on self.sku = st.sku and self.is_self and self.in_stock;

-- product_overview: một dòng sẵn sàng hiển thị cho mỗi sản phẩm (pivot + so sánh được thực hiện trong SQL).
-- DROP trước: create-or-replace không thể thêm/sắp xếp lại cột của view.
drop view if exists product_overview;
create view product_overview as
with by_competitor as (
    select
        sku,
        product_name,
        brand,
        category,
        -- giá của mọi cửa hàng, sắp xếp từ rẻ nhất; nếu bằng giá, cửa hàng của ta xếp trước
        jsonb_agg(
            jsonb_build_object(
                'store', competitor, 'price', price, 'is_self', is_self,
                'url', url, 'in_stock', in_stock, 'is_flash_sale', is_flash_sale)
            order by price, is_self desc
        )                                                                as prices_by_store,
        -- 3 cột xếp hạng "rẻ nhất": CHỈ xét cửa hàng CÒN HÀNG — đối thủ giá thấp nhưng HẾT HÀNG không
        -- được chiếm vị trí rẻ nhất (nếu không: lowest_store trỏ vào OOS, we_are_lowest sai, badge
        -- "lowest" không hiện). prices_by_store vẫn giữ cả OOS để hiển thị (gạch ngang ở UI).
        (array_agg(competitor order by price) filter (where not is_self and in_stock))[1]
                                                                         as cheapest_competitor,
        (array_agg(competitor order by price, is_self desc) filter (where in_stock))[1]
                                                                         as lowest_store,
        (array_agg(is_self order by price, is_self desc) filter (where in_stock))[1]
                                                                         as we_are_lowest,
        -- giá của TA chỉ khi CÒN HÀNG; hàng hết (price=0) hiển thị our_price=null ("—"), không phải 0.
        max(price) filter (where is_self and in_stock)                   as our_price,
        -- TA có còn hàng SKU này không (dùng để LOẠI sản phẩm ta hết hàng khỏi bảng so sánh).
        bool_or(is_self and in_stock)                                    as we_in_stock,
        max(scraped_at)                                                  as last_scraped
    from latest_prices
    group by sku, product_name, brand, category
)
-- Chỉ hiển thị sản phẩm TA đang CÒN HÀNG. Sản phẩm ta hết hàng (hoặc không còn trong catalog hiện
-- tại) bị loại khỏi bảng so sánh giá — chúng đã có riêng ở view out_of_stock_gap.
-- LEFT JOIN để sản phẩm ta còn hàng nhưng chưa có đối thủ vẫn xuất hiện (cột thị trường = null).
select
    c.sku,
    c.product_name,
    c.brand,
    c.category,
    c.prices_by_store,
    c.cheapest_competitor,
    c.lowest_store,
    c.we_are_lowest,
    c.our_price,
    c.last_scraped,
    pc.num_sources,
    pc.mean_price,
    pc.median_price,
    pc.lowest_price,
    pc.highest_price,
    pc.delta_vs_mean,
    pc.pct_vs_mean
from by_competitor c
left join price_comparison pc on pc.sku = c.sku
where c.we_in_stock
order by coalesce(pc.num_sources, 0) desc, c.sku;

-- needs_attention: sản phẩm "bị đối thủ (CÒN HÀNG) bán rẻ hơn" = our_price > lowest_price. lowest_price
-- (price_stats) CHỈ tính đối thủ `not is_self and in_stock` → so đúng với giá mua được. KHÔNG dùng
-- we_are_lowest (cột đó tính cả đối thủ HẾT HÀNG → giá OOS rẻ hơn làm nó =false dù ta rẻ nhất trong hàng
-- còn bán → lọt +0%/-1%). Giá bằng nhau không tính. Tệ-nhất-trước theo % ta đắt hơn giá rẻ nhất.
create or replace view needs_attention as
select *
from product_overview
where our_price > lowest_price
order by (our_price - lowest_price) / lowest_price desc;

-- out_of_stock_gap: sản phẩm mà TA (Thành Nhân) đang HẾT HÀNG nhưng có ÍT NHẤT MỘT đối thủ CÒN
-- HÀNG — cơ hội bị mất doanh số. Chỉ tính lần scrape gần nhất (latest_prices đã lọc theo cửa sổ
-- 2 giờ) nên các dòng cũ/tồn kho không gây dương tính giả.
--   - we_in_stock  = false : ta có SKU này nhưng in_stock=false ("Liên hệ")
--   - competitors_in_stock >= 1 : có đối thủ đang còn hàng
-- Sắp xếp theo số đối thủ còn hàng giảm dần (cạnh tranh gắt nhất trước), rồi theo giá đối thủ thấp
-- nhất (mất khách vào tay ai rẻ nhất).
create or replace view out_of_stock_gap as
with by_sku as (
    select
        sku,
        product_name,
        brand,
        category,
        -- ta còn hàng không? (dòng is_self của SKU này trong lần scrape gần nhất)
        bool_or(is_self and in_stock)                                  as we_in_stock,
        -- ta có mặt trong lần scrape này không? (phân biệt "ta hết hàng" với "không scrape thấy ta")
        bool_or(is_self)                                               as we_present,
        count(*) filter (where not is_self and in_stock)               as competitors_in_stock,
        min(price) filter (where not is_self and in_stock)             as cheapest_competitor_price,
        (array_agg(competitor order by price)
            filter (where not is_self and in_stock))[1]                as cheapest_competitor,
        -- URL của đối thủ rẻ nhất (cùng thứ tự sort theo giá) để dashboard link tới nơi mua được.
        (array_agg(url order by price)
            filter (where not is_self and in_stock))[1]                as cheapest_competitor_url,
        -- URL trang của TA cho sản phẩm này (để xem/khôi phục hàng).
        max(url) filter (where is_self)                                as our_url
    from latest_prices
    group by sku, product_name, brand, category
)
select
    sku,
    product_name,
    brand,
    category,
    competitors_in_stock,
    cheapest_competitor,
    cheapest_competitor_price,
    cheapest_competitor_url,
    our_url
from by_sku
where we_present                    -- ta có theo dõi SKU này
  and not we_in_stock               -- nhưng ta đang HẾT HÀNG
  and competitors_in_stock >= 1     -- và có đối thủ CÒN HÀNG
order by competitors_in_stock desc, cheapest_competitor_price asc;

-- out_of_stock_gap_by_category: SỐ LƯỢNG sản phẩm OOS-gap theo từng danh mục (group + count trong
-- SQL). Landing chỉ cần con số này cho mỗi thẻ danh mục → trả ~11 dòng thay vì tải toàn bộ chi
-- tiết OOS rồi tự đếm ở frontend.
create or replace view out_of_stock_gap_by_category as
select category, count(*) as n
from out_of_stock_gap
group by category;

-- competitor_coverage: số lượng sản phẩm khớp theo từng (brand, category), theo từng đối thủ.
-- CROSS JOIN trên các cặp (brand, category) có thật để một cửa hàng không có hàng của tổ hợp nào
-- đó vẫn xuất hiện với products_matched = 0. latest_prices đã mang sẵn brand + category nên không
-- cần JOIN thêm products (tránh nhân dòng làm sai count/avg).
-- DROP trước: create-or-replace không thể chèn cột mới ở giữa.
drop view if exists competitor_coverage;
create view competitor_coverage as
select
    co.name,
    co.is_self,
    bc.brand,
    bc.category,
    count(lp.sku)                          as products_matched,
    coalesce(round(avg(lp.price)), 0)      as avg_price
from competitors co
cross join (select distinct brand, category from products) bc
left join latest_prices lp
       on lp.competitor = co.name and lp.brand = bc.brand and lp.category = bc.category
group by co.name, co.is_self, bc.brand, bc.category
order by co.is_self desc, bc.brand, products_matched desc, co.name;

-- competitor_coverage_all: tổng hợp trên tất cả các brand (nhưng vẫn theo từng category), dùng cho
-- view "All brands" của một danh mục.
drop view if exists competitor_coverage_all;
create view competitor_coverage_all as
select
    co.name,
    co.is_self,
    cat.category,
    count(lp.sku)                          as products_matched,
    coalesce(round(avg(lp.price)), 0)      as avg_price
from competitors co
cross join (select distinct category from products) cat
left join latest_prices lp on lp.competitor = co.name and lp.category = cat.category
group by co.name, co.is_self, cat.category
order by co.is_self desc, products_matched desc, co.name;

-- comparable_coverage: độ phủ trên các sản phẩm SO SÁNH ĐƯỢC (TA còn hàng). Với mỗi (category,
-- competitor): đếm số sản phẩm mà CẢ TA và đối thủ đó ĐỀU còn hàng. Đây là con số đúng để hiện
-- cạnh bảng so giá — khác competitor_coverage (đếm mọi SKU khớp trong catalog, kể cả hàng ta hết,
-- nên có thể báo "13" trong khi chỉ 2 sản phẩm so được, và 13 đó không trùng 2 sản phẩm đang hiện).
-- `comparable_total` = tổng sản phẩm ta còn hàng trong danh mục (mẫu số, giống product_overview).
-- Tính hết trong SQL để frontend chỉ đọc kết quả (không lặp prices_by_store ở client).
create or replace view comparable_coverage as
with self_instock as (   -- các SKU mà TA còn hàng, theo danh mục (tập "so sánh được")
    select distinct sku, category
    from latest_prices
    where is_self and in_stock
),
totals as (              -- mẫu số: tổng sản phẩm ta còn hàng mỗi danh mục
    select category, count(*) as comparable_total
    from self_instock
    group by category
)
select
    co.name,
    co.is_self,
    si.category,
    t.comparable_total,
    -- tử số: trong tập ta còn hàng, đối thủ này cũng còn hàng bao nhiêu sản phẩm
    count(*) filter (where lp.in_stock)                     as products_matched
from competitors co
cross join self_instock si
join totals t on t.category = si.category
left join latest_prices lp
       on lp.sku = si.sku and lp.competitor = co.name and lp.in_stock
where not co.is_self
group by co.name, co.is_self, si.category, t.comparable_total
order by si.category, products_matched desc, co.name;

-- ── Các view theo TỪNG DANH MỤC ──────────────────────────────────────────────────────────────────
-- Chuỗi view ở trên (latest_prices → … → product_overview, competitor_coverage) là ĐA DANH MỤC:
-- chúng mang `category` xuyên suốt nhưng không lọc theo nó. Dashboard đọc các view per-category
-- MỎNG bên dưới, mỗi cái chỉ là một bộ lọc `where category = '<Danh mục>'` trên view chung.
--
-- Nhờ vậy, thêm một danh mục mới = thêm 3 view một-dòng ở đây (không đụng gì tới chuỗi tính toán),
-- và dashboard chỉ cần một dropdown chọn tên view (product_overview_laptop / _monitor / …).
-- Khi thêm danh mục mới: copy 3 dòng cuối, đổi 'Laptop' thành danh mục mới.

-- Laptop
create or replace view product_overview_laptop as
    select * from product_overview where category = 'Laptop';
-- (needs_attention_laptop bỏ đi: thừa với needs_attention — view đó đã có cột category, lọc bằng
--  `where category='Laptop'`. Không ai đọc bản theo-danh-mục này.)
create or replace view competitor_coverage_laptop as
    select name, is_self, brand, products_matched, avg_price
    from competitor_coverage where category = 'Laptop';
create or replace view competitor_coverage_all_laptop as
    select name, is_self, products_matched, avg_price
    from competitor_coverage_all where category = 'Laptop';
-- out_of_stock_gap là ĐA DANH MỤC (có cả SSD/HDD/…); dashboard laptop đọc bản lọc sẵn này để các
-- mục hết hàng thuộc danh mục khác không lọt vào — front-end không cần tự lọc.
create or replace view out_of_stock_gap_laptop as
    select * from out_of_stock_gap where category = 'Laptop';

-- Monitor (danh mục đầu tiên mở rộng ngoài laptop)
create or replace view product_overview_monitor as
    select * from product_overview where category = 'Monitor';
-- (needs_attention_monitor bỏ đi: thừa với needs_attention — lọc bằng `where category='Monitor'`.)
create or replace view competitor_coverage_monitor as
    select name, is_self, brand, products_matched, avg_price
    from competitor_coverage where category = 'Monitor';
create or replace view competitor_coverage_all_monitor as
    select name, is_self, products_matched, avg_price
    from competitor_coverage_all where category = 'Monitor';

-- RLS: dashboard sử dụng public anon key, nên anon/authenticated chỉ được phép SELECT.
-- Scraper ghi dữ liệu bằng service_role key, key này bỏ qua (bypass) RLS.
alter table products      enable row level security;
alter table competitors   enable row level security;
alter table sources       enable row level security;
alter table price_history enable row level security;

create policy "public read products"      on products      for select to anon, authenticated using (true);
create policy "public read competitors"    on competitors    for select to anon, authenticated using (true);
create policy "public read sources"        on sources        for select to anon, authenticated using (true);
create policy "public read price_history"  on price_history  for select to anon, authenticated using (true);

-- price_activity: TẦN SUẤT ĐỔI GIÁ của mỗi cửa hàng, CHIA THEO TỪNG TUẦN (dashboard có dropdown
-- chọn tuần để "zoom" vào đúng 1 tuần). Mỗi dòng = (cửa hàng × tuần). Dùng cả lịch sử price_history
-- (append-only). Trả lời: "tuần này đối thủ nào đổi giá nhiều nhất, và TA phản ứng chậm cỡ nào?"
--
-- VÌ SAO chia cho SỐ SẢN PHẨM: tổng thô lệch theo ĐỘ PHỦ — cửa hàng ta theo dõi 400 sản phẩm sẽ có
-- nhiều lần đổi hơn cửa hàng ta chỉ theo dõi 20, DÙ cửa hàng 20 sản phẩm đổi giá mỗi ngày. Chia cho
-- số SKU khác nhau khử thiên lệch → đo đúng HÀNH VI đổi giá, không phải độ phủ của ta.
--
-- ĐẾM QUA RANH GIỚI TUẦN (carry-across): một lần đổi = lần scrape có giá khác lần scrape NGAY TRƯỚC
-- (lag không giới hạn trong tuần), được gán vào tuần của lần scrape SAU. Nhờ vậy giá đặt cuối tuần
-- trước, giữ sang tuần này vẫn được tính là 1 lần đổi ở tuần này, không bị bỏ sót ở ranh giới tuần.
--
-- LOẠI nhiễu TRÙNG SKU: bỏ các điểm có nhiều giá khác nhau ở CÙNG (sku, competitor, scraped_at).
-- drop trước vì create-or-replace không đổi được cột (lỗi 42P16) khi nâng cấp view cũ.
drop view if exists price_activity;
create view price_activity as
with clean as (   -- bỏ các điểm bị trùng SKU (cùng sku+competitor+timestamp mà giá khác nhau)
    select ph.product_sku, ph.competitor, ph.price, ph.scraped_at
    from price_history ph
    -- BỎ QUA lúc hết hàng: hàng hết ghi price=0 ("Liên hệ"). 0 → 24.990.000 (có hàng lại) và
    -- 24.990.000 → 0 (hết hàng) KHÔNG phải đổi giá — đó là đổi TRẠNG THÁI KHO. Chỉ TA (Thành Nhân)
    -- ghi price=0, nên nếu không lọc thì cột của CHÍNH TA bị thổi phồng so với đối thủ.
    where ph.in_stock
      and ph.price > 0
      and not exists (
        select 1 from price_history ph2
        where ph2.product_sku = ph.product_sku
          and ph2.competitor  = ph.competitor
          and ph2.scraped_at  = ph.scraped_at
          and ph2.price      <> ph.price
    )
),
seq as (
    -- Đánh dấu "đổi giá" so với lần quan sát NGAY TRƯỚC trong cùng chuỗi (sku, competitor). lag()
    -- KHÔNG giới hạn trong tuần → đổi ở ranh giới tuần vẫn được đếm, gán vào tuần của scrape SAU.
    -- week_start = thứ Hai đầu tuần ISO chứa lần scrape đó (mốc để gộp + nhãn dropdown).
    select
        product_sku,
        competitor,
        scraped_at::date - (extract(isodow from scraped_at)::int - 1)  as week_start,
        price <> lag(price) over (
            partition by product_sku, competitor order by scraped_at
        ) as changed
    from clean
),
agg as (          -- gộp theo (cửa hàng, TUẦN): số lần đổi trong tuần + số sản phẩm khác nhau trong tuần
    select
        competitor,
        week_start,
        count(*) filter (where changed)  as price_changes,
        count(distinct product_sku)      as products
    from seq
    group by competitor, week_start
),
live_weeks as (
    -- Chỉ giữ TUẦN thực sự có dữ liệu đổi giá ở đâu đó — loại tuần đầu (chỉ 1 lần scrape, không SKU
    -- nào có lần quan sát trước để so → 0 đổi toàn bộ). Trong tuần được giữ, cửa hàng đổi 0 lần VẪN
    -- hiện (bar = 0), không biến mất.
    select week_start from agg group by week_start having sum(price_changes) > 0
)
select
    a.competitor,
    coalesce(c.is_self, false)                                    as is_self,
    a.week_start,
    a.price_changes,
    a.products,
    -- Đã zoom đúng 1 TUẦN nên KHÔNG chia cho số tuần nữa — chỉ (đổi / sản phẩm) × 100 → "số lần đổi
    -- giá / 100 sản phẩm / tuần" dạng số nguyên. ::numeric để tránh chia nguyên.
    round(a.price_changes::numeric / nullif(a.products, 0) * 100)::int
        as changes_per_100_products_week
from agg a
join live_weeks lw on lw.week_start = a.week_start
left join competitors c on c.name = a.competitor
where a.products > 0
order by a.week_start desc, changes_per_100_products_week desc nulls last;

-- sku_price_trend_7d: DIỄN BIẾN GIÁ 7 NGÀY GẦN NHẤT của TỪNG SẢN PHẨM tại TỪNG CỬA HÀNG.
-- Mỗi dòng = (sku × cửa hàng). Dashboard hiện stat này cạnh giá của mỗi cửa hàng trong bảng sản phẩm:
-- đã đổi giá mấy lần, tăng hay giảm, và net bao nhiêu %.
--   - changes  = tổng số lần đổi giá trong 7 ngày (tăng + giảm)
--   - increases / decreases = số lần tăng / số lần giảm (một SKU có thể vừa tăng vừa giảm)
--   - direction = 'up' | 'down' | 'flat' — so giá ĐẦU và CUỐI cửa sổ 7 ngày (net), KHÔNG phải lần đổi
--     cuối. Giá bật lên rồi về chỗ cũ → changes=2 nhưng direction='flat', pct_change=0.
--   - pct_change = (giá cuối − giá đầu) / giá đầu × 100, làm tròn 1 chữ số thập phân
-- Chỉ trả về các cặp CÓ đổi giá (changes > 0) → bảng nhẹ; sản phẩm không đổi giá thì frontend hiện "—".
-- CTE clean loại điểm trùng SKU giống các view khác (cùng sku+cửa hàng+timestamp mà giá khác nhau).
--
-- QUAN TRỌNG — BỎ QUA LÚC HẾT HÀNG (in_stock=false / price=0): hàng hết được ghi price=0 ("Liên hệ")
-- hoặc in_stock=false. Nếu tính chúng như một mức giá thì:
--     0 → 24.990.000  = "tăng vô hạn %"  (thực ra chỉ là CÓ HÀNG TRỞ LẠI)
--     24.990.000 → 0  = "giảm 100%"      (thực ra chỉ là HẾT HÀNG)
-- Vì vậy clean CHỈ giữ quan sát có GIÁ THẬT (in_stock và price > 0). lag() nhờ đó so giá thật gần
-- nhất với giá thật kế tiếp, BỎ QUA quãng hết hàng ở giữa — sản phẩm hết hàng rồi có lại đúng giá cũ
-- sẽ cho changes = 0 (đúng), không phải 2 lần "đổi giá" ảo.
create or replace view sku_price_trend_7d as
with clean as (
    select ph.product_sku, ph.competitor, ph.price, ph.scraped_at
    from price_history ph
    where ph.scraped_at >= now() - interval '7 days'
      and ph.in_stock            -- bỏ quan sát lúc hết hàng
      and ph.price > 0           -- bỏ "Liên hệ" (price = 0)
      and not exists (
          select 1 from price_history ph2
          where ph2.product_sku = ph.product_sku
            and ph2.competitor  = ph.competitor
            and ph2.scraped_at  = ph.scraped_at
            and ph2.price      <> ph.price
      )
),
seq as (   -- so với lần quan sát NGAY TRƯỚC của cùng (sku, cửa hàng) trong cửa sổ 7 ngày
    select
        product_sku,
        competitor,
        price,
        scraped_at,
        lag(price) over (partition by product_sku, competitor order by scraped_at) as prev_price,
        first_value(price) over (
            partition by product_sku, competitor order by scraped_at
            rows between unbounded preceding and unbounded following
        ) as first_price,
        last_value(price) over (
            partition by product_sku, competitor order by scraped_at
            rows between unbounded preceding and unbounded following
        ) as last_price
    from clean
)
select
    product_sku,
    competitor,
    count(*) filter (where prev_price is not null and price <> prev_price)  as changes,
    count(*) filter (where prev_price is not null and price >  prev_price)  as increases,
    count(*) filter (where prev_price is not null and price <  prev_price)  as decreases,
    min(first_price)                                                        as first_price,
    min(last_price)                                                         as last_price,
    -- net: so giá đầu vs cuối cửa sổ (không phải lần đổi cuối)
    case
        when min(last_price) > min(first_price) then 'up'
        when min(last_price) < min(first_price) then 'down'
        else 'flat'
    end                                                                     as direction,
    round((min(last_price) - min(first_price))
          / nullif(min(first_price), 0) * 100, 1)                           as pct_change
from seq
group by product_sku, competitor
having count(*) filter (where prev_price is not null and price <> prev_price) > 0
order by changes desc, product_sku;
