<?php
$pageTitle = "Quản Lý Dữ Liệu - TNC Dashboard";
$extraHeadHtml = <<<'HTML'
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
HTML;
include 'includes/head.php';
include 'includes/body-start.php';
?>
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

<?php
$extraScripts = '<script src="assets/data-manager.js"></script>';
include 'includes/footer.php';
?>
