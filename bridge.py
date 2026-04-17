import os
import time
import requests
import subprocess
import shutil
import urllib3
import json
import sys

# Suppress insecure request warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration - Adjust these to your local paths
TOOLKIT_DIR = r"C:\Users\mwyant\OneDrive\Falstar Publishing Dev\opencode-local-audio-toolkit"
STT_SCRIPT = os.path.join(TOOLKIT_DIR, "stt", "transcribe.py")
TTS_SCRIPT = os.path.join(TOOLKIT_DIR, "tts", "tts_book.py")
VENV_PYTHON = os.path.join(TOOLKIT_DIR, "venv", "Scripts", "python.exe")

SERVER_URL = "https://127.0.0.1:8133"
# The Agent sync files - Prioritizing ~/.opencode
USER_HOME = os.path.expanduser("~")
BASE_SYNC_DIR = os.path.join(USER_HOME, ".opencode", "voice_bridge")
if not os.path.exists(BASE_SYNC_DIR):
    # Fallback to current directory if .opencode doesn't exist yet
    BASE_SYNC_DIR = os.path.dirname(os.path.abspath(__file__))

INBOX_FILE = os.path.join(BASE_SYNC_DIR, "brain_inbox.txt")
OUTBOX_FILE = os.path.join(BASE_SYNC_DIR, "brain_outbox.txt")

# Where to put audio responses for the server to serve
RESPONSES_DIR = os.path.join(BASE_SYNC_DIR, "responses")

os.makedirs(BASE_SYNC_DIR, exist_ok=True)
os.makedirs(RESPONSES_DIR, exist_ok=True)

def run_stt(audio_path):
    print(f"[*] Running STT on {audio_path}...", flush=True)
    try:
        # Using a timeout to prevent infinite hangs
        result = subprocess.run([VENV_PYTHON, STT_SCRIPT, audio_path], capture_output=True, text=True, check=True, timeout=60)
        full_output = result.stdout.strip()
        lines = full_output.split("\n")
        captured_text = []
        
        # Parse the specific output format of the toolkit
        for line in lines:
            if line.startswith("[ ") and " -> " in line:
                parts = line.split("]", 1)
                if len(parts) > 1:
                    captured_text.append(parts[1].strip())
        
        if not captured_text:
            # Fallback parsing
            dash_count = 0
            for line in lines:
                if "---" in line:
                    dash_count += 1
                    continue
                if dash_count == 2:
                    if line.strip() and not line.startswith("Transcription finished"):
                        captured_text.append(line.strip())
        
        final_text = " ".join(captured_text) if captured_text else "No speech detected."
        return final_text
    except subprocess.TimeoutExpired:
        print("[!] STT Timed out", flush=True)
        return "Transcription timed out."
    except Exception as e:
        print(f"[!] STT Error: {e}", flush=True)
        return "Error transcribing audio."

def run_tts(text, task_id):
    print(f"[*] Running TTS for task {task_id}...", flush=True)
    # The toolkit expects a markdown file
    temp_md = os.path.join(RESPONSES_DIR, f"{task_id}.md")
    with open(temp_md, "w", encoding="utf-8") as f:
        f.write(text)
    
    try:
        subprocess.run([VENV_PYTHON, TTS_SCRIPT, temp_md], check=True, timeout=120)
        # The toolkit saves to a specific output folder structure
        output_folder = os.path.join(TOOLKIT_DIR, "output_audio", task_id)
        if os.path.exists(output_folder):
            for f in os.listdir(output_folder):
                if f.endswith(".wav"):
                    src = os.path.join(output_folder, f)
                    dst = os.path.join(RESPONSES_DIR, f"{task_id}.wav")
                    shutil.copy(src, dst)
                    return f"/responses/{task_id}.wav"
    except Exception as e:
        print(f"[!] TTS Error: {e}", flush=True)
    return None

