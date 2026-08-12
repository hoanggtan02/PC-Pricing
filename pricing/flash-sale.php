<?php
$pageTitle = "Flash Sale Detector - TNC Dashboard";
$extraHeadHtml = <<<'HTML'
<style>
        .flash-badge {
            background: linear-gradient(135deg, #f59e0b, #ef4444);
            color: white;
            padding: 0.2rem 0.6rem;
            border-radius: 0.35rem;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.05em;
            animation: flash-pulse 1.5s ease-in-out infinite;
        }
        @keyframes flash-pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.75; }
        }
        .kpi-flash {
            border-left: 4px solid #f59e0b;
            background: linear-gradient(135deg, #fffbeb 0%, #fff 100%);
        }
        #flash-empty {
            display: none;
            text-align: center;
            padding: 4rem 2rem;
            color: var(--text-muted);
        }
    </style>
HTML;
include 'includes/head.php';
include 'includes/body-start.php';
?>
<header class="glass-header">
        <div class="header-content">
            <div>
                <h1><i class="bi bi-lightning-charge-fill" style="color:#f59e0b"></i> Flash Sale Detector</h1>
                <p>Đối thủ nào đang giảm giá sốc? TNC có đang bị mất khách không?</p>
            </div>
            <div class="status-badge" id="last-update"><i class="bi bi-clock"></i> Đang tải...</div>
        </div>
    </header>

    <main class="dashboard-grid">
        <div class="kpi-row">
            <div class="glass-card kpi-card kpi-flash">
                <h3><i class="bi bi-lightning-charge" style="color:#f59e0b"></i> Sản phẩm Flash Sale</h3>
                <div class="value" id="flash-kpi-total" style="color:#f59e0b">--</div>
                <div class="sub-text">đang được đánh dấu flash sale</div>
            </div>
            <div class="glass-card kpi-card">
                <h3><i class="bi bi-shop"></i> Cửa hàng có Flash Sale</h3>
                <div class="value" id="flash-kpi-stores">--</div>
                <div class="sub-text">đối thủ đang chạy khuyến mãi</div>
            </div>
            <div class="glass-card kpi-card kpi-danger">
                <h3><i class="bi bi-exclamation-triangle"></i> TNC bị ảnh hưởng</h3>
                <div class="value highlight-red" id="flash-kpi-affected">--</div>
                <div class="sub-text">sản phẩm ta đang bán đắt hơn giá flash</div>
            </div>
        </div>

        <!-- Danh sách flash sale -->
        <div class="glass-card table-section">
            <div class="section-header">
                <h2><i class="bi bi-lightning-charge"></i> Tất cả sản phẩm đang Flash Sale</h2>
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:0.75rem;margin-bottom:1.25rem;align-items:end;">
                <div>
                    <label style="font-size:0.8rem;color:var(--text-muted);font-weight:600;margin-bottom:0.4rem;display:block;">Tìm kiếm</label>
                    <div style="position:relative;">
                        <input type="text" id="flash-search-filter" class="glass-input" placeholder="Tên SP, SKU..." style="padding-left:2.2rem;">
                        <i class="bi bi-search" style="position:absolute;left:0.8rem;top:50%;transform:translateY(-50%);color:var(--text-muted);"></i>
                    </div>
                </div>
                <div>
                    <label style="font-size:0.8rem;color:var(--text-muted);font-weight:600;margin-bottom:0.4rem;display:block;">Cửa hàng</label>
                    <select id="flash-store-filter" class="glass-select" style="width:100%;">
                        <option value="all">Tất cả cửa hàng</option>
                    </select>
                </div>
                <div>
                    <label style="font-size:0.8rem;color:var(--text-muted);font-weight:600;margin-bottom:0.4rem;display:block;">Danh mục</label>
                    <select id="flash-category-filter" class="glass-select" style="width:100%;">
                        <option value="all">Tất cả danh mục</option>
                    </select>
                </div>
                <div>
                    <label style="font-size:0.8rem;color:var(--text-muted);font-weight:600;margin-bottom:0.4rem;display:block;">Thương hiệu</label>
                    <select id="flash-brand-filter" class="glass-select" style="width:100%;">
                        <option value="all">Tất cả thương hiệu</option>
                    </select>
                </div>
            </div>

            <div id="flash-empty">
                <i class="bi bi-check-circle" style="font-size:3rem;color:var(--green)"></i>
                <p style="margin-top:1rem;font-size:1.1rem;font-weight:600">Không có Flash Sale nào đang diễn ra</p>
                <p style="font-size:0.9rem;margin-top:0.5rem">Dữ liệu Flash Sale được cập nhật sau mỗi lần chạy scraper</p>
            </div>
            <div class="table-responsive" id="flash-table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Sản phẩm</th>
                            <th>Cửa hàng Flash Sale</th>
                            <th>Giá Flash Sale</th>
                            <th>Giá TNC</th>
                            <th>TNC đắt hơn</th>
                            <th>Danh mục</th>
                            <th>Link</th>
                        </tr>
                    </thead>
                    <tbody id="flash-table-body">
                        <tr><td colspan="7" class="text-center">Đang tải dữ liệu...</td></tr>
                    </tbody>
                </table>
                    <div id="flash-table-pagination" class="pagination-bar"></div>
            </div>
        </div>
    </main>

<?php
$extraScripts = '<script src="assets/flash-sale.js"></script>';
include 'includes/footer.php';
?>
