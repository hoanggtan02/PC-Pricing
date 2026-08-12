<?php
// PC Pricing Dashboard - Trang Chủ Tổng Quan (PHP + Vanilla JS)
?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bảng giá PC - Thành Nhân Computer</title>
    <link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@300;400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <link rel="stylesheet" href="assets/style.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div id="cr-overlay">
        <svg class="loader" viewBox="0 0 160 160" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
            <defs>
                <linearGradient id="lg" x1="90.48" y1="111.14" x2="161.56" y2="8.12" gradientUnits="userSpaceOnUse">
                    <stop offset="0" stop-color="#014f2b" />
                    <stop offset=".17" stop-color="#0e5b2d" />
                    <stop offset=".5" stop-color="#327b35" />
                    <stop offset=".95" stop-color="#6cb041" />
                    <stop offset="1" stop-color="#75c044" />
                </linearGradient>
                <linearGradient id="lg1" x1="6" y1="145.75" x2="62.13" y2="57.17" xlink:href="#lg" />
                <linearGradient id="lg2" x1="32.92" y1="37.18" x2="133.55" y2="124.75" xlink:href="#lg" />
            </defs>

            <path fill="url(#lg)" opacity="0.18" d="M156.63,22.44c-.58-1.5-1.33-2.94-2.33-4.19-.63-.78-1.37-1.44-2.19-1.97-3.75-2.43-9.19-2.4-13.22-1.31-5.85,1.58-10.99,5.14-15.82,8.69-10.63,7.82-19.88,17.53-28.42,27.54-1.21,1.41-2.44,2.86-3.65,4.36-.04.06-.1.12-.16.2-.02.02-.04.06-.06.08-.08.08-.14.18-.22.26-.2.26-.4.52-.6.77h0s7.14,6.27,7.14,6.27c.2-.26.4-.5.6-.75,4.11-5,8.11-9.56,11.86-13.55.04-.04.06-.06.1-.1.02-.02.06-.06.06-.08.02-.02.06-.06.06-.08,12.69-13.29,22.93-20.39,27.07-17.55,5.73,3.95-2.3,26-18.41,52.95h0s2.33,2.26,2.33,2.26c5.78,5.6,15.91,6.96,21.99,1.69l5.13-6.45c-.41,1.13-.84,2.26-1.27,3.38,4.43-11.47,8.21-23.27,10.38-35.37,1.54-8.6,2.87-18.65-.35-27.04Z" />
            <path fill="url(#lg1)" opacity="0.18" d="M62.85,97.08c-18.07,22.13-34.09,35.52-39.51,31.79-5.67-3.91,2.12-25.58,17.93-52.16,0,0,.01.01.02.02l-.02-.02-5-4.48c-5.39-4.8-13.49-4.96-19.02-.32-1.28,1.06-2.61,2.36-4.01,3.91-3.75,9.8-6.94,19.82-9.14,30.04-2.21,10.24-5.16,24.8.81,34.4,1.41,2.27,3.48,3.88,6.04,4.66,9.59,2.94,19.24-3.52,26.61-9.01,10.81-8.05,20.21-18,28.88-28.26.91-1.07,1.97-2.13,2.75-3.3.04-.06.1-.12.14-.18.1-.12.2-.24.3-.36.06-.06.1-.14.16-.2h0l-6.94-6.51" />
            <path fill="url(#lg2)" opacity="0.18" d="M141.71,86.8c-6.08,5.27-15.18,5.02-20.96-.58l-2.33-2.26h0s0,0,0,0l-.14-.2-21.2-20.63s0,0,0,0l-7.14-6.27h0s0,0,0,0c-.08-.08-46.54-43.42-46.57-43.45-.01.03-16.47,31.79-19.99,38.85-.06.12-.12.22-.16.32-.18.37-.35.75-.52,1.13-.82,1.75-1.64,3.51-2.44,5.28l-.03.07c-.91,2.01-1.79,4.03-2.66,6.06-.21.49-.41.98-.62,1.48-.64,1.52-1.28,3.05-1.9,4.58-.31.77-.62,1.55-.92,2.33-.3.77-.59,1.54-.89,2.31,1.4-1.55,2.73-2.85,4.01-3.91,5.53-4.64,13.64-4.48,19.02.32l5,4.48.02.02c.1.09,1.21,1.03,1.23.99,4.31,4.08,7.81,7.4,11.28,10.78.4.39.79.76,1.13,1.1l1.68,1.59,4.58,4.33,1.66,1.57,6.94,6.51,2.42,2.28,44.54,40.72c9.94-19,19.93-37.09,27.98-57,.64-1.57,1.26-3.16,1.88-4.74.43-1.13.86-2.25,1.27-3.38l-6.16,5.34Z" />

            <path id="a1" fill="url(#lg)" opacity="0" d="M156.63,22.44c-.58-1.5-1.33-2.94-2.33-4.19-.63-.78-1.37-1.44-2.19-1.97-3.75-2.43-9.19-2.4-13.22-1.31-5.85,1.58-10.99,5.14-15.82,8.69-10.63,7.82-19.88,17.53-28.42,27.54-1.21,1.41-2.44,2.86-3.65,4.36-.04.06-.1.12-.16.2-.02.02-.04.06-.06.08-.08.08-.14.18-.22.26-.2.26-.4.52-.6.77h0s7.14,6.27,7.14,6.27c.2-.26.4-.5.6-.75,4.11-5,8.11-9.56,11.86-13.55.04-.04.06-.06.1-.1.02-.02.06-.06.06-.08.02-.02.06-.06.06-.08,12.69-13.29,22.93-20.39,27.07-17.55,5.73,3.95-2.3,26-18.41,52.95h0s2.33,2.26,2.33,2.26c5.78,5.6,15.91,6.96,21.99,1.69l5.13-6.45c-.41,1.13-.84,2.26-1.27,3.38,4.43-11.47,8.21-23.27,10.38-35.37,1.54-8.6,2.87-18.65-.35-27.04Z" />
            <path id="a2" fill="url(#lg1)" opacity="0" d="M62.85,97.08c-18.07,22.13-34.09,35.52-39.51,31.79-5.67-3.91,2.12-25.58,17.93-52.16,0,0,.01.01.02.02l-.02-.02-5-4.48c-5.39-4.8-13.49-4.96-19.02-.32-1.28,1.06-2.61,2.36-4.01,3.91-3.75,9.8-6.94,19.82-9.14,30.04-2.21,10.24-5.16,24.8.81,34.4,1.41,2.27,3.48,3.88,6.04,4.66,9.59,2.94,19.24-3.52,26.61-9.01,10.81-8.05,20.21-18,28.88-28.26.91-1.07,1.97-2.13,2.75-3.3.04-.06.1-.12.14-.18.1-.12.2-.24.3-.36.06-.06.1-.14.16-.2h0l-6.94-6.51" />
            <path id="a3" fill="url(#lg2)" opacity="0" d="M141.71,86.8c-6.08,5.27-15.18,5.02-20.96-.58l-2.33-2.26h0s0,0,0,0l-.14-.2-21.2-20.63s0,0,0,0l-7.14-6.27h0s0,0,0,0c-.08-.08-46.54-43.42-46.57-43.45-.01.03-16.47,31.79-19.99,38.85-.06.12-.12.22-.16.32-.18.37-.35.75-.52,1.13-.82,1.75-1.64,3.51-2.44,5.28l-.03.07c-.91,2.01-1.79,4.03-2.66,6.06-.21.49-.41.98-.62,1.48-.64,1.52-1.28,3.05-1.9,4.58-.31.77-.62,1.55-.92,2.33-.3.77-.59,1.54-.89,2.31,1.4-1.55,2.73-2.85,4.01-3.91,5.53-4.64,13.64-4.48,19.02.32l5,4.48.02.02c.1.09,1.21,1.03,1.23.99,4.31,4.08,7.81,7.4,11.28,10.78.4.39.79.76,1.13,1.1l1.68,1.59,4.58,4.33,1.66,1.57,6.94,6.51,2.42,2.28,44.54,40.72c9.94-19,19.93-37.09,27.98-57,.64-1.57,1.26-3.16,1.88-4.74.43-1.13.86-2.25,1.27-3.38l-6.16,5.34Z" />
        </svg>
    </div>

    <div class="background-blobs">
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>
    </div>

    <div class="app-container">
        <nav class="nav-menu">
            <a href="index.php" class="active"><i class="bi bi-speedometer2"></i> Tổng quan</a>
            <a href="category.php"><i class="bi bi-grid-3x3-gap"></i> Theo Danh Mục</a>
            <a href="brand.php"><i class="bi bi-tags"></i> Theo Thương Hiệu</a>
            <a href="stock-gap.php"><i class="bi bi-box-seam"></i> Khoảng Trống Hàng</a>
            <a href="price-activity.php"><i class="bi bi-graph-up-arrow"></i> Biến Động Giá</a>
            <a href="trend.php"><i class="bi bi-activity"></i> Xu Hướng 7 Ngày</a>
            <a href="product.php"><i class="bi bi-search"></i> Chi Tiết SP</a>
            <a href="flash-sale.php"><i class="bi bi-lightning-charge"></i> Flash Sale</a>
        </nav>

        <header class="glass-header">
            <div class="header-content">
                <div>
                    <h1><i class="bi bi-bar-chart-fill"></i> Bảng giá PC (TNC)</h1>
                    <p>Dashboard so sánh giá thị trường — Hệ thống định giá tối ưu</p>
                </div>
                <div class="status-badge" id="last-update"><i class="bi bi-clock"></i> Đang kết nối Supabase...</div>
            </div>
        </header>

        <main class="dashboard-grid">
            <!-- 1. KPI Cards -->
            <div class="kpi-row">
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-box2"></i> Sản phẩm theo dõi</h3>
                    <div class="value" id="kpi-products">--</div>
                    <div class="sub-text" id="kpi-categories">-- danh mục</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-shop"></i> Đối thủ cạnh tranh</h3>
                    <div class="value" id="kpi-competitors">--</div>
                    <div class="sub-text">cửa hàng đang theo dõi</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-percent"></i> Trung bình vs Thị trường</h3>
                    <div class="value" id="kpi-avg-diff">--</div>
                    <div class="sub-text">trên các sản phẩm có đối thủ</div>
                </div>
                <div class="glass-card kpi-card kpi-danger">
                    <h3><i class="bi bi-exclamation-triangle"></i> Bị đối thủ bán rẻ hơn</h3>
                    <div class="value highlight-red" id="kpi-beaten">--</div>
                    <div class="sub-text">cần điều chỉnh giá</div>
                </div>
            </div>

            <!-- 2. Biểu đồ tần suất đổi giá -->
            <div class="glass-card section-card">
                <div class="section-header">
                    <div>
                        <h2><i class="bi bi-activity"></i> Tần suất đổi giá theo cửa hàng</h2>
                        <p class="section-subtitle">Số lần đổi giá trên mỗi <strong>100 sản phẩm</strong> trong tuần đã chọn</p>
                    </div>
                    <select id="week-select" class="glass-select">
                        <option value="">Đang tải các tuần...</option>
                    </select>
                </div>
                <div class="chart-container">
                    <canvas id="homepage-activity-chart"></canvas>
                </div>
                <details class="formula-details">
                    <summary><i class="bi bi-info-circle"></i> Xem công thức tính chỉ số này</summary>
                    <div class="formula-content">
                        <p><strong>Công thức:</strong> (Số lần đổi giá trong tuần ÷ Số sản phẩm theo dõi) × 100.</p>
                        <p>Chỉ số giúp so sánh công bằng hành vi định giá của đối thủ, không bị thiên lệch bởi quy mô danh mục.</p>
                    </div>
                </details>
            </div>

            <!-- 3. Danh mục phòng ban -->
            <div class="categories-section">
                <h2 class="section-title"><i class="bi bi-grid-1x2"></i> Danh mục — Chọn phòng ban</h2>
                <div class="categories-grid" id="categories-cards-grid">
                    <div class="text-center">Đang nạp danh mục...</div>
                </div>
            </div>

            <!-- 4. Bảng Needs Attention -->
            <div class="glass-card table-section">
                <div class="section-header">
                    <h2><i class="bi bi-exclamation-diamond"></i> Sản phẩm bị đối thủ bán rẻ hơn</h2>
                    <select id="brand-filter" class="glass-select">
                        <option value="all">Tất cả thương hiệu</option>
                    </select>
                </div>
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>Tên sản phẩm</th>
                                <th>Danh mục</th>
                                <th>Giá TNC</th>
                                <th>Giá rẻ nhất</th>
                                <th>Đối thủ</th>
                                <th>TNC đắt hơn</th>
                                <th>Nguồn</th>
                            </tr>
                        </thead>
                        <tbody id="table-body">
                            <tr><td colspan="7" class="text-center">Đang tải dữ liệu...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </main>
    </div>

    <script src="assets/config.js?v=10001"></script>
    <script src="assets/loader.js"></script>
    <script>
    (function() {
        console.log("🔥 Direct script running on index.php");
        const BRAND_COLORS = {
            'Thế Giới Di Động': '#eab308', 'FPT Shop': '#ef4444', 'An Phát PC': '#8b5cf6',
            'Thành Nhân': '#014f2b', 'Phong Vũ': '#3b82f6', 'CellphoneS': '#f97316',
            'HACOM': '#06b6d4', 'Hà Nội Computer': '#06b6d4', 'GearVN': '#84cc16', 'Memoryzone': '#ec4899'
        };
        const getColor = name => BRAND_COLORS[name] || '#94a3b8';
        const CATEGORY_DISPLAY = {
            'laptop': { label: 'Laptop', icon: 'bi-laptop' }, 'monitor': { label: 'Màn hình', icon: 'bi-display' },
            'ssd': { label: 'SSD', icon: 'bi-device-ssd' }, 'ram': { label: 'RAM', icon: 'bi-memory' },
            'cpu': { label: 'CPU', icon: 'bi-cpu' }, 'mainboard': { label: 'Mainboard', icon: 'bi-motherboard' },
            'vga': { label: 'Card màn hình', icon: 'bi-gpu-card' }
        };
        const getCategoryName = cat => CATEGORY_DISPLAY[cat.toLowerCase()]?.label ?? cat;
        const getCategoryIcon = cat => CATEGORY_DISPLAY[cat.toLowerCase()]?.icon ?? 'bi-grid';

        let homepageChart = null;

        async function initHomepage() {
            try {
                const lastUpdate = document.getElementById('last-update');
                if (lastUpdate) lastUpdate.innerHTML = '<i class="bi bi-arrow-repeat spin"></i> Đang nạp dữ liệu...';

                // Tải danh sách sản phẩm
                const products = await supabaseFetch('product_overview', 'select=sku,product_name,brand,category,our_price,lowest_price,cheapest_competitor,num_sources,pct_vs_mean');
                console.log("Loaded products:", products.length);

                // Tải danh sách đối thủ
                const competitors = await supabaseFetch('competitors', 'is_self=eq.false');

                // Tải out of stock gaps
                let oosGaps = [];
                try { oosGaps = await supabaseFetch('out_of_stock_gap_by_category'); } catch(e) { console.warn(e); }

                // Tải price activity
                let activity = [];
                try { activity = await supabaseFetch('price_activity', 'order=week_start.desc'); } catch(e) { console.warn(e); }

                // 1. KPIs
                if (document.getElementById('kpi-products')) document.getElementById('kpi-products').textContent = products.length;
                if (document.getElementById('kpi-competitors')) document.getElementById('kpi-competitors').textContent = competitors.length;
                if (document.getElementById('kpi-categories')) document.getElementById('kpi-categories').textContent = `trên ${new Set(products.map(p => p.category)).size} danh mục`;

                const beaten = products.filter(p => p.our_price && p.lowest_price && p.our_price > p.lowest_price).length;
                if (document.getElementById('kpi-beaten')) document.getElementById('kpi-beaten').textContent = beaten;

                const withDelta = products.filter(p => p.pct_vs_mean !== null);
                const avgDiff = withDelta.length ? (withDelta.reduce((s, p) => s + p.pct_vs_mean, 0) / withDelta.length).toFixed(1) : 0;
                const avgEl = document.getElementById('kpi-avg-diff');
                if (avgEl) {
                    avgEl.textContent = (avgDiff > 0 ? '+' : '') + avgDiff + '%';
                    avgEl.className = 'value ' + (avgDiff > 0 ? 'highlight-red' : 'highlight-green');
                }

                // 2. Thẻ danh mục
                const grid = document.getElementById('categories-cards-grid');
                if (grid) {
                    grid.innerHTML = '';
                    const catData = {};
                    products.forEach(p => {
                        if (!catData[p.category]) catData[p.category] = { count: 0, sumDelta: 0, countDelta: 0, beaten: 0 };
                        const c = catData[p.category];
                        c.count++;
                        if (p.our_price && p.lowest_price && p.our_price > p.lowest_price) c.beaten++;
                        if (p.pct_vs_mean !== null) { c.sumDelta += p.pct_vs_mean; c.countDelta++; }
                    });

                    const oosMap = new Map(oosGaps.map(item => [item.category ? item.category.toLowerCase() : '', item.n]));

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
                                ${oos > 0 ? `<span class="badge badge-red">${oos}</span>` : '<strong class="highlight-green">0</strong>'}
                            </div>
                            <div class="card-footer">Xem chi tiết <i class="bi bi-arrow-right"></i></div>
                        `;
                        grid.appendChild(card);
                    });
                }

                // 3. Biểu đồ tần suất đổi giá
                const weekSelect = document.getElementById('week-select');
                if (weekSelect && activity.length > 0) {
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

                    function renderChart(week) {
                        const chartEl = document.getElementById('homepage-activity-chart');
                        if (!chartEl || typeof Chart === 'undefined') return;
                        const weekRows = activity.filter(r => r.week_start === week).sort((a, b) => b.changes_per_100_products_week - a.changes_per_100_products_week);
                        const labels = weekRows.map(r => r.competitor);
                        const values = weekRows.map(r => r.changes_per_100_products_week);
                        const colors = weekRows.map(r => getColor(r.competitor));
                        if (homepageChart) homepageChart.destroy();
                        homepageChart = new Chart(chartEl.getContext('2d'), {
                            type: 'bar',
                            data: { labels, datasets: [{ data: values, backgroundColor: colors, borderRadius: 8 }] },
                            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
                        });
                    }

                    if (weeks.length > 0) {
                        renderChart(weeks[0]);
                        weekSelect.addEventListener('change', e => renderChart(e.target.value));
                    }
                }

                // 4. Bảng cần chú ý
                const tbody = document.getElementById('table-body');
                if (tbody) {
                    const needsAttention = products
                        .filter(p => p.our_price && p.lowest_price && p.our_price > p.lowest_price)
                        .sort((a, b) => (b.our_price - b.lowest_price) / b.lowest_price - (a.our_price - a.lowest_price) / a.lowest_price);

                    if (needsAttention.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="7" class="text-center">🎉 Tuyệt vời! Không có sản phẩm nào bị đối thủ bán rẻ hơn.</td></tr>`;
                    } else {
                        tbody.innerHTML = needsAttention.map(p => {
                            const diff = p.our_price - p.lowest_price;
                            const diffPct = ((diff / p.lowest_price) * 100).toFixed(1);
                            return `
                            <tr>
                                <td>
                                    <a href="product.php?sku=${encodeURIComponent(p.sku)}" style="font-weight:600;font-size:0.9rem;color:var(--text-main);text-decoration:none" class="product-link">
                                        ${truncate(p.product_name, 55)} <i class="bi bi-box-arrow-up-right" style="font-size:0.75rem;color:var(--accent)"></i>
                                    </a>
                                    <div style="font-size:0.75rem;color:var(--text-muted)">${p.sku} · ${p.brand}</div>
                                </td>
                                <td><span class="badge badge-neutral">${getCategoryName(p.category)}</span></td>
                                <td style="font-weight:700">${formatVND(p.our_price)}</td>
                                <td style="color:var(--green-500);font-weight:700">${formatVND(p.lowest_price)}</td>
                                <td><span class="badge badge-green">${p.cheapest_competitor || '—'}</span></td>
                                <td>
                                    <span class="badge badge-red">+${formatVND(diff)}</span>
                                    <div style="font-size:0.75rem;color:var(--red-500);margin-top:2px">+${diffPct}%</div>
                                </td>
                                <td><a href="product.php?sku=${encodeURIComponent(p.sku)}" class="badge badge-neutral" style="text-decoration:none"><i class="bi bi-search"></i> So sánh (${p.num_sources || 0})</a></td>
                            </tr>`;
                        }).join('');
                    }
                }

                // Bộ lọc thương hiệu
                const brandSelect = document.getElementById('brand-filter');
                if (brandSelect) {
                    const brands = [...new Set(products.map(p => p.brand))].sort();
                    brands.forEach(b => {
                        const opt = document.createElement('option');
                        opt.value = b;
                        opt.textContent = b;
                        brandSelect.appendChild(opt);
                    });
                }

                if (lastUpdate) lastUpdate.innerHTML = `<i class="bi bi-check-circle"></i> Cập nhật lần cuối: ${new Date().toLocaleString('vi-VN')}`;

                // Ẩn màn hình chờ Loading Overlay
                window.hideLoader?.();

            } catch (err) {
                console.error("Index Page Error:", err);
                const lastUpdate = document.getElementById('last-update');
                if (lastUpdate) lastUpdate.innerHTML = `<span style="color:red">❌ ${err.message}</span>`;
                
                // Ẩn màn hình chờ nếu gặp lỗi
                window.hideLoader?.();
            }
        }

        document.addEventListener('DOMContentLoaded', initHomepage);
    })();
    </script>
</body>
</html>
