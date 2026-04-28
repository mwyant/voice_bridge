# OpenCode Voice Bridge: Agent Interaction Protocol v1.0

This document defines the standard operating procedure for an OpenCode Agent acting as the "Brain" for the Voice Bridge.

## 1. System Requirements
- Services must be launched using `launch_voice.ps1` (detached mode).
- Standard sync directory: `~/.opencode/voice_bridge/`.

## 2. The Communication Loop

### Step A: Passive Monitoring
The Agent should periodically check for the existence of `brain_inbox.txt`.
- **Trigger:** File existence.
- **Action:** Read the UTF-8 text content.

### Step B: Acknowledgment
To prevent the bridge from timing out and to signal the UI that the "Brain" is active:
1. Delete `brain_inbox.txt` immediately after reading.
2. (Optional) Update the server's global state if real-time "typing" indicators are needed.

### Step C: Response Generation
Process the user's text and prepare a JSON payload.
- **Format:** `{"text": "Spoken response", "command": "optional terminal command"}`
- **Write to:** `brain_outbox.txt`

### Step D: Execution Watch
If a `command` was included in Step C, the Agent must monitor for `brain_confirmation.txt`.
- **If detected:** Read the JSON, execute the command, and send a *new* follow-up response to the user confirming the outcome.
- **Cleanup:** Delete `brain_confirmation.txt` after execution.

## 4. Activation
- **Slash Command:** `/voice-bridge-activate`
- **Configuration:** Point the command to `C:\Users\mwyant\.opencode\voice_bridge\launch_voice.ps1`.
- **Logic:** This script handles process cleanup, SSL verification, and detached background execution for both the FastAPI server and the Bridge service.
