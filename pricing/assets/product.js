// =====================================================================
// product.js — Chi Tiết Sản Phẩm (product.php)
// Nguồn: product_overview (prices_by_store) + sku_price_trend_7d
// =====================================================================

let allProductList = [];  // danh sách để autocomplete
let currentSku     = '';

// ── Autocomplete tìm kiếm ────────────────────────────────────────────
async function loadProductList() {
    try {
        const products = await supabaseFetch('product_overview',
            'select=sku,product_name,brand,category&order=product_name');
        allProductList = products;

        // Nếu có SKU từ URL (PHP truyền xuống), tự động tìm kiếm
        if (typeof INITIAL_SKU !== 'undefined' && INITIAL_SKU) {
            document.getElementById('sku-search').value = INITIAL_SKU;
            loadProduct(INITIAL_SKU);
        } else {
            window.hideLoader?.();
        }
    } catch (err) {
        console.error('Không thể tải danh sách sản phẩm:', err);
        window.hideLoader?.();
    }
}

function showSuggestions(query) {
    const box = document.getElementById('suggestion-box');
    if (!query || query.length < 2) { box.style.display = 'none'; return; }

    const q = query.toLowerCase();
    const matches = allProductList
        .filter(p => p.product_name.toLowerCase().includes(q) || p.sku.toLowerCase().includes(q))
        .slice(0, 8);

    if (matches.length === 0) { box.style.display = 'none'; return; }

    box.innerHTML = matches.map(p => `
        <div class="suggestion-item" onclick="selectProduct('${p.sku}', '${p.product_name.replace(/'/g, "\\'")}')">
            <div style="font-weight:600;font-size:0.88rem">${truncate(p.product_name, 55)}</div>
            <span class="sku-tag">${p.sku} · ${p.brand} · ${p.category}</span>
        </div>
    `).join('');
    box.style.display = 'block';
}

function selectProduct(sku, name) {
    document.getElementById('sku-search').value = name;
    document.getElementById('suggestion-box').style.display = 'none';
    loadProduct(sku);
}

function doSearch() {
    const val = document.getElementById('sku-search').value.trim();
    // Tìm trong danh sách xem có SKU trùng không
    const exact = allProductList.find(p =>
        p.sku.toLowerCase() === val.toLowerCase() ||
        p.product_name.toLowerCase() === val.toLowerCase()
    );
    if (exact) {
        loadProduct(exact.sku);
    } else if (allProductList.length > 0) {
        // Lấy kết quả đầu tiên của autocomplete
        const q = val.toLowerCase();
        const first = allProductList.find(p =>
            p.product_name.toLowerCase().includes(q) || p.sku.toLowerCase().includes(q)
        );
        if (first) loadProduct(first.sku);
    }
}

