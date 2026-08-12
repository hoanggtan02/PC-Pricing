// =====================================================================
// stock-gap.js — Khoảng Trống Hàng Hóa
// Đọc view `out_of_stock_gap`: SKU mà TNC hết hàng, đối thủ còn bán
// =====================================================================

const formatVND = (price) => {
    if (!price) return '—';
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(price);
};

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
                <div style="font-weight:600">${row.product_name}</div>
                <div style="font-size:0.75rem;color:var(--text-muted)">${row.sku}</div>
            </td>
            <td><span class="badge badge-neutral">${row.brand}</span></td>
            <td><span class="badge badge-neutral">${row.category}</span></td>
            <td>
                <span class="badge badge-red" style="font-size:0.9rem">
                    ${row.competitors_in_stock} đối thủ
                </span>
            </td>
            <td style="font-weight:700;color:var(--green-500)">${formatVND(row.cheapest_competitor_price)}</td>
            <td>${row.cheapest_competitor || '—'}</td>
            <td>
                ${row.cheapest_competitor_url
                    ? `<a href="${row.cheapest_competitor_url}" target="_blank" class="badge badge-green" style="text-decoration:none">🔗 Xem</a>`
                    : '—'
                }
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
        const res = await fetch(`${SUPABASE_URL}/rest/v1/out_of_stock_gap?order=competitors_in_stock.desc`, { headers });
        allGapData = await res.json();

        // KPIs
        document.getElementById('gap-total').textContent = allGapData.length;

        const totalCompetitors = allGapData.reduce((s, r) => s + (r.competitors_in_stock || 0), 0);
        document.getElementById('gap-competitors').textContent = totalCompetitors;

        const riskRevenue = allGapData.reduce((s, r) => s + (r.cheapest_competitor_price || 0), 0);
        document.getElementById('gap-revenue-risk').textContent = formatVND(riskRevenue);

        document.getElementById('last-update').textContent = `${allGapData.length} sản phẩm cần nhập thêm`;

        renderGapTable(allGapData);

    } catch (e) {
        console.error(e);
        document.getElementById('gap-table-body').innerHTML =
            '<tr><td colspan="7" class="text-center highlight-red">Lỗi tải dữ liệu. Kiểm tra F12 Console.</td></tr>';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    fetchStockGap();
    document.getElementById('gap-category-filter').addEventListener('change', applyGapFilters);
    document.getElementById('gap-brand-filter').addEventListener('change', applyGapFilters);
});
