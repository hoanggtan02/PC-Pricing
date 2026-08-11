# How competitor scrapers navigate to a non-laptop category page

This documents the flow that takes a `(competitor, category)` pair — e.g. `(hacom, monitor)` — and turns
it into the actual listing URL the scraper drives the browser to. Laptop is the special case (per-brand
search URLs baked into each scraper's `BRANDS` dict); **every other category** goes through the shared
`resolve_url()` mechanism described here.

## Design decision: search-by-default, so we don't hardcode 8 × 18 URLs

The naive approach would be a lookup table of one URL per **(shop, category)** pair — with 8 competitor
shops and 18 enabled categories that's a **144-cell matrix** of hand-maintained links, every one of which
404s the day a shop re-slugs a category page. We deliberately avoid that.

Instead the rule is **"search by default, explicit link only where search fails."** Most shops expose a
single search box whose URL contract (`?q={query}`) is stable and category-agnostic, so **one template per
shop covers every category** — we just swap the query term. Only the shops whose search is unreliable or
incomplete for our purposes get hand-curated per-category links.

3 shops (`phongvu`, `tgdd`, `fptshop`) — hand-curated `paths:` per category, preferred here for
  **coverage and URL stability**, not because search is impossible. All three run behind the VN proxy;
  `fptshop` is the only *paged* scraper. Two of them (`fptshop`, `phongvu`) *also* have a `search_url`
  now — as a **fallback only** (see strategy 2); `tgdd` deliberately has none (evidence below).

| shop | working search URL | search result | curated path | curated result |
|---|---|---|---|---|
| `fptshop` | `…/tim-kiem?s=màn hình` | ~48 monitor links | `/man-hinh` | ~84 |
| `phongvu` | `…/search?router=productListing&query=màn hình` | ~40 cards | `/c/man-hinh-may-tinh` | ~45 |

**Tradeoff** is **coverage**: the curated category page returns the *fuller* catalog (84 vs 48,
45 vs 40), and its URL is **deterministic** — search URLs get canonicalized by the site (FPT rewrites
`?s=man-hinh` → `?s=man-hinh&sort=noi-bat&categories=man-hinh` client-side) and result *ordering* shifts
between loads, which is noisier to scrape. We prefer the path where one exists; **search is the fallback
that fills the gaps** — for `fptshop`/`phongvu` a category with no curated path (e.g. `fptshop`/`printer`,
which was `None`) now falls to search and yields ~23 real printers instead of zero.

**Why `tgdd` gets NO search fallback (measured, 2026-07):** TGĐĐ categorizes your search-bar keyword
on the fly and redirects to a specific category URL. If you manually type "man hinh" into its search bar,
TGĐĐ resolves it to `https://www.thegioididong.com/man-hinh-may-tinh?key=man+hinh&sc=new`. This means
there is no single fixed search endpoint where we can just substitute `{query}` — the URL TGĐĐ lands on
depends on how *it* classifies the term. So `tgdd` is path-only, hardcoded per category.

Why search is preferred as the *default* everywhere else: its URL contract almost never changes (category
landing pages get renamed and merged constantly), and it doesn't require the shop's taxonomy to match ours
— we ask for the term and filter the results ourselves with `name_match` / `name_exclude` (see below). The
cost of the curated-link tier is real (a re-slugged category page 404s until manually updated), so we use
it only where it meaningfully improves coverage. `resolve_url` encodes exactly this priority:
**explicit path first (the override), search template otherwise (the fallback).**

## The one entry point: `resolve_url(competitor, category)`

Defined in [`scraper/config.py`](../scraper/scraper/config.py) (`resolve_url`). Given a short competitor
key (`hacom`, `anphat`, `fptshop`, …) and a category (`monitor`, `printer`, `cpu`, …), it returns the
listing URL, or `None` if that pair isn't configured. It tries **two strategies, in order**:

### 1. Explicit per-category path (`paths:` in the category config) — wins if present

```python
path = (cat.get("paths") or {}).get(competitor)
if path:
    return path
```

Some shops have no usable search box for our purposes (or a category landing page is far cleaner /
more complete than search), so we hard-code the category URL per shop under the category's `paths:` block
in [`config/sources.yaml`](../scraper/config/sources.yaml). These are the URLs supplied by hand.

Today only **three** shops rely exclusively on explicit paths: **`phongvu`, `tgdd`, `fptshop`**. A path
may be a plain URL (scroll/load-more shops) or a **template containing `{page}`** (paged shops — see fptshop).

### 2. Search-box fallback (`search_url` template + category `search_term`)

```python
search_url = competitors[competitor]["search_url"]   # e.g. "https://hacom.vn/tim?q={query}"
term       = cat["search_term"]                       # e.g. "màn hình"
return search_url.replace("{query}", quote_plus(term))
```

If no explicit path is configured for that shop, we fill the shop's search-box template with the
**category's** search term (URL-encoded). This is the same machinery laptop uses, except the query is a
category term (`"máy in"`, `"màn hình"`) instead of a brand.

Five shops have a `search_url` template in the `competitors:` block:

| shop | `search_url` |
|---|---|
| `hacom` | `https://hacom.vn/tim?q={query}` |
| `cellphones` | `https://cellphones.com.vn/catalogsearch/result?q={query}` |
| `anphat` | `https://www.anphatpc.com.vn/tim?scat_id=&q={query}` |
| `memoryzone` | `https://memoryzone.com.vn/search?query={query}` |
| `gearvn` | `https://gearvn.com/search?q={query}` |

If a category also lists one of these shops under `paths:`, the **explicit path wins** (strategy 1 is
checked first). So a shop can be search-based for most categories and path-based for one, per-category.

## What each scraper does with the resolved URL

Each `discover_<shop>.py` calls `resolve_url(...)` inside `discover()` for the non-laptop branch, then
navigates by one of two patterns. (`use_proxy=True` shops route through the VN proxy because they
geo-block foreign IPs — **see [proxy.md](proxy.md)** for why the proxy exists, what it costs, and how to
turn it off when running from a Vietnam server.)

| shop | navigation | network |
|---|---|---|
| anphat | scroll / "Xem thêm" load-more loop | direct |
| cellphones | scroll / load-more loop | direct |
| hacom | scroll / load-more loop | direct |
| gearvn | scroll / load-more loop | direct |
| memoryzone | scroll / load-more loop | direct |
| phongvu | scroll / load-more loop | **proxy** |
| tgdd | scroll / load-more loop | **proxy** |
| **fptshop** | **paged** `{page}` URL loop | **proxy** |

**Scroll / load-more shops**: `goto_with_retry(page, url, selector, …)` once, then click the
"Xem thêm" / "load-more" button (or scroll) in a bounded loop (`range(40)` / `range(60)`), stopping when
several consecutive clicks add no new cards.

**Paged shop (fptshop)**: the resolved URL is a template with `{page}`. The scraper loops
`for n in range(1, PAGE_CAP + 1)` doing `page.goto(url.format(page=n))`, breaking when a page adds nothing
new. `PAGE_CAP = 50` is a safety stop; a `for…else` prints a warning if the cap is hit while pages are
still yielding products (category longer than the cap — consider raising it).

## After navigation: two filters decide what's kept

Once the cards are read, each product name passes through the category's regexes (both from
[`config.py`](../scraper/scraper/config.py)):

- **`name_match_re(category)`** — keep only names matching the category (drops search noise).
- **`name_exclude_re(category)`** — reject names matching the exclude pattern *even if* they matched
  `name_match` (e.g. toner cartridges / monitor arms whose names contain the category word but aren't the
  product). **All 8 competitor scrapers apply this** (previously only TNC did — that gap let a toner
  cartridge match the printer category).

Kept products then go through `derive_sku(name, url, category)` and are written only if the SKU already
exists in TNC's catalog (match-only — competitors never create new catalog rows).

## Quick inspection

See exactly which strategy each shop uses for a given category:

```bash
cd scraper && python -c "
from scraper.config import resolve_url
cat = 'monitor'   # or printer, scanner, ups, cpu, projector, tv, tablet, ...
for shop in ['anphat','cellphones','hacom','phongvu','fptshop','tgdd','gearvn','memoryzone']:
    print(f'{shop:12}', resolve_url(shop, cat))
"
```

A URL containing the category's search term (`?q=màn+hình`) means strategy 2 (search); a hard-coded
category/landing URL means strategy 1 (explicit path); `None` means that `(shop, category)` pair isn't
configured and the shop is skipped for that category.
