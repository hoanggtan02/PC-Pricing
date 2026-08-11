<?php
// PC Pricing Dashboard - Trang Chủ Tổng Quan (PHP + Vanilla JS)
?>
<!DOCTYPE html>
<html lang="vi" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bảng giá PC - Thành Nhân Computer</title>
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
            <a href="index.php" class="active">Tổng quan</a>
            <a href="category.php?name=Laptop">Theo Danh Mục</a>
            <a href="brand.php?name=Dell">Theo Thương Hiệu</a>
            <a href="stock-gap.php">Khoảng Trống Hàng</a>
            <a href="price-activity.php">Biến Động Giá</a>
        </nav>

        <header class="glass-header">
            <div class="header-content">
                <div>
                    <h1>Bảng giá PC (TNC)</h1>
                    <p>Dashboard so sánh giá thị trường - Hệ thống định giá tối ưu</p>
                </div>
                <div class="status-badge" id="last-update">Đang tải kết nối Supabase...</div>
            </div>
        </header>

        <main class="dashboard-grid">
            <!-- 1. Hàng KPI tổng hợp -->
            <div class="kpi-row">
                <div class="glass-card kpi-card">
                    <h3>Sản phẩm theo dõi</h3>
                    <div class="value" id="kpi-products">--</div>
                    <div class="sub-text" id="kpi-categories">-- danh mục</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3>Đối thủ</h3>
                    <div class="value" id="kpi-competitors">--</div>
                    <div class="sub-text">cửa hàng đang hoạt động</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3>Trung bình vs Thị trường</h3>
                    <div class="value" id="kpi-avg-diff">--</div>
                    <div class="sub-text">trên các sản phẩm có đối thủ</div>
                </div>
                <div class="glass-card kpi-card kpi-danger">
                    <h3>Bị đối thủ bán rẻ hơn</h3>
                    <div class="value highlight-red" id="kpi-beaten">--</div>
                    <div class="sub-text">cần điều chỉnh giá giảm</div>
                </div>
            </div>

            <!-- 2. Biểu đồ tần suất đổi giá theo tuần (Tương tự React) -->
            <div class="glass-card section-card">
                <div class="section-header">
                    <div>
                        <h2>Tần suất đổi giá theo cửa hàng</h2>
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
                    <summary>ⓘ Xem công thức tính chỉ số này</summary>
                    <div class="formula-content">
                        <p><strong>Công thức:</strong> (Số lần đổi giá trong tuần ÷ Số sản phẩm theo dõi) × 100.</p>
                        <p>Chỉ số giúp so sánh công bằng hành vi định giá của đối thủ, không bị thiên lệch bởi quy mô lớn hay nhỏ của danh mục sản phẩm.</p>
                    </div>
                </details>
            </div>

            <!-- 3. Danh mục phòng ban (Category Cards Grid như React) -->
            <div class="categories-section">
                <h2 class="section-title">Danh mục — Chọn phòng ban của bạn</h2>
                <div class="categories-grid" id="categories-cards-grid">
                    <!-- Javascript nạp danh sách card -->
                    <div class="text-center">Đang nạp các phòng ban...</div>
                </div>
            </div>

            <!-- 4. Danh sách Needs Attention -->
            <div class="glass-card table-section">
                <div class="section-header">
                    <h2>⚠️ Top sản phẩm bị đối thủ bán rẻ hơn (Cần chú ý nhất)</h2>
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
                                <th>Giá của TNC</th>
                                <th>Giá rẻ nhất</th>
                                <th>Đối thủ bán rẻ nhất</th>
                                <th>TNC đắt hơn</th>
                                <th>Độ phủ</th>
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

    <!-- Tải cấu hình & Script -->
    <script src="assets/config.js"></script>
    <script src="assets/script.js"></script>
</body>
</html>
