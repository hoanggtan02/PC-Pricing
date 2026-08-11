<?php
// PC Pricing Dashboard - Trang Khoảng Trống Hàng Hóa (Out-of-Stock Gap)
?>
<!DOCTYPE html>
<html lang="vi" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TNC - Khoảng Trống Hàng Hóa</title>
    <meta name="description" content="Sản phẩm TNC đang hết hàng trong khi đối thủ vẫn còn - cơ hội mất doanh số">
    <link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@300;400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
    <div class="background-blobs">
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>
    </div>

    <div class="app-container">
        <nav class="nav-menu">
            <a href="index.php">Tổng quan</a>
            <a href="category.php">Theo Danh Mục</a>
            <a href="brand.php">Theo Thương Hiệu</a>
            <a href="stock-gap.php" class="active">Khoảng Trống Hàng</a>
            <a href="price-activity.php">Biến Động Giá</a>
        </nav>

        <header class="glass-header">
            <div class="header-content">
                <div>
                    <h1>⚠️ Khoảng Trống Hàng Hóa</h1>
                    <p>Sản phẩm TNC đang hết hàng — trong khi đối thủ vẫn còn bán</p>
                </div>
                <div class="status-badge" id="last-update">Đang tải...</div>
            </div>
        </header>

        <main class="dashboard-grid">
            <!-- KPI Row -->
            <div class="kpi-row">
                <div class="glass-card kpi-card kpi-danger">
                    <h3>Sản phẩm hết hàng</h3>
                    <div class="value highlight-red" id="gap-total">--</div>
                    <div class="sub-text">TNC hết, đối thủ còn</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3>Tổng đối thủ cạnh tranh</h3>
                    <div class="value" id="gap-competitors">--</div>
                    <div class="sub-text">đang bán thay TNC</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3>Doanh thu rủi ro</h3>
                    <div class="value highlight-red" id="gap-revenue-risk">--</div>
                    <div class="sub-text">theo giá đối thủ rẻ nhất</div>
                </div>
            </div>

            <!-- Bộ lọc -->
            <div class="glass-card table-section">
                <div class="section-header">
                    <h2>Danh sách sản phẩm mất cơ hội</h2>
                    <div class="filters">
                        <select id="gap-category-filter" class="glass-select">
                            <option value="">Tất cả danh mục</option>
                            <option value="Laptop">Laptop</option>
                            <option value="Monitor">Màn hình</option>
                            <option value="Ssd">SSD</option>
                            <option value="Ram">RAM</option>
                            <option value="Cpu">CPU</option>
                            <option value="Vga">Card màn hình</option>
                            <option value="Mainboard">Mainboard</option>
                        </select>
                        <select id="gap-brand-filter" class="glass-select" style="margin-left:0.5rem">
                            <option value="">Tất cả thương hiệu</option>
                            <option value="Dell">Dell</option>
                            <option value="Lenovo">Lenovo</option>
                            <option value="HP">HP</option>
                            <option value="Apple">Apple</option>
                            <option value="Asus">Asus</option>
                            <option value="Acer">Acer</option>
                            <option value="MSI">MSI</option>
                        </select>
                    </div>
                </div>
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>Sản phẩm</th>
                                <th>Thương hiệu</th>
                                <th>Danh mục</th>
                                <th>Đối thủ cạnh tranh</th>
                                <th>Giá đối thủ rẻ nhất</th>
                                <th>Đối thủ rẻ nhất</th>
                                <th>Link đối thủ</th>
                            </tr>
                        </thead>
                        <tbody id="gap-table-body">
                            <tr><td colspan="7" class="text-center">Đang tải dữ liệu...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </main>
    </div>

    <script src="assets/config.js"></script>
    <script src="assets/stock-gap.js"></script>
</body>
</html>
