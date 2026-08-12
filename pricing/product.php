<?php
$pageTitle = "Chi Tiết Sản Phẩm - TNC Dashboard";
$extraHeadHtml = <<<'HTML'
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .search-box-wrap {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1.5rem;
        }
        .search-box {
            flex: 1;
            padding: 0.75rem 1rem;
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            font-family: 'Plus Jakarta Sans', sans-serif;
            font-size: 0.95rem;
            outline: none;
            background: white;
            color: var(--text-main);
            transition: border-color 0.2s;
        }
        .search-box:focus { border-color: var(--accent); }
        .search-btn {
            padding: 0.75rem 1.5rem;
            background: var(--accent);
            color: white;
            border: none;
            border-radius: 0.5rem;
            font-family: 'Exo 2', sans-serif;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.4rem;
            transition: opacity 0.2s;
        }
        .search-btn:hover { opacity: 0.85; }
        .price-row-self { background: rgba(1, 79, 43, 0.04); font-weight: 700; }
        .suggestion-list {
            position: absolute;
            z-index: 9999;
            background: white;
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            box-shadow: 0 8px 32px rgba(0,0,0,0.18);
            max-height: 260px;
            overflow-y: auto;
            width: calc(100% - 120px);
            top: calc(100% + 4px);
            left: 0;
        }
        .suggestion-item {
            padding: 0.65rem 1rem;
            cursor: pointer;
            font-size: 0.88rem;
            border-bottom: 1px solid rgba(0,0,0,0.04);
            transition: background 0.15s;
        }
        .suggestion-item:hover { background: var(--accent-light); }
        .suggestion-item .sku-tag { font-size:0.75rem; color:var(--text-muted); }
        #product-detail { display: none; }
        #product-placeholder {
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
                <h1><i class="bi bi-search"></i> Chi Tiết Sản Phẩm</h1>
                <p>So sánh toàn bộ giá đối thủ và xu hướng 7 ngày cho từng SKU</p>
            </div>
            <div class="status-badge" id="last-update"><i class="bi bi-clock"></i> Nhập SKU để tra cứu</div>
        </div>
    </header>

    <main class="dashboard-grid">
        <!-- Thanh tìm kiếm -->
        <div class="glass-card" style="padding:1.25rem 1.5rem;margin-bottom:1.5rem;overflow:visible">
            <h2 class="section-title" style="margin-bottom:0.75rem"><i class="bi bi-search"></i> Tìm sản phẩm</h2>
            <div style="position:relative">
                <div class="search-box-wrap">
                    <input type="text" id="sku-search" class="search-box"
                        placeholder="Nhập tên sản phẩm hoặc mã SKU... (VD: Dell Latitude, LAPTOP-001)"
                        autocomplete="off" value="<?= htmlspecialchars($sku) ?>">
                    <button class="search-btn" onclick="doSearch()">
                        <i class="bi bi-search"></i> Tra cứu
                    </button>
                </div>
                <div id="suggestion-box" class="suggestion-list" style="display:none"></div>
            </div>
        </div>

        <!-- Placeholder khi chưa chọn sản phẩm -->
        <div id="product-placeholder">
            <i class="bi bi-box2" style="font-size:3.5rem;color:var(--border-color)"></i>
            <p style="margin-top:1rem;font-size:1.1rem;font-weight:600;font-family:'Exo 2',sans-serif">
                Nhập tên hoặc mã SKU vào ô tìm kiếm bên trên
            </p>
            <p style="font-size:0.9rem;margin-top:0.4rem">
                Hệ thống sẽ hiện toàn bộ giá đối thủ và xu hướng 7 ngày cho sản phẩm đó
            </p>
        </div>

        <!-- Chi tiết sản phẩm (ẩn khi chưa tìm kiếm) -->
        <div id="product-detail">
            <!-- Thông tin sản phẩm + KPI -->
            <div class="kpi-row" id="product-kpi-row">
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-tag"></i> Giá TNC</h3>
                    <div class="value" id="p-our-price">--</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-trophy"></i> Giá rẻ nhất thị trường</h3>
                    <div class="value highlight-green" id="p-lowest-price">--</div>
                    <div class="sub-text" id="p-lowest-store">--</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-calculator"></i> Giá trung bình</h3>
                    <div class="value" id="p-mean-price">--</div>
                    <div class="sub-text" id="p-num-sources">-- đối thủ có giá</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-percent"></i> TNC so thị trường</h3>
                    <div class="value" id="p-pct">--</div>
                    <div class="sub-text">so với giá trung bình</div>
                </div>
            </div>

            <!-- Bảng giá tất cả đối thủ -->
            <div class="glass-card table-section">
                <div class="section-header">
                    <h2><i class="bi bi-table"></i> Bảng giá tất cả cửa hàng</h2>
                    <div id="product-meta" style="font-size:0.85rem;color:var(--text-muted)"></div>
                </div>
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>Cửa hàng</th>
                                <th>Giá niêm yết</th>
                                <th>Trạng thái</th>
                                <th>Flash Sale</th>
                                <th>So với TNC</th>
                                <th>Link</th>
                            </tr>
                        </thead>
                        <tbody id="product-price-table">
                            <tr><td colspan="6" class="text-center">Đang tải...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Xu hướng 7 ngày cho sản phẩm này -->
            <div class="glass-card section-card">
                <div class="section-header">
                    <h2><i class="bi bi-activity"></i> Xu hướng đổi giá 7 ngày gần nhất (từng cửa hàng)</h2>
                </div>
                <div id="product-trend-container">
                    <p class="text-center">Đang tải dữ liệu xu hướng...</p>
                </div>
            </div>
        </div>
    </main>

<?php
$extraScripts = '<script src="assets/product.js"></script>';
include 'includes/footer.php';
?>
