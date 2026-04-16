# OpenCode Voice Bridge Sync Script
$Source = "C:\Users\mwyant\OneDrive\TBD-Reusegineers\voice_bridge"
$Dest = "C:\Users\mwyant\.opencode\tools\voice_bridge"

Write-Host "[*] Syncing simplified alpha to .opencode..." -ForegroundColor Cyan
Copy-Item -Path "$Source\*" -Destination $Dest -Recurse -Force -Exclude "*.wav", "*.webm", "*.db", "*.log", ".git"
Write-Host "[SUCCESS] Sync complete." -ForegroundColor Green
