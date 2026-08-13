<?php
/**
 * api/supabase-proxy.php
 * 
 * Proxy mọi thao tác ghi vào Supabase dùng Service Role Key (để bypass RLS).
 * Frontend (JS) chỉ có anon key nên bị RLS chặn INSERT/UPDATE/DELETE.
 * 
 * Request: POST với body JSON:
 * {
 *   "method": "PATCH" | "POST" | "DELETE",
 *   "table": "sources" | "products" | ...,
 *   "match": { "product_sku": "...", "competitor": "..." },  // điều kiện WHERE (cho PATCH/DELETE)
 *   "data": { ... }  // body data (cho PATCH/POST)
 * }
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

// Preflight
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    echo json_encode(['success' => false, 'error' => 'Only POST allowed']);
    exit;
}

// Đọc body
$body = json_decode(file_get_contents('php://input'), true);
if (!$body) {
    echo json_encode(['success' => false, 'error' => 'Invalid JSON body']);
    exit;
}

$method   = strtoupper($body['method'] ?? '');
$table    = $body['table'] ?? '';
$match    = $body['match'] ?? [];
$data     = $body['data'] ?? [];

// Validate
$allowedMethods = ['PATCH', 'POST', 'DELETE'];
$allowedTables  = ['sources', 'products', 'price_history', 'competitors'];

if (!in_array($method, $allowedMethods)) {
    echo json_encode(['success' => false, 'error' => "Method '$method' not allowed"]);
    exit;
}
if (!in_array($table, $allowedTables)) {
    echo json_encode(['success' => false, 'error' => "Table '$table' not allowed"]);
    exit;
}
if (empty($table)) {
    echo json_encode(['success' => false, 'error' => 'Missing table']);
    exit;
}

// Đọc service role key từ .env
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

// Build URL với query params từ match (WHERE conditions)
$apiUrl = "$supabaseUrl/rest/v1/$table";
if (!empty($match)) {
    $params = [];
    foreach ($match as $col => $val) {
        $params[] = urlencode($col) . '=eq.' . urlencode($val);
    }
    $apiUrl .= '?' . implode('&', $params);
}

// Gọi Supabase API
$ch = curl_init($apiUrl);
$curlOpts = [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_SSL_VERIFYPEER => false,
    CURLOPT_CUSTOMREQUEST  => $method,
    CURLOPT_HTTPHEADER     => [
        "apikey: $supabaseKey",
        "Authorization: Bearer $supabaseKey",
        "Content-Type: application/json",
        "Prefer: return=minimal"
    ],
];

if (in_array($method, ['PATCH', 'POST']) && !empty($data)) {
    $curlOpts[CURLOPT_POSTFIELDS] = json_encode($data);
}

curl_setopt_array($ch, $curlOpts);
$res    = curl_exec($ch);
$status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$curlErr = curl_error($ch);
curl_close($ch);

if ($curlErr) {
    echo json_encode(['success' => false, 'error' => "cURL error: $curlErr"]);
    exit;
}

if ($status >= 200 && $status < 300) {
    // latest_prices_cache là snapshot. Mọi thay đổi nguồn (nhất là bật/tắt active)
    // phải làm mới snapshot để category.php không hiển thị nguồn đã tắt.
    if ($table === 'sources') {
        $refresh = curl_init("$supabaseUrl/rest/v1/rpc/refresh_latest_prices");
        curl_setopt_array($refresh, [
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
        $refreshRes = curl_exec($refresh);
        $refreshStatus = curl_getinfo($refresh, CURLINFO_HTTP_CODE);
        $refreshErr = curl_error($refresh);
        curl_close($refresh);

        if ($refreshStatus < 200 || $refreshStatus >= 300) {
            $detail = $refreshErr ?: $refreshRes;
            echo json_encode([
                'success' => false,
                'error' => "Source was saved, but the dashboard cache could not refresh (HTTP $refreshStatus): $detail"
            ]);
            exit;
        }
    }

    echo json_encode(['success' => true, 'status' => $status]);
} else {
    echo json_encode(['success' => false, 'error' => "Supabase API Error (HTTP $status): $res"]);
}
