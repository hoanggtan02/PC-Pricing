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
                <div style="font-weight:600;font-size:0.9rem">${truncate(p.product_name, 55)}</div>
                <div style="font-size:0.75rem;color:var(--text-muted)">${p.sku}</div>
            </td>
            <td><span class="badge badge-neutral">${p.category}</span></td>
            <td style="font-weight:700">${formatVND(p.our_price)}</td>
            <td style="color:var(--green-500);font-weight:700">${formatVND(p.lowest_price)}</td>
            <td>${p.cheapest_competitor || '—'}</td>
            <td>${priceDiffBadge}</td>
            <td style="color:var(--text-muted);font-size:0.8rem">${p.num_sources || 0} nguồn</td>
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

// ── Fetch dữ liệu theo thương hiệu ───────────────────────────────────
async function fetchBrandData(brand) {
    try {
        document.getElementById('brand-table-body').innerHTML =
            '<tr><td colspan="7" class="text-center">Đang tải...</td></tr>';

        const encodedBrand = encodeURIComponent(brand);

        const [products, coverage] = await Promise.all([
            supabaseFetch('product_overview',
                `brand=ilike.${encodedBrand}&select=sku,product_name,category,our_price,lowest_price,cheapest_competitor,num_sources,pct_vs_mean&order=pct_vs_mean.desc.nullslast`),
            supabaseFetch('competitor_coverage',
                `brand=ilike.${encodedBrand}`),
        ]);

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
        renderBrandCoverageTable(coverage);

    } catch (err) {
        console.error(err);
        document.getElementById('brand-table-body').innerHTML =
            `<tr><td colspan="7" class="text-center highlight-red">❌ Lỗi: ${err.message}</td></tr>`;
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
