# 🚀 MMDP Live Stream Worker Setup (Updated 2026)

This documentation provides a step-by-step guide to setting up a Live Stream Worker with Tracking and Proxy capabilities.

---

## 1. Prerequisites (Nginx & PHP)
Install the core web server and PHP components:
```bash
sudo apt update
sudo apt install nginx php-fpm php-cli libnginx-mod-rtmp ffmpeg git -y
```
## 2. Python & Worker Agent Setup
Install Python dependencies and clone the worker repository:
```bash
sudo apt install python3-pip -y
pip3 install flask flask-cors psutil

cd /var/www
sudo git clone [https://github.com/koboboaung/live-worker-agent.git](https://github.com/koboboaung/live-worker-agent.git) worker
```

## 3. Service Configuration
Set up the worker agent to run as a system service:
```bash
sudo cp /var/www/worker/worker_agent.py /var/www/
sudo cp /var/www/worker/worker_agent.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable worker_agent
sudo systemctl start worker_agent
```

## 4. Tracking System (Folder & Permissions)
This setup is crucial for real-time CCU tracking:
```bash
Bash
# Create tracking folder
sudo mkdir -p /var/www/html/tmp/tracking

# Copy PHP Logic files to web root
sudo cp /var/www/worker/live.php /var/www/html/
sudo cp /var/www/worker/get_viewers.php /var/www/html/

# Set ownership and permissions
sudo chown -R www-data:www-data /var/www/html/tmp/tracking
sudo chmod -R 775 /var/www/html/tmp/tracking
```

## 5. Firewall Configuration
Open necessary ports for RTMP, Web, and Flask:
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 1935/tcp
sudo ufw allow 5000/tcp
sudo ufw --force enable
```

## 6. Nginx Configuration
RTMP Setup
Add the following block to the end of /etc/nginx/nginx.conf:
```bash
rtmp {
    server {
        listen 1935;
        chunk_size 4096;
        application live {
            live on;
            record off;
        }
    }
}
```
Virtual Host Setup
Replace the content of /etc/nginx/sites-available/default with:
```bash

server {
    listen 80 default_server;
    listen [::]:80 default_server;

    root /var/www/html;
    index index.php index.html index.htm index.nginx-debian.html;
    server_name _;

    location / {
        try_files $uri $uri/ =404;
    }

    # Tracking Proxy Rule
    location ~ ^/live/([^/]+)/(.*\.m3u8)$ {
        rewrite ^/live/([^/]+)/(.*\.m3u8)$ /live.php?channel=$1&file=$2 last;
    }

    # PHP-FPM Connection
    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        # Note: Match your PHP version (e.g., php8.1, php8.3)
        fastcgi_pass unix:/var/run/php/php8.1-fpm.sock;
    }
}
```

## 7. Finalize and Restart
```bash
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl restart worker_agent
```

📊 Useful API Endpoints
View CCU API Info:
https://live.mmstreaming.com/ccu_api.php?channel=mychannel

Stream URL: 
https://live.mmstreaming.com/live/mychannel/playlist.m3u8

🛠 Troubleshooting
Check Logs: tail -f /var/log/nginx/error.log

Verify PHP Socket: ls /var/run/php/ (Update Nginx config if the version differs)

Worker Status: sudo systemctl status worker_agent
