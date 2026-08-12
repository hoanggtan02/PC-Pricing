<?php // data-manager.php — Quản lý & Kiểm tra Dữ liệu ?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quản Lý Dữ Liệu - TNC Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@300;400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <link rel="stylesheet" href="assets/style.css">
    <style>
        /* data-manager.php specific styles */
        td { vertical-align: middle; }
        th { white-space: nowrap; }
        .url-cell {
            max-width: 280px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .url-cell a {
            color: var(--accent);
            text-decoration: none;
            font-size: 0.83rem;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }
        .url-cell a:hover { text-decoration: underline; }
        .anomaly-row { background: #FFFBF2 !important; }
        .anomaly-badge {
            display: inline-flex; align-items: center; gap: 0.3rem;
            background: #FFF3CD; color: #856404; border: 1px solid #FFECB5;
            border-radius: 0.35rem; padding: 0.2rem 0.55rem; font-size: 0.72rem; font-weight: 700;
        }
        .sku-suspect { color: var(--red); font-weight: 700; font-family: 'Exo 2', monospace; }
    </style>

</head>
<body>
    <div id="cr-overlay">
        <svg class="loader" viewBox="0 0 160 160" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
            <defs>
                <linearGradient id="lg" x1="90.48" y1="111.14" x2="161.56" y2="8.12" gradientUnits="userSpaceOnUse">
                    <stop offset="0" stop-color="#014f2b"/><stop offset=".17" stop-color="#0e5b2d"/>
                    <stop offset=".5" stop-color="#327b35"/><stop offset=".95" stop-color="#6cb041"/>
                    <stop offset="1" stop-color="#75c044"/>
                </linearGradient>
                <linearGradient id="lg1" x1="6" y1="145.75" x2="62.13" y2="57.17" xlink:href="#lg"/>
                <linearGradient id="lg2" x1="32.92" y1="37.18" x2="133.55" y2="124.75" xlink:href="#lg"/>
            </defs>
            <path fill="url(#lg)" opacity="0.18" d="M156.63,22.44c-.58-1.5-1.33-2.94-2.33-4.19-.63-.78-1.37-1.44-2.19-1.97-3.75-2.43-9.19-2.4-13.22-1.31-5.85,1.58-10.99,5.14-15.82,8.69-10.63,7.82-19.88,17.53-28.42,27.54-1.21,1.41-2.44,2.86-3.65,4.36-.04.06-.1.12-.16.2-.02.02-.04.06-.06.08-.08.08-.14.18-.22.26-.2.26-.4.52-.6.77h0s7.14,6.27,7.14,6.27c.2-.26.4-.5.6-.75,4.11-5,8.11-9.56,11.86-13.55.04-.04.06-.06.1-.1.02-.02.06-.06.06-.08.02-.02.06-.06.06-.08,12.69-13.29,22.93-20.39,27.07-17.55,5.73,3.95-2.3,26-18.41,52.95h0s2.33,2.26,2.33,2.26c5.78,5.6,15.91,6.96,21.99,1.69l5.13-6.45c-.41,1.13-.84,2.26-1.27,3.38,4.43-11.47,8.21-23.27,10.38-35.37,1.54-8.6,2.87-18.65-.35-27.04Z"/>
            <path fill="url(#lg1)" opacity="0.18" d="M62.85,97.08c-18.07,22.13-34.09,35.52-39.51,31.79-5.67-3.91,2.12-25.58,17.93-52.16,0,0,.01.01.02.02l-.02-.02-5-4.48c-5.39-4.8-13.49-4.96-19.02-.32-1.28,1.06-2.61,2.36-4.01,3.91-3.75,9.8-6.94,19.82-9.14,30.04-2.21,10.24-5.16,24.8.81,34.4,1.41,2.27,3.48,3.88,6.04,4.66,9.59,2.94,19.24-3.52,26.61-9.01,10.81-8.05,20.21-18,28.88-28.26.91-1.07,1.97-2.13,2.75-3.3.04-.06.1-.12.14-.18.1-.12.2-.24.3-.36.06-.06.1-.14.16-.2h0l-6.94-6.51"/>
            <path id="a1" fill="url(#lg)" opacity="0" d="M156.63,22.44c-.58-1.5-1.33-2.94-2.33-4.19-.63-.78-1.37-1.44-2.19-1.97-3.75-2.43-9.19-2.4-13.22-1.31-5.85,1.58-10.99,5.14-15.82,8.69-10.63,7.82-19.88,17.53-28.42,27.54-1.21,1.41-2.44,2.86-3.65,4.36-.04.06-.1.12-.16.2-.02.02-.04.06-.06.08-.08.08-.14.18-.22.26-.2.26-.4.52-.6.77h0s7.14,6.27,7.14,6.27c.2-.26.4-.5.6-.75,4.11-5,8.11-9.56,11.86-13.55.04-.04.06-.06.1-.1.02-.02.06-.06.06-.08.02-.02.06-.06.06-.08,12.69-13.29,22.93-20.39,27.07-17.55,5.73,3.95-2.3,26-18.41,52.95h0s2.33,2.26,2.33,2.26c5.78,5.6,15.91,6.96,21.99,1.69l5.13-6.45c-.41,1.13-.84,2.26-1.27,3.38,4.43-11.47,8.21-23.27,10.38-35.37,1.54-8.6,2.87-18.65-.35-27.04Z"/>
            <path id="a2" fill="url(#lg1)" opacity="0" d="M62.85,97.08c-18.07,22.13-34.09,35.52-39.51,31.79-5.67-3.91,2.12-25.58,17.93-52.16,0,0,.01.01.02.02l-.02-.02-5-4.48c-5.39-4.8-13.49-4.96-19.02-.32-1.28,1.06-2.61,2.36-4.01,3.91-3.75,9.8-6.94,19.82-9.14,30.04-2.21,10.24-5.16,24.8.81,34.4,1.41,2.27,3.48,3.88,6.04,4.66,9.59,2.94,19.24-3.52,26.61-9.01,10.81-8.05,20.21-18,28.88-28.26.91-1.07,1.97-2.13,2.75-3.3.04-.06.1-.12.14-.18.1-.12.2-.24.3-.36.06-.06.1-.14.16-.2h0l-6.94-6.51"/>
            <path id="a3" fill="url(#lg2)" opacity="0" d="M141.71,86.8c-6.08,5.27-15.18,5.02-20.96-.58l-2.33-2.26h0s0,0,0,0l-.14-.2-21.2-20.63s0,0,0,0l-7.14-6.27h0s0,0,0,0c-.08-.08-46.54-43.42-46.57-43.45-.01.03-16.47,31.79-19.99,38.85-.06.12-.12.22-.16.32-.18.37-.35.75-.52,1.13-.82,1.75-1.64,3.51-2.44,5.28l-.03.07c-.91,2.01-1.79,4.03-2.66,6.06-.21.49-.41.98-.62,1.48-.64,1.52-1.28,3.05-1.9,4.58-.31.77-.62,1.55-.92,2.33-.3.77-.59,1.54-.89,2.31,1.4-1.55,2.73-2.85,4.01-3.91,5.53-4.64,13.64-4.48,19.02.32l5,4.48.02.02c.1.09,1.21,1.03,1.23.99,4.31,4.08,7.81,7.4,11.28,10.78.4.39.79.76,1.13,1.1l1.68,1.59,4.58,4.33,1.66,1.57,6.94,6.51,2.42,2.28,44.54,40.72c9.94-19,19.93-37.09,27.98-57,.64-1.57,1.26-3.16,1.88-4.74.43-1.13.86-2.25,1.27-3.38l-6.16,5.34Z"/>
        </svg>
    </div>

    <div class="background-blobs"><div class="blob blob-1"></div><div class="blob blob-2"></div></div>
    <div class="app-container">
                <nav class="nav-menu">
            <a href="index.php"><i class="bi bi-speedometer2"></i> Tổng quan</a>
            <a href="category.php"><i class="bi bi-funnel"></i> Bộ Lọc Chi Tiết</a>
            <a href="stock-gap.php"><i class="bi bi-box-seam"></i> Khoảng Trống Hàng</a>
            <a href="price-activity.php"><i class="bi bi-graph-up-arrow"></i> Biến Động Giá</a>
            <a href="trend.php"><i class="bi bi-activity"></i> Xu Hướng 7 Ngày</a>
            <a href="product.php"><i class="bi bi-search"></i> Chi Tiết SP</a>
            <a href="flash-sale.php"><i class="bi bi-lightning-charge"></i> Flash Sale</a>
            <a href="data-manager.php" class="active"><i class="bi bi-database-gear"></i> Quản Lý DL</a>
        </nav>

        <header class="glass-header">
            <div class="header-content">
                <div>
                    <h1><i class="bi bi-database-gear"></i> Quản Lý Dữ Liệu</h1>
                    <p>Kiểm tra, sửa đổi và xóa nguồn cào giá — phân trang tự động tối ưu tốc độ</p>
                </div>
                <div style="display:flex;gap:0.75rem;align-items:center;flex-wrap:wrap">
                    <div id="anomaly-header-badge" style="display:none;background:var(--red-bg);color:var(--red);border:1px solid rgba(224,90,90,0.2);padding:0.6rem 1.2rem;border-radius:0.5rem;font-size:0.85rem;font-weight:700">
                        <i class="bi bi-exclamation-triangle"></i> <span id="anomaly-count-hdr">0</span> vấn đề cần xem
                    </div>
                    <button class="btn-primary" onclick="DM.refreshAll()">
                        <i class="bi bi-arrow-clockwise"></i> Tải lại
                    </button>
                </div>
            </div>
        </header>

        <main>
            <!-- Tabs -->
            <div class="dm-tabs">
                <button class="dm-tab-btn active" id="tab-btn-sources" onclick="DM.switchTab('sources')">
                    <i class="bi bi-link-45deg"></i> Nguồn Cào Giá
                    <span class="tab-count" id="tab-count-sources">—</span>
                </button>
                <button class="dm-tab-btn tab-warn" id="tab-btn-anomalies" onclick="DM.switchTab('anomalies')">
                    <i class="bi bi-exclamation-triangle"></i> Bất Thường
                    <span class="tab-count" id="tab-count-anomalies">—</span>
                </button>
                <button class="dm-tab-btn" id="tab-btn-products" onclick="DM.switchTab('products')">
                    <i class="bi bi-box-seam"></i> Sản Phẩm
                    <span class="tab-count" id="tab-count-products">—</span>
                </button>
                <button class="dm-tab-btn" id="tab-btn-history" onclick="DM.switchTab('history')">
                    <i class="bi bi-clock-history"></i> Lịch Sử Giá
                </button>
            </div>

            <!-- ── Tab: Sources ── -->
            <div class="dm-panel active" id="panel-sources">
                <div class="glass-card table-section">
                    <div class="section-header">
                        <h2><i class="bi bi-link-45deg"></i> Danh sách nguồn cào giá</h2>
                        <span id="sources-meta" style="font-size:0.85rem;color:var(--text-muted)"></span>
                    </div>
                    <div class="dm-toolbar">
                        <input class="dm-search" id="src-search" placeholder="🔍  Tìm SKU, tên sản phẩm, cửa hàng..." oninput="DM.filterSources()">
                        <select class="dm-filter" id="src-filter-store" onchange="DM.filterSources()">
                            <option value="">Tất cả cửa hàng</option>
                        </select>
                        <select class="dm-filter" id="src-filter-status" onchange="DM.filterSources()">
                            <option value="">Tất cả trạng thái</option>
                            <option value="active">✅ Đang active</option>
                            <option value="inactive">❌ Đã tắt</option>
                        </select>
                        <button class="btn-primary" onclick="DM.exportSources()"><i class="bi bi-download"></i> Xuất CSV</button>
                    </div>
                    <div class="table-responsive">
                        <table>
                            <thead><tr>
                                <th>SKU</th><th>Tên sản phẩm</th><th>Cửa hàng</th>
                                <th>URL đang cào</th><th>Giá gần nhất</th>
                                <th>Cập nhật cuối</th><th style="text-align:center">Active</th><th>Hành động</th>
                            </tr></thead>
                            <tbody id="sources-tbody">
                                <tr class="loading-row"><td colspan="8"><span class="spinner"></span> Đang tải...</td></tr>
                            </tbody>
                        </table>
                    </div>
                    <!-- Pagination Bar for Sources -->
                    <div class="pagination-bar" id="sources-pagination"></div>
                </div>
            </div>

            <!-- ── Tab: Anomalies ── -->
            <div class="dm-panel" id="panel-anomalies">
                <div class="glass-card table-section" style="margin-bottom:1.25rem">
                    <div class="section-header">
                        <h2><i class="bi bi-exclamation-triangle" style="color:var(--red)"></i> SKU nghi vấn</h2>
                        <span style="font-size:0.85rem;color:var(--text-muted)">SKU quá ngắn (&lt;5 ký tự) hoặc chỉ là số nguyên</span>
                    </div>
                    <div class="table-responsive">
                        <table>
                            <thead><tr>
                                <th>SKU (nghi vấn)</th><th>Tên sản phẩm</th>
                                <th>Danh mục</th><th>Thương hiệu</th><th>Vấn đề</th><th>Hành động</th>
                            </tr></thead>
                            <tbody id="anomaly-sku-tbody">
                                <tr class="loading-row"><td colspan="6"><span class="spinner"></span> Đang phân tích...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="glass-card table-section" style="margin-bottom:1.25rem">
                    <div class="section-header">
                        <h2><i class="bi bi-currency-dollar" style="color:var(--red)"></i> Giá bất thường</h2>
                        <span style="font-size:0.85rem;color:var(--text-muted)">Giá = 0đ, hoặc &gt; 200 triệu</span>
                    </div>
                    <div class="table-responsive">
                        <table>
                            <thead><tr>
                                <th>SKU</th><th>Tên sản phẩm</th><th>Cửa hàng</th>
                                <th>Giá bất thường</th><th>Thời điểm</th><th>Hành động</th>
                            </tr></thead>
                            <tbody id="anomaly-price-tbody">
                                <tr class="loading-row"><td colspan="6"><span class="spinner"></span> Đang phân tích...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="glass-card table-section">
                    <div class="section-header">
                        <h2><i class="bi bi-shop" style="color:var(--gold)"></i> Sản phẩm không có nguồn nào</h2>
                        <span style="font-size:0.85rem;color:var(--text-muted)">Có trong catalog nhưng chưa cào đối thủ</span>
                    </div>
                    <div class="table-responsive">
                        <table>
                            <thead><tr>
                                <th>SKU</th><th>Tên sản phẩm</th><th>Danh mục</th><th>Thương hiệu</th>
                            </tr></thead>
                            <tbody id="anomaly-nosrc-tbody">
                                <tr class="loading-row"><td colspan="4"><span class="spinner"></span> Đang phân tích...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- ── Tab: Products ── -->
            <div class="dm-panel" id="panel-products">
                <div class="glass-card table-section">
                    <div class="section-header">
                        <h2><i class="bi bi-box-seam"></i> Danh sách sản phẩm</h2>
                        <span id="products-meta" style="font-size:0.85rem;color:var(--text-muted)"></span>
                    </div>
                    <div class="dm-toolbar">
                        <input class="dm-search" id="prod-search" placeholder="🔍  Tìm tên, SKU, danh mục, thương hiệu..." oninput="DM.filterProducts()">
                        <select class="dm-filter" id="prod-filter-cat" onchange="DM.filterProducts()">
                            <option value="">Tất cả danh mục</option>
                        </select>
                        <select class="dm-filter" id="prod-filter-brand" onchange="DM.filterProducts()">
                            <option value="">Tất cả thương hiệu</option>
                        </select>
                        <button class="btn-primary" onclick="DM.exportProducts()"><i class="bi bi-download"></i> Xuất CSV</button>
                    </div>
                    <div class="table-responsive">
                        <table>
                            <thead><tr>
                                <th>SKU</th><th>Tên sản phẩm</th><th>Danh mục</th>
                                <th>Thương hiệu</th><th>Giá TNC</th><th>Số nguồn</th><th>Hành động</th>
                            </tr></thead>
                            <tbody id="products-tbody">
                                <tr class="loading-row"><td colspan="7"><span class="spinner"></span> Đang tải...</td></tr>
                            </tbody>
                        </table>
                    </div>
                    <!-- Pagination Bar for Products -->
                    <div class="pagination-bar" id="products-pagination"></div>
                </div>
            </div>

            <!-- ── Tab: History ── -->
            <div class="dm-panel" id="panel-history">
                <div class="glass-card table-section">
                    <div class="section-header">
                        <h2><i class="bi bi-clock-history"></i> Lịch sử giá theo SKU</h2>
                    </div>
                    <div class="dm-toolbar">
                        <div style="position:relative;flex:1;min-width:200px">
                            <input class="dm-search" id="hist-sku-input" placeholder="Nhập SKU hoặc tên sản phẩm..." style="width:100%" oninput="DM.histSuggest(this.value)">
                            <div id="hist-suggest-box" style="display:none;position:absolute;z-index:9999;background:white;border:1px solid var(--border-color);border-radius:0.5rem;box-shadow:0 8px 24px rgba(0,0,0,0.1);width:100%;max-height:220px;overflow-y:auto;top:calc(100% + 4px);left:0"></div>
                        </div>
                        <select class="dm-filter" id="hist-store" onchange="DM.loadHistory()">
                            <option value="">Tất cả cửa hàng</option>
                        </select>
                        <select class="dm-filter" id="hist-days">
                            <option value="7">7 ngày</option>
                            <option value="30" selected>30 ngày</option>
                            <option value="90">90 ngày</option>
                        </select>
                        <button class="btn-primary" onclick="DM.loadHistory()"><i class="bi bi-search"></i> Tra cứu</button>
                    </div>
                    <div class="table-responsive">
                        <table>
                            <thead><tr>
                                <th>Cửa hàng</th><th>Giá</th><th>Còn hàng</th>
                                <th>Thời điểm cào</th><th>Hành động</th>
                            </tr></thead>
                            <tbody id="history-tbody">
                                <tr><td colspan="5" class="text-center" style="padding:3rem">Nhập SKU để xem lịch sử giá</td></tr>
                            </tbody>
                        </table>
                    </div>
                    <!-- Pagination Bar for History -->
                    <div class="pagination-bar" id="history-pagination"></div>
                </div>
            </div>
        </main>
    </div>

    <!-- Toast -->
    <div id="dm-toast"></div>

    <!-- Confirm Modal -->
    <div id="dm-modal-backdrop" style="display:none" class="dm-modal-backdrop">
        <div class="dm-modal">
            <h3 id="modal-title"><i class="bi bi-trash"></i> Xác nhận</h3>
            <p id="modal-body"></p>
            <div class="modal-warn" id="modal-warn" style="display:none"></div>
            <div class="modal-actions">
                <button class="btn-modal-cancel" onclick="DM.closeModal()">Hủy</button>
                <button id="modal-confirm-btn" class="btn-modal-confirm">Xác nhận</button>
            </div>
        </div>
    </div>

    <!-- Form Edit Modal Popup -->
    <div id="dm-edit-modal-backdrop" style="display:none" class="dm-modal-backdrop">
        <div class="dm-modal">
            <h3 id="edit-modal-title"><i class="bi bi-pencil-square"></i> Chỉnh sửa dữ liệu</h3>
            <div id="edit-modal-body" style="display:flex;flex-direction:column;gap:1rem;margin-top:1.25rem;"></div>
            <div class="modal-actions">
                <button class="btn-modal-cancel" onclick="DM.closeEditModal()">Hủy bỏ</button>
                <button id="edit-modal-save-btn" class="btn-primary"><i class="bi bi-floppy"></i> Lưu thay đổi</button>
            </div>
        </div>
    </div>

    <script src="assets/config.js"></script>
    <script src="assets/loader.js"></script>
    <script src="assets/data-manager.js"></script>
</body>
</html>
