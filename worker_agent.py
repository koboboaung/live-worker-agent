import datetime
import json
import os
import psutil
import requests
import secrets
import shutil
import subprocess
import threading
import time

import boto3
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Main Server IP
ALLOWED_IPS = ['127.0.0.1', '146.190.90.223', '10.104.0.7']

# Global State Variables
server_bandwidth = {"download_mbps": 0.0, "upload_mbps": 0.0, "total_mbps": 0.0}
active_srt_streams = {"push_inputs": 0, "pull_outputs": 0, "active_connections": []}

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def patch_m3u8(filepath):
    """Playlist FRAME-RATE=25 Helper"""
    for _ in range(15):
        if os.path.exists(filepath):
            time.sleep(1)
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                if 'FRAME-RATE' not in content:
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if line.startswith('#EXT-X-STREAM-INF:'):
                            lines[i] = line + ',FRAME-RATE=25'
                    with open(filepath, 'w') as f:
                        f.write('\n'.join(lines))
            except Exception:
                pass
            break
        time.sleep(1)

def monitor_ffmpeg(key, cmd):
    """FFmpeg Process Monitoring နှင့် Auto-Restart Loop"""
    log_file_path = f"/var/www/html/hls/{key}_error.log"
    
    while True:
        if os.path.exists(log_file_path) and os.path.getsize(log_file_path) > 10 * 1024 * 1024:
            try:
                os.remove(log_file_path)
            except Exception:
                pass

        try:
            with open(log_file_path, "a") as logfile:
                start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logfile.write(f"\n[{start_time}] --- Starting/Restarting FFmpeg for {key} ---\n")
                
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.DEVNULL, 
                    stderr=logfile,
                    stdin=subprocess.DEVNULL, 
                    close_fds=True
                )
                process.wait()
                
                stop_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logfile.write(f"[{stop_time}] --- FFmpeg stopped with exit code: {process.returncode} ---\n")
        except Exception as e:
            print(f"Logging error: {e}")

        if os.path.exists(f"/var/www/html/hls/{key}"):
            time.sleep(2)
            continue 
        else:
            break

def track_bandwidth():
    """Server Bandwidth Monitoring Thread"""
    global server_bandwidth
    last_io = psutil.net_io_counters()
    
    while True:
        time.sleep(1) 
        current_io = psutil.net_io_counters()
        
        dl_mbps = (current_io.bytes_recv - last_io.bytes_recv) * 8 / 1_000_000
        ul_mbps = (current_io.bytes_sent - last_io.bytes_sent) * 8 / 1_000_000
        
        server_bandwidth["download_mbps"] = round(dl_mbps, 2)
        server_bandwidth["upload_mbps"] = round(ul_mbps, 2)
        server_bandwidth["total_mbps"] = round(dl_mbps + ul_mbps, 2)
        
        last_io = current_io

# Background Threads စတင်ခြင်း
threading.Thread(target=track_bandwidth, daemon=True).start()

