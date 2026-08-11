<?php
// PC Pricing Dashboard - Biến Động Giá
?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Biến Động Giá - TNC Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@300;400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
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
            <a href="index.php"><i class="bi bi-speedometer2"></i> Tổng quan</a>
            <a href="category.php"><i class="bi bi-grid-3x3-gap"></i> Theo Danh Mục</a>
            <a href="brand.php"><i class="bi bi-tags"></i> Theo Thương Hiệu</a>
            <a href="stock-gap.php"><i class="bi bi-box-seam"></i> Khoảng Trống Hàng</a>
            <a href="price-activity.php" class="active"><i class="bi bi-graph-up-arrow"></i> Biến Động Giá</a>
            <a href="trend.php"><i class="bi bi-activity"></i> Xu Hướng 7 Ngày</a>
            <a href="product.php"><i class="bi bi-search"></i> Chi Tiết SP</a>
            <a href="flash-sale.php"><i class="bi bi-lightning-charge"></i> Flash Sale</a>
        </nav>

        <header class="glass-header">
            <div class="header-content">
                <div>
                    <h1><i class="bi bi-graph-up-arrow"></i> Biến Động Giá Thị Trường</h1>
                    <p>Tần suất đổi giá của từng đối thủ — ai đang "nhúc nhích" nhất thị trường?</p>
                </div>
                <select id="week-select" class="glass-select">
                    <option value="">Chọn tuần...</option>
                </select>
            </div>
        </header>

        <main class="dashboard-grid">
            <div class="kpi-row">
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-trophy"></i> Đối thủ đổi giá nhiều nhất</h3>
                    <div class="value" id="act-most-active">--</div>
                    <div class="sub-text" id="act-most-active-count">lần / 100 sản phẩm</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-building"></i> TNC đổi giá</h3>
                    <div class="value" id="act-tnc-changes">--</div>
                    <div class="sub-text">lần / 100 sản phẩm trong tuần</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-arrow-repeat"></i> Tổng lần đổi giá</h3>
                    <div class="value" id="act-total-changes">--</div>
                    <div class="sub-text">trên toàn thị trường tuần này</div>
                </div>
            </div>

            <div class="glass-card section-card">
                <div class="section-header">
                    <h2><i class="bi bi-bar-chart-fill"></i> Biểu đồ tần suất đổi giá (lần / 100 sản phẩm)</h2>
                </div>
                <div class="chart-container">
                    <canvas id="activity-chart"></canvas>
                </div>
            </div>

            <div class="glass-card table-section">
                <div class="section-header">
                    <h2><i class="bi bi-list-ol"></i> Chi tiết từng đối thủ</h2>
                </div>
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>Cửa hàng</th>
                                <th>Lần đổi giá</th>
                                <th>Số SP theo dõi</th>
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
