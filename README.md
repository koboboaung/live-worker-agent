# MMDP live stream worker

Nginx install
```bash
sudo apt update
sudo apt install nginx -y
```

pip3 သွင်းရန်
```bash
sudo apt update
sudo apt install python3-pip -y
pip3 --version
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

ffmpeg install
```bash
sudo apt install ffmpeg
```

# port open
```bash
apt update
apt install ufw -y
sudo ufw allow 5000/tcp
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
```bash
sudo systemctl restart nginx
sudo systemctl reload nginx
```
run worker vps
```bash
  systemctl 
  sudo systemctl daemon-reload
  sudo systemctl start worker_agent
  systemctl start worker_agent
```

auto start worker (vps reboot)
```bash
sudo systemctl enable worker_agent
```
