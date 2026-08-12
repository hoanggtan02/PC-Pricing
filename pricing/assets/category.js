// =====================================================================
// category.js — Bộ Lọc Chi Tiết & Phân Tích Thị Trường
// =====================================================================

let allProducts = [];
let allOosData = [];
let catPaginator;
let oosPaginator;
let currentSelectedSku = null;

// Subtab switching
function switchSubTab(tabName) {
    document.querySelectorAll('.subtab-panel').forEach(p => p.style.display = 'none');
    document.querySelectorAll('.tabs-nav-container .dm-tab-btn').forEach(b => b.classList.remove('active'));
    
    document.getElementById(`subpanel-${tabName}`).style.display = 'block';
    document.getElementById(`subtab-btn-${tabName}`).classList.add('active');
}

// ── Render bảng sản phẩm Master ─────────────────────────────────────
function renderCategoryTablePage(products) {
    const tbody = document.getElementById('category-table-body');
    if (!tbody) return;

    if (products.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center">Không tìm thấy sản phẩm nào khớp bộ lọc.</td></tr>';
        return;
    }

    tbody.innerHTML = products.map(p => {
        const diff    = (p.our_price && p.lowest_price) ? p.our_price - p.lowest_price : null;
        const diffPct = diff !== null ? ((diff / p.lowest_price) * 100).toFixed(1) : null;
        const priceDiffBadge = diff === null
            ? '<span class="badge badge-neutral">Không có đối thủ</span>'
            : diff > 0
                ? `<span class="badge badge-red">+${diffPct}%</span>`
                : `<span class="badge badge-green">${diffPct}%</span>`;

        const isSelected = p.sku === currentSelectedSku ? 'selected-row' : '';

        return `
        <tr class="clickable-row ${isSelected}" data-sku="${p.sku}">
            <td>
                <div style="font-weight:600;font-size:0.9rem;color:var(--text-main);">${truncate(p.product_name, 50)}</div>
                <div style="font-size:0.75rem;color:var(--text-muted)">${p.sku} · ${p.brand} · ${p.category}</div>
            </td>
            <td style="font-weight:700">${formatVND(p.our_price)}</td>
            <td style="color:var(--green-500);font-weight:700">${formatVND(p.lowest_price)}</td>
            <td>${priceDiffBadge}</td>
        </tr>`;
    }).join('');

    // Bắt sự kiện click dòng
    tbody.querySelectorAll('.clickable-row').forEach(row => {
        row.addEventListener('click', () => {
            const sku = row.getAttribute('data-sku');
            selectProductRow(sku);
        });
    });
}

