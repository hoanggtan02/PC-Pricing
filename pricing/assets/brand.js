// =====================================================================
// brand.js — Trang Theo Thương Hiệu (brand.php)
// Dữ liệu: product_overview (lọc brand), competitor_coverage
// =====================================================================
// Lấy dữ liệu brand từ URL hoặc mặc định
const urlParams = new URLSearchParams(window.location.search);
let currentBrand = urlParams.get('name') || 'Dell';

// ── Render bảng sản phẩm ─────────────────────────────────────────────
function renderBrandTable(products) {
    const tbody = document.getElementById('brand-table-body');

    if (products.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">Không có dữ liệu cho thương hiệu này.</td></tr>';
        return;
    }

    tbody.innerHTML = products.map(p => {
        const diff    = (p.our_price && p.lowest_price) ? p.our_price - p.lowest_price : null;
        const diffPct = diff !== null ? ((diff / p.lowest_price) * 100).toFixed(1) : null;
        const priceDiffBadge = diff === null
            ? '<span class="badge badge-neutral">Không có thị trường</span>'
            : diff > 0
                ? `<span class="badge badge-red">+${diffPct}% (đắt hơn)</span>`
                : `<span class="badge badge-green">${diffPct}% (rẻ hơn)</span>`;

        return `
        <tr>
            <td>
                <a href="product.php?sku=${encodeURIComponent(p.sku)}" style="font-weight:600;font-size:0.9rem;color:var(--text-main);text-decoration:none" class="product-link">
                    ${truncate(p.product_name, 55)} <i class="bi bi-box-arrow-up-right" style="font-size:0.75rem;color:var(--accent)"></i>
                </a>
                <div style="font-size:0.75rem;color:var(--text-muted)">${p.sku}</div>
            </td>
            <td><span class="badge badge-neutral">${p.category}</span></td>
            <td style="font-weight:700">${formatVND(p.our_price)}</td>
            <td style="color:var(--green-500);font-weight:700">${formatVND(p.lowest_price)}</td>
            <td>${p.cheapest_competitor || '—'}</td>
            <td>${priceDiffBadge}</td>
            <td><a href="product.php?sku=${encodeURIComponent(p.sku)}" class="badge badge-neutral" style="text-decoration:none"><i class="bi bi-search"></i> So sánh (${p.num_sources || 0})</a></td>
        </tr>`;
    }).join('');
}

