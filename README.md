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

#  ufw status စစ်ပါ မရှိရင်

apt update && apt install nano -y
echo "127.0.0.1 vpsname.vm vpsname" >> /etc/hosts

sudo ufw enable
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 1935/tcp
sudo ufw allow 5000/tcp
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
systemctl restart worker_agent
```

auto start worker (vps reboot)
```bash
sudo systemctl enable worker_agent
```
