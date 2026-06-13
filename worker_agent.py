import os, psutil, subprocess, shutil
import threading, time
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ALLOWED_IPS = ['38.60.244.208']

# ==========================================
# ဤ Function သည် FFmpeg ထုတ်ပေးသော playlist.m3u8 ကို စောင့်ဖတ်ပြီး
# FRAME-RATE=25 ကို အလိုအလျောက် ဝင်ရေးပေးမည်ဖြစ်ပါသည်။
# ==========================================
def patch_m3u8(filepath):
    # Master playlist ဖိုင်ထွက်လာဖို့ ၁၅ စက္ကန့်ခန့် စောင့်မည်
    for _ in range(15):
        if os.path.exists(filepath):
            time.sleep(2)  # ဖိုင်အပြည့်အစုံ ရေးပြီးသည်အထိ ၂ စက္ကန့် ထပ်စောင့်ပါမည်
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                
                # FRAME-RATE မပါသေးဘူးဆိုရင် အတင်းဝင်ထည့်ပါမည်
                if 'FRAME-RATE' not in content:
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if line.startswith('#EXT-X-STREAM-INF:'):
                            lines[i] = line + ',FRAME-RATE=25'
                    
                    with open(filepath, 'w') as f:
                        f.write('\n'.join(lines))
            except Exception as e:
                pass
            break
        time.sleep(1)

@app.route('/stats', methods=['GET'])
def get_stats():
    active = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd_list = proc.info.get('cmdline')
            if cmd_list:
                cmd_str = ' '.join(cmd_list)
                
                # ffmpeg process ဖြစ်ပြီး /var/www/html/hls/ လမ်းကြောင်း ပါဝင်လျှင်
                if 'ffmpeg' in cmd_str and '/var/www/html/hls/' in cmd_str:
                    
                    # /var/www/html/hls/ ပြီးနောက်လာသော key ကို ဖြတ်ယူခြင်း
                    parts = cmd_str.split('/var/www/html/hls/')
                    if len(parts) > 1:
                        key = parts[1].split('/')[0]
                        if key and key not in active:
                            active.append(key)
        except: 
            continue
            
    return jsonify({
        "cpu_usage": psutil.cpu_percent(),
        "ram_usage": psutil.virtual_memory().percent,
        "active_streams": active
    })

@app.route('/restart', methods=['POST'])
def restart_worker():
    if request.remote_addr not in ALLOWED_IPS:
        return jsonify({'error': 'Forbidden'}), 403
    
    threading.Thread(target=lambda: (time.sleep(1), subprocess.run(['systemctl', 'restart', 'worker_agent'])), daemon=True).start()
    return jsonify({'status': 'success', 'message': 'Worker is restarting...'})

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'alive', 'pid': os.getpid(), 'user': 'root'})

@app.route('/start_encoder', methods=['POST'])
def start_encoder():
    data = request.json
    key, src = data.get('stream_key'), data.get('source_url')
    source_type = data.get('source_type', 'rtmp') # RTMP လား SRT လား ခွဲခြားရန်
    
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
            f"-profile:v:{i}", "baseline",
            f"-r:v:{i}", "25",
        ]) 
        var_map.append(f"v:{i},a:{i},name:{c['name']}")
        
    # Input Command စီစဉ်ခြင်း (-re ကို RTMP အတွက်သာ သုံးမည်)
    cmd = ["ffmpeg", "-y"]
    if source_type == 'rtmp':
        cmd.append("-re")
        
    cmd.extend(["-i", src, "-filter_complex", ";".join(filt), *map_v, *map_a,
           "-preset", "superfast", "-tune", "zerolatency", "-g", "100", "-keyint_min", "100", "-sc_threshold", "0",
           "-c:a", "aac", "-b:a", "128k", "-ac", "2", *enc,
           "-f", "hls", "-hls_time", "4", "-hls_list_size", "6", "-hls_flags", "delete_segments+split_by_time+independent_segments",
           "-hls_segment_type", "mpegts", "-vtag", "avc1", "-hls_segment_filename", f"{out_dir}/%v/%s.ts", "-strftime", "1",
           "-var_stream_map", " ".join(var_map), "-master_pl_name", "playlist.m3u8", f"{out_dir}/%v/chunks.m3u8"])
    
    try:
        subprocess.Popen(
            cmd, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL, 
            stdin=subprocess.DEVNULL, 
            close_fds=True
        )
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
        except: continue
    
    shutil.rmtree(f"/var/www/html/hls/{key}", ignore_errors=True)
    return jsonify({"status": "success", "message": f"Stream {key} stopped"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