// ── Render bảng độ phủ đối thủ theo Brand ────────────────────────────
function renderBrandCoverageTable(coverageData) {
    const container = document.getElementById('brand-coverage-container');
    if (!container) return;

    // Gộp theo competitor, tính tổng matched và avg_price trung bình trên các category
    const byCompetitor = {};
    coverageData.filter(c => !c.is_self).forEach(c => {
        if (!byCompetitor[c.name]) byCompetitor[c.name] = { matched: 0, prices: [] };
        byCompetitor[c.name].matched += c.products_matched;
        if (c.avg_price) byCompetitor[c.name].prices.push(c.avg_price);
    });

    const competitors = Object.entries(byCompetitor)
        .map(([name, d]) => ({
            name,
            products_matched: d.matched,
            avg_price: d.prices.length ? Math.round(d.prices.reduce((s, v) => s + v, 0) / d.prices.length) : 0,
        }))
        .sort((a, b) => b.products_matched - a.products_matched);

    if (competitors.length === 0) {
        container.innerHTML = '<p class="text-center">Chưa có dữ liệu độ phủ.</p>';
        return;
    }

    const maxMatch = Math.max(...competitors.map(c => c.products_matched), 1);

    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Đối thủ</th>
                    <th>Sản phẩm khớp</th>
                    <th>Giá trung bình</th>
                    <th>Độ phủ</th>
                </tr>
            </thead>
            <tbody>
                ${competitors.map(c => {
                    const pct = Math.round((c.products_matched / maxMatch) * 100);
                    return `
                    <tr>
                        <td style="font-weight:600">${c.name}</td>
                        <td style="font-weight:700;color:var(--accent)">${c.products_matched}</td>
                        <td>${formatVND(c.avg_price)}</td>
                        <td>
                            <div style="display:flex;align-items:center;gap:8px">
                                <div style="flex:1;height:8px;background:#e2e8f0;border-radius:4px;overflow:hidden">
                                    <div style="height:100%;width:${pct}%;background:var(--accent);border-radius:4px"></div>
                                </div>
                                <span style="font-size:0.8rem;color:var(--text-muted);min-width:30px">${pct}%</span>
                            </div>
                        </td>
                    </tr>`;
                }).join('')}
            </tbody>
        </table>`;
}

// ── Render bảng Chi tiết giá từng đối thủ & link web ───────────────
function renderStoreBreakdown(products, trend7dMap) {
    const container = document.getElementById('brand-store-breakdown-container');
    if (!container) return;

    if (products.length === 0) {
        container.innerHTML = '<p class="text-center">Không có sản phẩm.</p>';
        return;
    }

    container.innerHTML = products.map(p => {
        const stores = typeof p.prices_by_store === 'string'
            ? JSON.parse(p.prices_by_store)
            : (p.prices_by_store || []);

        return `
        <div style="margin-bottom:1.5rem;padding-bottom:1rem;border-bottom:1px solid var(--glass-border)">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.5rem">
                <div>
                    <a href="product.php?sku=${encodeURIComponent(p.sku)}" style="font-weight:700;font-size:0.95rem;color:var(--text-main);text-decoration:none">
                        ${p.product_name} <i class="bi bi-box-arrow-up-right" style="font-size:0.75rem;color:var(--accent)"></i>
                    </a>
                    <span class="sku-tag" style="margin-left:0.5rem">${p.sku}</span>
                </div>
                <div><span class="badge badge-neutral">${p.category}</span></div>
            </div>

            <table style="width:100%">
                <thead>
                    <tr>
                        <th style="width:40%">Cửa hàng đối thủ</th>
                        <th style="text-align:right">Giá niêm yết</th>
                        <th style="text-align:right">Chênh lệch TNC</th>
                        <th style="text-align:right">Đổi giá 7 ngày</th>
                        <th style="text-align:center">Web chính thức</th>
                    </tr>
                </thead>
                <tbody>
                    ${stores.map(s => {
                        const isLowest = s.store === p.cheapest_competitor;
                        const key = `${p.sku}|${s.store}`;
                        const t = trend7dMap.get(key);

                        // Render 7-day trend
                        let trendHtml = '<span style="color:var(--text-muted)">—</span>';
                        if (t) {
                            const arrow = t.direction === 'up' ? '▲' : t.direction === 'down' ? '▼' : '●';
                            const color = t.direction === 'up' ? 'var(--red)' : t.direction === 'down' ? 'var(--green)' : 'var(--text-muted)';
                            const pct   = t.pct_change ? Math.abs(t.pct_change) + '%' : '';
                            trendHtml   = `<span style="color:${color};font-weight:600" title="Đổi ${t.changes} lần trong 7 ngày">${arrow} ${pct} (${t.changes}×)</span>`;
                        }

                        const diff = (p.our_price && s.in_stock && s.price)
                            ? ((p.our_price - s.price) / s.price * 100).toFixed(1)
                            : null;
                        const diffBadge = diff === null ? '—' : diff > 0
                            ? `<span class="badge badge-red">+${diff}%</span>`
                            : `<span class="badge badge-green">${diff}%</span>`;

                        return `
                        <tr class="${s.is_self ? 'price-row-self' : ''}">
                            <td>
                                <div style="display:flex;align-items:center;gap:0.4rem;flex-wrap:wrap">
                                    ${s.is_self ? '<i class="bi bi-house-fill" style="color:var(--accent)"></i>' : ''}
                                    <strong>${s.store}</strong>
                                    ${s.is_self ? '<span class="badge badge-green">TNC</span>' : ''}
                                    ${isLowest && s.in_stock ? '<span class="badge badge-green">Rẻ nhất</span>' : ''}
                                    ${s.is_flash_sale && s.in_stock ? '<span class="flash-badge"><i class="bi bi-lightning-charge-fill"></i> FLASH</span>' : ''}
                                    ${!s.in_stock ? '<span class="badge badge-yellow">Hết hàng</span>' : ''}
                                </div>
                            </td>
                            <td style="text-align:right;font-weight:700;${!s.in_stock ? 'text-decoration:line-through;opacity:0.6' : ''}">
                                ${s.in_stock ? formatVND(s.price) : 'Hết hàng'}
                            </td>
                            <td style="text-align:right">${diffBadge}</td>
                            <td style="text-align:right">${trendHtml}</td>
                            <td style="text-align:center">
                                ${s.url
                                    ? `<a href="${s.url}" target="_blank" class="badge badge-neutral" style="text-decoration:none" title="Mở web ${s.store} để xác nhận giá">
                                        <i class="bi bi-box-arrow-up-right"></i> Mở Web
                                       </a>`
                                    : '—'}
                            </td>
                        </tr>`;
                    }).join('')}
                </tbody>
            </table>
        </div>`;
    }).join('');
}

// ── Fetch dữ liệu theo thương hiệu ───────────────────────────────────
async function fetchBrandData(brand) {
    try {
        document.getElementById('brand-table-body').innerHTML =
            '<tr><td colspan="7" class="text-center">Đang tải...</td></tr>';
        document.getElementById('brand-store-breakdown-container').innerHTML =
            '<p class="text-center">Đang tải chi tiết cửa hàng...</p>';

        const encodedBrand = encodeURIComponent(brand);

        const [products, coverage, trend7dRows] = await Promise.all([
            supabaseFetch('product_overview',
                `brand=ilike.${encodedBrand}&order=pct_vs_mean.desc.nullslast`),
            supabaseFetch('competitor_coverage',
                `brand=ilike.${encodedBrand}`),
            supabaseFetch('sku_price_trend_7d', ''),
        ]);

        const trend7dMap = new Map();
        (trend7dRows || []).forEach(r => trend7dMap.set(`${r.product_sku}|${r.competitor}`, r));

        // KPIs
        document.getElementById('brand-kpi-products').textContent = products.length;

        const beaten = products.filter(p => p.our_price && p.lowest_price && p.our_price > p.lowest_price).length;
        document.getElementById('brand-kpi-beaten').textContent   = beaten;

        const withDelta = products.filter(p => p.pct_vs_mean !== null);
        const avg = withDelta.length
            ? (withDelta.reduce((s, p) => s + p.pct_vs_mean, 0) / withDelta.length).toFixed(1)
            : null;
        const avgEl = document.getElementById('brand-kpi-avg');
        avgEl.textContent = avg !== null ? (avg > 0 ? '+' : '') + avg + '%' : '—';
        if (avg !== null) avgEl.className = `value ${avg > 0 ? 'highlight-red' : 'highlight-green'}`;

        document.getElementById('last-update').textContent = `Đang xem: ${brand}`;

        renderBrandTable(products);
        renderStoreBreakdown(products, trend7dMap);
        renderBrandCoverageTable(coverage);

        window.hideLoader?.();

    } catch (err) {
        console.error(err);
        document.getElementById('brand-table-body').innerHTML =
            `<tr><td colspan="7" class="text-center highlight-red">❌ Lỗi: ${err.message}</td></tr>`;
        window.hideLoader?.();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    fetchBrandData(currentBrand);

    const brandSelect = document.getElementById('brand-select');
    brandSelect?.addEventListener('change', (e) => {
        currentBrand = e.target.value;
        fetchBrandData(currentBrand);
    });
});
