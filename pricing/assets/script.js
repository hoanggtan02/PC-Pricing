// =====================================================================
// script.js — Trang Chủ Tổng Quan (index.php)
// Dữ liệu: product_overview, competitors, out_of_stock_gap_by_category,
//           price_activity, latest_prices_cache
// =====================================================================

let allProducts = [];
let activeBrandFilter = 'all';
let homepageChart = null;

// Cấu hình font chữ sang trọng đồng bộ cho Chart.js
if (typeof Chart !== 'undefined') {
    Chart.defaults.font.family = "'Plus Jakarta Sans', sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = '#5E6E65';
}

// Màu sắc đối thủ
const BRAND_COLORS = {
    'Thế Giới Di Động': '#eab308',
    'FPT Shop':         '#ef4444',
    'An Phát PC':       '#8b5cf6',
    'Thành Nhân':       '#014f2b',
    'Phong Vũ':         '#3b82f6',
    'CellphoneS':       '#f97316',
    'HACOM':            '#06b6d4',
    'Hà Nội Computer':  '#06b6d4',
    'GearVN':           '#84cc16',
    'Memoryzone':       '#ec4899',
};
const getColor = (name) => BRAND_COLORS[name] || '#94a3b8';

// Tên danh mục hiển thị đẹp
// Tên + icon danh mục
const CATEGORY_DISPLAY = {
    'laptop':    { label: 'Laptop',           icon: 'bi-laptop' },
    'monitor':   { label: 'Màn hình',         icon: 'bi-display' },
    'ssd':       { label: 'SSD',              icon: 'bi-device-ssd' },
    'ram':       { label: 'RAM',              icon: 'bi-memory' },
    'cpu':       { label: 'CPU',              icon: 'bi-cpu' },
    'mainboard': { label: 'Mainboard',        icon: 'bi-motherboard' },
    'vga':       { label: 'Card màn hình',    icon: 'bi-gpu-card' },
};
const getCategoryName  = (cat) => CATEGORY_DISPLAY[cat.toLowerCase()]?.label ?? cat;
const getCategoryIcon  = (cat) => CATEGORY_DISPLAY[cat.toLowerCase()]?.icon  ?? 'bi-grid';

