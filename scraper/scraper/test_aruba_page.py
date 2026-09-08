import sys, httpx
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

headers = {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'}
url = 'https://wifi.com.vn/aruba-instant-on-ap17-1167mbps-chiu-tai-50-user.html'
r = httpx.get(url, headers=headers, timeout=15)
soup = BeautifulSoup(r.text, 'html.parser')

print('Status:', r.status_code)
print('Title:', soup.title.string if soup.title else '')
print('H1:', soup.select_one('h1').text.strip() if soup.select_one('h1') else 'No H1')

# Price selectors
for sel in ['.pd-deal-price', '.pd-price', '.p-price', '.detail-price', '.price', 'span[class*="price"]', 'div[class*="price"]']:
    els = soup.select(sel)
    if els:
        print(f'Selector {sel}: {[e.text.strip().replace("\xa0", " ") for e in els[:3]]}')
