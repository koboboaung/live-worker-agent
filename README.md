Worker VPS အသစ် git clone
  # cd /var/www
  # git clone https://github.com/koboboaung/live-worker-agent.git worker

ပြီးမှ service file ကိုကိုယ်တိုင်ထည့်
  # nano /etc/systemd/system/worker_agent.service
(ဒီမှာ paste လုပ်)

  # systemctl 
  # daemon-reload
  # systemctl enable worker_agent
  # systemctl start worker_agent
