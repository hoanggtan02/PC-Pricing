// =====================================================================
// price-activity.js — Biến Động Giá Thị Trường
// Đọc view `price_activity`: tần suất đổi giá theo (đối thủ × tuần)
// =====================================================================

// Cấu hình font chữ sang trọng đồng bộ cho Chart.js
if (typeof Chart !== 'undefined') {
    Chart.defaults.font.family = "'Plus Jakarta Sans', sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = '#5E6E65';
}

// Màu thương hiệu
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

let activityChart   = null;
let allActivityData = [];
let activityPaginator;

function weekLabel(weekStart) {
    const mon = new Date(weekStart + 'T00:00:00');
    const sun = new Date(mon);
    sun.setDate(mon.getDate() + 6);
    return `${mon.getDate()}–${sun.getDate()} Th${sun.getMonth() + 1}`;
}

function renderActivityTablePage(sorted) {
    const tbody = document.getElementById('activity-table-body');
    tbody.innerHTML = '';
    sorted.forEach(row => {
        const ratio = row.changes_per_100_products_week;
        let badge = '<span class="badge badge-green">Thấp</span>';
        if (ratio > 20) badge = '<span class="badge badge-red">Cao</span>';
        else if (ratio > 10) badge = '<span class="badge" style="background:#fef9c3;color:#a16207">Trung bình</span>';

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>
                <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${getColor(row.competitor)};margin-right:8px"></span>
                <strong>${row.competitor}</strong>
                ${row.is_self ? '<span class="badge badge-green" style="margin-left:4px;font-size:0.7rem">Chúng ta</span>' : ''}
            </td>
            <td style="font-weight:700">${row.price_changes}</td>
            <td>${row.products}</td>
            <td style="font-weight:700;color:var(--accent)">${ratio}</td>
            <td>${badge}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderActivity(weekData) {
    const sorted = [...weekData].sort((a, b) => b.changes_per_100_products_week - a.changes_per_100_products_week);

    // KPIs
    const topStore = sorted.find(r => !r.is_self);
    document.getElementById('act-most-active').textContent = topStore ? topStore.competitor : '—';
    document.getElementById('act-most-active-count').textContent =
        topStore ? `${topStore.changes_per_100_products_week} lần / 100 sản phẩm` : '';

    const tnc = sorted.find(r => r.is_self);
    document.getElementById('act-tnc-changes').textContent =
        tnc ? tnc.changes_per_100_products_week : '0';

    const totalChanges = weekData.reduce((s, r) => s + (r.price_changes || 0), 0);
    document.getElementById('act-total-changes').textContent = totalChanges;

    // Biểu đồ
    const labels = sorted.map(r => r.competitor);
    const values = sorted.map(r => r.changes_per_100_products_week);
    const colors = sorted.map(r => getColor(r.competitor));

    const ctx = document.getElementById('activity-chart').getContext('2d');
    if (activityChart) activityChart.destroy();
    activityChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Lần đổi giá / 100 sản phẩm',
                data: values,
                backgroundColor: colors,
                borderRadius: 8,
                borderSkipped: false,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.raw} lần / 100 sản phẩm`
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

    // Phân trang bảng chi tiết
    activityPaginator.setData(sorted);
}

async function fetchPriceActivity() {
    try {
        allActivityData = await supabaseFetch('price_activity', 'order=week_start.desc');

        if (allActivityData.length === 0) {
            document.getElementById('activity-table-body').innerHTML =
                '<tr><td colspan="5" class="text-center">Chưa có đủ dữ liệu lịch sử để phân tích.</td></tr>';
            return;
        }

        const weeks = [...new Set(allActivityData.map(r => r.week_start))].sort((a, b) => b.localeCompare(a)).slice(0, 8);

        const select = document.getElementById('week-select');
        weeks.forEach((w, i) => {
            const opt = document.createElement('option');
            opt.value = w;
            opt.textContent = weekLabel(w) + (i === 0 ? ' (Gần nhất)' : '');
            select.appendChild(opt);
        });

        select.value = weeks[0];
        const latestWeekData = allActivityData.filter(r => r.week_start === weeks[0]);
        renderActivity(latestWeekData);

        select.addEventListener('change', (e) => {
            const filtered = allActivityData.filter(r => r.week_start === e.target.value);
            renderActivity(filtered);
        });

        window.hideLoader?.();

    } catch (e) {
        console.error(e);
        document.getElementById('activity-table-body').innerHTML =
            '<tr><td colspan="5" class="text-center highlight-red">Lỗi tải dữ liệu.</td></tr>';
        window.hideLoader?.();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    activityPaginator = createPaginator({
        containerId: 'activity-table-pagination',
        renderFn: renderActivityTablePage,
        defaultSize: 15
    });
    fetchPriceActivity();
});