# ==========================================
# 1. VOD ENCODER (Background Worker + AES-128 + S3)
# ==========================================
def vod_encode_and_upload(video_id, user_id, videoname, source_url, webhook_url, s3_keys, key_api_url, resolutions=[720], year=None, month=None):
    out_dir = f"/var/www/html/hls/vod_{video_id}"
    os.makedirs(out_dir, exist_ok=True)
    
    key_file_path = os.path.join(out_dir, 'enc.key')
    key_info_path = os.path.join(out_dir, 'enc.keyinfo')
    
    encryption_key = secrets.token_bytes(16)
    with open(key_file_path, 'wb') as f:
        f.write(encryption_key)
        
    with open(key_info_path, 'w') as f:
        f.write(f"{key_api_url}\n")
        f.write(f"{key_file_path}\n")

    cfg = {
        360: {'scale': '640:360', 'b': '800k', 'max': '1000k', 'buf': '1500k', 'name': '360p'},
        720: {'scale': '1280:720', 'b': '1700k', 'max': '2000k', 'buf': '3000k', 'name': '720p'},
        1080: {'scale': '1920:1080', 'b': '4000k', 'max': '5000k', 'buf': '7000k', 'name': '1080p'}
    }
    
    outputs = [r for r in resolutions if r in cfg]
    if not outputs: 
        outputs = [720]

    filt = [f"[0:v:0]split={len(outputs)}" + "".join(f"[v{i}]" for i in range(len(outputs)))]
    map_v, map_a, enc, var_map = [], [], [], []
    
    for i, r in enumerate(outputs):
        c = cfg[r]
        filt.append(f"[v{i}]scale={c['scale']}[v{i}out]")
        
        map_v.extend(["-map", f"[v{i}out]"])
        map_a.extend(["-map", "0:a:0"])
        
        enc.extend([
            f"-c:v:{i}", "libx264", 
            f"-b:v:{i}", c['b'], 
            f"-maxrate:v:{i}", c['max'], 
            f"-bufsize:v:{i}", c['buf'], 
            "-preset", "superfast", 
            f"-r:v:{i}", "25", 
            f"-g:v:{i}", "50", 
            f"-keyint_min:v:{i}", "50", 
            "-sc_threshold", "0", 
            "-x264-params", "nal-hrd=cbr:force-cfr=1"
        ])
        var_map.append(f"v:{i},a:{i},name:{c['name']}")

    cmd = [
        "ffmpeg", "-y", "-i", source_url,
        "-filter_complex", ";".join(filt),
        *map_v, *map_a,
        "-c:a", "aac", "-b:a", "128k",
        *enc,
        "-f", "hls", 
        "-hls_time", "10", 
        "-hls_list_size", "0", 
        "-hls_key_info_file", key_info_path, 
        "-master_pl_name", "playlist.m3u8",
        "-hls_segment_filename", f"{out_dir}/%v/segment_%03d.ts", 
        "-var_stream_map", " ".join(var_map),
        f"{out_dir}/%v/chunks.m3u8"
    ]
    
    try:
        process = subprocess.run(cmd, capture_output=True, text=True)
        if process.returncode != 0:
            error_msg = process.stderr[-500:] if process.stderr else "Unknown FFmpeg Error"
            raise Exception(f"FFmpeg Error: {error_msg}")
        
        s3_client = boto3.client('s3',
            region_name='ap-southeast-1',
            endpoint_url='https://s3.ap-southeast-1.wasabisys.com',
            aws_access_key_id=s3_keys['access_key'],
            aws_secret_access_key=s3_keys['secret_key']
        )
        
        bucket_name = "vodfile" 
        if not year: year = time.strftime('%Y')
        if not month: month = time.strftime('%m')        
        
        s3_folder = f"usr/{user_id}/ott/hls/{year}/{month}/{videoname}"
        
        for root, dirs, files in os.walk(out_dir):
            for file in files:
                if file.endswith('.keyinfo'): 
                    continue 
                
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, out_dir) 
                s3_path = f"{s3_folder}/{relative_path}"
                s3_client.upload_file(local_path, bucket_name, s3_path, ExtraArgs={'ACL': 'public-read'})
                
        hls_url = f"https://{bucket_name}.s3.ap-southeast-1.wasabisys.com/{s3_folder}/playlist.m3u8"
        requests.post(webhook_url, json={"video_id": video_id, "status": "completed", "hls_url": hls_url})
        
    except Exception as e:
        with open("/var/www/html/hls/error.log", "a") as logfile:
            logfile.write(f"Video {video_id} Error: {str(e)}\n")
        requests.post(webhook_url, json={"video_id": video_id, "status": "error", "message": str(e)})
        
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)

# ==========================================
# 2. FLASK ROUTES / API ENDPOINTS
# ==========================================
@app.route('/start_vod_encode', methods=['POST'])
def start_vod_encode():
    if request.remote_addr not in ALLOWED_IPS:
        return jsonify({'error': 'Forbidden: Access Denied'}), 403

    data = request.json
    video_id = data.get('video_id')
    user_id = data.get('user_id') 
    videoname = data.get('videoname') 
    year = data.get('year')
    month = data.get('month')
    source_url = data.get('source_url')
    webhook_url = data.get('webhook_url')
    s3_keys = data.get('s3_keys')
    key_api_url = data.get('key_api_url')
    resolutions = data.get('resolutions', [720]) 
    
    if not all([video_id, user_id, videoname, source_url, webhook_url, s3_keys, key_api_url]):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400
        
    thread = threading.Thread(
        target=vod_encode_and_upload, 
        args=(video_id, user_id, videoname, source_url, webhook_url, s3_keys, key_api_url, resolutions, year, month),
        daemon=True
    )
    thread.start()
    
    return jsonify({"status": "queued", "video_id": video_id, "message": "VOD encoding started"})

