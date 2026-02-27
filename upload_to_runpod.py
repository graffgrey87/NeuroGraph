import subprocess
import base64

with open(r"f:\Neuro_Graph\NeuroGraph\bot.py", "rb") as f:
    b64 = base64.b64encode(f.read()).decode('utf-8')

cmd = ["ssh", "-tt", "-o", "StrictHostKeyChecking=no", "-i", r"C:\Users\Kasutaja\.ssh\id_ed25519", "x63b85f8hsseis-644114b5@ssh.runpod.io"]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
script = f"echo '{b64}' | base64 -d > /workspace/bot.py\nexit\n"
out, err = p.communicate(script.encode('utf-8'))
print("=== OUT ===")
print(out.decode('utf-8', errors='replace'))
print("=== ERR ===")
print(err.decode('utf-8', errors='replace'))
