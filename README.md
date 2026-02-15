Worker VPS အသစ် git clone
```bash
cd /var/www
git clone https://github.com/koboboaung/live-worker-agent.git worker
```

ပြီးမှ service file ကိုကိုယ်တိုင်ထည့်
```bash
  nano /etc/systemd/system/worker_agent.service
```
(ဒီမှာ paste လုပ်)

```bash
  systemctl 
  daemon-reload
  systemctl enable worker_agent
  systemctl start worker_agent
```
