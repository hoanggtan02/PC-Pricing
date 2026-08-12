// =====================================================================
// flash-sale.js — Flash Sale Detector (flash-sale.php)
// Nguồn: latest_prices_cache (is_flash_sale = true)
// =====================================================================

let flashData   = [];
let allProducts = {};
let flashPaginator;

// ── Build dropdown động ───────────────────────────────────────────────
function buildFlashDropdowns() {
    // Cửa hàng
    const stores = [...new Set(flashData.map(r => r.competitor).filter(Boolean))].sort();
    const storeSel = document.getElementById('flash-store-filter');
    const prevStore = storeSel.value;
    storeSel.innerHTML = '<option value="all">Tất cả cửa hàng</option>';
    stores.forEach(s => {
        const o = document.createElement('option');
        o.value = s; o.textContent = s;
        storeSel.appendChild(o);
    });
    if (stores.includes(prevStore)) storeSel.value = prevStore;

    // Danh mục
    const cats = [...new Set(flashData.map(r => r.category).filter(Boolean))].sort();
    const catSel = document.getElementById('flash-category-filter');
    const prevCat = catSel.value;
    catSel.innerHTML = '<option value="all">Tất cả danh mục</option>';
    cats.forEach(c => {
        const o = document.createElement('option');
        o.value = c; o.textContent = c;
        catSel.appendChild(o);
    });
    if (cats.includes(prevCat)) catSel.value = prevCat;

    // Thương hiệu — liên kết theo danh mục
    buildFlashBrandDropdown(catSel.value);
}

function buildFlashBrandDropdown(selectedCat) {
    const brandSel = document.getElementById('flash-brand-filter');
    const prev = brandSel.value;
    const source = selectedCat === 'all' ? flashData : flashData.filter(r => r.category === selectedCat);
    const brands = [...new Set(source.map(r => r.brand).filter(Boolean))].sort();
    brandSel.innerHTML = '<option value="all">Tất cả thương hiệu</option>';
    brands.forEach(b => {
        const o = document.createElement('option');
        o.value = b; o.textContent = b;
        brandSel.appendChild(o);
    });
    if (brands.includes(prev)) brandSel.value = prev; else brandSel.value = 'all';
}

// ── Áp dụng bộ lọc ───────────────────────────────────────────────────
function applyFlashFilter() {
    const q     = (document.getElementById('flash-search-filter')?.value || '').toLowerCase().trim();
    const store = document.getElementById('flash-store-filter').value;
    const cat   = document.getElementById('flash-category-filter').value;
    const brand = document.getElementById('flash-brand-filter').value;

    let filtered = flashData;
    if (q)            filtered = filtered.filter(r => r.product_name.toLowerCase().includes(q) || r.sku.toLowerCase().includes(q));
    if (store !== 'all') filtered = filtered.filter(r => r.competitor === store);
    if (cat   !== 'all') filtered = filtered.filter(r => r.category  === cat);
    if (brand !== 'all') filtered = filtered.filter(r => r.brand     === brand);

    const empty     = document.getElementById('flash-empty');
    const tableWrap = document.getElementById('flash-table-wrap');

    if (filtered.length === 0) {
        empty.style.display     = 'block';
        tableWrap.style.display = 'none';
        flashPaginator.setData([]);
        return;
    }
    empty.style.display     = 'none';
    tableWrap.style.display = 'block';
    flashPaginator.setData(filtered);
}

// ── Render bảng ───────────────────────────────────────────────────────
function renderFlashTablePage(rows) {
    const tbody = document.getElementById('flash-table-body');

    tbody.innerHTML = rows.map(r => {
        const ourPrice = allProducts[r.sku];
        let diffCell = '—';
        if (ourPrice && r.price) {
            const diff    = ourPrice - r.price;
            const diffPct = ((diff / r.price) * 100).toFixed(1);
            diffCell = diff > 0
                ? `<span class="badge badge-red">+${formatVND(diff)} (+${diffPct}%)</span>`
                : `<span class="badge badge-green">${formatVND(diff)} (${diffPct}%)</span>`;
        }

        return `<tr>
            <td>
                <a href="product.php?sku=${encodeURIComponent(r.sku)}" style="font-weight:600;font-size:0.9rem;color:var(--text-main);text-decoration:none">
                    ${truncate(r.product_name, 50)} <i class="bi bi-box-arrow-up-right" style="font-size:0.75rem;color:var(--accent)"></i>
                </a>
                <div style="font-size:0.75rem;color:var(--text-muted)">${r.sku} · ${r.brand || ''}</div>
            </td>
            <td><span class="badge badge-neutral">${r.competitor}</span></td>
            <td>
                <span class="flash-badge"><i class="bi bi-lightning-charge-fill"></i> FLASH</span>
                <strong style="margin-left:0.4rem;color:var(--red)">${formatVND(r.price)}</strong>
            </td>
            <td style="font-weight:700">${ourPrice ? formatVND(ourPrice) : '—'}</td>
            <td>${diffCell}</td>
            <td><span class="badge badge-neutral">${r.category}</span></td>
            <td>
                ${r.url
                    ? `<a href="${r.url}" target="_blank" class="badge badge-neutral" style="text-decoration:none">
                        <i class="bi bi-box-arrow-up-right"></i> Xem
                       </a>`
                    : '—'}
            </td>
        </tr>`;
    }).join('');
}

// ── Tải dữ liệu ──────────────────────────────────────────────────────
async function fetchFlashSaleData() {
    try {
        const [flashRows, ourPrices] = await Promise.all([
            supabaseFetch('latest_prices_cache',
                'is_flash_sale=eq.true&is_self=eq.false&select=sku,product_name,brand,category,competitor,price,url,scraped_at'),
            supabaseFetch('latest_prices_cache',
                'is_self=eq.true&in_stock=eq.true&select=sku,price'),
        ]);

        ourPrices.forEach(p => { allProducts[p.sku] = p.price; });
        flashData = flashRows;

        const stores   = new Set(flashRows.map(r => r.competitor));
        const affected = flashRows.filter(r => {
            const ourPrice = allProducts[r.sku];
            return ourPrice && ourPrice > r.price;
        });

        document.getElementById('flash-kpi-total').textContent    = flashRows.length;
        document.getElementById('flash-kpi-stores').textContent   = stores.size;
        document.getElementById('flash-kpi-affected').textContent = affected.length;

        document.getElementById('last-update').innerHTML =
            `<i class="bi bi-lightning-charge"></i> ${flashRows.length} sản phẩm flash sale`;

        // Build tất cả dropdowns động
        buildFlashDropdowns();

        applyFlashFilter();
        window.hideLoader?.();

    } catch (err) {
        console.error(err);
        document.getElementById('flash-table-body').innerHTML =
            `<tr><td colspan="7" class="text-center highlight-red">❌ Lỗi: ${err.message}</td></tr>`;
        window.hideLoader?.();
    }
}

// ── Khởi động ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    flashPaginator = createPaginator({
        containerId: 'flash-table-pagination',
        renderFn: renderFlashTablePage,
        defaultSize: 25
    });

    fetchFlashSaleData();

    document.getElementById('flash-search-filter')?.addEventListener('input', applyFlashFilter);
    document.getElementById('flash-store-filter').addEventListener('change', applyFlashFilter);
    document.getElementById('flash-category-filter').addEventListener('change', () => {
        buildFlashBrandDropdown(document.getElementById('flash-category-filter').value);
        applyFlashFilter();
    });
    document.getElementById('flash-brand-filter').addEventListener('change', applyFlashFilter);
});
