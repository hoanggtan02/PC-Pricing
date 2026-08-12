<?php
$pageTitle = "Xu Hướng Giá 7 Ngày - TNC Dashboard";
$extraHeadHtml = <<<'HTML'

HTML;
include 'includes/head.php';
include 'includes/body-start.php';
?>
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
                    <div id="trend-table-pagination" class="pagination-bar"></div>
            </div>
        </div>
    </main>

<?php
$extraScripts = '<script src="assets/trend.js"></script>';
include 'includes/footer.php';
?>
