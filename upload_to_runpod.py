import subprocess
import base64

files = {
    r"f:\Neuro_Graph\NeuroGraph\bot.py": "/workspace/bot.py",
    r"f:\Neuro_Graph\NeuroGraph\webapp_server.py": "/workspace/webapp_server.py",
    r"f:\Neuro_Graph\NeuroGraph\templates\status.html": "/workspace/templates/status.html"
}

cmd = ["ssh", "-tt", "-o", "StrictHostKeyChecking=no", "-i", r"C:\Users\Kasutaja\.ssh\id_ed25519", "x63b85f8hsseis-644114b5@ssh.runpod.io"]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

script = "mkdir -p /workspace/templates\n"
for local_path, remote_path in files.items():
    with open(local_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')
    script += f"echo '{b64}' | base64 -d > {remote_path}\n"

script += "pkill -f webapp_server.py; nohup python3 /workspace/webapp_server.py > /workspace/webapp.log 2>&1 &\n"
script += "pkill -9 -f bot.py; rm -f /tmp/bot.sock; nohup python3 /workspace/bot.py > /workspace/bot.log 2>&1 &\n"
script += "exit\n"

out, err = p.communicate(script.encode('utf-8'))
print("=== OUT ===")
print(out.decode('utf-8', errors='replace'))
print("=== ERR ===")
print(err.decode('utf-8', errors='replace'))
