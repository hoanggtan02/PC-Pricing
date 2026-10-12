import urllib.request
import re
from bs4 import BeautifulSoup
import sys

sys.stdout.reconfigure(encoding="utf-8")

urls = [
    "https://www.tnc.com.vn/laptop-hp-laptop-15-fd2184tu-dp2c1pa.html",
    "https://www.tnc.com.vn/laptop-asus-rog-zephyrus-g14-ga403gm-sy164w.html",
    "https://www.tnc.com.vn/may-bo-tnc-van-phong-r55600gt-16g-256g.html",
    "https://www.tnc.com.vn/laptop-asus-rog-strix-g16-g614pr-ts103w.html",
    "https://www.tnc.com.vn/laptop-msi-crosshair-16-hx-e14wfk-075vn.html",
    "https://www.tnc.com.vn/laptop-dell-14-dc14255-dc14255-r7165w11slu-2y.html",
    "https://www.tnc.com.vn/laptop-lenovo-thinkpad-e16-gen-4-21y4007eva.html",
    "https://www.tnc.com.vn/mini-pc-msi-cubi-5-12m-412bvn-i5-1235u-936-b0a811-412.html"
]

for url in urls:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=8) as r:
            html = r.read().decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            promos = soup.select(".promo-item-text")
            if promos:
                for p in promos:
                    txt = p.get_text(separator=" ", strip=True)
                    dates = re.findall(r"\d{1,2}/\d{1,2}/\d{4}", txt)
                    print(f"URL: {url}")
                    print(f"  Dates: {dates}")
                    print(f"  Text: {txt[:120]}...")
            else:
                print(f"URL: {url} -> NO PROMO")
    except Exception as e:
        print(f"URL: {url} -> ERROR: {e}")
