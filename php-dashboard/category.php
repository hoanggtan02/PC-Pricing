<?php
// PC Pricing Dashboard - PHP Version
?>
<!DOCTYPE html>
<html lang="vi" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TNC PC Pricing Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@300;400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="assets/style.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="background-blobs">
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>
    </div>

    <div class="app-container">
        <nav class="nav-menu">
            <a href="index.php">Tổng quan</a>
            <a href="category.php" class="active">Theo Danh Mục</a>
            <a href="brand.php">Theo Thương Hiệu</a>
            <a href="stock-gap.php">Khoảng Trống Hàng</a>
            <a href="price-activity.php">Biến Động Giá</a>
        </nav>

        <header class="glass-header">
            <div class="header-content">
                <div>
                    <h1>Bảng giá theo Danh Mục</h1>
                    <p>Phân tích giá và khoảng trống hết hàng theo từng danh mục</p>
                </div>
                <div class="status-badge" id="last-update">
                    Đang tải dữ liệu...
                </div>
            </div>
        </header>

        <main class="dashboard-grid">
            <div class="kpi-row">
                <div class="glass-card kpi-card">
                    <h3>Sản phẩm trong danh mục</h3>
                    <div class="value" id="cat-kpi-products">--</div>
                </div>
                <div class="glass-card kpi-card kpi-danger">
                    <h3>Bị đối thủ bán rẻ hơn</h3>
                    <div class="value highlight-red" id="cat-kpi-beaten">--</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3>Trung bình so với thị trường</h3>
                    <div class="value" id="cat-kpi-avg">--</div>
                </div>
            </div>

            <div class="glass-card table-section">
                <div class="section-header">
                    <h2>Sản phẩm theo danh mục</h2>
                    <div class="filters">
                        <select id="category-select" class="glass-select">
                            <option value="laptop">Laptop</option>
                            <option value="monitor">Màn hình (Monitor)</option>
                            <option value="ssd">SSD</option>
                            <option value="ram">RAM</option>
                            <option value="cpu">CPU</option>
                            <option value="mainboard">Mainboard</option>
                            <option value="vga">VGA</option>
                        </select>
                    </div>
                </div>
                <div class="table-responsive">
                    <table id="products-table">
                        <thead>
                            <tr>
                                <th>Tên sản phẩm</th>
                                <th>Hãng (Brand)</th>
                                <th>Giá của TNC</th>
                                <th>Giá rẻ nhất</th>
                                <th>Đối thủ rẻ nhất</th>
                                <th>Chênh lệch vs thị trường</th>
                                <th>Nguồn</th>
                            </tr>
                        </thead>
                        <tbody id="category-table-body">
                            <tr><td colspan="7" class="text-center">Đang tải dữ liệu...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Bảng độ phủ đối thủ -->
            <div class="glass-card table-section">
                <div class="section-header">
                    <h2>Độ phủ của từng đối thủ trong danh mục này</h2>
                </div>
                <div id="coverage-container">Đang tải...</div>
            </div>
        </main>
    </div>

    <script src="assets/config.js"></script>
    <script src="assets/category.js"></script>
</body>
</html>
