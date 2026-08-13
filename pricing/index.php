<?php
$pageTitle = "Bảng giá PC - Thành Nhân Computer";
$extraHeadHtml = <<<'HTML'
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
HTML;
include 'includes/head.php';
include 'includes/body-start.php';
?>
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
                    <div id="index-table-pagination" class="pagination-bar"></div>
                </div>
            </div>
        </main>
    </div>

    <script src="assets/config.js?v=10001"></script>
    <script src="assets/loader.js"></script>
    <script src="assets/pagination.js"></script>

<?php
ob_start();
?>
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
        let homepagePaginator;
        let allBeatenProducts = [];
        let activeBrandFilter = 'all';

        function renderBeatenTablePage(items) {
            const tbody = document.getElementById('table-body');
            if (!tbody) return;
            if (items.length === 0) {
                tbody.innerHTML = `<tr><td colspan="7" class="text-center">🎉 Tuyệt vời! Không có sản phẩm nào bị đối thủ bán rẻ hơn.</td></tr>`;
                return;
            }
            tbody.innerHTML = items.map(p => {
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

        function applyFilters() {
            let filtered = allBeatenProducts;
            if (activeBrandFilter !== 'all') {
                filtered = filtered.filter(p => p.brand === activeBrandFilter);
            }
            homepagePaginator.setData(filtered);
        }

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
                        // category.js nhận tham số `category` để tự áp bộ lọc lúc tải trang.
                        card.href = `category.php?category=${encodeURIComponent(cat)}`;
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
                allBeatenProducts = products
                    .filter(p => p.our_price && p.lowest_price && p.our_price > p.lowest_price)
                    .sort((a, b) => (b.our_price - b.lowest_price) / b.lowest_price - (a.our_price - a.lowest_price) / a.lowest_price);

                homepagePaginator = createPaginator({
                    containerId: 'index-table-pagination',
                    renderFn: renderBeatenTablePage,
                    defaultSize: 25
                });

                applyFilters();

                // Bộ lọc thương hiệu
                const brandSelect = document.getElementById('brand-filter');
                if (brandSelect) {
                    brandSelect.innerHTML = '<option value="all">Tất cả thương hiệu</option>';
                    const brands = [...new Set(allBeatenProducts.map(p => p.brand))].sort();
                    brands.forEach(b => {
                        const opt = document.createElement('option');
                        opt.value = b;
                        opt.textContent = b;
                        brandSelect.appendChild(opt);
                    });
                    brandSelect.addEventListener('change', (e) => {
                        activeBrandFilter = e.target.value;
                        applyFilters();
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
<?php
$extraScripts = ob_get_clean();
include 'includes/footer.php';
?>
