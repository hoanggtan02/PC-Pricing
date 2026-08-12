<?php
// PC Pricing Dashboard - Khoảng Trống Hàng Hóa
?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Khoảng Trống Hàng - TNC Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@300;400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
    <div id="cr-overlay">
        <svg class="loader" viewBox="0 0 160 160" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
            <defs>
                <linearGradient id="lg" x1="90.48" y1="111.14" x2="161.56" y2="8.12" gradientUnits="userSpaceOnUse">
                    <stop offset="0" stop-color="#014f2b" />
                    <stop offset=".17" stop-color="#0e5b2d" />
                    <stop offset=".5" stop-color="#327b35" />
                    <stop offset=".95" stop-color="#6cb041" />
                    <stop offset="1" stop-color="#75c044" />
                </linearGradient>
                <linearGradient id="lg1" x1="6" y1="145.75" x2="62.13" y2="57.17" xlink:href="#lg" />
                <linearGradient id="lg2" x1="32.92" y1="37.18" x2="133.55" y2="124.75" xlink:href="#lg" />
            </defs>

            <path fill="url(#lg)" opacity="0.18" d="M156.63,22.44c-.58-1.5-1.33-2.94-2.33-4.19-.63-.78-1.37-1.44-2.19-1.97-3.75-2.43-9.19-2.4-13.22-1.31-5.85,1.58-10.99,5.14-15.82,8.69-10.63,7.82-19.88,17.53-28.42,27.54-1.21,1.41-2.44,2.86-3.65,4.36-.04.06-.1.12-.16.2-.02.02-.04.06-.06.08-.08.08-.14.18-.22.26-.2.26-.4.52-.6.77h0s7.14,6.27,7.14,6.27c.2-.26.4-.5.6-.75,4.11-5,8.11-9.56,11.86-13.55.04-.04.06-.06.1-.1.02-.02.06-.06.06-.08.02-.02.06-.06.06-.08,12.69-13.29,22.93-20.39,27.07-17.55,5.73,3.95-2.3,26-18.41,52.95h0s2.33,2.26,2.33,2.26c5.78,5.6,15.91,6.96,21.99,1.69l5.13-6.45c-.41,1.13-.84,2.26-1.27,3.38,4.43-11.47,8.21-23.27,10.38-35.37,1.54-8.6,2.87-18.65-.35-27.04Z" />
            <path fill="url(#lg1)" opacity="0.18" d="M62.85,97.08c-18.07,22.13-34.09,35.52-39.51,31.79-5.67-3.91,2.12-25.58,17.93-52.16,0,0,.01.01.02.02l-.02-.02-5-4.48c-5.39-4.8-13.49-4.96-19.02-.32-1.28,1.06-2.61,2.36-4.01,3.91-3.75,9.8-6.94,19.82-9.14,30.04-2.21,10.24-5.16,24.8.81,34.4,1.41,2.27,3.48,3.88,6.04,4.66,9.59,2.94,19.24-3.52,26.61-9.01,10.81-8.05,20.21-18,28.88-28.26.91-1.07,1.97-2.13,2.75-3.3.04-.06.1-.12.14-.18.1-.12.2-.24.3-.36.06-.06.1-.14.16-.2h0l-6.94-6.51" />
            <path id="a3" fill="url(#lg2)" opacity="0" d="M141.71,86.8c-6.08,5.27-15.18,5.02-20.96-.58l-2.33-2.26h0s0,0,0,0l-.14-.2-21.2-20.63s0,0,0,0l-7.14-6.27h0s0,0,0,0c-.08-.08-46.54-43.42-46.57-43.45-.01.03-16.47,31.79-19.99,38.85-.06.12-.12.22-.16.32-.18.37-.35.75-.52,1.13-.82,1.75-1.64,3.51-2.44,5.28l-.03.07c-.91,2.01-1.79,4.03-2.66,6.06-.21.49-.41.98-.62,1.48-.64,1.52-1.28,3.05-1.9,4.58-.31.77-.62,1.55-.92,2.33-.3.77-.59,1.54-.89,2.31,1.4-1.55,2.73-2.85,4.01-3.91,5.53-4.64,13.64-4.48,19.02.32l5,4.48.02.02c.1.09,1.21,1.03,1.23.99,4.31,4.08,7.81,7.4,11.28,10.78.4.39.79.76,1.13,1.1l1.68,1.59,4.58,4.33,1.66,1.57,6.94,6.51,2.42,2.28,44.54,40.72c9.94-19,19.93-37.09,27.98-57,.64-1.57,1.26-3.16,1.88-4.74.43-1.13.86-2.25,1.27-3.38l-6.16,5.34Z" />

            <path id="a1" fill="url(#lg)" opacity="0" d="M156.63,22.44c-.58-1.5-1.33-2.94-2.33-4.19-.63-.78-1.37-1.44-2.19-1.97-3.75-2.43-9.19-2.4-13.22-1.31-5.85,1.58-10.99,5.14-15.82,8.69-10.63,7.82-19.88,17.53-28.42,27.54-1.21,1.41-2.44,2.86-3.65,4.36-.04.06-.1.12-.16.2-.02.02-.04.06-.06.08-.08.08-.14.18-.22.26-.2.26-.4.52-.6.77h0s7.14,6.27,7.14,6.27c.2-.26.4-.5.6-.75,4.11-5,8.11-9.56,11.86-13.55.04-.04.06-.06.1-.1.02-.02.06-.06.06-.08.02-.02.06-.06.06-.08,12.69-13.29,22.93-20.39,27.07-17.55,5.73,3.95-2.3,26-18.41,52.95h0s2.33,2.26,2.33,2.26c5.78,5.6,15.91,6.96,21.99,1.69l5.13-6.45c-.41,1.13-.84,2.26-1.27,3.38,4.43-11.47,8.21-23.27,10.38-35.37,1.54-8.6,2.87-18.65-.35-27.04Z" />
            <path id="a2" fill="url(#lg1)" opacity="0" d="M62.85,97.08c-18.07,22.13-34.09,35.52-39.51,31.79-5.67-3.91,2.12-25.58,17.93-52.16,0,0,.01.01.02.02l-.02-.02-5-4.48c-5.39-4.8-13.49-4.96-19.02-.32-1.28,1.06-2.61,2.36-4.01,3.91-3.75,9.8-6.94,19.82-9.14,30.04-2.21,10.24-5.16,24.8.81,34.4,1.41,2.27,3.48,3.88,6.04,4.66,9.59,2.94,19.24-3.52,26.61-9.01,10.81-8.05,20.21-18,28.88-28.26.91-1.07,1.97-2.13,2.75-3.3.04-.06.1-.12.14-.18.1-.12.2-.24.3-.36.06-.06.1-.14.16-.2h0l-6.94-6.51" />
            <path id="a3" fill="url(#lg2)" opacity="0" d="M141.71,86.8c-6.08,5.27-15.18,5.02-20.96-.58l-2.33-2.26h0s0,0,0,0l-.14-.2-21.2-20.63s0,0,0,0l-7.14-6.27h0s0,0,0,0c-.08-.08-46.54-43.42-46.57-43.45-.01.03-16.47,31.79-19.99,38.85-.06.12-.12.22-.16.32-.18.37-.35.75-.52,1.13-.82,1.75-1.64,3.51-2.44,5.28l-.03.07c-.91,2.01-1.79,4.03-2.66,6.06-.21.49-.41.98-.62,1.48-.64,1.52-1.28,3.05-1.9,4.58-.31.77-.62,1.55-.92,2.33-.3.77-.59,1.54-.89,2.31,1.4-1.55,2.73-2.85,4.01-3.91,5.53-4.64,13.64-4.48,19.02.32l5,4.48.02.02c.1.09,1.21,1.03,1.23.99,4.31,4.08,7.81,7.4,11.28,10.78.4.39.79.76,1.13,1.1l1.68,1.59,4.58,4.33,1.66,1.57,6.94,6.51,2.42,2.28,44.54,40.72c9.94-19,19.93-37.09,27.98-57,.64-1.57,1.26-3.16,1.88-4.74.43-1.13.86-2.25,1.27-3.38l-6.16,5.34Z" />
        </svg>
    </div>

    <div class="background-blobs">
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>
    </div>

    <div class="app-container">
                <nav class="nav-menu">
            <a href="index.php"><i class="bi bi-speedometer2"></i> Tổng quan</a>
            <a href="category.php"><i class="bi bi-funnel"></i> Bộ Lọc Chi Tiết</a>
            <a href="stock-gap.php" class="active"><i class="bi bi-box-seam"></i> Khoảng Trống Hàng</a>
            <a href="price-activity.php"><i class="bi bi-graph-up-arrow"></i> Biến Động Giá</a>
            <a href="trend.php"><i class="bi bi-activity"></i> Xu Hướng 7 Ngày</a>
            <a href="product.php"><i class="bi bi-search"></i> Chi Tiết SP</a>
            <a href="flash-sale.php"><i class="bi bi-lightning-charge"></i> Flash Sale</a>
            <a href="data-manager.php"><i class="bi bi-database-gear"></i> Quản Lý DL</a>
        </nav>

        <header class="glass-header">
            <div class="header-content">
                <div>
                    <h1><i class="bi bi-box-seam-fill"></i> Khoảng Trống Hàng Hóa</h1>
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
                    <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
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
                        <select id="gap-brand-filter" class="glass-select">
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
    </div>

    <script src="assets/pagination.js"></script>
    <script src="assets/config.js"></script>
    <script src="assets/loader.js"></script>
    <script src="assets/stock-gap.js"></script>
</body>
</html>
