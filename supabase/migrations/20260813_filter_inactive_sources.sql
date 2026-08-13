-- Không đưa nguồn đã tắt vào latest_prices_cache hay các view dashboard phụ thuộc.
-- Chạy migration này trên Supabase sau khi deploy mã PHP.
create or replace function refresh_latest_prices() returns void
language plpgsql security definer as $$
begin
    delete from latest_prices_cache where true;
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
    join products p on p.sku = ph.product_sku
    join competitors co on co.name = ph.competitor
    join cat_cutoff cc on cc.category = p.category
    join sources s on s.product_sku = ph.product_sku
                  and s.competitor = ph.competitor
                  and s.active
    where ph.scraped_at > cc.cutoff
    order by ph.product_sku, ph.competitor, ph.scraped_at desc;
end;
$$;

-- Làm sạch ngay snapshot hiện tại sau khi thay hàm.
select refresh_latest_prices();