// ── Chọn và hiển thị chi tiết sản phẩm ──────────────────────────────
async function selectProductRow(sku) {
    currentSelectedSku = sku;
    
    // Highlight dòng được chọn
    const tbody = document.getElementById('category-table-body');
    tbody.querySelectorAll('.clickable-row').forEach(r => {
        if (r.getAttribute('data-sku') === sku) {
            r.classList.add('selected-row');
        } else {
            r.classList.remove('selected-row');
        }
    });

    const p = allProducts.find(item => item.sku === sku);
    if (!p) return;

    // Hiển thị khung content chi tiết
    document.getElementById('detail-placeholder').style.display = 'none';
    const detailContent = document.getElementById('detail-content');
    detailContent.style.display = 'block';

    // Cập nhật thông tin cơ bản
    document.getElementById('detail-product-name').textContent = p.product_name;
    document.getElementById('detail-product-sku').textContent = p.sku;
    document.getElementById('detail-product-brand').textContent = p.brand;
    document.getElementById('detail-product-category').textContent = p.category;

    // Chi tiết giá cửa hàng (từ JSON prices_by_store)
    const storesBody = document.getElementById('detail-stores-body');
    const stores = typeof p.prices_by_store === 'string'
        ? JSON.parse(p.prices_by_store)
        : (p.prices_by_store || []);

    if (stores.length === 0) {
        storesBody.innerHTML = '<tr><td colspan="4" class="text-center">Không có dữ liệu giá.</td></tr>';
    } else {
        const selfPrice = stores.find(s => s.is_self && s.in_stock)?.price;
        const sortedStores = [...stores].sort((a, b) => {
            if (!a.in_stock && b.in_stock) return 1;
            if (a.in_stock && !b.in_stock) return -1;
            return (a.price || 0) - (b.price || 0);
        });

        storesBody.innerHTML = sortedStores.map(s => {
            const diff = selfPrice && !s.is_self && s.in_stock
                ? ((selfPrice - s.price) / s.price * 100).toFixed(1)
                : null;
            const diffBadge = diff === null ? '—' : diff > 0
                ? `<span class="badge badge-red">+${diff}%</span>`
                : `<span class="badge badge-green">${diff}%</span>`;

            const isSelfClass = s.is_self ? 'price-row-self' : '';

            return `
            <tr class="${isSelfClass}">
                <td>
                    <div style="font-weight:600;display:flex;align-items:center;gap:4px">
                        ${s.is_self ? '<i class="bi bi-house-fill" style="color:var(--accent)"></i>' : ''}
                        ${s.store}
                        ${s.is_flash_sale ? '<span class="flash-badge"><i class="bi bi-lightning-charge-fill"></i> FLASH</span>' : ''}
                    </div>
                </td>
                <td style="text-align:right;font-weight:700">
                    ${s.in_stock ? formatVND(s.price) : '<span style="color:var(--text-muted)">Hết hàng</span>'}
                </td>
                <td style="text-align:right">${diffBadge}</td>
                <td style="text-align:center">
                    ${s.url ? `<a href="${s.url}" target="_blank" class="badge badge-neutral" style="text-decoration:none"><i class="bi bi-box-arrow-up-right"></i> Mở</a>` : '—'}
                </td>
            </tr>`;
        }).join('');
    }

    // Tải động xu hướng 7 ngày
    const trendContainer = document.getElementById('detail-trend-container');
    trendContainer.innerHTML = '<p class="text-center" style="font-size:0.8rem;color:var(--text-muted)">Đang tải xu hướng...</p>';

    try {
        const trends = await supabaseFetch('sku_price_trend_7d', `product_sku=eq.${encodeURIComponent(sku)}&order=changes.desc`);
        if (trends.length === 0) {
            trendContainer.innerHTML = '<p class="text-center" style="font-size:0.8rem;color:var(--text-muted)">Không có biến động giá 7 ngày qua.</p>';
        } else {
            const DIRECTION_CONFIG = {
                up:   { icon: 'bi-arrow-up-circle-fill',  color: 'var(--red)' },
                down: { icon: 'bi-arrow-down-circle-fill', color: 'var(--green)' },
                flat: { icon: 'bi-dash-circle',            color: 'var(--text-muted)' },
            };

            trendContainer.innerHTML = `
                <table style="width:100%;font-size:0.82rem;">
                    <thead>
                        <tr>
                            <th>Cửa hàng</th>
                            <th>Đổi giá</th>
                            <th style="text-align:right">Trước</th>
                            <th style="text-align:right">Hiện tại</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${trends.map(t => {
                            const dir = DIRECTION_CONFIG[t.direction] || DIRECTION_CONFIG.flat;
                            const pct = t.pct_change ? Math.abs(t.pct_change) + '%' : '0%';
                            return `
                            <tr>
                                <td><strong>${t.competitor}</strong></td>
                                <td>
                                    <i class="bi ${dir.icon}" style="color:${dir.color}"></i>
                                    <span style="font-weight:600;color:${dir.color}">${pct} (${t.changes}×)</span>
                                </td>
                                <td style="text-align:right">${formatVND(t.first_price)}</td>
                                <td style="text-align:right;font-weight:700">${formatVND(t.last_price)}</td>
                            </tr>`;
                        }).join('')}
                    </tbody>
                </table>`;
        }
    } catch(err) {
        console.error(err);
        trendContainer.innerHTML = '<p class="text-center" style="font-size:0.8rem;color:var(--red)">Lỗi tải xu hướng.</p>';
    }
}

