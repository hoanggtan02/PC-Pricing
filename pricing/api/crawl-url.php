<?php
// api/crawl-url.php
header('Content-Type: application/json');

$url = $_GET['url'] ?? '';
$sku = $_GET['sku'] ?? '';
$competitor = $_GET['competitor'] ?? '';

if (empty($url) || empty($sku) || empty($competitor)) {
    echo json_encode(['success' => false, 'error' => 'Missing url, sku, or competitor']);
    exit;
}

$userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';

$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true, 
    CURLOPT_FOLLOWLOCATION => true, 
    CURLOPT_SSL_VERIFYPEER => false, 
    CURLOPT_TIMEOUT => 20, 
    CURLOPT_USERAGENT => $userAgent
]);

$html = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$error = curl_error($ch);
curl_close($ch);

if (!$html) {
    echo json_encode(['success' => false, 'error' => "Failed to fetch URL: $error (HTTP $httpCode)"]);
    exit;
}

function extractPrice($html) {
    if (preg_match('/class="price-current[^>]*>([\d\.]+)/', $html, $m)) return (int)str_replace('.', '', $m[1]);
    if (preg_match('/class="box-price-present[^>]*>([\d\.]+)/', $html, $m)) return (int)str_replace('.', '', $m[1]);
    if (preg_match('/"price":\s?"?(\d+)"?/', $html, $m)) return (int)$m[1];
    if (preg_match('/property="product:price:amount" content="(\d+)"/', $html, $m)) return (int)$m[1];
    if (preg_match('/b1-semibold[^>]*>([\d\.,]+)/i', $html, $m)) return (int)preg_replace('/[^0-9]/', '', $m[1]);
    // Thêm các rule tìm giá khác nếu cần
    return 0;
}

$price = extractPrice($html);

if ($price > 0) {
    // Đọc .env để lấy SUPABASE Service Role Key
    $envPath = __DIR__ . '/../../scraper/.env';
    $supabaseUrl = '';
    $supabaseKey = '';
    
    if (file_exists($envPath)) {
        $env = parse_ini_file($envPath);
        $supabaseUrl = $env['SUPABASE_URL'] ?? '';
        $supabaseKey = $env['SUPABASE_KEY'] ?? '';
    }
    
    if (!$supabaseUrl || !$supabaseKey) {
        echo json_encode(['success' => false, 'error' => 'Could not read Supabase config from .env']);
        exit;
    }
    
    // Ghi vào Supabase bằng cURL (dùng service role key để bypass RLS)
    $data = [
        'product_sku' => $sku,
        'competitor' => $competitor,
        'price' => $price,
        'currency' => 'VND',
        'in_stock' => true
    ];
    
    $chSb = curl_init("$supabaseUrl/rest/v1/price_history");
    curl_setopt_array($chSb, [
        CURLOPT_POST => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER => [
            "apikey: $supabaseKey",
            "Authorization: Bearer $supabaseKey",
            "Content-Type: application/json",
            "Prefer: return=minimal"
        ],
        CURLOPT_POSTFIELDS => json_encode($data),
        CURLOPT_SSL_VERIFYPEER => false
    ]);
    
    $sbRes = curl_exec($chSb);
    $sbStatus = curl_getinfo($chSb, CURLINFO_HTTP_CODE);
    curl_close($chSb);
    
    if ($sbStatus >= 200 && $sbStatus < 300) {
        // latest_prices_cache là snapshot, không tự đổi khi price_history có bản ghi mới.
        // Refresh ngay để product_overview (và category.php) nhìn thấy giá vừa cào.
        $chRefresh = curl_init("$supabaseUrl/rest/v1/rpc/refresh_latest_prices");
        curl_setopt_array($chRefresh, [
            CURLOPT_POST => true,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => [
                "apikey: $supabaseKey",
                "Authorization: Bearer $supabaseKey",
                "Content-Type: application/json",
                "Prefer: return=minimal"
            ],
            CURLOPT_POSTFIELDS => '{}',
            CURLOPT_SSL_VERIFYPEER => false
        ]);

        $refreshRes = curl_exec($chRefresh);
        $refreshStatus = curl_getinfo($chRefresh, CURLINFO_HTTP_CODE);
        $refreshError = curl_error($chRefresh);
        curl_close($chRefresh);

        if ($refreshStatus >= 200 && $refreshStatus < 300) {
            echo json_encode(['success' => true, 'price' => $price, 'url' => $url]);
        } else {
            // Giá đã được lưu nhưng cache chưa thể làm mới: báo lỗi rõ ràng để tránh UI nói là đã cập nhật.
            $detail = $refreshError ?: $refreshRes;
            echo json_encode([
                'success' => false,
                'error' => "Price was saved, but the dashboard cache could not refresh (HTTP $refreshStatus): $detail"
            ]);
        }
    } else {
        echo json_encode(['success' => false, 'error' => "Supabase API Error (HTTP $sbStatus): $sbRes"]);
    }
} else {
    echo json_encode(['success' => false, 'error' => 'Could not extract price from this URL.']);
}
