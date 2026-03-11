param(
  [Parameter(Mandatory = $true)]
  [string]$Message
)

$ErrorActionPreference = "Stop"

Write-Host "Syncing with origin/main..."
git pull --rebase origin main

Write-Host "Staging changes..."
git add .

$pending = git status --porcelain
if (-not $pending) {
  Write-Host "No changes to commit."
  exit 0
}

Write-Host "Committing..."
git commit -m $Message

Write-Host "Pushing to GitHub..."
git push origin main

Write-Host "Done. Cloudflare should auto-deploy from main."