// ── Render bảng Hết hàng đối thủ còn ────────────────────────────────
function renderOosTablePage(oosList) {
    const tbody = document.getElementById('category-oos-body');
    if (!tbody) return;

    if (oosList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center">🎉 Không có cơ hội mất bán nào khớp bộ lọc!</td></tr>';
        return;
    }

    tbody.innerHTML = oosList.map(r => `
        <tr>
            <td>
                <div style="font-weight:600;font-size:0.9rem;">${truncate(r.product_name, 50)}</div>
                <div style="font-size:0.75rem;color:var(--text-muted)">${r.brand} · ${r.category}</div>
            </td>
            <td><span class="sku-tag">${r.sku}</span></td>
            <td><span class="badge badge-yellow">${r.competitors_in_stock} đối thủ</span></td>
            <td><span class="badge badge-neutral">${r.cheapest_competitor || '—'}</span></td>
            <td style="font-weight:700;color:var(--green-500)">${r.cheapest_competitor_price ? formatVND(r.cheapest_competitor_price) : '—'}</td>
            <td>
                <div style="display:flex;gap:0.3rem">
                    ${r.our_url ? `<a href="${r.our_url}" target="_blank" class="badge badge-neutral" style="text-decoration:none"><i class="bi bi-house"></i> Web TNC</a>` : ''}
                    ${r.cheapest_competitor_url ? `<a href="${r.cheapest_competitor_url}" target="_blank" class="badge badge-red" style="text-decoration:none"><i class="bi bi-box-arrow-up-right"></i> Web Đối Thủ</a>` : ''}
                </div>
            </td>
        </tr>
    `).join('');
}

