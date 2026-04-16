# OpenCode Voice Bridge Launcher (Multi-Session Aware)
param(
    [string]$AgentName = "Main"
)

# Paths
$VoiceDir = "C:\Users\mwyant\.opencode\tools\voice_bridge"
$PythonPath = "C:\Python314\python.exe"
$LogOut = Join-Path $VoiceDir "stdout.log"
$LogErr = Join-Path $VoiceDir "stderr.log"

# Generate a unique Session ID for this OpenCode instance if not provided
$SessionID = [guid]::NewGuid().ToString().Substring(0,8)
Write-Host "[*] Starting Voice Bridge for Agent: $AgentName (Session: $SessionID)" -ForegroundColor Cyan

# 1. Check if Server is already running
$serverProc = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*server.py*" -and $_.Name -eq "python.exe" }
if (!$serverProc) {
    Write-Host "[*] Shared Voice Server not found. Launching..." -ForegroundColor Yellow
    Start-Process $PythonPath -ArgumentList (Join-Path $VoiceDir "server.py") -WorkingDirectory $VoiceDir -RedirectStandardOutput $LogOut -RedirectStandardError $LogErr -NoNewWindow
    Start-Sleep -Seconds 2
} else {
    Write-Host "[*] Shared Voice Server is already running." -ForegroundColor Gray
}

# 2. Verify Certificates
if (!(Test-Path (Join-Path $VoiceDir "cert.pem"))) {
    Write-Host "[*] Generating SSL certificates..." -ForegroundColor Yellow
    & $PythonPath (Join-Path $VoiceDir "generate_cert.py")
}

# 3. Launch the dedicated Bridge for this session
# We pass the SessionID to the bridge so it knows which inbox/outbox files to use
Write-Host "[*] Launching dedicated Bridge..." -ForegroundColor Green
Start-Process $PythonPath -ArgumentList @((Join-Path $VoiceDir "bridge.py"), "--session-id", $SessionID) -WorkingDirectory $VoiceDir -RedirectStandardOutput $LogOut -RedirectStandardError $LogErr -NoNewWindow

Write-Host "[SUCCESS] Voice Bridge is now active at https://heathson.ai.local:8133" -ForegroundColor Green
Write-Host "[*] Your Session ID is: $SessionID" -ForegroundColor White
Write-Host "[*] Use this ID on the webpage to talk to THIS session." -ForegroundColor Gray
