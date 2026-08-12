<?php
// PC Pricing Dashboard - Trang Bộ Lọc Chi Tiết (Gộp Danh Mục & Thương Hiệu)
?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bộ Lọc Thị Trường - TNC Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@300;400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <link rel="stylesheet" href="assets/style.css">
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
</head>
<body>
    <div id="cr-overlay">
        <svg class="loader" viewBox="0 0 160 160" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
            <defs>
                <linearGradient id="lg" x1="90.48" y1="111.14" x2="161.56" y2="8.12" gradientUnits="userSpaceOnUse">
                    <stop offset="0" stop-color="#014f2b" />
                    <stop offset=".17" stop-color="#0e5b2d" />
                    <stop offset=".5" stop-color="#327b35" />
                    <stop offset=".95" stop-color="#6cb041" />
                    <stop offset="1" stop-color="#75c044" />
                </linearGradient>
                <linearGradient id="lg1" x1="6" y1="145.75" x2="62.13" y2="57.17" xlink:href="#lg" />
                <linearGradient id="lg2" x1="32.92" y1="37.18" x2="133.55" y2="124.75" xlink:href="#lg" />
            </defs>

            <path fill="url(#lg)" opacity="0.18" d="M156.63,22.44c-.58-1.5-1.33-2.94-2.33-4.19-.63-.78-1.37-1.44-2.19-1.97-3.75-2.43-9.19-2.4-13.22-1.31-5.85,1.58-10.99,5.14-15.82,8.69-10.63,7.82-19.88,17.53-28.42,27.54-1.21,1.41-2.44,2.86-3.65,4.36-.04.06-.1.12-.16.2-.02.02-.04.06-.06.08-.08.08-.14.18-.22.26-.2.26-.4.52-.6.77h0s7.14,6.27,7.14,6.27c.2-.26.4-.5.6-.75,4.11-5,8.11-9.56,11.86-13.55.04-.04.06-.06.1-.1.02-.02.06-.06.06-.08.02-.02.06-.06.06-.08,12.69-13.29,22.93-20.39,27.07-17.55,5.73,3.95-2.3,26-18.41,52.95h0s2.33,2.26,2.33,2.26c5.78,5.6,15.91,6.96,21.99,1.69l5.13-6.45c-.41,1.13-.84,2.26-1.27,3.38,4.43-11.47,8.21-23.27,10.38-35.37,1.54-8.6,2.87-18.65-.35-27.04Z" />
            <path fill="url(#lg1)" opacity="0.18" d="M62.85,97.08c-18.07,22.13-34.09,35.52-39.51,31.79-5.67-3.91,2.12-25.58,17.93-52.16,0,0,.01.01.02.02l-.02-.02-5-4.48c-5.39-4.8-13.49-4.96-19.02-.32-1.28,1.06-2.61,2.36-4.01,3.91-3.75,9.8-6.94,19.82-9.14,30.04-2.21,10.24-5.16,24.8.81,34.4,1.41,2.27,3.48,3.88,6.04,4.66,9.59,2.94,19.24-3.52,26.61-9.01,10.81-8.05,20.21-18,28.88-28.26.91-1.07,1.97-2.13,2.75-3.3.04-.06.1-.12.14-.18.1-.12.2-.24.3-.36.06-.06.1-.14.16-.2h0l-6.94-6.51" />
            <path fill="url(#lg2)" opacity="0.18" d="M141.71,86.8c-6.08,5.27-15.18,5.02-20.96-.58l-2.33-2.26h0s0,0,0,0l-.14-.2-21.2-20.63s0,0,0,0l-7.14-6.27h0s0,0,0,0c-.08-.08-46.54-43.42-46.57-43.45-.01.03-16.47,31.79-19.99,38.85-.06.12-.12.22-.16.32-.18.37-.35.75-.52,1.13-.82,1.75-1.64,3.51-2.44,5.28l-.03.07c-.91,2.01-1.79,4.03-2.66,6.06-.21.49-.41.98-.62,1.48-.64,1.52-1.28,3.05-1.9,4.58-.31.77-.62,1.55-.92,2.33-.3.77-.59,1.54-.89,2.31,1.4-1.55,2.73-2.85,4.01-3.91,5.53-4.64,13.64-4.48,19.02.32l5,4.48.02.02c.1.09,1.21,1.03,1.23.99,4.31,4.08,7.81,7.4,11.28,10.78.4.39.79.76,1.13,1.1l1.68,1.59,4.58,4.33,1.66,1.57,6.94,6.51,2.42,2.28,44.54,40.72c9.94-19,19.93-37.09,27.98-57,.64-1.57,1.26-3.16,1.88-4.74.43-1.13.86-2.25,1.27-3.38l-6.16,5.34Z" />

            <path id="a1" fill="url(#lg)" opacity="0" d="M156.63,22.44c-.58-1.5-1.33-2.94-2.33-4.19-.63-.78-1.37-1.44-2.19-1.97-3.75-2.43-9.19-2.4-13.22-1.31-5.85,1.58-10.99,5.14-15.82,8.69-10.63,7.82-19.88,17.53-28.42,27.54-1.21,1.41-2.44,2.86-3.65,4.36-.04.06-.1.12-.16.2-.02.02-.04.06-.06.08-.08.08-.14.18-.22.26-.2.26-.4.52-.6.77h0s7.14,6.27,7.14,6.27c.2-.26.4-.5.6-.75,4.11-5,8.11-9.56,11.86-13.55.04-.04.06-.06.1-.1.02-.02.06-.06.06-.08.02-.02.06-.06.06-.08,12.69-13.29,22.93-20.39,27.07-17.55,5.73,3.95-2.3,26-18.41,52.95h0s2.33,2.26,2.33,2.26c5.78,5.6,15.91,6.96,21.99,1.69l5.13-6.45c-.41,1.13-.84,2.26-1.27,3.38,4.43-11.47,8.21-23.27,10.38-35.37,1.54-8.6,2.87-18.65-.35-27.04Z" />
            <path id="a2" fill="url(#lg1)" opacity="0" d="M62.85,97.08c-18.07,22.13-34.09,35.52-39.51,31.79-5.67-3.91,2.12-25.58,17.93-52.16,0,0,.01.01.02.02l-.02-.02-5-4.48c-5.39-4.8-13.49-4.96-19.02-.32-1.28,1.06-2.61,2.36-4.01,3.91-3.75,9.8-6.94,19.82-9.14,30.04-2.21,10.24-5.16,24.8.81,34.4,1.41,2.27,3.48,3.88,6.04,4.66,9.59,2.94,19.24-3.52,26.61-9.01,10.81-8.05,20.21-18,28.88-28.26.91-1.07,1.97-2.13,2.75-3.3.04-.06.1-.12.14-.18.1-.12.2-.24.3-.36.06-.06.1-.14.16-.2h0l-6.94-6.51" />
            <path id="a3" fill="url(#lg2)" opacity="0" d="M141.71,86.8c-6.08,5.27-15.18,5.02-20.96-.58l-2.33-2.26h0s0,0,0,0l-.14-.2-21.2-20.63s0,0,0,0l-7.14-6.27h0s0,0,0,0c-.08-.08-46.54-43.42-46.57-43.45-.01.03-16.47,31.79-19.99,38.85-.06.12-.12.22-.16.32-.18.37-.35.75-.52,1.13-.82,1.75-1.64,3.51-2.44,5.28l-.03.07c-.91,2.01-1.79,4.03-2.66,6.06-.21.49-.41.98-.62,1.48-.64,1.52-1.28,3.05-1.9,4.58-.31.77-.62,1.55-.92,2.33-.3.77-.59,1.54-.89,2.31,1.4-1.55,2.73-2.85,4.01-3.91,5.53-4.64,13.64-4.48,19.02.32l5,4.48.02.02c.1.09,1.21,1.03,1.23.99,4.31,4.08,7.81,7.4,11.28,10.78.4.39.79.76,1.13,1.1l1.68,1.59,4.58,4.33,1.66,1.57,6.94,6.51,2.42,2.28,44.54,40.72c9.94-19,19.93-37.09,27.98-57,.64-1.57,1.26-3.16,1.88-4.74.43-1.13.86-2.25,1.27-3.38l-6.16,5.34Z" />
        </svg>
    </div>

    <div class="background-blobs">
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>
    </div>

    <div class="app-container">
        <nav class="nav-menu">
            <a href="index.php"><i class="bi bi-speedometer2"></i> Tổng quan</a>
            <a href="category.php" class="active"><i class="bi bi-funnel"></i> Bộ Lọc Chi Tiết</a>
            <a href="stock-gap.php"><i class="bi bi-box-seam"></i> Khoảng Trống Hàng</a>
            <a href="price-activity.php"><i class="bi bi-graph-up-arrow"></i> Biến Động Giá</a>
            <a href="trend.php"><i class="bi bi-activity"></i> Xu Hướng 7 Ngày</a>
            <a href="product.php"><i class="bi bi-search"></i> Chi Tiết SP</a>
            <a href="flash-sale.php"><i class="bi bi-lightning-charge"></i> Flash Sale</a>
            <a href="data-manager.php"><i class="bi bi-database-gear"></i> Quản Lý DL</a>
        </nav>

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
                            <option value="Laptop">Laptop</option>
                            <option value="Monitor">Màn hình (Monitor)</option>
                            <option value="Ssd">SSD</option>
                            <option value="Ram">RAM</option>
                            <option value="Cpu">CPU</option>
                            <option value="Mainboard">Mainboard</option>
                            <option value="Vga">Card màn hình (VGA)</option>
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
    </div>

    <script src="assets/pagination.js"></script>
    <script src="assets/config.js"></script>
    <script src="assets/loader.js"></script>
    <script src="assets/category.js"></script>
</body>
</html>
