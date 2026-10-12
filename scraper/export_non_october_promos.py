import paramiko
import sys
import re
import csv
from collections import Counter
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("thanhnhan.co", port=22, username="root", password="Tnc@19191966", timeout=20)

query = """
SELECT 
    p.maso,
    pd.title,
    pd.friendly_url,
    p.display,
    p.stop_business,
    pp.description
FROM product_promotion pp
INNER JOIN product p ON pp.product_ID = p.product_ID
INNER JOIN product_desc pd ON p.product_ID = pd.product_ID
WHERE pp.description IS NOT NULL AND pp.description != ''
ORDER BY p.product_ID DESC;
"""

sftp = ssh.open_sftp()
with sftp.open("/tmp/query_promo.sql", "w") as f:
    f.write(query)

stdin, stdout, stderr = ssh.exec_command("mysql thanhnhan_db < /tmp/query_promo.sql")
data = stdout.read().decode("utf-8", errors="ignore")
sftp.remove("/tmp/query_promo.sql")
sftp.close()
ssh.close()

lines = data.split("\n")
rows = []
month_counter = Counter()

date_regex = re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})")
month_text_regex = re.compile(r"(tháng\s+\d{1,2})", re.IGNORECASE)

csv_out_path = r"C:\xampp\htdocs\Tan\PC-Pricing\scraper\danh_sach_khuyen_mai_khong_phai_thang_10.csv"

with open(csv_out_path, mode="w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Mã TNC",
        "Tên sản phẩm",
        "Trạng thái kinh doanh",
        "Thời gian khuyến mãi phát hiện",
        "Các tháng phát hiện",
        "URL sản phẩm TNC",
        "Đoạn text khuyến mãi chi tiết"
    ])

    for line in lines[1:]:
        if not line.strip(): continue
        parts = line.split("\t")
        if len(parts) < 6: continue
        
        maso = parts[0]
        title = parts[1]
        url_slug = parts[2]
        display = parts[3]
        stop_biz = parts[4]
        raw_desc = parts[5]
        
        soup = BeautifulSoup(raw_desc, "html.parser")
        clean_text = soup.get_text(separator=" ", strip=True)
        
        dates = date_regex.findall(clean_text)
        month_texts = month_text_regex.findall(clean_text)
        
        product_url = f"https://www.tnc.com.vn/{url_slug}.html"
        
        is_october = False
        is_other_month = False
        other_dates = []
        months_found = set()
        
        for d in dates:
            m = re.search(r"/(\d{1,2})/", d)
            if m:
                month = int(m.group(1))
                months_found.add(f"Tháng {month}")
                month_counter[f"Tháng {month}"] += 1
                if month == 10:
                    is_october = True
                else:
                    is_other_month = True
                    other_dates.append(d)
                    
        for mt in month_texts:
            m = re.search(r"tháng\s+(\d{1,2})", mt, re.I)
            if m:
                month = int(m.group(1))
                months_found.add(f"Tháng {month}")
                month_counter[f"Tháng {month}"] += 1
                if month == 10:
                    is_october = True
                else:
                    is_other_month = True
                    other_dates.append(mt)
                    
        if is_other_month:
            status = "Đang hiển thị & Đang bán" if display == "1" and stop_biz == "0" else (
                "Ngừng kinh doanh" if stop_biz == "1" else "Đang ẩn"
            )
            dates_str = ", ".join(sorted(list(set(other_dates))))
            months_str = ", ".join(sorted(list(months_found)))
            writer.writerow([
                maso,
                title,
                status,
                dates_str,
                months_str,
                product_url,
                clean_text[:400]
            ])
            rows.append({
                "maso": maso,
                "title": title,
                "status": status,
                "dates": dates_str,
                "months": months_str,
                "url": product_url
            })

print(f"DONE! Đã xuất {len(rows)} sản phẩm vào: {csv_out_path}")
print("\nThống kê các tháng xuất hiện trong khuyến mãi cũ:")
for m, count in month_counter.most_common():
    print(f"  - {m}: {count} lượt xuất hiện")

active_count = sum(1 for r in rows if "Đang bán" in r["status"])
print(f"\nTrong đó:")
print(f"  - Đang kinh doanh & hiển thị trên web: {active_count} sản phẩm")
print(f"  - Đã ngừng kinh doanh / đang ẩn: {len(rows) - active_count} sản phẩm")
