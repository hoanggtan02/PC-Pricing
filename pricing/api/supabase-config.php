<?php
/**
 * Đọc cấu hình Supabase cho API nội bộ.
 *
 * Ưu tiên biến môi trường của web server. Khi deploy riêng thư mục `pricing`,
 * có thể đặt file `pricing/.env` (không commit) thay vì phụ thuộc scraper/.env.
 */
function getSupabaseConfig(): array
{
    $url = getenv('SUPABASE_URL') ?: '';
    $key = getenv('SUPABASE_KEY') ?: '';

    if ($url && $key) {
        return [$url, $key];
    }

    $envPaths = [
        dirname(__DIR__) . '/.env',        // pricing/.env: deploy chỉ pricing
        __DIR__ . '/../../scraper/.env',   // môi trường phát triển đầy đủ
    ];

    foreach ($envPaths as $envPath) {
        if (!is_file($envPath) || !is_readable($envPath)) {
            continue;
        }

        $env = parse_ini_file($envPath, false, INI_SCANNER_RAW);
        if ($env === false) {
            continue;
        }

        $url = $url ?: ($env['SUPABASE_URL'] ?? '');
        $key = $key ?: ($env['SUPABASE_KEY'] ?? '');
        if ($url && $key) {
            return [$url, $key];
        }
    }

    return ['', ''];
}
