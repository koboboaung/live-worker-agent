channel/
	├── 360p/
	│   ├── index.m3u8
	│   └── segment_001.ts
	├── 720p/
	│   ├── index.m3u8
	│   └── segment_001.ts
	├── 1080p/
	│   ├── index.m3u8
	│   └── segment_001.ts
	└── master.m3u8
	
	# Worker VPS အသစ် git clone
cd /var/www
git clone https://github.com/koboboaung/live-worker-agent.git worker

# ပြီးမှ service file ကိုကိုယ်တိုင်ထည့်
nano /etc/systemd/system/worker_agent.service
# (ဒီမှာ paste လုပ်)

systemctl 
daemon-reload
systemctl enable worker_agent
systemctl start worker_agent