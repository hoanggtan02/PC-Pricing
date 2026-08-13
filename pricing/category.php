<?php
$pageTitle = "Bộ Lọc Thị Trường - TNC Dashboard";
$extraHeadHtml = <<<'HTML'
<style>
        .master-detail-layout {
            display: grid;
            grid-template-columns: 1.6fr 1fr;
            gap: 1.5rem;
            align-items: start;
            margin-bottom: 1.5rem;
        }

        /* Sticky detail panel — stays visible while scrolling the master list */
        .detail-sticky-col {
            position: sticky;
            top: 1rem;
        }

        /* Scrollable master list */
        .master-scroll-wrap {
            max-height: 620px;
            overflow-y: auto;
            overflow-x: auto;
            border-radius: 0.4rem;
            /* Custom scrollbar */
            scrollbar-width: thin;
            scrollbar-color: var(--border-color) transparent;
        }
        .master-scroll-wrap::-webkit-scrollbar { width: 6px; height: 6px; }
        .master-scroll-wrap::-webkit-scrollbar-track { background: transparent; }
        .master-scroll-wrap::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 99px; }
        .master-scroll-wrap::-webkit-scrollbar-thumb:hover { background: var(--gold); }

        /* Sticky thead inside scrollable wrapper */
        .master-scroll-wrap thead th {
            position: sticky;
            top: 0;
            background: white;
            z-index: 2;
            box-shadow: 0 1px 0 var(--border-color);
        }
        
        .selected-row {
            background-color: rgba(1, 79, 43, 0.08) !important;
            border-left: 3px solid var(--accent) !important;
        }

        .price-row-self {
            background-color: rgba(1, 79, 43, 0.04);
        }

        .clickable-row {
            cursor: pointer;
            transition: background-color 0.2s ease;
        }
        .clickable-row:hover {
            background-color: rgba(0, 0, 0, 0.02);
        }

        @media (max-width: 1024px) {
            .master-detail-layout {
                grid-template-columns: 1fr;
            }
            .detail-sticky-col {
                position: static;
            }
        }
    </style>
