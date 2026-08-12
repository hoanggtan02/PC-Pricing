// =====================================================================
// pagination.js — Shared Pagination Utility
// Dùng chung cho tất cả các trang: category, brand, stock-gap, flash-sale,
//                                    price-activity, trend, script (index)
// =====================================================================

/**
 * Tạo và quản lý phân trang client-side cho một bảng bất kỳ.
 * @param {Object} config
 * @param {string}   config.containerId    - ID của div chứa pagination bar
 * @param {Function} config.renderFn       - Hàm render bảng nhận (pageItems) làm tham số
 * @param {number}   [config.defaultSize]  - Số dòng mặc định mỗi trang (default: 25)
 */
function createPaginator(config) {
    const { containerId, renderFn, defaultSize = 25 } = config;
    let _allItems    = [];
    let _currentPage = 1;
    let _pageSize    = defaultSize;

    function _getContainer() {
        return document.getElementById(containerId);
    }

    function _render() {
        const total      = _allItems.length;
        const totalPages = Math.max(1, Math.ceil(total / _pageSize));
        if (_currentPage > totalPages) _currentPage = totalPages;

        const start     = (_currentPage - 1) * _pageSize;
        const pageItems = _allItems.slice(start, start + _pageSize);

        // Gọi hàm render của module (render dòng bảng)
        renderFn(pageItems);

        // Render pagination bar
        const container = _getContainer();
        if (!container) return;

        if (total === 0) {
            container.innerHTML = '';
            return;
        }

        const startItem = start + 1;
        const endItem   = Math.min(total, start + _pageSize);

        // Build page buttons (window of 5)
        let pageBtns = '';
        let startP = Math.max(1, _currentPage - 2);
        let endP   = Math.min(totalPages, _currentPage + 2);

        if (startP > 1) {
            pageBtns += `<button class="page-btn" data-page="1">1</button>`;
            if (startP > 2) pageBtns += `<span class="page-ellipsis">…</span>`;
        }
        for (let p = startP; p <= endP; p++) {
            pageBtns += `<button class="page-btn${p === _currentPage ? ' active' : ''}" data-page="${p}">${p}</button>`;
        }
        if (endP < totalPages) {
            if (endP < totalPages - 1) pageBtns += `<span class="page-ellipsis">…</span>`;
            pageBtns += `<button class="page-btn" data-page="${totalPages}">${totalPages}</button>`;
        }

        container.innerHTML = `
            <div class="page-info">
                Hiển thị <strong>${startItem} – ${endItem}</strong> / tổng <strong>${total}</strong> dòng
            </div>
            <div class="pagination-controls">
                <select class="page-size-select" data-paginator-size>
                    <option value="10"  ${_pageSize ===  10 ? 'selected' : ''}>10 / trang</option>
                    <option value="25"  ${_pageSize ===  25 ? 'selected' : ''}>25 / trang</option>
                    <option value="50"  ${_pageSize ===  50 ? 'selected' : ''}>50 / trang</option>
                    <option value="100" ${_pageSize === 100 ? 'selected' : ''}>100 / trang</option>
                </select>
                <button class="page-btn" data-page="${_currentPage - 1}" ${_currentPage <= 1 ? 'disabled' : ''}>
                    <i class="bi bi-chevron-left"></i>
                </button>
                ${pageBtns}
                <button class="page-btn" data-page="${_currentPage + 1}" ${_currentPage >= totalPages ? 'disabled' : ''}>
                    <i class="bi bi-chevron-right"></i>
                </button>
            </div>
        `;

        // Bind events
        container.querySelectorAll('.page-btn[data-page]').forEach(btn => {
            btn.addEventListener('click', () => {
                const p = parseInt(btn.getAttribute('data-page'));
                if (!isNaN(p) && p >= 1 && p <= totalPages) {
                    _currentPage = p;
                    _render();
                    // Smooth scroll to top of table
                    container.scrollIntoView({ behavior: 'smooth', block: 'end' });
                }
            });
        });
        const sizeSelect = container.querySelector('[data-paginator-size]');
        if (sizeSelect) {
            sizeSelect.addEventListener('change', () => {
                _pageSize    = parseInt(sizeSelect.value) || 25;
                _currentPage = 1;
                _render();
            });
        }
    }

    return {
        /**
         * Load data mới và reset về trang 1
         * @param {Array} items - Toàn bộ dữ liệu
         */
        setData(items) {
            _allItems    = items || [];
            _currentPage = 1;
            _render();
        },
        /** Reload trang hiện tại (dùng khi data không đổi) */
        refresh() {
            _render();
        },
        /** Lấy toàn bộ items */
        getAll() { return _allItems; }
    };
}