@app.route('/start_encoder', methods=['POST'])
def start_encoder():
    data = request.json
    key, src = data.get('stream_key'), data.get('source_url')
    source_type = data.get('source_type', 'rtmp') 
    
    if not key or not src:
        return jsonify({"status": "error", "message": "Missing key or source url"}), 400
    
    res = {360: data.get('res_360', 0), 720: data.get('res_720', 0), 1080: data.get('res_1080', 0)}
    if not any(res.values()):
        return jsonify({"status": "error", "message": "No resolutions selected"}), 400
    
    out_dir = f"/var/www/html/hls/{key}"
    os.makedirs(out_dir, exist_ok=True)
    
    cfg = {
        '360': {'scale': '640:360', 'b': '800k', 'max': '1000k', 'buf': '1500k', 'name': '360p'},
        '720': {'scale': '1280:720', 'b': '1700k', 'max': '2000k', 'buf': '3000k', 'name': '720p'},
        '1080': {'scale': '1920:1080', 'b': '4000k', 'max': '5000k', 'buf': '7000k', 'name': '1080p'}
    }
    outputs = [f'v{r}' for r in [360,720,1080] if res[r]]
    filt = [f"[0:v:0]split={len(outputs)}" + "".join(f"[{o}]" for o in outputs)]
    map_v, map_a, enc, var_map = [], [], [], []
    
    for i, o in enumerate(outputs):
        c = cfg[o[1:]]
        filt.append(f"[{o}]fps=25,scale={c['scale']}[{o}out]")
        map_v.extend(["-map", f"[{o}out]"])
        map_a.extend(["-map", "0:a:0"])
        enc.extend([
            f"-c:v:{i}", "libx264", 
            f"-b:v:{i}", c['b'], 
            f"-maxrate:v:{i}", c['max'], 
            f"-bufsize:v:{i}", c['buf'], 
            f"-profile:v:{i}", "main",
            f"-r:v:{i}", "25",
        ]) 
        var_map.append(f"v:{i},a:{i},name:{c['name']}")
        
    cmd = ["ffmpeg", "-y", "-loglevel", "info"]
    
    if src.startswith("srt://") or source_type == "srt":
        srt_params = "auto-reconnect=1&reconnect_delay=3&max_reconnect_attempts=-1"
        src = f"{src}&{srt_params}" if "?" in src else f"{src}?{srt_params}"
    elif src.startswith("rtmp://") or source_type == "rtmp":
        # RTMP auto-reconnect
        cmd.extend([
            "-reconnect", "1",
            "-reconnect_at_eof", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-rw_timeout", "10000000"
        ])

    cmd.extend([
        "-fflags", "+genpts+discardcorrupt", 
        "-i", src,
        "-filter_complex", ";".join(filt), 
        *map_v, *map_a,
        "-preset", "superfast", "-tune", "zerolatency", "-g", "100", "-keyint_min", "100", "-sc_threshold", "0",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2", 
        "-ar", "44100",             
        "-af", "aresample=async=1", 
        "-fps_mode", "cfr",          
        
        *enc,
        "-f", "hls", "-hls_time", "4", "-hls_list_size", "10", 
        "-hls_flags", "delete_segments+independent_segments+append_list", 
        "-hls_segment_type", "mpegts", "-vtag", "avc1", "-hls_segment_filename", f"{out_dir}/%v/%s.ts", "-strftime", "1",
        "-var_stream_map", " ".join(var_map), "-master_pl_name", "playlist.m3u8", f"{out_dir}/%v/chunks.m3u8"
    ])
    
    try:
        threading.Thread(target=monitor_ffmpeg, args=(key, cmd), daemon=True).start()
        threading.Thread(target=patch_m3u8, args=(f"{out_dir}/playlist.m3u8",), daemon=True).start()
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
        
    return jsonify({"status": "started", "key": key, "streams": var_map})

