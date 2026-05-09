# 🚀 MMDP Live Stream Worker Setup (Updated 2026)

This documentation provides a step-by-step guide to setting up a Live Stream Worker with Tracking and Proxy capabilities.

---

## 1. Prerequisites (Nginx & PHP)
Install the core web server and PHP components:
```bash
sudo apt update
sudo apt install nginx php-fpm php-cli libnginx-mod-rtmp ffmpeg git -y

sudo apt install python3-pip -y
pip3 install flask flask-cors psutil

cd /var/www
sudo git clone [https://github.com/koboboaung/live-worker-agent.git](https://github.com/koboboaung/live-worker-agent.git) worker
