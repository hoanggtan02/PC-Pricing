<?php // trend.php — Xu hướng giá 7 ngày ?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Xu Hướng Giá 7 Ngày - TNC Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@300;400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <link rel="stylesheet" href="assets/style.css">
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
        <a href="trend.php" class="active"><i class="bi bi-activity"></i> Xu Hướng 7 Ngày</a>
        <a href="product.php"><i class="bi bi-search"></i> Chi Tiết SP</a>
        <a href="flash-sale.php"><i class="bi bi-lightning-charge"></i> Flash Sale</a>
    </nav>

    <header class="glass-header">
        <div class="header-content">
            <div>
                <h1><i class="bi bi-activity"></i> Xu Hướng Giá 7 Ngày</h1>
                <p>Sản phẩm nào vừa thay đổi giá trong 7 ngày qua? Tăng hay giảm?</p>
            </div>
            <div style="display:flex;gap:0.5rem;align-items:center;flex-wrap:wrap">
                <select id="trend-competitor-filter" class="glass-select">
                    <option value="all">Tất cả đối thủ</option>
                    <option value="competitor">Chỉ đối thủ</option>
                    <option value="self">Chỉ TNC</option>
                </select>
                <select id="trend-direction-filter" class="glass-select">
                    <option value="all">Tất cả chiều hướng</option>
                    <option value="up">↑ Tăng giá</option>
                    <option value="down">↓ Giảm giá</option>
                    <option value="flat">→ Không đổi net</option>
                </select>
                <div class="status-badge" id="last-update"><i class="bi bi-clock"></i> Đang tải...</div>
            </div>
        </div>
    </header>

    <main class="dashboard-grid">
        <!-- KPI Row -->
        <div class="kpi-row">
            <div class="glass-card kpi-card">
                <h3><i class="bi bi-arrow-up-circle"></i> Sản phẩm tăng giá</h3>
                <div class="value highlight-red" id="trend-kpi-up">--</div>
                <div class="sub-text">lần thay đổi (tăng)</div>
            </div>
            <div class="glass-card kpi-card">
                <h3><i class="bi bi-arrow-down-circle"></i> Sản phẩm giảm giá</h3>
                <div class="value highlight-green" id="trend-kpi-down">--</div>
                <div class="sub-text">lần thay đổi (giảm)</div>
            </div>
            <div class="glass-card kpi-card">
                <h3><i class="bi bi-arrow-repeat"></i> Tổng biến động</h3>
                <div class="value" id="trend-kpi-total">--</div>
                <div class="sub-text">lần đổi giá trong 7 ngày</div>
            </div>
            <div class="glass-card kpi-card kpi-danger">
                <h3><i class="bi bi-shop"></i> Đối thủ hoạt động nhất</h3>
                <div class="value" id="trend-kpi-most-active" style="font-size:1.2rem">--</div>
                <div class="sub-text" id="trend-kpi-most-active-count">-- lần đổi giá</div>
            </div>
        </div>

        <!-- Bảng xu hướng -->
        <div class="glass-card table-section">
            <div class="section-header">
                <h2><i class="bi bi-table"></i> Chi tiết biến động giá theo từng cặp (SKU × Cửa hàng)</h2>
                <span class="badge badge-neutral" id="trend-count-badge">-- dòng</span>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Sản phẩm</th>
                            <th>Cửa hàng</th>
                            <th>Chiều hướng</th>
                            <th>Giá đầu kỳ</th>
                            <th>Giá cuối kỳ</th>
                            <th>% Thay đổi</th>
                            <th>Số lần đổi</th>
                            <th>↑ Tăng</th>
                            <th>↓ Giảm</th>
                        </tr>
                    </thead>
                    <tbody id="trend-table-body">
                        <tr><td colspan="9" class="text-center">Đang tải dữ liệu...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </main>
</div>
<script src="assets/config.js"></script>
<script src="assets/trend.js"></script>
</body>
</html>
