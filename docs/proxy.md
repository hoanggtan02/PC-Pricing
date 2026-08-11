# Proxy: why we pay for a residential proxy, and how to turn it off in Vietnam

## Why the proxy exists

This app was developed and runs its scraper (GitHub Actions) on **US infrastructure**. Three of the
competitor sites — **Phong Vũ (`phongvu`), Thế Giới Di Động (`tgdd`), FPT Shop (`fptshop`)** — sit behind
**Cloudflare geo-blocking** that returns `403` to non-Vietnam IPs. From a US runner they are simply
unreachable.

To reach them we route those three scrapers through a **DataImpulse residential proxy** with Vietnam exit
IPs. Residential proxies are **metered (pay per GB)**, so this is a real recurring cost — and the reason
[`browser.py`](../scraper/scraper/browser.py) aborts heavy resources (`image`, `font`, `media`,
`stylesheet`) for proxied requests: the price/link data is already in the HTML+JS, and dropping the rest
cuts ~60–80% of bandwidth to stretch the GB allowance.

The other 5 shops (`hacom`, `cellphones`, `anphat`, `memoryzone`, `gearvn`) are **not** geo-blocked and
run direct, no proxy. See the per-shop `network` column in
[competitor-category-navigation.md](competitor-category-navigation.md).

## How it's wired

- **Which scrapers use it:** only the three geo-blocked ones call `browser_page(use_proxy=True)` —
  [`discover_phongvu.py`](../scraper/scraper/discover_phongvu.py),
  [`discover_tgdd.py`](../scraper/scraper/discover_tgdd.py),
  [`discover_fptshop.py`](../scraper/scraper/discover_fptshop.py).
- **Credentials:** read from env — `PROXY_SERVER`, `PROXY_USERNAME`, `PROXY_PASSWORD`
  (`_proxy_config()` in [`browser.py`](../scraper/scraper/browser.py)). Locally these live in
  `scraper/.env` (git-ignored, never committed); in CI they're GitHub Actions secrets.
- **Fail-loud, not fail-silent:** if a scraper asks for the proxy (`use_proxy=True`) but `PROXY_SERVER`
  is unset, `browser_page` raises `RuntimeError` instead of quietly proceeding and eating a `403`. That's
  deliberate — a geo-blocked scrape returning 0 rows should be a loud error, not a silent gap.

> ⚠️ Consequence for "just unset the proxy": because `use_proxy=True` is **hardcoded** in those three
> scrapers, simply clearing `PROXY_SERVER` doesn't disable the proxy — it makes them **crash** on the
> RuntimeError. To actually turn the proxy *off* (rather than remove credentials), use the toggle below.

## Turning the proxy OFF when running on a Vietnam server

If/when the scraper is moved to a **Vietnam-hosted server**, those three sites are reachable directly and
the residential proxy is **pure wasted cost** — a VN server IP already passes Cloudflare's geo check. At
that point we want the three scrapers to run direct, no proxy, **no code edits**.

The off-switch is an **environment toggle honored in one place** — `browser_page()` in
[`browser.py`](../scraper/scraper/browser.py#L106), where the guard already sits **commented out**, ready
to enable. Uncomment it and it treats `use_proxy=True` as "no proxy" (and does **not** raise):

```python
# already in browser_page(), before building `proxy` — just uncomment:
if os.environ.get("PROXY_DISABLED", "").strip() in ("1", "true", "yes"):
    use_proxy = False          # running from a VN IP → skip the residential proxy entirely
```

Then to switch regions you only flip one env var:

- **US runner (default today):** leave `PROXY_DISABLED` unset, keep `PROXY_SERVER`/`USERNAME`/`PASSWORD`
  populated → the three scrapers proxy through Vietnam.
- **Vietnam server:** set `PROXY_DISABLED=1` (and you can drop the `PROXY_*` credentials entirely) → all
  scrapers run direct, no metered bandwidth, no proxy bill.

This keeps the toggle in **one file** and off the per-scraper call sites, so no scraper code changes when
you relocate. (Alternative if you prefer no code change at all: point `PROXY_SERVER` at a local/no-op
value — but the env toggle above is cleaner and removes the crash-on-unset footgun.)
