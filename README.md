# Nginx install
```bash
sudo apt update
sudo apt install nginx -y
```

# Worker VPS အသစ် git clone
```bash
cd /var/www
git clone https://github.com/koboboaung/live-worker-agent.git worker
```

service file
```bash
cp /var/www/worker/worker_agent.service /etc/systemd/system/
```
(ဒီမှာ paste လုပ်)

```bash
  systemctl 
  daemon-reload
  systemctl enable worker_agent
  systemctl start worker_agent
```
