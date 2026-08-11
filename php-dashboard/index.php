<?php
// PC Pricing Dashboard - Trang Chủ Tổng Quan (PHP + Vanilla JS)
?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bảng giá PC - Thành Nhân Computer</title>
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
            <a href="index.php" class="active"><i class="bi bi-speedometer2"></i> Tổng quan</a>
            <a href="category.php"><i class="bi bi-grid-3x3-gap"></i> Theo Danh Mục</a>
            <a href="brand.php"><i class="bi bi-tags"></i> Theo Thương Hiệu</a>
            <a href="stock-gap.php"><i class="bi bi-box-seam"></i> Khoảng Trống Hàng</a>
            <a href="price-activity.php"><i class="bi bi-graph-up-arrow"></i> Biến Động Giá</a>
            <a href="trend.php"><i class="bi bi-activity"></i> Xu Hướng 7 Ngày</a>
            <a href="product.php"><i class="bi bi-search"></i> Chi Tiết SP</a>
            <a href="flash-sale.php"><i class="bi bi-lightning-charge"></i> Flash Sale</a>
        </nav>

        <header class="glass-header">
            <div class="header-content">
                <div>
                    <h1><i class="bi bi-bar-chart-fill"></i> Bảng giá PC (TNC)</h1>
                    <p>Dashboard so sánh giá thị trường — Hệ thống định giá tối ưu</p>
                </div>
                <div class="status-badge" id="last-update"><i class="bi bi-clock"></i> Đang kết nối Supabase...</div>
            </div>
        </header>

        <main class="dashboard-grid">
            <!-- 1. KPI Cards -->
            <div class="kpi-row">
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-box2"></i> Sản phẩm theo dõi</h3>
                    <div class="value" id="kpi-products">--</div>
                    <div class="sub-text" id="kpi-categories">-- danh mục</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-shop"></i> Đối thủ cạnh tranh</h3>
                    <div class="value" id="kpi-competitors">--</div>
                    <div class="sub-text">cửa hàng đang theo dõi</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-percent"></i> Trung bình vs Thị trường</h3>
                    <div class="value" id="kpi-avg-diff">--</div>
                    <div class="sub-text">trên các sản phẩm có đối thủ</div>
                </div>
                <div class="glass-card kpi-card kpi-danger">
                    <h3><i class="bi bi-exclamation-triangle"></i> Bị đối thủ bán rẻ hơn</h3>
                    <div class="value highlight-red" id="kpi-beaten">--</div>
                    <div class="sub-text">cần điều chỉnh giá</div>
                </div>
            </div>

            <!-- 2. Biểu đồ tần suất đổi giá -->
            <div class="glass-card section-card">
                <div class="section-header">
                    <div>
                        <h2><i class="bi bi-activity"></i> Tần suất đổi giá theo cửa hàng</h2>
                        <p class="section-subtitle">Số lần đổi giá trên mỗi <strong>100 sản phẩm</strong> trong tuần đã chọn</p>
                    </div>
                    <select id="week-select" class="glass-select">
                        <option value="">Đang tải các tuần...</option>
                    </select>
                </div>
                <div class="chart-container">
                    <canvas id="homepage-activity-chart"></canvas>
                </div>
                <details class="formula-details">
                    <summary><i class="bi bi-info-circle"></i> Xem công thức tính chỉ số này</summary>
                    <div class="formula-content">
                        <p><strong>Công thức:</strong> (Số lần đổi giá trong tuần ÷ Số sản phẩm theo dõi) × 100.</p>
                        <p>Chỉ số giúp so sánh công bằng hành vi định giá của đối thủ, không bị thiên lệch bởi quy mô danh mục.</p>
                    </div>
                </details>
            </div>

            <!-- 3. Danh mục phòng ban -->
            <div class="categories-section">
                <h2 class="section-title"><i class="bi bi-grid-1x2"></i> Danh mục — Chọn phòng ban</h2>
                <div class="categories-grid" id="categories-cards-grid">
                    <div class="text-center">Đang nạp danh mục...</div>
                </div>
            </div>

            <!-- 4. Bảng Needs Attention -->
            <div class="glass-card table-section">
                <div class="section-header">
                    <h2><i class="bi bi-exclamation-diamond"></i> Sản phẩm bị đối thủ bán rẻ hơn</h2>
                    <select id="brand-filter" class="glass-select">
                        <option value="all">Tất cả thương hiệu</option>
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
                                <th>TNC đắt hơn</th>
                                <th>Nguồn</th>
                            </tr>
                        </thead>
                        <tbody id="table-body">
                            <tr><td colspan="7" class="text-center">Đang tải dữ liệu...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </main>
    </div>

    <script src="assets/config.js"></script>
    <script src="assets/script.js"></script>
</body>
</html>
