<?php
$pageTitle = "Cơ hội - TNC Dashboard";
$extraHeadHtml = <<<'HTML'

HTML;
include 'includes/head.php';
include 'includes/body-start.php';
?>
<header class="glass-header">
            <div class="header-content">
                <div>
                    <h1><i class="bi bi-box-seam-fill"></i> Cơ Hội</h1>
                    <p>Sản phẩm TNC đang hết hàng — trong khi đối thủ vẫn còn bán</p>
                </div>
                <div class="status-badge" id="last-update"><i class="bi bi-clock"></i> Đang tải...</div>
            </div>
        </header>

        <main class="dashboard-grid">
            <div class="kpi-row">
                <div class="glass-card kpi-card kpi-danger">
                    <h3><i class="bi bi-exclamation-circle"></i> Sản phẩm hết hàng</h3>
                    <div class="value highlight-red" id="gap-total">--</div>
                    <div class="sub-text">TNC hết, đối thủ còn bán</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-shop"></i> Tổng lượt cạnh tranh</h3>
                    <div class="value" id="gap-competitors">--</div>
                    <div class="sub-text">đối thủ đang bán thay TNC</div>
                </div>
                <div class="glass-card kpi-card">
                    <h3><i class="bi bi-currency-dollar"></i> Doanh thu rủi ro</h3>
                    <div class="value highlight-red" id="gap-revenue-risk">--</div>
                    <div class="sub-text">theo giá đối thủ rẻ nhất</div>
                </div>
            </div>

            <div class="glass-card table-section">
                <div class="section-header">
                    <h2><i class="bi bi-list-ul"></i> Danh sách sản phẩm mất cơ hội</h2>
                </div>
                <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:0.75rem;margin-bottom:1.25rem;align-items:end;">
                    <div>
                        <label style="font-size:0.8rem;color:var(--text-muted);font-weight:600;margin-bottom:0.4rem;display:block;">Tìm kiếm</label>
                        <div style="position:relative;">
                            <input type="text" id="gap-search-filter" class="glass-input" placeholder="Nhập tên SP, SKU..." style="padding-left:2.2rem;">
                            <i class="bi bi-search" style="position:absolute;left:0.8rem;top:50%;transform:translateY(-50%);color:var(--text-muted);"></i>
                        </div>
                    </div>
                    <div>
                        <label style="font-size:0.8rem;color:var(--text-muted);font-weight:600;margin-bottom:0.4rem;display:block;">Danh mục</label>
                        <select id="gap-category-filter" class="glass-select" style="width:100%;">
                            <option value="">Tất cả danh mục</option>
                            <!-- Nạp động từ dữ liệu -->
                        </select>
                    </div>
                    <div>
                        <label style="font-size:0.8rem;color:var(--text-muted);font-weight:600;margin-bottom:0.4rem;display:block;">Thương hiệu</label>
                        <select id="gap-brand-filter" class="glass-select" style="width:100%;">
                            <option value="">Tất cả thương hiệu</option>
                            <!-- Nạp động từ dữ liệu -->
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
                                <th>Số đối thủ</th>
                                <th>Giá đối thủ rẻ nhất</th>
                                <th>Đối thủ rẻ nhất</th>
                                <th>Link</th>
                            </tr>
                        </thead>
                        <tbody id="gap-table-body">
                            <tr><td colspan="7" class="text-center">Đang tải dữ liệu...</td></tr>
                        </tbody>
                    </table>
                    <div id="gap-table-pagination" class="pagination-bar"></div>
                </div>
            </div>
        </main>

<?php
$extraScripts = '<script src="assets/stock-gap.js"></script>';
include 'includes/footer.php';
?>
