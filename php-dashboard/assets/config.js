// =====================================================================
// config.js — Cấu hình kết nối Supabase (dùng chung toàn bộ ứng dụng)
// Chỉ cần thay đổi file này khi đổi project Supabase
// =====================================================================

const SUPABASE_URL = 'https://ajhmxkpkrqqarovjsbzo.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_LpRci9QBx1cOdMN7ILzBjA_BDaOBorT';

// Headers dùng cho mọi request đến Supabase REST API
const headers = {
    'apikey': SUPABASE_ANON_KEY,
    'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
    'Content-Type': 'application/json',
    'Prefer': 'count=none' // Tắt đếm tổng số dòng để tăng tốc
};

// =====================================================================
// Hàm tiện ích dùng chung
// =====================================================================

/** Format số tiền sang dạng VNĐ: 24.990.000 ₫ */
const formatVND = (price) => {
    if (price === null || price === undefined) return '—';
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(price);
};

/** Rút gọn tên sản phẩm dài: giới hạn maxLen ký tự */
const truncate = (str, maxLen = 60) => {
    if (!str) return '—';
    return str.length > maxLen ? str.slice(0, maxLen) + '…' : str;
};

/** Thời gian tương đối: "2h trước", "3 ngày trước" */
const timeAgo = (isoStr) => {
    if (!isoStr) return '—';
    const diff = Date.now() - new Date(isoStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Vừa xong';
    if (mins < 60) return `${mins} phút trước`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs} giờ trước`;
    const days = Math.floor(hrs / 24);
    return `${days} ngày trước`;
};

/**
 * Hàm fetch Supabase với phân trang tự động (PostgREST trả tối đa 1000 dòng/request)
 * @param {string} viewName  - Tên view/bảng trong Supabase
 * @param {string} query     - Query string bổ sung (vd: "brand=eq.Dell&order=sku")
 * @param {number} pageSize  - Số dòng mỗi trang (mặc định 1000)
 * @returns {Promise<Array>} - Mảng toàn bộ dữ liệu
 */
async function supabaseFetch(viewName, query = '', pageSize = 1000) {
    const all = [];
    let from = 0;

    while (true) {
        const url = `${SUPABASE_URL}/rest/v1/${viewName}?${query}${query ? '&' : ''}limit=${pageSize}&offset=${from}`;
        const res = await fetch(url, { headers });
        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`Supabase lỗi [${res.status}] khi gọi ${viewName}: ${errText}`);
        }
        const batch = await res.json();
        all.push(...batch);
        if (batch.length < pageSize) break; // Đã lấy hết
        from += pageSize;
    }
    return all;
}
