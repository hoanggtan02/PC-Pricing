// =====================================================================
// flash-sale.js — Flash Sale Detector (flash-sale.php)
// Nguồn: latest_prices_cache (is_flash_sale = true)
// =====================================================================

let flashData    = [];
let allProducts  = {};
let activeStoreFilter = 'all';
let flashPaginator;

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

        const affectedSkus = new Set(flashRows.map(r => r.sku));
        const stores = new Set(flashRows.map(r => r.competitor));
        const affected = flashRows.filter(r => {
            const ourPrice = allProducts[r.sku];
            return ourPrice && ourPrice > r.price;
        });

        document.getElementById('flash-kpi-total').textContent    = flashRows.length;
        document.getElementById('flash-kpi-stores').textContent   = stores.size;
        document.getElementById('flash-kpi-affected').textContent = affected.length;

        document.getElementById('last-update').innerHTML =
            `<i class="bi bi-lightning-charge"></i> ${flashRows.length} sản phẩm flash sale`;

        const storeSelect = document.getElementById('flash-store-filter');
        [...stores].sort().forEach(s => {
            const opt = document.createElement('option');
            opt.value = s;
            opt.textContent = s;
            storeSelect.appendChild(opt);
        });
        storeSelect.addEventListener('change', (e) => {
            activeStoreFilter = e.target.value;
            applyFlashFilter();
        });

        applyFlashFilter();

        window.hideLoader?.();

    } catch (err) {
        console.error(err);
        document.getElementById('flash-table-body').innerHTML =
            `<tr><td colspan="7" class="text-center highlight-red">❌ Lỗi: ${err.message}</td></tr>`;
        window.hideLoader?.();
    }
}

function applyFlashFilter() {
    const filtered = activeStoreFilter === 'all'
        ? flashData
        : flashData.filter(r => r.competitor === activeStoreFilter);

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
                <div style="font-size:0.75rem;color:var(--text-muted)">${r.sku} · ${r.brand}</div>
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

document.addEventListener('DOMContentLoaded', () => {
    flashPaginator = createPaginator({
        containerId: 'flash-table-pagination',
        renderFn: renderFlashTablePage,
        defaultSize: 25
    });
    fetchFlashSaleData();
});
