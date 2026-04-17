# OpenCode Voice Bridge - GitHub Sync Tool
# Updates the local deployment from the latest GitHub code

$VoiceDir = "C:\Users\mwyant\.opencode\tools\voice_bridge"
Set-Location $VoiceDir

Write-Host "[*] Fetching latest updates from GitHub..." -ForegroundColor Cyan
git fetch origin

# Update to the latest on the current branch
$CurrentBranch = (git branch --show-current)
Write-Host "[*] Updating branch: $CurrentBranch" -ForegroundColor Gray
git pull origin $CurrentBranch --force

Write-Host "[SUCCESS] Toolkit synchronized with GitHub." -ForegroundColor Green
Write-Host "[*] If you changed server or bridge logic, remember to relaunch." -ForegroundColor Yellow
