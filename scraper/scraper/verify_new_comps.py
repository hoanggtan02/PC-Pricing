import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append('C:/xampp/htdocs/Tan/PC-Pricing/scraper')
from scraper.db import get_client

client = get_client()

for comp in ['Vũ Hoàng Telecom', 'Wifi.com.vn']:
    srcs = client.table('sources').select('product_sku,url').eq('competitor', comp).execute().data
    prices = client.table('latest_prices_cache').select('sku,price,in_stock,url').eq('competitor', comp).execute().data
    print(f"\n=== {comp} ===")
    print(f"  - Tổng số link sources: {len(srcs)}")
    print(f"  - Tổng số bản ghi giá trong cache: {len(prices)}")
    if prices:
        print("  - Một số sản phẩm mẫu:")
        for p in prices[:4]:
            sku = p['sku']
            price = p.get('price') or 0
            stock = p.get('in_stock')
            print(f"    + {sku}: {price:,} đ | Còn hàng: {stock}")
