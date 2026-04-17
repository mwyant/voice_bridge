# OpenCode Voice Bridge Launcher (Robust)
# Paths
$VoiceDir = "C:\Users\mwyant\.opencode\voice_bridge"
$PythonPath = "C:\Python314\python.exe"

# 1. Clean up old processes
Write-Host "[*] Cleaning up old voice bridge processes..." -ForegroundColor Cyan
$procs = Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -like "*server.py*" -or $_.CommandLine -like "*bridge.py*") -and $_.Name -eq "python.exe" }
foreach ($p in $procs) {
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

# 2. Verify Certificates
if (!(Test-Path (Join-Path $VoiceDir "cert.pem"))) {
    Write-Host "[*] Generating SSL certificates..." -ForegroundColor Yellow
    & $PythonPath (Join-Path $VoiceDir "generate_cert.py")
}

# 3. Launch Services
# Using simple Start-Process with -WorkingDirectory to ensure paths resolve
Write-Host "[*] Launching Voice Server and Bridge..." -ForegroundColor Green
$ServerLogOut = Join-Path $VoiceDir "server_stdout.log"
$ServerLogErr = Join-Path $VoiceDir "server_stderr.log"
$BridgeLogOut = Join-Path $VoiceDir "bridge_stdout.log"
$BridgeLogErr = Join-Path $VoiceDir "bridge_stderr.log"

Start-Process $PythonPath -ArgumentList (Join-Path $VoiceDir "server.py") -WorkingDirectory $VoiceDir -RedirectStandardOutput $ServerLogOut -RedirectStandardError $ServerLogErr -WindowStyle Hidden
Start-Process $PythonPath -ArgumentList (Join-Path $VoiceDir "bridge.py") -WorkingDirectory $VoiceDir -RedirectStandardOutput $BridgeLogOut -RedirectStandardError $BridgeLogErr -WindowStyle Hidden

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host "[SUCCESS] Voice Bridge launched in background at $timestamp" -ForegroundColor Green
exit 0


$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host "[SUCCESS] Voice Bridge is now active at https://heathson.ai.local:8133" -ForegroundColor Green
Write-Host "All processes started and I should be exiting now at $timestamp" -ForegroundColor Gray
