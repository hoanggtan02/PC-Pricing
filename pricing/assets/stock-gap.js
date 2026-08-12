// =====================================================================
// stock-gap.js — Khoảng Trống Hàng Hóa
// Đọc view `out_of_stock_gap`: SKU mà TNC hết hàng, đối thủ còn bán
// =====================================================================



let allGapData = [];

function renderGapTable(data) {
    const tbody = document.getElementById('gap-table-body');
    tbody.innerHTML = '';

    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">🎉 Tuyệt vời! Không có sản phẩm nào bị khoảng trống hàng hóa.</td></tr>';
        return;
    }

    data.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>
                <a href="product.php?sku=${encodeURIComponent(row.sku)}" style="font-weight:600;font-size:0.9rem;color:var(--text-main);text-decoration:none">
                    ${row.product_name} <i class="bi bi-box-arrow-up-right" style="font-size:0.75rem;color:var(--accent)"></i>
                </a>
                <div style="font-size:0.75rem;color:var(--text-muted)">${row.sku}</div>
            </td>
            <td><span class="badge badge-neutral">${row.brand}</span></td>
            <td><span class="badge badge-neutral">${row.category}</span></td>
            <td>
                <span class="badge badge-yellow" style="font-size:0.85rem">
                    ${row.competitors_in_stock} đối thủ còn
                </span>
            </td>
            <td style="font-weight:700;color:var(--green-500)">${formatVND(row.cheapest_competitor_price)}</td>
            <td><span class="badge badge-neutral">${row.cheapest_competitor || '—'}</span></td>
            <td>
                <div style="display:flex;gap:0.3rem">
                    ${row.our_url ? `<a href="${row.our_url}" target="_blank" class="badge badge-neutral" style="text-decoration:none" title="Xác nhận trang Web TNC"><i class="bi bi-house"></i> Web TNC</a>` : ''}
                    ${row.cheapest_competitor_url ? `<a href="${row.cheapest_competitor_url}" target="_blank" class="badge badge-red" style="text-decoration:none" title="Mở web ${row.cheapest_competitor} xác nhận giá"><i class="bi bi-box-arrow-up-right"></i> Web Đối Thủ</a>` : ''}
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function applyGapFilters() {
    const cat = document.getElementById('gap-category-filter').value;
    const brand = document.getElementById('gap-brand-filter').value;

    let filtered = allGapData;
    if (cat) filtered = filtered.filter(r => r.category === cat);
    if (brand) filtered = filtered.filter(r => r.brand === brand);

    renderGapTable(filtered);
}

async function fetchStockGap() {
    try {
        allGapData = await supabaseFetch('out_of_stock_gap', 'order=competitors_in_stock.desc');

        // KPIs
        window.hideLoader?.();
        document.getElementById('gap-total').textContent = allGapData.length;

        const totalCompetitors = allGapData.reduce((s, r) => s + (r.competitors_in_stock || 0), 0);
        document.getElementById('gap-competitors').textContent = totalCompetitors;

        const riskRevenue = allGapData.reduce((s, r) => s + (r.cheapest_competitor_price || 0), 0);
        document.getElementById('gap-revenue-risk').textContent = formatVND(riskRevenue);

        const lastUpdateEl = document.getElementById('last-update');
        if (lastUpdateEl) lastUpdateEl.textContent = `${allGapData.length} sản phẩm cần nhập thêm`;

        renderGapTable(allGapData);

        window.hideLoader?.();

    } catch (e) {
        console.error(e);
        document.getElementById('gap-table-body').innerHTML =
            '<tr><td colspan="7" class="text-center highlight-red">Lỗi tải dữ liệu. Kiểm tra F12 Console.</td></tr>';
        window.hideLoader?.();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    fetchStockGap();
    document.getElementById('gap-category-filter').addEventListener('change', applyGapFilters);
    document.getElementById('gap-brand-filter').addEventListener('change', applyGapFilters);
});