@app.route('/stop_encoder', methods=['POST'])
def stop_encoder():
    key = request.json.get('stream_key')
    if not key: 
        return jsonify({"status": "error", "message": "Stream key required"}), 400
    
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmd = ' '.join(proc.info.get('cmdline') or [])
            if 'ffmpeg' in cmd and f'/var/www/html/hls/{key}' in cmd:
                proc.kill()
        except Exception: 
            continue
    
    shutil.rmtree(f"/var/www/html/hls/{key}", ignore_errors=True)
    return jsonify({"status": "success", "message": f"Stream {key} stopped"})

@app.route('/stats', methods=['GET'])
def get_stats():
    active = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd_list = proc.info.get('cmdline')
            if cmd_list:
                cmd_str = ' '.join(cmd_list)
                if 'ffmpeg' in cmd_str and '/var/www/html/hls/' in cmd_str:
                    parts = cmd_str.split('/var/www/html/hls/')
                    if len(parts) > 1:
                        key = parts[1].split('/')[0]
                        if key and key not in active:
                            active.append(key)
        except Exception: 
            continue
    return jsonify({"cpu_usage": psutil.cpu_percent(), "ram_usage": psutil.virtual_memory().percent, "active_streams": active})

@app.route('/stream_logs/<key>', methods=['GET'])
def get_stream_logs(key):
    if request.remote_addr not in ALLOWED_IPS:
        return jsonify({'error': 'Forbidden: Access Denied'}), 403
        
    log_file_path = f"/var/www/html/hls/{key}_error.log"
    if not os.path.exists(log_file_path):
        return jsonify({"status": "error", "message": "Log file not found"}), 404
        
    try:
        with open(log_file_path, 'r') as f:
            lines = f.readlines()
            last_lines = lines[-100:] if len(lines) > 100 else lines
        return jsonify({"status": "success", "stream_key": key, "logs": "".join(last_lines)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/sls/on_event', methods=['GET', 'POST'])
def sls_on_event():
    global active_srt_streams
    
    if request.method == 'POST':
        event_data = {}
        if request.is_json:
            event_data = request.json
        elif request.form:
            event_data = dict(request.form)
        else:
            event_data = dict(request.args)
            
        if not event_data and request.data:
            try:
                event_data = json.loads(request.data.decode('utf-8'))
            except Exception:
                pass

        event_type = event_data.get('on_event')
        role = event_data.get('role_name')
        
        if event_type == 'on_connect':
            if role == 'publisher':
                active_srt_streams['push_inputs'] += 1
            elif role == 'player':
                active_srt_streams['pull_outputs'] += 1
            active_srt_streams['active_connections'].append(event_data)
                
        elif event_type == 'on_close':
            if role == 'publisher' and active_srt_streams['push_inputs'] > 0:
                active_srt_streams['push_inputs'] -= 1
            elif role == 'player' and active_srt_streams['pull_outputs'] > 0:
                active_srt_streams['pull_outputs'] -= 1
                
            active_srt_streams['active_connections'] = [
                conn for conn in active_srt_streams['active_connections'] 
                if not (conn.get('remote_ip') == event_data.get('remote_ip') and conn.get('remote_port') == event_data.get('remote_port'))
            ]
            
        return jsonify({"status": "success"})
    else:
        response_data = active_srt_streams.copy()
        response_data["bandwidth"] = server_bandwidth
        return jsonify(response_data)

@app.route('/restart', methods=['POST'])
def restart_worker():
    if request.remote_addr not in ALLOWED_IPS:
        return jsonify({'error': 'Forbidden'}), 403
        
    def restart_services():
        time.sleep(1)
        
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmd = ' '.join(proc.info.get('cmdline') or [])
                if 'ffmpeg' in cmd and '/var/www/html/hls/' in cmd:
                    proc.kill()
            except Exception:
                continue

        subprocess.run(['systemctl', 'restart', 'sls'])
        time.sleep(1)
        
        subprocess.run(['systemctl', 'restart', 'worker_agent'])
        
    threading.Thread(target=restart_services, daemon=True).start()
    return jsonify({'status': 'success', 'message': 'Restarting Worker, SLS, and all FFmpeg Streams...'})

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'alive', 'pid': os.getpid(), 'user': 'root'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