// ── Load chi tiết 1 sản phẩm ─────────────────────────────────────────
async function loadProduct(sku) {
    currentSku = sku;
    document.getElementById('product-placeholder').style.display = 'none';
    document.getElementById('product-detail').style.display = 'block';
    document.getElementById('last-update').innerHTML = `<i class="bi bi-hourglass-split"></i> Đang tải ${sku}...`;

    // Reset bảng
    document.getElementById('product-price-table').innerHTML =
        `<tr><td colspan="6" class="text-center">Đang tải...</td></tr>`;
    document.getElementById('product-trend-container').innerHTML =
        `<p class="text-center">Đang tải xu hướng...</p>`;

    try {
        const [rows, trends] = await Promise.all([
            supabaseFetch('product_overview', `sku=eq.${encodeURIComponent(sku)}&select=*`),
            supabaseFetch('sku_price_trend_7d', `product_sku=eq.${encodeURIComponent(sku)}&order=changes.desc`),
        ]);

        if (rows.length === 0) {
            document.getElementById('product-placeholder').style.display = 'block';
            document.getElementById('product-detail').style.display = 'none';
            document.getElementById('last-update').innerHTML =
                `<i class="bi bi-exclamation-circle"></i> Không tìm thấy SKU: ${sku}`;
            return;
        }

        const p = rows[0];
        const pricesByStore = typeof p.prices_by_store === 'string'
            ? JSON.parse(p.prices_by_store)
            : p.prices_by_store;

        // KPIs
        document.getElementById('p-our-price').textContent   = formatVND(p.our_price);
        document.getElementById('p-lowest-price').textContent = formatVND(p.lowest_price);
        document.getElementById('p-lowest-store').textContent = p.cheapest_competitor || '—';
        document.getElementById('p-mean-price').textContent  = formatVND(p.mean_price);
        document.getElementById('p-num-sources').textContent = `${p.num_sources || 0} đối thủ có giá`;

        const pct = p.pct_vs_mean;
        const pctEl = document.getElementById('p-pct');
        pctEl.textContent = pct !== null ? (pct > 0 ? '+' : '') + pct + '%' : '—';
        pctEl.className = 'value ' + (pct > 0 ? 'highlight-red' : 'highlight-green');

        // Meta
        document.getElementById('product-meta').innerHTML =
            `<span class="badge badge-neutral">${p.brand}</span>
             <span class="badge badge-neutral" style="margin-left:0.3rem">${p.category}</span>
             <span style="margin-left:0.5rem">Cập nhật: ${timeAgo(p.last_scraped)}</span>`;

        // Bảng giá tất cả đối thủ (từ prices_by_store JSON)
        const priceTable = document.getElementById('product-price-table');
        if (pricesByStore && pricesByStore.length > 0) {
            const selfPrice = pricesByStore.find(s => s.is_self && s.in_stock)?.price;

            priceTable.innerHTML = [...pricesByStore]
                .sort((a, b) => {
                    if (!a.in_stock && b.in_stock) return 1;
                    if (a.in_stock && !b.in_stock) return -1;
                    return (a.price || 0) - (b.price || 0);
                })
                .map(s => {
                    const rowClass = s.is_self ? 'price-row-self' : '';
                    const diff = selfPrice && !s.is_self && s.in_stock
                        ? ((selfPrice - s.price) / s.price * 100).toFixed(1)
                        : null;
                    const diffBadge = diff === null
                        ? '—'
                        : diff > 0
                            ? `<span class="badge badge-red">TNC đắt hơn +${diff}%</span>`
                            : `<span class="badge badge-green">TNC rẻ hơn ${diff}%</span>`;

                    return `<tr class="${rowClass}">
                        <td>
                            ${s.is_self ? '<i class="bi bi-house-fill" style="color:var(--accent)"></i> ' : ''}
                            <strong>${s.store}</strong>
                            ${s.is_self ? '<span class="badge badge-green" style="margin-left:0.3rem">TNC</span>' : ''}
                        </td>
                        <td style="font-weight:700">${s.in_stock ? formatVND(s.price) : '<span style="color:var(--text-muted)">Hết hàng</span>'}</td>
                        <td>${s.in_stock
                            ? '<span class="badge badge-green"><i class="bi bi-check-circle"></i> Còn hàng</span>'
                            : '<span class="badge badge-red"><i class="bi bi-x-circle"></i> Hết hàng</span>'}</td>
                        <td>${s.is_flash_sale
                            ? '<span class="flash-badge"><i class="bi bi-lightning-charge-fill"></i> FLASH</span>'
                            : '—'}</td>
                        <td>${diffBadge}</td>
                        <td>${s.url
                            ? `<a href="${s.url}" target="_blank" class="badge badge-neutral" style="text-decoration:none"><i class="bi bi-box-arrow-up-right"></i> Xem</a>`
                            : '—'}</td>
                    </tr>`;
                }).join('');
        } else {
            priceTable.innerHTML = '<tr><td colspan="6" class="text-center">Không có dữ liệu giá đối thủ.</td></tr>';
        }

        // Bảng xu hướng 7 ngày
        const trendContainer = document.getElementById('product-trend-container');
        if (trends.length === 0) {
            trendContainer.innerHTML = `<p class="text-center"><i class="bi bi-check-circle" style="color:var(--green)"></i> Không có biến động giá trong 7 ngày qua.</p>`;
        } else {
            const DIRECTION_CONFIG = {
                up:   { icon: 'bi-arrow-up-circle-fill',  color: 'var(--red)',        label: '↑ Tăng' },
                down: { icon: 'bi-arrow-down-circle-fill', color: 'var(--green)',      label: '↓ Giảm' },
                flat: { icon: 'bi-dash-circle',            color: 'var(--text-muted)', label: '→ Không đổi' },
            };
            trendContainer.innerHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>Cửa hàng</th>
                            <th>Chiều hướng</th>
                            <th>Giá đầu kỳ</th>
                            <th>Giá cuối kỳ</th>
                            <th>% Thay đổi</th>
                            <th>Số lần đổi</th>
                            <th>↑ Tăng</th>
                            <th>↓ Giảm</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${trends.map(r => {
                            const dir = DIRECTION_CONFIG[r.direction] || DIRECTION_CONFIG.flat;
                            const pct = r.pct_change !== null ? r.pct_change : 0;
                            return `<tr>
                                <td><span class="badge badge-neutral">${r.competitor}</span></td>
                                <td>
                                    <i class="bi ${dir.icon}" style="color:${dir.color}"></i>
                                    <span style="color:${dir.color};font-weight:600;margin-left:0.25rem">${dir.label}</span>
                                </td>
                                <td>${formatVND(r.first_price)}</td>
                                <td style="font-weight:700">${formatVND(r.last_price)}</td>
                                <td>${r.direction === 'up'
                                    ? `<span class="badge badge-red">+${pct}%</span>`
                                    : r.direction === 'down'
                                        ? `<span class="badge badge-green">${pct}%</span>`
                                        : `<span class="badge badge-neutral">0%</span>`
                                }</td>
                                <td style="text-align:center;font-weight:700">${r.changes}</td>
                                <td style="text-align:center;color:var(--red)">${r.increases}</td>
                                <td style="text-align:center;color:var(--green)">${r.decreases}</td>
                            </tr>`;
                        }).join('')}
                    </tbody>
                </table>`;
        }

        document.getElementById('last-update').innerHTML =
            `<i class="bi bi-check-circle"></i> ${p.product_name}`;

    } catch (err) {
        console.error(err);
        document.getElementById('product-price-table').innerHTML =
            `<tr><td colspan="6" class="text-center highlight-red">❌ Lỗi: ${err.message}</td></tr>`;
    }
}

// ── Khởi động ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadProductList();

    // Autocomplete sự kiện
    const input = document.getElementById('sku-search');
    input.addEventListener('input', (e) => showSuggestions(e.target.value));
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') doSearch();
    });

    // Ẩn suggestion khi click ra ngoài
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#sku-search') && !e.target.closest('#suggestion-box')) {
            document.getElementById('suggestion-box').style.display = 'none';
        }
    });
});
