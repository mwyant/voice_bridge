import os
import time
import json

# Absolute Paths
BASE_DIR = r"C:\Users\mwyant\.opencode\voice_bridge"
INBOX_FILE = os.path.join(BASE_DIR, "brain_inbox.txt")
OUTBOX_FILE = os.path.join(BASE_DIR, "brain_outbox.txt")
CONFIRM_FILE = os.path.join(BASE_DIR, "brain_confirmation.txt")

def main():
    print("[*] Passive Brain Forwarder active. Waiting for input...")
    
    while True:
        # Check for user speech input
        if os.path.exists(INBOX_FILE):
            with open(INBOX_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                print(f"\n[USER SPEECH DETECTED]: {content}")
                print(">>> PLEASE RESPOND TO THE ABOVE MESSAGE MANUALLY.")
                # We leave the file there so the main agent sees it during a 'sent' or log check
            time.sleep(1)

        # Check for UI button confirmation
        if os.path.exists(CONFIRM_FILE):
            with open(CONFIRM_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                print(f"\n[UI BUTTON CLICKED]: {content}")
                print(">>> USER HAS CLICKED EXECUTE. PLEASE VERIFY AND RUN.")
            time.sleep(1)
            
        time.sleep(0.5)

if __name__ == "__main__":
    main()