// ── Tính toán & render độ phủ đối thủ (Dynamic Coverage) ─────────────
function updateCoverage(filteredProducts) {
    const container = document.getElementById('coverage-container');
    if (!container) return;

    const counts = {};
    const prices = {};

    filteredProducts.forEach(p => {
        const stores = typeof p.prices_by_store === 'string'
            ? JSON.parse(p.prices_by_store)
            : (p.prices_by_store || []);
        
        stores.forEach(s => {
            if (s.is_self) return; // Bỏ qua cửa hàng Thành Nhân
            const name = s.store;
            if (!counts[name]) {
                counts[name] = 0;
                prices[name] = [];
            }
            if (s.in_stock) {
                counts[name]++;
                if (s.price) prices[name].push(s.price);
            }
        });
    });

    const competitors = Object.entries(counts).map(([name, count]) => {
        const priceList = prices[name];
        const avgPrice = priceList.length ? Math.round(priceList.reduce((a, b) => a + b, 0) / priceList.length) : 0;
        return { name, products_matched: count, avg_price: avgPrice };
    }).sort((a, b) => b.products_matched - a.products_matched);

    if (competitors.length === 0) {
        container.innerHTML = '<p class="text-center">Chưa có dữ liệu độ phủ cho bộ lọc hiện tại.</p>';
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
                                    <div style="height:100%;width:${pct}%;background:var(--accent);border-radius:4px;transition:width 0.5s"></div>
                                </div>
                                <span style="font-size:0.8rem;color:var(--text-muted);min-width:30px">${pct}%</span>
                            </div>
                        </td>
                    </tr>`;
                }).join('')}
            </tbody>
        </table>`;
}

// ── Áp dụng Bộ Lọc Đa Năng (Apply Multi-Filters) ────────────────────
function applyFilters() {
    const q = document.getElementById('filter-search').value.toLowerCase().trim();
    const cat = document.getElementById('filter-category').value;
    const brand = document.getElementById('filter-brand').value;
    const status = document.getElementById('filter-status').value;

    // 1. Lọc danh sách sản phẩm Master
    let filteredProducts = allProducts;

    if (q) {
        filteredProducts = filteredProducts.filter(p =>
            p.product_name.toLowerCase().includes(q) || p.sku.toLowerCase().includes(q)
        );
    }
    if (cat !== 'all') {
        filteredProducts = filteredProducts.filter(p => p.category.toLowerCase() === cat.toLowerCase());
    }
    if (brand !== 'all') {
        filteredProducts = filteredProducts.filter(p => p.brand.toLowerCase() === brand.toLowerCase());
    }
    if (status !== 'all') {
        if (status === 'beaten') {
            filteredProducts = filteredProducts.filter(p => p.our_price && p.lowest_price && p.our_price > p.lowest_price);
        } else if (status === 'beating') {
            filteredProducts = filteredProducts.filter(p => p.our_price && p.lowest_price && p.our_price <= p.lowest_price);
        } else if (status === 'no-competitor') {
            filteredProducts = filteredProducts.filter(p => !p.lowest_price || p.num_sources === 0);
        }
    }

    // Cập nhật KPIs
    document.getElementById('cat-kpi-products').textContent = filteredProducts.length;

    const beaten = filteredProducts.filter(p => p.our_price && p.lowest_price && p.our_price > p.lowest_price).length;
    document.getElementById('cat-kpi-beaten').textContent = beaten;

    const withDelta = filteredProducts.filter(p => p.pct_vs_mean !== null);
    const avg = withDelta.length
        ? (withDelta.reduce((s, p) => s + p.pct_vs_mean, 0) / withDelta.length).toFixed(1)
        : null;
    const avgEl = document.getElementById('cat-kpi-avg');
    avgEl.textContent = avg !== null ? (avg > 0 ? '+' : '') + avg + '%' : '—';
    if (avg !== null) {
        avgEl.className = `value ${avg > 0 ? 'highlight-red' : 'highlight-green'}`;
    } else {
        avgEl.className = 'value';
    }

    // Nạp dữ liệu vào Master Paginator
    catPaginator.setData(filteredProducts);

    // Reset detail view if the currently selected item is not in the filtered list
    if (currentSelectedSku && !filteredProducts.some(p => p.sku === currentSelectedSku)) {
        currentSelectedSku = null;
        document.getElementById('detail-placeholder').style.display = 'block';
        document.getElementById('detail-content').style.display = 'none';
    }

    // 2. Lọc danh sách OOS Gaps
    let filteredOos = allOosData;
    if (cat !== 'all') {
        filteredOos = filteredOos.filter(r => r.category.toLowerCase() === cat.toLowerCase());
    }
    if (brand !== 'all') {
        filteredOos = filteredOos.filter(r => r.brand.toLowerCase() === brand.toLowerCase());
    }
    if (q) {
        filteredOos = filteredOos.filter(r =>
            r.product_name.toLowerCase().includes(q) || r.sku.toLowerCase().includes(q)
        );
    }
    oosPaginator.setData(filteredOos);

    // 3. Tính toán lại độ phủ đối thủ động
    updateCoverage(filteredProducts);

    // Cập nhật tiêu đề hiển thị trạng thái
    const lastUpdate = document.getElementById('last-update');
    lastUpdate.innerHTML = `<i class="bi bi-funnel"></i> Đã lọc: ${filteredProducts.length} SP`;
}

// ── Tải toàn bộ dữ liệu ──────────────────────────────────────────────
async function fetchAllData() {
    try {
        document.getElementById('category-table-body').innerHTML =
            '<tr><td colspan="4" class="text-center">Đang tải dữ liệu...</td></tr>';

        const [products, oosList] = await Promise.all([
            supabaseFetch('product_overview', 'order=pct_vs_mean.desc.nullslast'),
            supabaseFetch('out_of_stock_gap', 'order=competitors_in_stock.desc'),
        ]);

        allProducts = products;
        allOosData = oosList;

        // Điền danh sách thương hiệu động vào Dropdown
        const brandSelect = document.getElementById('filter-brand');
        if (brandSelect) {
            brandSelect.innerHTML = '<option value="all">Tất cả thương hiệu</option>';
            const brands = [...new Set(products.map(p => p.brand).filter(Boolean))].sort();
            brands.forEach(b => {
                const opt = document.createElement('option');
                opt.value = b;
                opt.textContent = b;
                brandSelect.appendChild(opt);
            });
        }

        // Áp dụng bộ lọc lần đầu
        applyFilters();

        // Ẩn loader
        document.getElementById('cr-overlay')?.classList.add('hidden');

    } catch (err) {
        console.error(err);
        document.getElementById('category-table-body').innerHTML =
            `<tr><td colspan="4" class="text-center highlight-red">❌ Lỗi: ${err.message}</td></tr>`;
        document.getElementById('cr-overlay')?.classList.add('hidden');
    }
}

// ── Khởi động ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Khởi tạo các paginators
    catPaginator = createPaginator({
        containerId: 'cat-table-pagination',
        renderFn: renderCategoryTablePage,
        defaultSize: 25
    });

    oosPaginator = createPaginator({
        containerId: 'cat-oos-pagination',
        renderFn: renderOosTablePage,
        defaultSize: 15
    });

    // Lắng nghe sự kiện của bộ lọc
    document.getElementById('filter-search').addEventListener('input', applyFilters);
    document.getElementById('filter-category').addEventListener('change', applyFilters);
    document.getElementById('filter-brand').addEventListener('change', applyFilters);
    document.getElementById('filter-status').addEventListener('change', applyFilters);

    // Tải dữ liệu ban đầu
    fetchAllData();
});
