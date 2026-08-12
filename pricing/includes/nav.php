<?php
/**
 * includes/nav.php — Shared Navigation Menu
 * Dùng chung cho toàn bộ dashboard. Tự động detect trang hiện tại để đặt class "active".
 * 
 * Cách dùng: <?php include 'includes/nav.php'; ?>
 */
$currentPage = basename($_SERVER['PHP_SELF']);

$navItems = [
    ['href' => 'index.php',         'icon' => 'bi-speedometer2',    'label' => 'Tổng quan'],
    ['href' => 'category.php',      'icon' => 'bi-funnel',          'label' => 'Bộ Lọc Chi Tiết'],
    ['href' => 'stock-gap.php',     'icon' => 'bi-box-seam',        'label' => 'Cơ hội'],
    ['href' => 'price-activity.php','icon' => 'bi-graph-up-arrow',  'label' => 'Biến Động Giá'],
    ['href' => 'trend.php',         'icon' => 'bi-activity',        'label' => 'Xu Hướng 7 Ngày'],
    ['href' => 'product.php',       'icon' => 'bi-search',          'label' => 'Chi Tiết SP'],
    ['href' => 'flash-sale.php',    'icon' => 'bi-lightning-charge', 'label' => 'Flash Sale'],
    ['href' => 'data-manager.php',  'icon' => 'bi-database-gear',   'label' => 'Quản Lý DL'],
];
?>
<nav class="nav-menu">
<?php foreach ($navItems as $item): ?>
    <a href="<?= $item['href'] ?>"<?= $currentPage === $item['href'] ? ' class="active"' : '' ?>>
        <i class="bi <?= $item['icon'] ?>"></i> <?= $item['label'] ?>
    </a>
<?php endforeach; ?>
</nav>
