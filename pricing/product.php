<?php // product.php — Chi tiết sản phẩm
$sku = $_GET['sku'] ?? '';
?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chi Tiết Sản Phẩm - TNC Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@300;400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <link rel="stylesheet" href="assets/style.css">
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
            z-index: 100;
            background: white;
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            box-shadow: var(--shadow);
            max-height: 240px;
            overflow-y: auto;
            width: 100%;
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
            <path id="a3" fill="url(#lg2)" opacity="0" d="M141.71,86.8c-6.08,5.27-15.18,5.02-20.96-.58l-2.33-2.26h0s0,0,0,0l-.14-.2-21.2-20.63s0,0,0,0l-7.14-6.27h0s0,0,0,0c-.08-.08-46.54-43.42-46.57-43.45-.01.03-16.47,31.79-19.99,38.85-.06.12-.12.22-.16.32-.18.37-.35.75-.52,1.13-.82,1.75-1.64,3.51-2.44,5.28l-.03.07c-.91,2.01-1.79,4.03-2.66,6.06-.21.49-.41.98-.62,1.48-.64,1.52-1.28,3.05-1.9,4.58-.31.77-.62,1.55-.92,2.33-.3.77-.59,1.54-.89,2.31,1.4-1.55,2.73-2.85,4.01-3.91,5.53-4.64,13.64-4.48,19.02.32l5,4.48.02.02c.1.09,1.21,1.03,1.23.99,4.31,4.08,7.81,7.4,11.28,10.78.4.39.79.76,1.13,1.1l1.68,1.59,4.58,4.33,1.66,1.57,6.94,6.51,2.42,2.28,44.54,40.72c9.94-19,19.93-37.09,27.98-57,.64-1.57,1.26-3.16,1.88-4.74.43-1.13.86-2.25,1.27-3.38l-6.16,5.34Z" />

            <path id="a1" fill="url(#lg)" opacity="0" d="M156.63,22.44c-.58-1.5-1.33-2.94-2.33-4.19-.63-.78-1.37-1.44-2.19-1.97-3.75-2.43-9.19-2.4-13.22-1.31-5.85,1.58-10.99,5.14-15.82,8.69-10.63,7.82-19.88,17.53-28.42,27.54-1.21,1.41-2.44,2.86-3.65,4.36-.04.06-.1.12-.16.2-.02.02-.04.06-.06.08-.08.08-.14.18-.22.26-.2.26-.4.52-.6.77h0s7.14,6.27,7.14,6.27c.2-.26.4-.5.6-.75,4.11-5,8.11-9.56,11.86-13.55.04-.04.06-.06.1-.1.02-.02.06-.06.06-.08.02-.02.06-.06.06-.08,12.69-13.29,22.93-20.39,27.07-17.55,5.73,3.95-2.3,26-18.41,52.95h0s2.33,2.26,2.33,2.26c5.78,5.6,15.91,6.96,21.99,1.69l5.13-6.45c-.41,1.13-.84,2.26-1.27,3.38,4.43-11.47,8.21-23.27,10.38-35.37,1.54-8.6,2.87-18.65-.35-27.04Z" />
            <path id="a2" fill="url(#lg1)" opacity="0" d="M62.85,97.08c-18.07,22.13-34.09,35.52-39.51,31.79-5.67-3.91,2.12-25.58,17.93-52.16,0,0,.01.01.02.02l-.02-.02-5-4.48c-5.39-4.8-13.49-4.96-19.02-.32-1.28,1.06-2.61,2.36-4.01,3.91-3.75,9.8-6.94,19.82-9.14,30.04-2.21,10.24-5.16,24.8.81,34.4,1.41,2.27,3.48,3.88,6.04,4.66,9.59,2.94,19.24-3.52,26.61-9.01,10.81-8.05,20.21-18,28.88-28.26.91-1.07,1.97-2.13,2.75-3.3.04-.06.1-.12.14-.18.1-.12.2-.24.3-.36.06-.06.1-.14.16-.2h0l-6.94-6.51" />
            <path id="a3" fill="url(#lg2)" opacity="0" d="M141.71,86.8c-6.08,5.27-15.18,5.02-20.96-.58l-2.33-2.26h0s0,0,0,0l-.14-.2-21.2-20.63s0,0,0,0l-7.14-6.27h0s0,0,0,0c-.08-.08-46.54-43.42-46.57-43.45-.01.03-16.47,31.79-19.99,38.85-.06.12-.12.22-.16.32-.18.37-.35.75-.52,1.13-.82,1.75-1.64,3.51-2.44,5.28l-.03.07c-.91,2.01-1.79,4.03-2.66,6.06-.21.49-.41.98-.62,1.48-.64,1.52-1.28,3.05-1.9,4.58-.31.77-.62,1.55-.92,2.33-.3.77-.59,1.54-.89,2.31,1.4-1.55,2.73-2.85,4.01-3.91,5.53-4.64,13.64-4.48,19.02.32l5,4.48.02.02c.1.09,1.21,1.03,1.23.99,4.31,4.08,7.81,7.4,11.28,10.78.4.39.79.76,1.13,1.1l1.68,1.59,4.58,4.33,1.66,1.57,6.94,6.51,2.42,2.28,44.54,40.72c9.94-19,19.93-37.09,27.98-57,.64-1.57,1.26-3.16,1.88-4.74.43-1.13.86-2.25,1.27-3.38l-6.16,5.34Z" />
        </svg>
    </div>

    <div class="background-blobs"><div class="blob blob-1"></div><div class="blob blob-2"></div></div>
<div class="app-container">
    <nav class="nav-menu">
        <a href="index.php"><i class="bi bi-speedometer2"></i> Tổng quan</a>
        <a href="category.php"><i class="bi bi-grid-3x3-gap"></i> Theo Danh Mục</a>
        <a href="brand.php"><i class="bi bi-tags"></i> Theo Thương Hiệu</a>
        <a href="stock-gap.php"><i class="bi bi-box-seam"></i> Khoảng Trống Hàng</a>
        <a href="price-activity.php"><i class="bi bi-graph-up-arrow"></i> Biến Động Giá</a>
        <a href="trend.php"><i class="bi bi-activity"></i> Xu Hướng 7 Ngày</a>
        <a href="product.php" class="active"><i class="bi bi-search"></i> Chi Tiết SP</a>
        <a href="flash-sale.php"><i class="bi bi-lightning-charge"></i> Flash Sale</a>
    </nav>

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
        <div class="glass-card" style="padding:1.25rem 1.5rem;margin-bottom:1.5rem">
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
</div>
<script src="assets/config.js"></script>
<script>const INITIAL_SKU = `<?= addslashes($sku) ?>`;</script>
<script src="assets/loader.js"></script>
<script src="assets/product.js"></script>
</body>
</html>