// ── Render bảng "Cần chú ý" ──────────────────────────────────────────
function renderNeedsAttention(products) {
    const tbody = document.getElementById('table-body');
    const needsAttention = products
        .filter(p => p.our_price && p.lowest_price && p.our_price > p.lowest_price)
        .sort((a, b) =>
            (b.our_price - b.lowest_price) / b.lowest_price -
            (a.our_price - a.lowest_price) / a.lowest_price
        );

    if (needsAttention.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center">
            🎉 Tuyệt vời! Không có sản phẩm nào bị đối thủ bán rẻ hơn.
        </td></tr>`;
        return;
    }

    tbody.innerHTML = needsAttention.map(p => {
        const diff    = p.our_price - p.lowest_price;
        const diffPct = ((diff / p.lowest_price) * 100).toFixed(1);
        return `
        <tr>
            <td>
                <div style="font-weight:600;font-size:0.9rem">${truncate(p.product_name, 55)}</div>
                <div style="font-size:0.75rem;color:var(--text-muted)">${p.sku} · ${p.brand}</div>
            </td>
            <td><span class="badge badge-neutral">${getCategoryName(p.category)}</span></td>
            <td style="font-weight:700">${formatVND(p.our_price)}</td>
            <td style="color:var(--green-500);font-weight:700">${formatVND(p.lowest_price)}</td>
            <td><span class="badge badge-green">${p.cheapest_competitor}</span></td>
            <td>
                <span class="badge badge-red">+${formatVND(diff)}</span>
                <div style="font-size:0.75rem;color:var(--red-500);margin-top:2px">+${diffPct}%</div>
            </td>
            <td style="color:var(--text-muted);font-size:0.8rem">${p.num_sources || '—'} nguồn</td>
        </tr>`;
    }).join('');
}

// ── Render danh mục dạng thẻ (giống React) ───────────────────────────
function renderCategoryCards(products, oosGaps) {
    const grid = document.getElementById('categories-cards-grid');
    grid.innerHTML = '';

    // Gom dữ liệu theo danh mục
    const catData = {};
    products.forEach(p => {
        if (!catData[p.category]) {
            catData[p.category] = { count: 0, sumDelta: 0, countDelta: 0, beaten: 0 };
        }
        const c = catData[p.category];
        c.count++;
        if (p.our_price && p.lowest_price && p.our_price > p.lowest_price) {
            c.beaten++;
        }
        if (p.pct_vs_mean !== null) {
            c.sumDelta += p.pct_vs_mean;
            c.countDelta++;
        }
    });

    const oosMap = new Map(oosGaps.map(item => [item.category.toLowerCase(), item.n]));

    Object.entries(catData).forEach(([cat, data]) => {
        const oos = oosMap.get(cat.toLowerCase()) || 0;
        const avg = data.countDelta > 0 ? (data.sumDelta / data.countDelta).toFixed(1) : null;
        
        const card = document.createElement('a');
        card.href = `category.php?name=${encodeURIComponent(cat)}`;
        card.className = 'glass-card category-nav-card';
        card.innerHTML = `
            <div class="card-header">
                <h3><i class="bi ${getCategoryIcon(cat)}"></i> ${getCategoryName(cat)}</h3>
                <span class="badge badge-neutral"><i class="bi bi-box2"></i> ${data.count}</span>
            </div>
            <div class="card-metric">
                <span class="metric-label"><i class="bi bi-percent"></i> TB vs Thị trường</span>
                <span class="badge ${avg > 0 ? 'badge-red' : 'badge-green'}">
                    ${avg !== null ? (avg > 0 ? '+' : '') + avg + '%' : '—'}
                </span>
            </div>
            <div class="card-metric">
                <span class="metric-label"><i class="bi bi-exclamation-triangle"></i> Bị bán rẻ hơn</span>
                <strong class="${data.beaten > 0 ? 'highlight-red' : 'highlight-green'}">${data.beaten}</strong>
            </div>
            <div class="card-metric">
                <span class="metric-label"><i class="bi bi-slash-circle"></i> Hết hàng, đối thủ còn</span>
                ${oos > 0
                    ? `<span class="badge badge-red">${oos}</span>`
                    : '<strong class="highlight-green">0</strong>'
                }
            </div>
            <div class="card-footer">Xem chi tiết <i class="bi bi-arrow-right"></i></div>
        `;
        grid.appendChild(card);
    });
}

// ── Render biểu đồ hoạt động đổi giá ───────────────────────────────
function renderActivityChart(activityData, week) {
    const weekRows = activityData
        .filter(r => r.week_start === week)
        .sort((a, b) => b.changes_per_100_products_week - a.changes_per_100_products_week);

    const labels = weekRows.map(r => r.competitor);
    const values = weekRows.map(r => r.changes_per_100_products_week);
    const colors = weekRows.map(r => getColor(r.competitor));

    const ctx = document.getElementById('homepage-activity-chart').getContext('2d');
    if (homepageChart) homepageChart.destroy();
    
    homepageChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderRadius: 8,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => ` ${ctx.raw} lần đổi giá / 100 sản phẩm`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(0,0,0,0.05)' },
                    ticks: { color: '#64748b' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#64748b', maxRotation: 45 }
                }
            }
        }
    });
}

// ── Tải toàn bộ dữ liệu ──────────────────────────────────────────────
async function fetchDashboardData() {
    console.log('Bắt đầu tải dữ liệu Dashboard...');
    try {
        // Sử dụng Promise.allSettled để tránh 1 view lỗi làm dừng toàn bộ trang chủ
        const results = await Promise.allSettled([
            supabaseFetch('product_overview', 'select=sku,product_name,brand,category,our_price,lowest_price,cheapest_competitor,num_sources,pct_vs_mean'),
            supabaseFetch('competitors', 'is_self=eq.false'),
            supabaseFetch('out_of_stock_gap_by_category'),
            supabaseFetch('price_activity', 'order=week_start.desc'),
            supabaseFetch('latest_prices_cache', 'select=refreshed_at&order=refreshed_at.desc', 1),
        ]);

        const products    = results[0].status === 'fulfilled' ? results[0].value : [];
        const competitors = results[1].status === 'fulfilled' ? results[1].value : [];
        const oosGaps     = results[2].status === 'fulfilled' ? results[2].value : [];
        const activity    = results[3].status === 'fulfilled' ? results[3].value : [];
        const refreshRow  = results[4].status === 'fulfilled' ? results[4].value : [];

        if (results[0].status === 'rejected') console.error('L�        // Cập nhật KPIs chính (An toàn null-check)
        const elProds = document.getElementById('kpi-products');
        if (elProds) elProds.textContent = products.length;

        const elComps = document.getElementById('kpi-competitors');
        if (elComps) elComps.textContent = competitors.length;

        const elCats = document.getElementById('kpi-categories');
        if (elCats) elCats.textContent = `trên ${new Set(products.map(p => p.category)).size} danh mục`;

        const beaten = products.filter(p => p.our_price && p.lowest_price && p.our_price > p.lowest_price).length;
        const elBeaten = document.getElementById('kpi-beaten');
        if (elBeaten) elBeaten.textContent = beaten;

        const withDelta = products.filter(p => p.pct_vs_mean !== null);
        const avgDiff = withDelta.length ? (withDelta.reduce((s, p) => s + p.pct_vs_mean, 0) / withDelta.length).toFixed(1) : 0;
        const avgEl = document.getElementById('kpi-avg-diff');
        if (avgEl) {
            avgEl.textContent = (avgDiff > 0 ? '+' : '') + avgDiff + '%';
            avgEl.className = 'value ' + (avgDiff > 0 ? 'highlight-red' : 'highlight-green');
        }

        // Cập nhật thẻ danh mục
        renderCategoryCards(products, oosGaps);

        // Biểu đồ tần suất đổi giá
        const weekSelect = document.getElementById('week-select');
        if (weekSelect) {
            weekSelect.innerHTML = '';
            const weeks = [...new Set(activity.map(r => r.week_start))].sort((a, b) => b.localeCompare(a)).slice(0, 4);

            weeks.forEach((w, i) => {
                const opt = document.createElement('option');
                opt.value = w;
                const dMon = new Date(w);
                const dSun = new Date(dMon);
                dSun.setDate(dMon.getDate() + 6);
                opt.textContent = `${dMon.getDate()}–${dSun.getDate()} Th${dSun.getMonth()+1}` + (i === 0 ? ' (Tuần mới nhất)' : '');
                weekSelect.appendChild(opt);
            });

            if (weeks.length > 0) {
                renderActivityChart(activity, weeks[0]);
                weekSelect.addEventListener('change', (e) => {
                    renderActivityChart(activity, e.target.value);
                });
            }
        }

        // Bảng cần chú ý
        renderNeedsAttention(products);

        // Nạp hãng vào bộ lọc
        const brandSelect = document.getElementById('brand-filter');
        if (brandSelect) {
            const brands = [...new Set(products.map(p => p.brand))].sort();
            brands.forEach(b => {
                const opt = document.createElement('option');
                opt.value = b;
                opt.textContent = b;
                brandSelect.appendChild(opt);
            });
            brandSelect.addEventListener('change', (e) => {
                const filtered = e.target.value === 'all' ? allProducts : allProducts.filter(p => p.brand === e.target.value);
                renderNeedsAttention(filtered);
            });
        }

        // Cập nhật mốc thời gian
        const freshAt = refreshRow[0]?.refreshed_at || (products.length ? products[0].last_scraped : null) || new Date().toISOString();
        const lastUpdateEl = document.getElementById('last-update');
        if (lastUpdateEl) lastUpdateEl.innerHTML = `Cập nhật <strong>${timeAgo(freshAt)}</strong>`;ent = b;
            brandSelect.appendChild(opt);
        });
        brandSelect.addEventListener('change', (e) => {
            const filtered = e.target.value === 'all' ? allProducts : allProducts.filter(p => p.brand === e.target.value);
            renderNeedsAttention(filtered);
        });

        // Cập nhật mốc thời gian
        const freshAt = refreshRow[0]?.refreshed_at || (products.length ? products[0].last_scraped : null) || new Date().toISOString();
        document.getElementById('last-update').innerHTML = `Cập nhật <strong>${timeAgo(freshAt)}</strong>`;

    } catch (err) {
        console.error('Lỗi Dashboard:', err);
        const lastUpdateEl = document.getElementById('last-update');
        if (lastUpdateEl) lastUpdateEl.innerHTML = `<span class="highlight-red">❌ ${err.message}</span>`;
        const tbody = document.getElementById('table-body');
        if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="text-center highlight-red">❌ Lỗi kết nối: ${err.message}</td></tr>`;
    }
}

document.addEventListener('DOMContentLoaded', fetchDashboardData);
