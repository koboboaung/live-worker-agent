# MMDP Live Stream Worker (RTMP + SRT)

၁။ အခြေခံ Server Packages များ သွင်းရန်

Nginx Install
```bash
sudo apt update
sudo apt install nginx -y
```

PHP-FPM Install
```bash
sudo apt update
sudo apt install php-fpm php-cli -y
```

Python3 & pip3 Install
```bash
sudo apt update
sudo apt install python3-pip -y
sudo apt install python3-flask python3-flask-cors python3-psutil -y
```

Git Install
```bash
sudo apt update
sudo apt install git -y
```

၂။ Worker Agent (Python API) သွင်းရန် Git Clone
```bash
cd /var/www
git clone https://github.com/koboboaung/live-worker-agent.git worker
```

Service File ဖန်တီးရန်
```bash
cd
cp /var/www/worker/worker_agent.py /var/www/
cp /var/www/worker/worker_agent.service /etc/systemd/system/
```

HLS Folder
```bash
sudo mkdir -p /var/www/html/hls
sudo chown -R www-data:www-data /var/www/html/hls
sudo chmod -R 775 /var/www/html/hls
```

၃။ FFmpeg သွင်းရန်
```bash
sudo apt install ffmpeg -y
```

၄။ Firewall (Port များ ဖွင့်ရန်)
```bash
sudo apt update
apt install ufw -y
apt update && apt install nano -y
```

သင့် Hostname ကို ထည့်သွင်းရန်
echo "127.0.0.1 yourhostname.vm yourhostname" >> /etc/hosts
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 1935/tcp
sudo ufw allow 8888/udp
sudo ufw allow 5000/tcp
sudo ufw enable
sudo ufw status
```

၅။ RTMP Server (Nginx-RTMP) သွင်းရန်
```bash
sudo apt update
sudo apt install libnginx-mod-rtmp -y
sudo systemctl restart nginx
```

Nginx Configuration ပြင်ရန်
```bash
sudo nano /etc/nginx/nginx.conf
```

အောက်ပါ Code ကို ဖိုင်၏ အောက်ဆုံးတွင် ထည့်ပါ - Nginx
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

Nginx Web Site Configuration ပြင်ရန်
```bash
sudo nano /etc/nginx/sites-available/default
```
အောက်ပါအတိုင်း အစားထိုးပါ (PHP Version ကို မိမိသွင်းထားသည့်အတိုင်း ပြင်ပါ ဥပမာ- 8.3)-

Nginx
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
    
    location ~ ^/live/([^/]+)/(.*\.m3u8)$ {
        rewrite ^/live/([^/]+)/(.*\.m3u8)$ /live.php?channel=$1&file=$2 last;
    }

    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/var/run/php/php8.3-fpm.sock; 
    }
}
```


Nginx ကို Restart ချရန်
```bash
sudo systemctl restart nginx
sudo systemctl reload nginx
```

၆။ SRT Server (SLS) သွင်းရန် (NEW)
လိုအပ်သော Build Tools များ သွင်းရန်
```bash
sudo apt update
sudo apt install -y build-essential cmake pkg-config tclsh linux-headers-generic libssl-dev
```

SRT Library Compile လုပ်ရန်
```bash
cd /usr/src
sudo git clone https://github.com/Haivision/srt.git
cd srt
sudo ./configure
sudo make
sudo make install
sudo ldconfig
```

SRT Live Server (SLS) Compile လုပ်ရန်
```bash
cd /usr/src
sudo git clone https://github.com/Edward-Wu/srt-live-server.git
cd srt-live-server
sudo make
```

SLS Configuration ဖန်တီးရန်
```bash
sudo nano /usr/src/srt-live-server/sls.conf
```
အောက်က Code ကို ထည့်ပါ အဟောင်းတွေအားလုံးဖျက် အသစ်ထည့်- Code snippet
```bash
srt {
    worker_threads 1;
    worker_connections 100;
    log_file logs/error.log;
    log_level info;
	record_hls_path_prefix /var/www/html/dvr;
    
    server {
        listen 8888;
        latency 200;
        domain_player playstream;
        domain_publisher pushstream;
        backlog 100;
        idle_streams_timeout 60; #s -1: unlimited
        
        app {
            app_player live;
            app_publisher live;
            record_hls off; #on
			record_hls_segment_duration 10; #unit s
        }
    }
}
```

SLS Service အသစ် ဖန်တီးရန်
```bash
sudo nano /etc/systemd/system/sls.service
```

အောက်ပါ Code ကို ထည့်ပါ-
```bash
[Unit]
Description=SRT Live Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/usr/src/srt-live-server
ExecStart=/usr/src/srt-live-server/bin/sls -c /usr/src/srt-live-server/sls.conf
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

၇။ Service အားလုံးကို Start & Enable လုပ်ရန်
Worker Agent ကို နှိုးရန်
```bash
sudo systemctl daemon-reload
sudo systemctl start worker_agent
sudo systemctl enable worker_agent
sudo systemctl restart worker_agent
```

SRT Server ကို နှိုးရန်
```bash
sudo systemctl start sls
sudo systemctl enable sls
sudo systemctl status sls
sudo systemctl restart sls
```