HTML;
include 'includes/head.php';
include 'includes/body-start.php';
?>
<header class="glass-header">
            <div class="header-content">
                <div>
                    <h1><i class="bi bi-funnel-fill"></i> Bộ Lọc & Phân Tích Thị Trường</h1>
                    <p>Công cụ tìm kiếm, lọc theo danh mục & thương hiệu kết hợp so sánh giá đối thủ tức thì</p>
                </div>
                <div class="status-badge" id="last-update"><i class="bi bi-clock"></i> Đang tải dữ liệu...</div>
            </div>
        </header>

        <main class="dashboard-grid">
            <!-- KPIs -->
            <div class="kpi-row">
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-box2"></i> Sản phẩm khớp bộ lọc</h3>
                    <div class="value" id="cat-kpi-products">--</div>
                    <div class="sub-text">mã sản phẩm hiển thị</div>
                </div>
                <div class="glass-card kpi-card kpi-danger">
                    <h3><i class="bi bi-exclamation-triangle"></i> Bị đối thủ bán rẻ hơn</h3>
                    <div class="value highlight-red" id="cat-kpi-beaten">--</div>
                    <div class="sub-text">cần điều chỉnh giá</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-percent"></i> TB vs Thị trường</h3>
                    <div class="value" id="cat-kpi-avg">--</div>
                    <div class="sub-text">trên sản phẩm có đối thủ</div>
                </div>
            </div>

            <!-- Unified Search & Filter Controls -->
            <div class="glass-card filter-card" style="margin-bottom: 1.5rem; padding: 1.25rem;">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; align-items: end;">
                    <div>
                        <label style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600; margin-bottom: 0.4rem; display: block;">Tìm kiếm từ khóa</label>
                        <div style="position: relative;">
                            <input type="text" id="filter-search" class="glass-input" placeholder="Nhập tên SP, SKU..." style="width: 100%; padding-left: 2.2rem;">
                            <i class="bi bi-search" style="position: absolute; left: 0.8rem; top: 50%; transform: translateY(-50%); color: var(--text-muted);"></i>
                        </div>
                    </div>
                    <div>
                        <label style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600; margin-bottom: 0.4rem; display: block;">Danh mục</label>
                        <select id="filter-category" class="glass-select" style="width: 100%;">
                            <option value="all">Tất cả danh mục</option>
                            <!-- Danh mục được nạp động từ dữ liệu -->
                        </select>
                    </div>
                    <div>
                        <label style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600; margin-bottom: 0.4rem; display: block;">Thương hiệu</label>
                        <select id="filter-brand" class="glass-select" style="width: 100%;">
                            <option value="all">Tất cả thương hiệu</option>
                        </select>
                    </div>
                    <div>
                        <label style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600; margin-bottom: 0.4rem; display: block;">Trạng thái giá</label>
                        <select id="filter-status" class="glass-select" style="width: 100%;">
                            <option value="all">Tất cả trạng thái</option>
                            <option value="beaten">Bị đối thủ bán rẻ hơn</option>
                            <option value="beating">Chúng ta rẻ nhất / Bằng đối thủ</option>
                            <option value="no-competitor">Không có đối thủ</option>
                        </select>
                    </div>
                </div>
            </div>

            <!-- Master-Detail Layout -->
            <div class="master-detail-layout">
                
                <!-- Master Column (Product Table) -->
                <div class="glass-card table-section" style="margin-bottom: 0;">
                    <div class="section-header">
                        <h2><i class="bi bi-list-stars"></i> Danh sách sản phẩm</h2>
                    </div>
                    <div class="master-scroll-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Sản phẩm</th>
                                    <th>Giá TNC</th>
                                    <th>Rẻ nhất thị trường</th>
                                    <th>Chênh lệch</th>
                                </tr>
                            </thead>
                            <tbody id="category-table-body">
                                <tr><td colspan="4" class="text-center">Đang tải dữ liệu...</td></tr>
                            </tbody>
                        </table>
                    </div>
                    <div id="cat-table-pagination" class="pagination-bar"></div>
                </div>

                <!-- Detail Column (Competitor info + Trend) — sticky so it stays on screen -->
                <div class="glass-card table-section detail-sticky-col" id="detail-pane" style="margin-bottom: 0;">
                    <div id="detail-placeholder" style="padding: 4.5rem 1.5rem; text-align: center; color: var(--text-muted);">
                        <i class="bi bi-mouse2" style="font-size: 2.5rem; color: var(--accent); opacity: 0.7; display: block; margin-bottom: 1rem;"></i>
                        <p style="font-weight: 500;">Bấm chọn một dòng sản phẩm bên trái để xem so sánh giá đối thủ & xu hướng 7 ngày.</p>
                    </div>
                    
                    <div id="detail-content" style="display: none;">
                        <div style="padding-bottom: 1rem; border-bottom: 1px solid var(--glass-border); margin-bottom: 1rem;">
                            <h3 id="detail-product-name" style="font-size: 1.05rem; font-weight: 700; color: var(--text-main); margin: 0 0 0.4rem 0; line-height: 1.4;">--</h3>
                            <div style="display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap;">
                                <span class="sku-tag" id="detail-product-sku">--</span>
                                <span class="badge badge-neutral" id="detail-product-brand">--</span>
                                <span class="badge badge-neutral" id="detail-product-category">--</span>
                            </div>
                        </div>

                        <!-- Competitor Price Detail table -->
                        <div style="margin-bottom: 1.5rem;">
                            <h4 style="font-size: 0.85rem; font-weight: 700; color: var(--accent); margin-bottom: 0.6rem; display: flex; align-items: center; gap: 0.4rem;">
                                <i class="bi bi-shop"></i> Chi tiết giá đối thủ
                            </h4>
                            <table style="width: 100%; font-size: 0.85rem;">
                                <thead>
                                    <tr>
                                        <th>Cửa hàng</th>
                                        <th style="text-align: right;">Giá bán</th>
                                        <th style="text-align: right;">Chênh lệch</th>
                                        <th style="text-align: center;">Web</th>
                                    </tr>
                                </thead>
                                <tbody id="detail-stores-body">
                                    <!-- Rendered dynamically -->
                                </tbody>
                            </table>
                        </div>

                        <!-- 7d Price Trend table -->
                        <div>
                            <h4 style="font-size: 0.85rem; font-weight: 700; color: var(--accent); margin-bottom: 0.6rem; display: flex; align-items: center; gap: 0.4rem;">
                                <i class="bi bi-activity"></i> Xu hướng đổi giá (7 ngày)
                            </h4>
                            <div id="detail-trend-container">
                                <!-- Rendered dynamically -->
                            </div>
                        </div>
                    </div>
                </div>

            </div>

            <!-- Bottom Tabs Section (OOS Gaps and Coverage) -->
            <div class="glass-card table-section">
                <div class="tabs-nav-container" style="display: flex; gap: 0.5rem; margin-bottom: 1.25rem; border-bottom: 1px solid var(--glass-border); padding-bottom: 0.5rem;">
                    <button class="dm-tab-btn active" id="subtab-btn-oos" onclick="switchSubTab('oos')">
                        <i class="bi bi-slash-circle-fill"></i> Cơ hội mất bán (Ta hết hàng, đối thủ còn)
                    </button>
                    <button class="dm-tab-btn" id="subtab-btn-coverage" onclick="switchSubTab('coverage')">
                        <i class="bi bi-bar-chart-steps"></i> Độ phủ thị trường của đối thủ
                    </button>
                </div>

                <!-- Sub-panel 1: OOS Gaps -->
                <div class="subtab-panel active" id="subpanel-oos">
                    <div class="table-responsive">
                        <table>
                            <thead>
                                <tr>
                                    <th>Sản phẩm</th>
                                    <th>SKU</th>
                                    <th>Đối thủ còn</th>
                                    <th>Đối thủ rẻ nhất</th>
                                    <th>Giá rẻ nhất</th>
                                    <th>Kiểm tra web</th>
                                </tr>
                            </thead>
                            <tbody id="category-oos-body">
                                <tr><td colspan="6" class="text-center">Đang tải...</td></tr>
                            </tbody>
                        </table>
                        <div id="cat-oos-pagination" class="pagination-bar"></div>
                    </div>
                </div>

                <!-- Sub-panel 2: Coverage -->
                <div class="subtab-panel" id="subpanel-coverage" style="display: none;">
                    <div id="coverage-container">
                        <p class="text-center">Đang tải...</p>
                    </div>
                </div>
            </div>
        </main>

<?php
$extraScripts = '<script src="assets/category.js?v=10002"></script>';
include 'includes/footer.php';
?>
