<?php
	// ccu_api.php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

$channel = $_GET['channel'] ?? '';
$file_path = "/var/www/html/tmp/tracking/stream_" . $channel . ".json";

if (empty($channel) || !file_exists($file_path)) {
    echo json_encode([
        "status" => "error", 
        "viewers_count" => 0,
        "ips" => []
    ]);
    exit;
}

$data = json_decode(file_get_contents($file_path), true);

// JSON ထဲကနေ IP Address တွေကိုပဲ သီးသန့် Array တစ်ခုအနေနဲ့ ထုတ်ယူမယ်
$ip_list = [];
foreach ($data as $user) {
    if (isset($user['ip'])) {
        $ip_list[] = $user['ip'];
    }
}

echo json_encode([
    "status" => "success",
    "channel" => $channel,
    "viewers_count" => count($data),
    "ips" => $ip_list // IP list ကိုပါ ထည့်ပေးလိုက်မယ်
]);