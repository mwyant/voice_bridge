# OpenCode Voice Bridge

A robust, multi-device, local-first voice chat system for OpenCode.

## Features
- **Local STT/TTS:** Powered by `distil-whisper` and `Kokoro-82M`.
- **Real-Time Sync:** Multi-device synchronization via WebSockets.
- **Persistent Memory:** Conversation history stored in a local SQLite database.
- **Secure:** LAN access secured with SSL and passcode protection.
- **Non-Blocking:** Asynchronous listener pattern to prevent UI hangs.

## Deployment Workflow
The system is split into a development environment and a production deployment in the OpenCode profile.

### 1. Development
Location: `C:\Users\mwyant\OneDrive\TBD-Reusegineers\voice_bridge`
- Make changes in the `feature/robust-multi-device` branch.
- Push to GitHub: `git push origin feature/robust-multi-device`

### 2. Production Sync
Location: `C:\Users\mwyant\.opencode\tools\voice_bridge`
- To update the local toolkit from GitHub, run the sync script:
```powershell
& "C:\Users\mwyant\.opencode\tools\voice_bridge\sync_from_github.ps1"
```

## Launching the Bridge
To start the server and bridge in any OpenCode session:
```powershell
& "C:\Users\mwyant\.opencode\tools\voice_bridge\launch_voice.ps1"
```

## Monitoring for Voice Commands
Models should use the following pattern to listen for input:
```powershell
$voiceDir = "C:\Users\mwyant\.opencode\tools\voice_bridge"
$inbox = Join-Path $voiceDir "brain_inbox.txt"
$confirm = Join-Path $voiceDir "brain_confirmation.txt"

while ($true) {
    if (Test-Path $confirm) {
        Get-Content $confirm -Raw | Remove-Item $confirm -Force -PassThru
        break 
    }
    if (Test-Path $inbox) {
        Get-Content $inbox -Raw | Remove-Item $inbox -Force -PassThru
        break
    }
    Start-Sleep -Milliseconds 500
}
```
