<?php
// PC Pricing Dashboard - Trang Thương Hiệu
?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Theo Thương Hiệu - TNC Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@300;400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
    <div class="background-blobs">
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>
    </div>

    <div class="app-container">
        <nav class="nav-menu">
            <a href="index.php"><i class="bi bi-speedometer2"></i> Tổng quan</a>
            <a href="category.php"><i class="bi bi-grid-3x3-gap"></i> Theo Danh Mục</a>
            <a href="brand.php" class="active"><i class="bi bi-tags"></i> Theo Thương Hiệu</a>
            <a href="stock-gap.php"><i class="bi bi-box-seam"></i> Khoảng Trống Hàng</a>
            <a href="price-activity.php"><i class="bi bi-graph-up-arrow"></i> Biến Động Giá</a>
            <a href="trend.php"><i class="bi bi-activity"></i> Xu Hướng 7 Ngày</a>
            <a href="product.php"><i class="bi bi-search"></i> Chi Tiết SP</a>
            <a href="flash-sale.php"><i class="bi bi-lightning-charge"></i> Flash Sale</a>
        </nav>

        <header class="glass-header">
            <div class="header-content">
                <div>
                    <h1><i class="bi bi-tags-fill"></i> Bảng giá theo Thương Hiệu</h1>
                    <p>So sánh giá chi tiết từng mã sản phẩm theo hãng</p>
                </div>
                <div class="status-badge" id="last-update"><i class="bi bi-clock"></i> Đang tải...</div>
            </div>
        </header>

        <main class="dashboard-grid">
            <div class="kpi-row">
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-box2"></i> Sản phẩm trong hãng</h3>
                    <div class="value" id="brand-kpi-products">--</div>
                </div>
                <div class="glass-card kpi-card kpi-danger">
                    <h3><i class="bi bi-exclamation-triangle"></i> Bị đối thủ bán rẻ hơn</h3>
                    <div class="value highlight-red" id="brand-kpi-beaten">--</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-percent"></i> Trung bình vs Thị trường</h3>
                    <div class="value" id="brand-kpi-avg">--</div>
                </div>
            </div>

            <div class="glass-card table-section">
                <div class="section-header">
                    <h2><i class="bi bi-table"></i> Sản phẩm theo thương hiệu</h2>
                    <select id="brand-select" class="glass-select">
                        <option value="Dell">Dell</option>
                        <option value="Lenovo">Lenovo</option>
                        <option value="HP">HP</option>
                        <option value="Apple">Apple</option>
                        <option value="Asus">Asus</option>
                        <option value="Acer">Acer</option>
                        <option value="MSI">MSI</option>
                    </select>
                </div>
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>Tên sản phẩm</th>
                                <th>Danh mục</th>
                                <th>Giá TNC</th>
                                <th>Giá rẻ nhất</th>
                                <th>Đối thủ</th>
                                <th>Chênh lệch</th>
                                <th>Nguồn</th>
                            </tr>
                        </thead>
                        <tbody id="brand-table-body">
                            <tr><td colspan="7" class="text-center">Đang tải dữ liệu...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="glass-card table-section">
                <div class="section-header">
                    <h2><i class="bi bi-bar-chart-steps"></i> Độ phủ của từng đối thủ</h2>
                </div>
                <div id="brand-coverage-container"><p class="text-center">Đang tải...</p></div>
            </div>
        </main>
    </div>

    <script src="assets/config.js"></script>
    <script src="assets/brand.js"></script>
</body>
</html>
