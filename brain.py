import os
import time
import json
import requests

# Path configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INBOX_FILE = os.path.join(BASE_DIR, "brain_inbox.txt")
OUTBOX_FILE = os.path.join(BASE_DIR, "brain_outbox.txt")

# Persona / Context
SYSTEM_PROMPT = """You are a Senior Software Architect & UI/UX Specialist acting as the 'Brain' for the OpenCode Voice Bridge.
You are helping an engineer refine a local-first AI voice chat system.
Your responses should be technical, insightful, and concise.
If the user asks for actions, you can include a 'command' field in your JSON response to propose a shell command.
"""

def main():
    print(f"[*] Brain service started. Monitoring: {INBOX_FILE}")
    
    while True:
        if os.path.exists(INBOX_FILE):
            try:
                with open(INBOX_FILE, "r", encoding="utf-8") as f:
                    user_text = f.read().strip()
                
                if not user_text:
                    time.sleep(0.5)
                    continue

                print(f"[User Speech]: {user_text}")
                
                # We'll use a placeholder for now, but we want this to be intelligent.
                # In a real scenario, this script would call an LLM API or use a subagent.
                # Since we want to be the brain, we'll let the subagent handle it for now, 
                # but with better instructions.
                
                # For this specific prototype, we'll write a "thinking" message 
                # and let the subagent overwrite it if it can.
                # Actually, the most robust way is to have the subagent be this script.
                
                # Since I am the main agent, I will respond to the user's messages 
                # by monitoring the bridge logs and then telling the user what I did.
                # Wait, the user wants it to be autonomous.
                
                # Let's keep it simple: this script waits for input and then 
                # we'll use a subagent to provide the response.
                
            except Exception as e:
                print(f"[!] Brain error: {e}")
        
        time.sleep(1)

if __name__ == "__main__":
    main()