def main():
    print("[*] OpenCode Voice Bridge (Robust Mode) started.", flush=True)
    print(f"[*] Monitoring Server: {SERVER_URL}", flush=True)
    print(f"[*] Agent Sync Dir: {BASE_SYNC_DIR}", flush=True)

    # Cleanup any stale sync files
    if os.path.exists(INBOX_FILE): os.remove(INBOX_FILE)
    if os.path.exists(OUTBOX_FILE): os.remove(OUTBOX_FILE)

    while True:
        try:
            # 1. Poll for next task
            response = requests.get(f"{SERVER_URL}/agent/next", verify=False, timeout=5)
            data = response.json()
            task = data.get("task")
            
            if task:
                task_id = task["task_id"]
                audio_path = task["audio_path"]
                
                # 2. STT
                user_text = run_stt(audio_path)
                print(f"[User]: {user_text}", flush=True)
                
                # 3. Hand off to OpenCode Agent via File Sync
                # This is the "Listener" part - writing to the agent's inbox
                with open(INBOX_FILE, "w", encoding="utf-8") as f:
                    f.write(user_text)
                
                print(f"[*] Sent to Agent. Waiting for response...", flush=True)
                
                # Non-blocking wait (with timeout and abort check)
                agent_response_raw = ""
                wait_start = time.time()
                timeout = 120 # 2 minutes max for agent to think
                
                # Path for abort signal
                ABORT_SIGNAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "abort_signal.txt")
                if os.path.exists(ABORT_SIGNAL): os.remove(ABORT_SIGNAL)

                while not os.path.exists(OUTBOX_FILE):
                    if os.path.exists(ABORT_SIGNAL):
                        print("[!] Abort signal received.", flush=True)
                        os.remove(ABORT_SIGNAL)
                        agent_response_raw = "Task aborted by user."
                        break
                    if time.time() - wait_start > timeout:
                        agent_response_raw = "Agent timed out."
                        break
                    time.sleep(0.5)
                
                if not agent_response_raw and os.path.exists(OUTBOX_FILE):
                    with open(OUTBOX_FILE, "r", encoding="utf-8") as f:
                        agent_response_raw = f.read()
                
                # Cleanup sync files immediately
                if os.path.exists(INBOX_FILE): os.remove(INBOX_FILE)
                if os.path.exists(OUTBOX_FILE): os.remove(OUTBOX_FILE)
                
                # 4. Parse Agent Response
                # Agent might return JSON with "text" and "command"
                try:
                    agent_data = json.loads(agent_response_raw)
                    agent_text = agent_data.get("text", agent_response_raw)
                    command = agent_data.get("command")
                except Exception:
                    agent_text = agent_response_raw
                    command = None

                if not agent_text or agent_text.strip() == "":
                    agent_text = "I received your message but didn't have a specific response prepared."

                # 5. TTS
                audio_url = run_tts(agent_text, task_id)
                
                # 6. Post back to Server
                # v0.0.9: Explicit error handling for response posting
                try:
                    resp = requests.post(f"{SERVER_URL}/agent/respond/{task_id}", json={
                        "user_text": user_text,
                        "agent_text": agent_text,
                        "audio_url": audio_url,
                        "command": command
                    }, verify=False, timeout=10)
                    if resp.status_code == 200:
                        print(f"[*] Response posted successfully for {task_id}", flush=True)
                    else:
                        print(f"[!] Server returned {resp.status_code}: {resp.text}", flush=True)
                except Exception as e:
                    print(f"[!] Failed to post response: {e}", flush=True)
                
                print(f"[Agent]: {agent_text}", flush=True)
                if command:
                    print(f"[Command]: {command}", flush=True)
                
        except requests.exceptions.ConnectionError:
            print("[!] Cannot connect to server. Retrying in 5s...", flush=True)
            time.sleep(5)
        except Exception as e:
            print(f"[!] Bridge error: {e}", flush=True)
            time.sleep(1)
            
        time.sleep(0.5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[*] Bridge stopped by user.", flush=True)
        sys.exit(0)
