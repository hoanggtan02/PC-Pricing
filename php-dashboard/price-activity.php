<?php
// PC Pricing Dashboard - Trang Biến Động Giá (Price Activity)
?>
<!DOCTYPE html>
<html lang="vi" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TNC - Biến Động Giá Thị Trường</title>
    <meta name="description" content="Theo dõi tần suất đổi giá của các đối thủ theo từng tuần">
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
            <a href="category.php">Theo Danh Mục</a>
            <a href="brand.php">Theo Thương Hiệu</a>
            <a href="stock-gap.php">Khoảng Trống Hàng</a>
            <a href="price-activity.php" class="active">Biến Động Giá</a>
        </nav>

        <header class="glass-header">
            <div class="header-content">
                <div>
                    <h1>📊 Biến Động Giá Thị Trường</h1>
                    <p>Tần suất đổi giá của từng đối thủ — ai đang "nhúc nhích" nhất thị trường?</p>
                </div>
                <div class="filters">
                    <select id="week-select" class="glass-select">
                        <option value="">Chọn tuần...</option>
                    </select>
                </div>
            </div>
        </header>

        <main class="dashboard-grid">
            <!-- KPI Row -->
            <div class="kpi-row">
                <div class="glass-card kpi-card">
                    <h3>Đối thủ đổi giá nhiều nhất</h3>
                    <div class="value" id="act-most-active">--</div>
                    <div class="sub-text" id="act-most-active-count">lần / 100 sản phẩm</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3>TNC đổi giá</h3>
                    <div class="value" id="act-tnc-changes">--</div>
                    <div class="sub-text">lần / 100 sản phẩm trong tuần</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3>Tổng lần đổi giá (tuần)</h3>
                    <div class="value" id="act-total-changes">--</div>
                    <div class="sub-text">trên toàn thị trường</div>
                </div>
            </div>

            <!-- Biểu đồ -->
            <div class="glass-card table-section">
                <div class="section-header">
                    <h2>Biểu đồ tần suất đổi giá (lần / 100 sản phẩm)</h2>
                </div>
                <div class="chart-container">
                    <canvas id="activity-chart"></canvas>
                </div>
            </div>

            <!-- Bảng chi tiết -->
            <div class="glass-card table-section">
                <div class="section-header">
                    <h2>Chi tiết từng đối thủ</h2>
                </div>
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>Cửa hàng</th>
                                <th>Lần đổi giá</th>
                                <th>Số sản phẩm theo dõi</th>
                                <th>Lần đổi / 100 SP</th>
                                <th>Mức độ hoạt động</th>
                            </tr>
                        </thead>
                        <tbody id="activity-table-body">
                            <tr><td colspan="5" class="text-center">Đang tải dữ liệu...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </main>
    </div>

    <script src="assets/config.js"></script>
    <script src="assets/price-activity.js"></script>
</body>
</html>
