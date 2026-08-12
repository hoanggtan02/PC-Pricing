<?php
/**
 * includes/head.php — Shared HTML <head> section
 *
 * Biến có thể set trước khi include:
 *   $pageTitle      (string) — Tiêu đề tab trình duyệt, mặc định "TNC Dashboard"
 *   $extraHeadHtml  (string) — CSS/script đặc thù của trang (ví dụ: Chart.js, inline <style>)
 */
$pageTitle     = $pageTitle     ?? 'TNC Dashboard';
$extraHeadHtml = $extraHeadHtml ?? '';
?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?= htmlspecialchars($pageTitle) ?></title>
    <link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@300;400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <link rel="stylesheet" href="assets/style.css">
    <?= $extraHeadHtml ?>
</head>
