import os
import psutil
import subprocess
import signal
import sys
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Main server IPs ကိုပဲခွင့်ပြုမယ်
ALLOWED_IPS = ['38.60.244.208', '127.0.0.1']  # ခင်ဗျား Main Server IP ထည့်ပါ

@app.route('/stats', methods=['GET'])
def get_stats():
    active_streams = []
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline and any('ffmpeg' in arg for arg in cmdline):
                cmd_str = " ".join(cmdline)
                if '/var/www/html/hls/' in cmd_str:
                    parts = cmd_str.split('/var/www/html/hls/')
                    if len(parts) > 1:
                        key = parts[1].split('/')[0]
                        if key and key not in active_streams:
                            active_streams.append(key)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return jsonify({
        "cpu_usage": psutil.cpu_percent(),
        "ram_usage": psutil.virtual_memory().percent,
        "active_streams": active_streams
    })

# ============== RESTART API (IP Based) ==============
@app.route('/restart', methods=['POST'])
def restart_worker():
    """Worker agent ကို restart လုပ်မယ် (IP Based)"""
    try:
        # IP စစ်မယ်
        client_ip = request.remote_addr
        if client_ip not in ALLOWED_IPS:
            print(f"Blocked restart attempt from {client_ip}")
            return jsonify({'error': 'Forbidden - IP not allowed'}), 403
        
        # Log ထားမယ်
        print(f"Restart requested from {client_ip}")
        
        # Response အရင်ပြန်ပေးမယ်
        response = jsonify({'status': 'success', 'message': 'Worker is restarting...'})
        
        # Background thread နဲ့ restart လုပ်မယ်
        def delayed_restart():
            import time
            time.sleep(1)  # Response ပြန်ပေးဖို့ 1 sec စောင့်
            print("Restarting worker service...")
            subprocess.run(['systemctl', 'restart', 'worker_agent'])
        
        import threading
        threading.Thread(target=delayed_restart, daemon=True).start()
        
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============== HEALTH CHECK ==============
@app.route('/health', methods=['GET'])
def health_check():
    """Worker အလုပ်လုပ်နေလားစစ်ဆေးမယ်"""
    return jsonify({
        'status': 'alive',
        'pid': os.getpid(),
        'user': 'root'
    })

@app.route('/start', methods=['POST'])
def start_stream():
    data = request.json
    key = data.get('stream_key')
    if not key: return jsonify({"status": "error"}), 400
    subprocess.Popen(["bash", "/var/www/run_transcode.sh", str(key)], 
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return jsonify({"status": "started"})

@app.route('/start_encoder', methods=['POST'])
def start_encoder():
    data = request.json
    key = data.get('stream_key')
    source_url = data.get('source_url', '')
    
    r360 = data.get('res_360', 0)
    r720 = data.get('res_720', 0)
    r1080 = data.get('res_1080', 0)

    output_dir = f"/var/www/html/hls/{key}"
    os.makedirs(output_dir, exist_ok=True)

    cmd = ["ffmpeg", "-re", "-i", source_url]
    map_index = 0
    var_stream_map = []

    if r360:
        cmd += ["-map", "0:v:0", "-map", "0:a:0", f"-s:v:{map_index}", "640x360", f"-b:v:{map_index}", "400k"]
        var_stream_map.append(f"v:{map_index},a:{map_index},name:360p")
        map_index += 1
    
    if r720:
        cmd += ["-map", "0:v:0", "-map", "0:a:0", f"-s:v:{map_index}", "1280x720", f"-b:v:{map_index}", "1500k"]
        var_stream_map.append(f"v:{map_index},a:{map_index},name:720p")
        map_index += 1

    if r1080:
        if source_url.endswith('.m3u8') or "http" in source_url:
            cmd += ["-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy"]
        else:
            cmd += ["-map", "0:v:0", "-map", "0:a:0", f"-s:v:{map_index}", "1920x1080", f"-b:v:{map_index}", "3000k"]
        var_stream_map.append(f"v:{map_index},a:{map_index},name:1080p")
        map_index += 1

    # HLS parameters with timestamp-based segment naming
    hls_options = [
        "-c:v", "libx264", 
        "-preset", "superfast", 
        "-tune", "zerolatency", 
        "-profile:v", "baseline", 
        "-maxrate", "2500k", 
        "-bufsize", "5000k", 
        "-g", "60", 
        "-keyint_min", "60", 
        "-sc_threshold", "0", 
        "-c:a", "aac", "-b:a", "128k", 
        "-f", "hls", 
        "-hls_time", "2", 
        "-hls_list_size", "5", 
        "-hls_flags", "delete_segments+split_by_time",
        "-hls_segment_filename", f"{output_dir}/%v/%s.ts",
        "-hls_segment_type", "mpegts",
        "-master_pl_name", "playlist.m3u8",
         "-strftime", "1"
    ]
    
    if var_stream_map:
        hls_options.extend(["-var_stream_map", " ".join(var_stream_map)])
        hls_options.append(f"{output_dir}/%v/chunks.m3u8")
    else:
        hls_options.append(f"{output_dir}/chunks.m3u8")

    cmd += hls_options
    
    # Log the command for debugging
    print(f"Running FFmpeg: {' '.join(cmd)}")
    
    subprocess.Popen(cmd)
    return jsonify({"status": "started", "key": key})

@app.route('/stop_encoder', methods=['POST'])
def stop_encoder():
    data = request.json
    key = data.get('stream_key')
    if not key: 
        return jsonify({"status": "error", "message": "Stream key required"}), 400
    
    found = False
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline and any('ffmpeg' in arg for arg in cmdline):
                cmd_str = " ".join(cmdline)
                if f"/var/www/html/hls/{key}" in cmd_str or f"live/{key}" in cmd_str:
                    proc.kill()
                    found = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
            
    if found:
        return jsonify({"status": "success", "message": f"Stream {key} stopped"})
    else:
        return jsonify({"status": "error", "message": "Stream not found or already stopped"})
        
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
     # dashboard ကပြောင်းထားတဲ့ port အတိုင်း ဒီနှစ်ခုတူညီရမည်
