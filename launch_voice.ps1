# OpenCode Voice Bridge Launcher (Robust)
# Paths
$VoiceDir = "C:\Users\mwyant\.opencode\tools\voice_bridge"
$PythonPath = "C:\Python314\python.exe"
$LogOut = Join-Path $VoiceDir "stdout.log"
$LogErr = Join-Path $VoiceDir "stderr.log"

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
# Using -WindowStyle Hidden and ensuring no stream capture to prevent PowerShell hang
Write-Host "[*] Launching Voice Server and Bridge..." -ForegroundColor Green
Start-Process $PythonPath -ArgumentList (Join-Path $VoiceDir "server.py") -WorkingDirectory $VoiceDir -RedirectStandardOutput $LogOut -RedirectStandardError $LogErr -WindowStyle Hidden
Start-Process $PythonPath -ArgumentList (Join-Path $VoiceDir "bridge.py") -WorkingDirectory $VoiceDir -RedirectStandardOutput $LogOut -RedirectStandardError $LogErr -WindowStyle Hidden

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host "[SUCCESS] Voice Bridge is now active at https://heathson.ai.local:8133" -ForegroundColor Green
Write-Host "All processes started and I should be exiting now at $timestamp" -ForegroundColor Gray
