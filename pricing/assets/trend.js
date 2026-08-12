// =====================================================================
// trend.js — Xu Hướng Giá 7 Ngày (trend.php)
// Nguồn: sku_price_trend_7d + product_overview (để lấy tên sản phẩm)
// =====================================================================

let trendData = [];
let productNames = {};

const DIRECTION_CONFIG = {
    up:   { icon: 'bi-arrow-up-circle-fill',   color: 'var(--red)',   label: '↑ Tăng' },
    down: { icon: 'bi-arrow-down-circle-fill',  color: 'var(--green)', label: '↓ Giảm' },
    flat: { icon: 'bi-dash-circle',             color: 'var(--text-muted)', label: '→ Không đổi' },
};

function renderTrendTable(data) {
    const tbody = document.getElementById('trend-table-body');
    document.getElementById('trend-count-badge').textContent = `${data.length} dòng`;

    if (data.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center">Không có biến động giá nào phù hợp bộ lọc.</td></tr>`;
        return;
    }

    tbody.innerHTML = data.map(r => {
        const dir   = DIRECTION_CONFIG[r.direction] || DIRECTION_CONFIG.flat;
        const pct   = r.pct_change !== null ? r.pct_change : 0;
        const pctBadge = r.direction === 'up'
            ? `<span class="badge badge-red">+${pct}%</span>`
            : r.direction === 'down'
                ? `<span class="badge badge-green">${pct}%</span>`
                : `<span class="badge badge-neutral">0%</span>`;

        const name = productNames[r.product_sku]
            ? `<div style="font-weight:600;font-size:0.9rem">${truncate(productNames[r.product_sku], 50)}</div>
               <div style="font-size:0.75rem;color:var(--text-muted)">${r.product_sku}</div>`
            : `<div style="font-size:0.85rem;color:var(--text-muted)">${r.product_sku}</div>`;

        const isSelf = r.competitor === 'Thành Nhân' || r.is_self;

        return `<tr>
            <td>${name}</td>
            <td>
                <span class="badge ${isSelf ? 'badge-green' : 'badge-neutral'}">${r.competitor}</span>
            </td>
            <td>
                <i class="bi ${dir.icon}" style="color:${dir.color};font-size:1.1rem"></i>
                <span style="color:${dir.color};font-weight:600;margin-left:0.3rem">${dir.label}</span>
            </td>
            <td style="font-weight:600">${formatVND(r.first_price)}</td>
            <td style="font-weight:700">${formatVND(r.last_price)}</td>
            <td>${pctBadge}</td>
            <td style="text-align:center;font-weight:700">${r.changes}</td>
            <td style="text-align:center;color:var(--red)">${r.increases}</td>
            <td style="text-align:center;color:var(--green)">${r.decreases}</td>
        </tr>`;
    }).join('');
}

function applyFilters() {
    const compFilter = document.getElementById('trend-competitor-filter').value;
    const dirFilter  = document.getElementById('trend-direction-filter').value;

    let filtered = trendData;
    if (compFilter === 'competitor') filtered = filtered.filter(r => !r.is_self);
    if (compFilter === 'self')       filtered = filtered.filter(r => r.is_self);
    if (dirFilter !== 'all')         filtered = filtered.filter(r => r.direction === dirFilter);

    renderTrendTable(filtered);
}

async function fetchTrendData() {
    try {
        const [trends, products] = await Promise.all([
            supabaseFetch('sku_price_trend_7d', 'order=changes.desc'),
            supabaseFetch('product_overview', 'select=sku,product_name'),
        ]);

        // Map tên sản phẩm
        products.forEach(p => { productNames[p.sku] = p.product_name; });
        trendData = trends;

        // KPIs
        const totalChanges   = trends.reduce((s, r) => s + r.changes, 0);
        const totalIncreases = trends.reduce((s, r) => s + r.increases, 0);
        const totalDecreases = trends.reduce((s, r) => s + r.decreases, 0);

        document.getElementById('trend-kpi-up').textContent    = totalIncreases;
        document.getElementById('trend-kpi-down').textContent  = totalDecreases;
        document.getElementById('trend-kpi-total').textContent = totalChanges;

        // Đối thủ đổi giá nhiều nhất (gộp theo competitor)
        const byComp = {};
        trends.forEach(r => { byComp[r.competitor] = (byComp[r.competitor] || 0) + r.changes; });
        const topComp = Object.entries(byComp).sort((a, b) => b[1] - a[1])[0];
        if (topComp) {
            document.getElementById('trend-kpi-most-active').textContent       = topComp[0];
            document.getElementById('trend-kpi-most-active-count').textContent = `${topComp[1]} lần đổi giá`;
        }

        document.getElementById('last-update').innerHTML = `<i class="bi bi-check-circle"></i> ${trends.length} cặp có biến động`;

        renderTrendTable(trendData);

        document.getElementById('trend-competitor-filter').addEventListener('change', applyFilters);
        document.getElementById('trend-direction-filter').addEventListener('change', applyFilters);

        window.hideLoader?.();

    } catch (err) {
        console.error(err);
        document.getElementById('trend-table-body').innerHTML =
            `<tr><td colspan="9" class="text-center highlight-red">❌ Lỗi: ${err.message}</td></tr>`;
        window.hideLoader?.();
    }
}

document.addEventListener('DOMContentLoaded', fetchTrendData);
