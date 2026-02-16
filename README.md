# Nginx install
```bash
sudo apt update
sudo apt install nginx -y
```

# pip3 သွင်းရန်
```bash
sudo apt update
sudo apt install python3-pip -y
pip3 --version
pip3 install flask flask-cors psutil
```

# git clone
```bash
cd /var/www
git clone https://github.com/koboboaung/live-worker-agent.git worker
```

# service file
```bash
cp /var/www/worker/worker_agent.py /var/www/
cp /var/www/worker/worker_agent.service /etc/systemd/system/
```

# ffmpeg install
```bash
sudo apt install ffmpeg
```

# run worker vps
```bash
  systemctl 
  sudo systemctl daemon-reload
  sudo systemctl start worker_agent
  systemctl start worker_agent
```

# port open
```bash
sudo ufw allow 5000/tcp
sudo ufw status
```
