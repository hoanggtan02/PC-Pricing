<?php
$pageTitle = "Biến Động Giá - TNC Dashboard";
$extraHeadHtml = <<<'HTML'
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
HTML;
include 'includes/head.php';
include 'includes/body-start.php';
?>
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
                    <div id="activity-table-pagination" class="pagination-bar"></div>
                </div>
            </div>
        </main>

<?php
$extraScripts = '<script src="assets/price-activity.js"></script>';
include 'includes/footer.php';
?>
