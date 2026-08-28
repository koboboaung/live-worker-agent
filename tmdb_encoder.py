import datetime
import os
import subprocess
import shutil
import threading
import time
import requests
import boto3
import secrets
import math
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ALLOWED_IPS = ['127.0.0.1', '146.190.90.223', '10.104.0.7'] # Allow your CMS IP
TMP_DIR = "/tmp/ffmpeg_tmdb"

def process_tmdb_encode(job_id, filename, user_id, download_url, webhook_url, s3_config):
    basename = os.path.splitext(filename)[0]
    user_dir = f"{TMP_DIR}/{user_id}"
    out_dir = f"{user_dir}/{basename}"
    key_dir = f"{out_dir}/key"
    input_file = f"{user_dir}/{filename}"
    
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(key_dir, exist_ok=True)

    try:
        # 1. Download MP4 from CMS Server
        print(f"[{job_id}] Downloading {filename} from CMS...")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        with requests.get(download_url, headers=headers, stream=True) as r:
            r.raise_for_status()
            with open(input_file, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        # Get (Bytes)
        file_size = os.path.getsize(input_file) if os.path.exists(input_file) else 0

        # 2. Generate AES-128 Key & Key Info
        print(f"[{job_id}] Generating AES keys...")
        random_key = secrets.token_bytes(16)
        key_file_path = f"{key_dir}/video.key"
        with open(key_file_path, 'wb') as f:
            f.write(random_key)
        
        key_url_for_player = "key/video.key"
        key_info_path = f"{out_dir}/video.keyinfo"
        with open(key_info_path, 'w') as f:
            f.write(f"{key_url_for_player}\n{key_file_path}\n")

        # 3. Generate Thumbnails & VTT
        print(f"[{job_id}] Generating VTT and Thumbnails...")
        duration_cmd = f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 '{input_file}'"
        duration_str = subprocess.check_output(duration_cmd, shell=True).decode().strip()
        duration = float(duration_str) if duration_str else 0

        if duration > 0:
            thumb_count = 100
            interval = duration / thumb_count
            
            thumb_cmd = f"ffmpeg -y -i '{input_file}' -vf 'fps=1/{interval},scale=160:90,tile=10x10' -frames:v 1 '{out_dir}/thumbnails.jpg'"
            subprocess.run(thumb_cmd, shell=True)

            vtt_file = f"{out_dir}/thumbnails.vtt"
            with open(vtt_file, "w") as f:
                f.write("WEBVTT\n")
                counter = 0
                for i in range(thumb_count):
                    start = time.strftime('%H:%M:%S.000', time.gmtime(counter))
                    counter += interval
                    end = time.strftime('%H:%M:%S.000', time.gmtime(counter))
                    x = (i % 10) * 160
                    y = math.floor(i / 10) * 90
                    f.write(f"\n{start} --> {end}\nthumbnails.jpg#xywh={x},{y},160,90\n")

        # 4. HLS Encode (Using -c copy just like your PHP cron to keep it fast)
        print(f"[{job_id}] Encoding HLS...")
        hls_cmd = [
            "ffmpeg", "-y", "-i", input_file,
            "-c", "copy", "-f", "hls", "-hls_time", "5", 
            "-hls_segment_type", "mpegts", "-hls_playlist_type", "vod",
            "-hls_segment_filename", f"{out_dir}/segment_%03d.ts",
            "-hls_key_info_file", key_info_path,
            "-nostats", f"{out_dir}/playlist.m3u8"
        ]
        hls_process = subprocess.run(hls_cmd, capture_output=True, text=True)
        if hls_process.returncode != 0:
            raise Exception("FFmpeg HLS failed.")

        # 5. Upload to S3 (Boto3 integration)
        print(f"[{job_id}] Uploading to S3...")
        s3_client = boto3.client('s3',
            region_name=s3_config['region'],
            endpoint_url=s3_config['endpoint'],
            aws_access_key_id=s3_config['access_key'],
            aws_secret_access_key=s3_config['secret_key']
        )
        
        day_date = time.strftime('%Y/%m/%d')
        
        # Upload HLS Files
        hls_dest_folder = f"{s3_config['main_folder']}/{user_id}/{s3_config['hls_folder']}/{day_date}/{basename}"
        for root, dirs, files in os.walk(out_dir):
            for file in files:
                if file.endswith('.keyinfo'): 
                    continue 
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, out_dir) 
                s3_path = f"{hls_dest_folder}/{relative_path}"
                s3_client.upload_file(local_path, s3_config['bucket_hls'], s3_path, ExtraArgs={'ContentType': 'video/MP2T' if file.endswith('.ts') else 'application/x-mpegURL'})

        # Upload MP4 Original File
        mp4_dest_path = f"{s3_config['main_folder']}/{user_id}/{s3_config['mp4_folder']}/{day_date}/{filename}"
        s3_client.upload_file(input_file, s3_config['bucket_mp4'], mp4_dest_path, ExtraArgs={
            'ContentType': 'application/octet-stream',
            'ContentDisposition': f'attachment; filename={filename}'
        })

        # 6. Webhook Callback to CMS
        requests.post(webhook_url, json={
            "job_id": job_id, 
            "status": "completed",
            "file_size": file_size
        })
        print(f"[{job_id}] Job Completed Successfully.")

    except Exception as e:
        print(f"[{job_id}] Error: {str(e)}")
        requests.post(webhook_url, json={"job_id": job_id, "status": "error", "message": str(e)})
        
    finally:
        # Cleanup
        if os.path.exists(input_file):
            os.remove(input_file)
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir, ignore_errors=True)

is_encoding_in_progress = False
encode_lock = threading.Lock()

@app.route('/start_tmdb_encode', methods=['POST'])
def start_tmdb_encode():
    global is_encoding_in_progress
    
    with encode_lock:
        if is_encoding_in_progress:
            return jsonify({"status": "error", "message": "Encoder is busy with another job."}), 429
        is_encoding_in_progress = True

    data = request.json
    job_id = data.get('job_id')
    filename = data.get('filename')
    user_id = data.get('user_id')
    download_url = data.get('download_url')
    webhook_url = data.get('webhook_url')
    s3_config = data.get('s3_config')

    if not all([job_id, filename, user_id, download_url, webhook_url, s3_config]):
        with encode_lock:
            is_encoding_in_progress = False
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    def background_worker():
        global is_encoding_in_progress
        try:
            process_tmdb_encode(job_id, filename, user_id, download_url, webhook_url, s3_config)
        finally:
            with encode_lock:
                is_encoding_in_progress = False

    thread = threading.Thread(target=background_worker, daemon=True)
    thread.start()
    
    return jsonify({"status": "queued", "message": "Encoding started."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
