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

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", default="Main")
    args = parser.parse_args()
    
    session_prefix = args.session_id
    MY_INBOX = os.path.join(BASE_DIR, f"brain_inbox_{session_prefix}.txt")
    MY_OUTBOX = os.path.join(BASE_DIR, f"brain_outbox_{session_prefix}.txt")

    print(f"[*] OpenCode Voice Bridge (Session: {session_prefix}) started.", flush=True)
    if os.path.exists(MY_INBOX): os.remove(MY_INBOX)
    if os.path.exists(MY_OUTBOX): os.remove(MY_OUTBOX)

    while True:
        try:
            # We filter tasks by this session_id? 
            # Or the server just gives us any task and we check?
            # Better: Update server to allow polling for a specific session_id
            response = requests.get(f"{SERVER_URL}/agent/next?session_id={session_prefix}", verify=False)
            data = response.json()
            task = data.get("task")
            
            if task:
                task_session_id = task["session_id"]
                device_id = task["device_id"]
                audio_path = task["audio_path"]
                
                # 1. Transcribe
                user_text = run_stt(audio_path)
                print(f"[User @ {device_id}]: {user_text}", flush=True)
                
                # 2. Hand off to OpenCode Agent
                with open(MY_INBOX, "w", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "text": user_text, 
                        "device_id": device_id, 
                        "session_id": task_session_id
                    }))
                
                print(f"[*] Waiting for Agent response for {task_session_id}...", flush=True)
                agent_response_text = ""
                while True:
                    if os.path.exists(MY_OUTBOX):
                        try:
                            with open(MY_OUTBOX, "r", encoding="utf-8") as f:
                                resp_data = json.loads(f.read())
                            if resp_data.get("session_id") == task_session_id:
                                agent_response_text = resp_data.get("text")
                                break
                        except Exception: pass
                    time.sleep(0.5)
                
                if os.path.exists(MY_INBOX): os.remove(MY_INBOX)
                if os.path.exists(MY_OUTBOX): os.remove(MY_OUTBOX)
                
                # 3. Synthesize
                audio_url = run_tts(agent_response_text, task_session_id)
                
                # 4. Post back
                requests.post(f"{SERVER_URL}/agent/respond/{task_session_id}", json={
                    "user_text": user_text,
                    "agent_text": agent_response_text,
                    "audio_url": audio_url,
                    "device_id": device_id
                }, verify=False)
                print(f"[Agent]: {agent_response_text}", flush=True)

                
        except Exception as e:
            print(f"[!] Bridge loop error: {e}", flush=True)
            
        time.sleep(1)

if __name__ == "__main__":
    main()
