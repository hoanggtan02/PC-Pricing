"""Script import dữ liệu sản phẩm TNC từ các file XML Google Shopping Feed.
Cách dùng:
    python -m scraper.import_xml          # Import dữ liệu vào Supabase
    python -m scraper.import_xml --dry    # Chạy thử nghiệm và in kết quả, không ghi vào DB
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Fix Windows console encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from .db import get_client, upsert_products, upsert_sources, insert_prices
from .brand import brand_of
from .sku import derive_sku

XML_DIR = Path(__file__).resolve().parent.parent / "xml"

# Danh mục hợp lệ của database
VALID_CATEGORIES = {
    "Monitor", "Cpu", "Vga", "Mainboard", "Printer", "Scanner", "Ups", 
    "Projector", "Tv", "Tablet", "Ram", "Ssd", "Hdd", "Keyboard", 
    "Mouse", "Combo", "Webcam", "Usb", "Memcard", "Box", "Router", 
    "Switch", "Accesspoint", "Pc", "Server", "Workstation"
}

def clean_price(price_text: str) -> int | None:
    if not price_text:
        return None
    # Trích xuất số từ các dạng: "52590000 VND", "48.990.000đ", "1090000"
    digits = re.sub(r"[^\d]", "", price_text)
    return int(digits) if digits else None

def detect_category(product_type: str, file_name: str, title: str) -> str | None:
    """Xác định danh mục hệ thống dựa trên thông tin XML."""
    pt = (product_type or "").lower()
    fn = file_name.lower()
    t = (title or "").lower()

    # 1. Dựa trên tên file XML
    if "laptop" in fn:
        return "Laptop"
    if "man-hinh-lcd" in fn or "màn hình" in pt:
        return "Monitor"
    if "pc-server" in fn:
        if "workstation" in t or "máy trạm" in t or "may tram" in pt:
            return "Workstation"
        if "server" in t or "máy chủ" in t or "may chu" in pt:
            return "Server"
        return "Pc"
    if "camera" in fn:
        if "webcam" in t or "webcam" in pt:
            return "Webcam"
        return None # Bỏ qua camera an ninh nếu không theo dõi

    # 2. Dựa trên g:product_type
    if "hdd/ssd" in pt or "ssd/hdd" in pt:
        if "ssd" in t:
            return "Ssd"
        return "Hdd"
    if "cpu" in pt or "bộ vi xử lý" in pt or "bo vi xu ly" in pt:
        return "Cpu"
    if "vga" in pt or "card màn hình" in pt or "card man hinh" in pt or "card đồ họa" in pt:
        return "Vga"
    if "mainboard" in pt or "bo mạch chủ" in pt or "bo mach chu" in pt:
        return "Mainboard"
    if "ram" in pt:
        return "Ram"
    if "ssd" in pt or "ổ cứng ssd" in pt or "o cung ssd" in pt:
        return "Ssd"
    if "hdd" in pt or "ổ cứng hdd" in pt or "o cung hdd" in pt:
        # Nếu là HDD di động thì bỏ qua hoặc để dưới dạng Hdd thông thường
        return "Hdd"
    if "router" in pt or "bộ phát wifi" in pt or "wireless" in pt:
        return "Router"
    if "switch" in pt:
        return "Switch"
    if "access point" in pt:
        return "Accesspoint"
    if "bàn phím" in pt or "keyboard" in pt:
        return "Keyboard"
    if "chuột" in pt or "mouse" in pt:
        return "Mouse"
    if "usb" in pt:
        return "Usb"
    if "thẻ nhớ" in pt:
        return "Memcard"
    if "box" in pt or "docking" in pt or "hộp đựng ổ cứng" in pt:
        return "Box"
    if "máy in" in pt or "printer" in pt:
        return "Printer"
    if "may scan" in pt or "máy scan" in pt or "scanner" in pt:
        return "Scanner"
    if "bộ lưu điện" in pt or "ups" in pt:
        return "Ups"
    if "máy chiếu" in pt or "projector" in pt:
        return "Projector"

    # 3. Dựa trên tiêu đề sản phẩm (Fallback cuối cùng)
    if "laptop" in t:
        return "Laptop"
    if "màn hình" in t or "lcd" in t or "monitor" in t:
        return "Monitor"
    if "mainboard" in t or "bo mạch chủ" in t:
        return "Mainboard"
    if "card màn hình" in t or "card đồ họa" in t:
        return "Vga"
    
    return None

def parse_xml_file(filepath: Path) -> list[dict]:
    """Parse một file XML Google Feed và trả về danh sách các sản phẩm thô."""
    filename = filepath.name
    print(f"Đang đọc file {filename}...")
    
    products_raw = []
    try:
        # Google Shopping Feed thường dùng namespaces
        namespaces = {
            'g': 'http://base.google.com/ns/1.0'
        }
        
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        # Tìm các tag <item>
        items = root.findall('.//item')
        print(f"  → Tìm thấy {len(items)} thẻ <item>.")
        
        for item in items:
            title_el = item.find('title')
            link_el = item.find('link')
            
            title = title_el.text.strip() if title_el is not None else ""
            link = link_el.text.strip() if link_el is not None else ""
            
            if not title or not link:
                continue
                
            # Đọc các tag g:
            id_el = item.find('g:id', namespaces)
            price_el = item.find('g:price', namespaces)
            sale_price_el = item.find('g:sale_price', namespaces)
            brand_el = item.find('g:brand', namespaces)
            availability_el = item.find('g:availability', namespaces)
            product_type_el = item.find('g:product_type', namespaces)
            
            id_str = id_el.text.strip() if id_el is not None else ""
            shop_sku = id_str.split('-')[0] if id_str else None
            
            price_str = price_el.text.strip() if price_el is not None else ""
            sale_price_str = sale_price_el.text.strip() if sale_price_el is not None else ""
            
            # Ưu tiên lấy sale_price (giá bán hiện tại), nếu không có thì lấy price gốc
            actual_price = clean_price(sale_price_str) or clean_price(price_str)
            
            brand = brand_el.text.strip() if brand_el is not None else brand_of(title)
            availability = availability_el.text.strip() if availability_el is not None else "in stock"
            product_type = product_type_el.text.strip() if product_type_el is not None else ""
            
            in_stock = (availability.lower() == "in stock" or "in_stock" in availability.lower())
            
            products_raw.append({
                "title": title,
                "link": link,
                "price": actual_price,
                "brand": brand,
                "in_stock": in_stock,
                "product_type": product_type,
                "file_name": filename,
                "shop_sku": shop_sku
            })
            
    except Exception as e:
        print(f"  ❌ Lỗi khi đọc file {filename}: {e}")
        
    return products_raw

def main():
    parser = argparse.ArgumentParser(description="Import TNC product catalog from local XML feeds.")
    parser.add_argument("--dry", action="store_true", help="dry run (don't write to DB)")
    args = parser.parse_args()

    if not XML_DIR.exists() or not XML_DIR.is_dir():
        print(f"Thư mục chứa XML không tồn tại: {XML_DIR}")
        sys.exit(1)
        
    xml_files = list(XML_DIR.glob("*.xml"))
    if not xml_files:
        print(f"Không tìm thấy file XML nào trong: {XML_DIR}")
        sys.exit(0)

    print(f"Tìm thấy {len(xml_files)} file XML. Bắt đầu xử lý...")
    
    all_raw_items = []
    for filepath in xml_files:
        all_raw_items.extend(parse_xml_file(filepath))
        
    print(f"\nTổng cộng: Parse được {len(all_raw_items)} sản phẩm từ tất cả các file XML.")
    
    # Chuẩn hóa, lọc và gán SKU
    products_to_upsert = []
    sources_to_upsert = []
    prices_to_insert = []
    
    skipped_no_sku = 0
    skipped_no_cat = 0
    skipped_no_price = 0
    
    seen_skus = set()

    for item in all_raw_items:
        # 1. Phát hiện category
        cat = detect_category(item["product_type"], item["file_name"], item["title"])
        if not cat:
            skipped_no_cat += 1
            continue
            
        # 2. Derive SKU
        sku = derive_sku(item["title"], item["link"], cat)
        if not sku:
            skipped_no_sku += 1
            continue
            
        # 3. Lọc giá hợp lệ
        if not item["price"]:
            skipped_no_price += 1
            continue
            
        # Tránh trùng SKU trong chính file XML nhập vào
        if sku in seen_skus:
            continue
        seen_skus.add(sku)
            
        # Chuẩn bị dữ liệu ghi vào DB
        products_to_upsert.append({
            "sku": sku,
            "name": item["title"],
            "brand": item["brand"],
            "category": cat,
            "shop_sku": item["shop_sku"]
        })
        
        sources_to_upsert.append({
            "product_sku": sku,
            "competitor": "Thành Nhân",
            "url": item["link"],
            "active": True
        })
        
        prices_to_insert.append({
            "product_sku": sku,
            "competitor": "Thành Nhân",
            "price": item["price"],
            "in_stock": item["in_stock"]
        })

    print(f"\nSau khi lọc và chuẩn hóa:")
    print(f"  - Sản phẩm hợp lệ để nạp: {len(products_to_upsert)}")
    print(f"  - Bị loại do không xác định được Category: {skipped_no_cat}")
    print(f"  - Bị loại do không trích xuất được SKU (hoặc bị loại bỏ do từ khóa sản phẩm cũ): {skipped_no_sku}")
    print(f"  - Bị loại do không có giá: {skipped_no_price}")

    if not args.dry:
        if products_to_upsert:
            print("\nĐang ghi nhận vào Supabase...")
            client = get_client()
            
            # Ghi vào DB
            upsert_products(client, products_to_upsert)
            print(f"  ✅ Đã cập nhật danh mục {len(products_to_upsert)} sản phẩm TNC vào bảng 'products'.")
            
            upsert_sources(client, sources_to_upsert)
            print(f"  ✅ Đã cập nhật {len(sources_to_upsert)} nguồn cào của Thành Nhân.")
            
            insert_prices(client, prices_to_insert)
            print(f"  ✅ Đã ghi nhận {len(prices_to_insert)} bản ghi giá mới nhất của Thành Nhân.")
            
            # Refresh views
            print("Đang làm mới cache latest_prices...")
            try:
                client.rpc("refresh_latest_prices").execute()
                print("  ✅ Làm mới cache thành công.")
            except Exception as e:
                print(f"  ❌ Lỗi khi làm mới cache: {e}")
        else:
            print("\nKhông có sản phẩm nào hợp lệ để ghi vào DB.")
    else:
        print("\n[Dry Run] Không có dữ liệu nào được ghi vào cơ sở dữ liệu.")
        # In một số sản phẩm mẫu
        if products_to_upsert:
            print("\nMột số sản phẩm mẫu:")
            for i in range(min(5, len(products_to_upsert))):
                p = products_to_upsert[i]
                pr = prices_to_insert[i]
                print(f"  - [{p['category']}] {p['sku']}: {p['name']} ({pr['price']:,} VND) - InStock: {pr['in_stock']}")

if __name__ == "__main__":
    main()
