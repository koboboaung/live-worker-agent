# MMDP live stream worker

Nginx install
```bash
sudo apt update
sudo apt install nginx -y
```

PHP-FPM install
```bash
sudo apt update
sudo apt install php-fpm php-cli -y
```

pip3 သွင်းရန်
```bash
sudo apt update
sudo apt install python3-pip -y
pip3 install flask flask-cors psutil
```

git clone
```bash
sudo apt update
sudo apt install git
cd /var/www
git clone https://github.com/koboboaung/live-worker-agent.git worker
```

service file
```bash
cd
cp /var/www/worker/worker_agent.py /var/www/
cp /var/www/worker/worker_agent.service /etc/systemd/system/
```

API Track Folder
```bash
sudo chown -R www-data:www-data /var/www/html/tmp/tracking
sudo chmod -R 775 /var/www/html/tmp/tracking
```

ffmpeg install
```bash
sudo apt install ffmpeg
```

# port open
```bash
sudo apt update
apt install ufw -y
apt update && apt install nano -y
echo "127.0.0.1 yourhostname.vm yourhostname" >> /etc/hosts
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 1935/tcp
sudo ufw allow 5000/tcp
sudo ufw enable
sudo ufw status
```

rtmp install
```bash
sudo apt update
sudo apt install libnginx-mod-rtmp
sudo systemctl restart nginx

sudo nano /etc/nginx/nginx.conf
```

```
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
/etc/nginx/sites-available/default
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
        
        # သတိပြုရန် - သင့်စက်မှာ သွင်းထားတဲ့ PHP version ကိုက်ညီဖို့ လိုပါမယ် (ဥပမာ php8.1, php7.4 စသဖြင့်)
        fastcgi_pass unix:/var/run/php/php8.1-fpm.sock; 
    }
}


```

```bash
sudo systemctl restart nginx
sudo systemctl reload nginx
```
run worker vps
```bash
systemctl 
sudo systemctl daemon-reload
sudo systemctl start worker_agent
sudo systemctl restart worker_agent
```

auto start worker (vps reboot)
```bash
sudo systemctl enable worker_agent
```
