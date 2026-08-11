<?php // flash-sale.php — Flash Sale Detector ?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flash Sale Detector - TNC Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@300;400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <link rel="stylesheet" href="assets/style.css">
    <style>
        .flash-badge {
            background: linear-gradient(135deg, #f59e0b, #ef4444);
            color: white;
            padding: 0.2rem 0.6rem;
            border-radius: 0.3rem;
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
</head>
<body>
<div class="background-blobs"><div class="blob blob-1"></div><div class="blob blob-2"></div></div>
<div class="app-container">
    <nav class="nav-menu">
        <a href="index.php"><i class="bi bi-speedometer2"></i> Tổng quan</a>
        <a href="category.php"><i class="bi bi-grid-3x3-gap"></i> Theo Danh Mục</a>
        <a href="brand.php"><i class="bi bi-tags"></i> Theo Thương Hiệu</a>
        <a href="stock-gap.php"><i class="bi bi-box-seam"></i> Khoảng Trống Hàng</a>
        <a href="price-activity.php"><i class="bi bi-graph-up-arrow"></i> Biến Động Giá</a>
        <a href="trend.php"><i class="bi bi-activity"></i> Xu Hướng 7 Ngày</a>
        <a href="product.php"><i class="bi bi-search"></i> Chi Tiết SP</a>
        <a href="flash-sale.php" class="active"><i class="bi bi-lightning-charge"></i> Flash Sale</a>
    </nav>

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
                <select id="flash-store-filter" class="glass-select">
                    <option value="all">Tất cả cửa hàng</option>
                </select>
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
            </div>
        </div>
    </main>
</div>
<script src="assets/config.js"></script>
<script src="assets/flash-sale.js"></script>
</body>
</html>
