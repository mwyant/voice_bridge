import os
import time
import requests
import subprocess
import shutil
import urllib3
import json

# Suppress insecure request warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Paths
TOOLKIT_DIR = r"C:\Users\mwyant\OneDrive\Falstar Publishing Dev\opencode-local-audio-toolkit"
STT_SCRIPT = os.path.join(TOOLKIT_DIR, "stt", "transcribe.py")
TTS_SCRIPT = os.path.join(TOOLKIT_DIR, "tts", "tts_book.py")
VENV_PYTHON = os.path.join(TOOLKIT_DIR, "venv", "Scripts", "python.exe")

SERVER_URL = "https://127.0.0.1:8133"
BASE_DIR = r"C:\Users\mwyant\.opencode\tools\voice_bridge"
RESPONSES_DIR = os.path.join(BASE_DIR, "responses")
INBOX_FILE = os.path.join(BASE_DIR, "brain_inbox.txt")
OUTBOX_FILE = os.path.join(BASE_DIR, "brain_outbox.txt")

def run_stt(audio_path):
    print(f"[*] Running STT on {audio_path}...", flush=True)
    try:
        result = subprocess.run([VENV_PYTHON, STT_SCRIPT, audio_path], capture_output=True, text=True, check=True)
        full_output = result.stdout.strip()
        lines = full_output.split("\n")
        captured_text = []
        for line in lines:
            if line.startswith("[ ") and " -> " in line:
                parts = line.split("]", 1)
                if len(parts) > 1:
                    captured_text.append(parts[1].strip())
        if not captured_text:
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
    except Exception as e:
        print(f"[!] STT Error: {e}", flush=True)
        return "Error transcribing audio."

def run_tts(text, session_id):
    print(f"[*] Running TTS for session {session_id}...", flush=True)
    temp_md = os.path.join(RESPONSES_DIR, f"{session_id}.md")
    with open(temp_md, "w", encoding="utf-8") as f:
        f.write(text)
    try:
        subprocess.run([VENV_PYTHON, TTS_SCRIPT, temp_md], check=True)
        output_folder = os.path.join(TOOLKIT_DIR, "output_audio", session_id)
        if os.path.exists(output_folder):
            for f in os.listdir(output_folder):
                if f.endswith(".wav"):
                    src = os.path.join(output_folder, f)
                    dst = os.path.join(RESPONSES_DIR, f"{session_id}.wav")
                    shutil.copy(src, dst)
                    return f"/responses/{session_id}.wav"
    except Exception as e:
        print(f"[!] TTS Error: {e}", flush=True)
    return None

def main():
    print("[*] OpenCode Voice Bridge (Alpha Mode) started.", flush=True)
    if os.path.exists(INBOX_FILE): os.remove(INBOX_FILE)
    if os.path.exists(OUTBOX_FILE): os.remove(OUTBOX_FILE)

    while True:
        try:
            response = requests.get(f"{SERVER_URL}/agent/next", verify=False)
            data = response.json()
            task = data.get("task")
            
            if task:
                session_id = task["session_id"]
                audio_path = task["audio_path"]
                
                # 1. Transcribe
                user_text = run_stt(audio_path)
                print(f"[User]: {user_text}", flush=True)
                
                # 2. Hand off to OpenCode Agent
                with open(INBOX_FILE, "w", encoding="utf-8") as f:
                    f.write(user_text)
                
                print(f"[*] Waiting for Agent response...", flush=True)
                agent_response_text = ""
                while not os.path.exists(OUTBOX_FILE):
                    time.sleep(0.5)
                
                with open(OUTBOX_FILE, "r", encoding="utf-8") as f:
                    agent_response_text = f.read()
                
                if os.path.exists(INBOX_FILE): os.remove(INBOX_FILE)
                if os.path.exists(OUTBOX_FILE): os.remove(OUTBOX_FILE)
                
                # 3. Synthesize
                audio_url = run_tts(agent_response_text, session_id)
                
                # 4. Post back
                try:
                    agent_data = json.loads(agent_response_text)
                    agent_text = agent_data.get("text", agent_response_text)
                    command = agent_data.get("command")
                except Exception:
                    agent_text = agent_response_text
                    command = None

                requests.post(f"{SERVER_URL}/agent/respond/{session_id}", json={
                    "user_text": user_text,
                    "agent_text": agent_text,
                    "audio_url": audio_url,
                    "command": command
                }, verify=False)
                print(f"[Agent]: {agent_text}", flush=True)
                
        except Exception as e:
            print(f"[!] Bridge loop error: {e}", flush=True)
            
        time.sleep(1)

if __name__ == "__main__":
    main()
