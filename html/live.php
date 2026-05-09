<?php
	// live.php
$channel = $_GET['channel'] ?? '';
// URL ကနေ file path ကိုယူမယ် (ဥပမာ- 360p/chunks.m3u8)
$file_uri = $_GET['file'] ?? 'playlist.m3u8';

$real_file_path = "/var/www/html/hls/" . $channel . "/" . ltrim($file_uri, '/');

if (empty($channel) || !file_exists($real_file_path)) {
    http_response_code(404);
    exit("File not found");
}

// === Tracking Logic (Master Playlist ခေါ်မှသာ Tracking လုပ်မည်) ===
if (basename($file_uri) == 'playlist.m3u8') {
    $user_ip = $_SERVER['HTTP_CF_CONNECTING_IP'] ?? $_SERVER['REMOTE_ADDR'];
    $user_agent = $_SERVER['HTTP_USER_AGENT'] ?? 'unknown';
    $device_key = md5($user_ip . $user_agent);

    $log_dir = "/var/www/html/tmp/tracking";
    $count_file = $log_dir . "/stream_" . $channel . ".json";
    $now = time();

    if (flock($fp = fopen($count_file, "c+"), LOCK_EX)) {
        $content = stream_get_contents($fp);
        $active_users = $content ? json_decode($content, true) : [];
        $active_users[$device_key] = ['last_seen' => $now, 'ip' => $user_ip];
        
        $filtered_users = [];
        foreach ($active_users as $key => $user) {
            if (($now - $user['last_seen']) < 15) {
                $filtered_users[$key] = $user;
            }
        }
        ftruncate($fp, 0);
        rewind($fp);
        fwrite($fp, json_encode($filtered_users));
        fflush($fp);
        flock($fp, LOCK_UN);
        fclose($fp);
    }
}

// === Content Rewriting ===
header('Content-Type: application/vnd.apple.mpegurl');
header('Access-Control-Allow-Origin: *');

$cdn_base = "https://262504.mmcdn.cc/hls/" . $channel;
$content = file_get_contents($real_file_path);
$lines = explode("\n", $content);
$new_lines = [];

// လက်ရှိဖိုင်ရှိနေတဲ့ folder လမ်းကြောင်းကိုယူမယ် (chunks.m3u8 အတွက်)
$current_dir = dirname($file_uri);
if ($current_dir == '.') $current_dir = '';
else $current_dir = '/' . ltrim($current_dir, '/');

foreach ($lines as $line) {
    $line = trim($line);
    if (empty($line)) continue;

    if ($line[0] === '#') {
        $new_lines[] = $line;
    } else {
        // ၁။ .m3u8 ဖိုင် (Chunks) ဖြစ်လျှင် Proxy လမ်းကြောင်းပေးမည်
        if (strpos($line, '.m3u8') !== false) {
            $new_lines[] = "/live/" . $channel . ($current_dir ? $current_dir . "/" : "/") . ltrim($line, '/');
        } 
        // ၂။ .ts ဖိုင်ဖြစ်လျှင် CDN URL သို့ အစားထိုးမည်
        else if (strpos($line, '.ts') !== false) {
            $new_lines[] = $cdn_base . $current_dir . "/" . ltrim($line, '/');
        } 
        else {
            $new_lines[] = $line;
        }
    }
}
echo implode("\n", $new_lines);