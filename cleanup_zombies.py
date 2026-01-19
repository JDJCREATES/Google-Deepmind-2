import subprocess
import os
import sys

print("Starting zombie process cleanup on ports 5200-5300...")
count = 0

for port in range(5200, 5301):
    try:
        # Check port using netstat
        cmd = f'netstat -ano | findstr :{port}'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if not result.stdout:
            continue

        pids = set()
        for line in result.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5:
                # Format: Proto Local Address Foreign Address State PID
                # Check if it actually matches the port string to avoid partial matches (e.g. 5200 matching 15200)
                local_addr = parts[1]
                if f":{port}" in local_addr:
                    pid = parts[-1]
                    if pid.isdigit() and pid != "0":
                        pids.add(pid)
        
        for pid in pids:
            print(f"🔪 Killing PID {pid} on port {port}")
            subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, capture_output=True)
            count += 1
            
    except Exception as e:
        print(f"Error on port {port}: {e}")

print(f"Cleanup complete. Killed {count} processes.")
